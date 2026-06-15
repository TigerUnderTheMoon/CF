"""Run the guarded v2.1 downstream filtering mini-validation."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.archive_paths import v2_1_failed_provenance_root
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot._archived.downstream_filtering_v2_1 import (
    DEFAULT_BUDGET_USD,
    DEFAULT_MAX_API_REQUESTS,
    V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_GATE,
    V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY,
    V2_1DownstreamFilteringError,
    build_candidate_scores_for_records,
    build_downstream_filtering_preregistration,
    build_downstream_filtering_report,
    build_filtering_replay_jobs,
    markdown_for_preregistration,
    markdown_for_report,
    select_filtering_samples,
    validate_downstream_filtering_readiness,
)
from fma.real_task_pilot._archived.fresh_preflight import attempt_payloads_from_results
from fma.real_task_pilot._archived.fresh_preflight_v2_1 import estimate_attempt_cost_usd
from fma.real_task_pilot.generation import GeneratedTraceResult, load_prompt_template
from scripts.run_s_fma_v2_1_fresh_holdout_preflight import (
    SingleRequestOpenAITraceAdapter,
    generate_trace_once,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_1_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--write-preregistration-only",
        action="store_true",
        help="Write the fixed request-only preregistration artifacts and exit.",
    )
    parser.add_argument(
        "--allow-downstream-filtering-validation-only",
        action="store_true",
        help="Required explicit guard for the v2.1 downstream filtering mini-validation.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        default=None,
        help="User-approved hard budget ceiling. Must be exactly USD 5.0.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_pilot_config(args.config)
    output_root = Path(
        config.get("experiment", {}).get(
            "output_dir", "outputs/s_fma_v2_1_fresh_holdout"
        )
    )
    output_root = v2_1_failed_provenance_root(output_root)
    paths = v2_1_downstream_filtering_paths(output_root)

    if args.write_preregistration_only:
        preregistration = build_downstream_filtering_preregistration()
        _write_json(paths["preregistration"], preregistration)
        _write_text(paths["preregistration_md"], markdown_for_preregistration(preregistration))
        print(
            json.dumps(
                {
                    "status": "PREREGISTRATION_WRITTEN",
                    "scope": preregistration["requested_scope"],
                    "path": str(paths["preregistration"]),
                },
                sort_keys=True,
            )
        )
        return

    if args.approved_budget_usd is None:
        raise V2_1DownstreamFilteringError("--approved-budget-usd is required for API execution.")

    preregistration = _load_required_json(paths["preregistration"])
    source_artifacts = preregistration.get("source_artifacts", {})
    original_records = _load_required_records(Path(source_artifacts["original_traces"]))
    pilot_report = _load_required_json(Path(source_artifacts["pilot_report"]))
    abandonment_audit = _load_required_json(Path(source_artifacts["full_abandonment_audit"]))
    structural_diagnostics = _load_required_json(Path(source_artifacts["structural_diagnostics"]))
    redundancy_analysis = _load_required_json(Path(source_artifacts["redundancy_analysis"]))

    try:
        readiness = validate_downstream_filtering_readiness(
            preregistration=preregistration,
            pilot_report=pilot_report,
            abandonment_audit=abandonment_audit,
            current_status=str(
                config.get("frozen_boundary", {}).get("current_project_status")
                or "PILOT_BLOCKED"
            ),
            allow_downstream_filtering_validation_only=args.allow_downstream_filtering_validation_only,
            approved_budget_usd=args.approved_budget_usd,
        )
        candidate_rows, leakage_audit = build_candidate_scores_for_records(
            original_records,
            config=_candidate_score_config(config),
            structural_diagnostics=structural_diagnostics,
            redundancy_analysis=redundancy_analysis,
        )
        write_records(candidate_rows, paths["candidate_scores"])
        _write_json(paths["leakage_audit"], leakage_audit)
        if leakage_audit.get("target_leakage_detected") is True:
            raise V2_1DownstreamFilteringError("candidate leakage audit must be clean.")
        selected = select_filtering_samples(
            original_records,
            candidate_rows,
            records_per_task=readiness["sample_count_by_task"],
            seed=int(readiness["selection_seed"]),
        )
        jobs = build_filtering_replay_jobs(selected, candidate_rows)
        write_records(jobs, paths["jobs"])
        live_config = _live_replay_config(config, readiness=readiness)
        replay_prompt = load_prompt_template(
            live_config.get("stochastic_smoke", {}).get(
                "replay_prompt_file", "prompts/real_task_replay.txt"
            )
        )
        adapter = SingleRequestOpenAITraceAdapter()
    except Exception as exc:
        report = _gate_failure_report(
            error=exc,
            approved_budget_usd=float(args.approved_budget_usd),
            request_cap=DEFAULT_MAX_API_REQUESTS,
        )
        _write_json(paths["report"], report)
        _write_text(paths["report_md"], markdown_for_report(report))
        _write_json(paths["cost"], _cost_report(report))
        print(json.dumps({"status": report["status"], "error": str(exc)}, sort_keys=True))
        return

    results: list[GeneratedTraceResult] = []
    result_jobs: list[Mapping[str, Any]] = []
    traces: list[dict[str, Any]] = []
    budget_stop_triggered = False
    request_stop_triggered = False

    pending_jobs = list(jobs)
    retry_round = 0
    while pending_jobs:
        next_pending: list[dict[str, Any]] = []
        for job in pending_jobs:
            if len(results) >= int(readiness["max_api_requests"]):
                request_stop_triggered = True
                break
            attempts = _attempt_payloads(results, result_jobs)
            cost_used = estimate_attempt_cost_usd(attempts, config=live_config) or 0.0
            if cost_used >= float(readiness["approved_budget_usd"]):
                budget_stop_triggered = True
                break

            result = generate_trace_once(
                job,
                adapter=adapter,
                config=live_config,
                prompt_template=replay_prompt,
            )
            results.append(result)
            result_jobs.append(job)
            if result.record is not None:
                traces.append(_trace_payload(result.record, job))
            elif retry_round == 0:
                next_pending.append(dict(job))
            _write_live_checkpoint(paths, results, result_jobs, traces)

        if budget_stop_triggered or request_stop_triggered or retry_round >= 1:
            break
        retry_round += 1
        pending_jobs = next_pending[: max(0, int(readiness["max_api_requests"]) - len(results))]

    attempts = _attempt_payloads(results, result_jobs)
    cost_used = estimate_attempt_cost_usd(attempts, config=live_config) or 0.0
    report = build_downstream_filtering_report(
        jobs=jobs,
        original_records=selected,
        replay_records=traces,
        api_attempts=len(attempts),
        cost_used_usd=cost_used,
        approved_budget_usd=float(readiness["approved_budget_usd"]),
        request_cap=int(readiness["max_api_requests"]),
        min_valid_pairs=int(readiness["min_valid_pairs"]),
        min_valid_pairs_per_task=int(readiness["min_valid_pairs_per_task"]),
        budget_stop_triggered=budget_stop_triggered,
        request_stop_triggered=request_stop_triggered,
    )
    _write_json(paths["report"], report)
    _write_text(paths["report_md"], markdown_for_report(report))
    _write_json(paths["cost"], _cost_report(report, attempts=attempts))
    print(
        json.dumps(
            {
                "status": report["status"],
                "api_attempts": report["api_attempts"],
                "cost_used_usd": report["cost_used_usd"],
                "valid_pair_count": report["valid_pair_count"],
                "next_allowed_step": report["next_allowed_step"],
            },
            sort_keys=True,
        )
    )


def v2_1_downstream_filtering_paths(output_root: Path) -> dict[str, Path]:
    output_root = v2_1_failed_provenance_root(output_root)
    return {
        "preregistration": output_root / "v2_1_downstream_filtering_preregistration.json",
        "preregistration_md": output_root / "v2_1_downstream_filtering_preregistration.md",
        "candidate_scores": output_root / "v2_1_downstream_filtering_candidate_scores.jsonl",
        "leakage_audit": output_root / "v2_1_downstream_filtering_leakage_audit.json",
        "jobs": output_root / "v2_1_downstream_filtering_jobs.jsonl",
        "attempts": output_root / "v2_1_downstream_filtering_attempts.jsonl",
        "traces": output_root / "v2_1_downstream_filtering_traces.jsonl",
        "report": output_root / "v2_1_downstream_filtering_report.json",
        "report_md": output_root / "v2_1_downstream_filtering_report.md",
        "cost": output_root / "logs" / "v2_1_downstream_filtering_cost_report.json",
    }


def _candidate_score_config(config: Mapping[str, Any]) -> dict[str, Any]:
    cloned = deepcopy(dict(config))
    replay = dict(cloned.get("replay", {}))
    replay["max_spans_per_trace"] = 2
    cloned["replay"] = replay
    return cloned


def _live_replay_config(config: Mapping[str, Any], *, readiness: Mapping[str, Any]) -> dict[str, Any]:
    cloned = deepcopy(dict(config))
    experiment = dict(cloned.get("experiment", {}))
    experiment["current_task_scope"] = V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY
    experiment["user_approved_budget_usd"] = float(readiness["approved_budget_usd"])
    experiment["max_api_requests_pilot"] = int(readiness["max_api_requests"])
    experiment["pilot_generation_requests"] = int(readiness["max_api_requests"])
    cloned["experiment"] = experiment

    api = dict(cloned.get("api", {}))
    api.setdefault("endpoint", "/v1/responses")
    api.setdefault("api_date", "2026-06-06")
    api.setdefault("service_tier", "default")
    api.setdefault("store", False)
    api.setdefault("request_timeout_seconds", 45)
    cloned["api"] = api

    model = dict(cloned.get("model", {}))
    model.setdefault("primary", "gpt-5.5")
    model.setdefault("fallback_order", [model["primary"]])
    model.setdefault("temperature", 0.0)
    model.setdefault("top_p", 1.0)
    model.setdefault("max_output_tokens", 2048)
    cloned["model"] = model

    pricing = dict(cloned.get("pricing", {}))
    pricing.setdefault("input_per_million_usd", 5.0)
    pricing.setdefault("output_per_million_usd", 30.0)
    pricing.setdefault("basis", "v2.1 downstream filtering mini-validation ceiling")
    cloned["pricing"] = pricing

    generation = dict(cloned.get("generation", {}))
    generation.setdefault("minimum_schema_success_rate", 0.95)
    generation.setdefault("minimum_tag_success_rate", 0.95)
    cloned["generation"] = generation

    smoke = dict(cloned.get("stochastic_smoke", {}))
    smoke.setdefault("replay_prompt_file", "prompts/real_task_replay.txt")
    smoke.setdefault("mask_token", "[REASONING_MASK]")
    cloned["stochastic_smoke"] = smoke
    return cloned


def _trace_payload(record: Mapping[str, Any], job: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(record),
        "status": "success",
        "condition": job.get("condition"),
        "span_index": job.get("span_index"),
        "filtered_span_index": job.get("filtered_span_index"),
        "retained_span_index": job.get("retained_span_index"),
        "filtering_policy": job.get("filtering_policy"),
        "filtered_candidate_score": job.get("filtered_candidate_score"),
        "retained_candidate_score": job.get("retained_candidate_score"),
    }


def _attempt_payloads(
    results: Sequence[GeneratedTraceResult],
    jobs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    attempts = attempt_payloads_from_results(results, role="downstream_filtering_replay", samples=jobs)
    for attempt, job in zip(attempts, jobs):
        attempt["condition"] = job.get("condition")
        attempt["span_index"] = job.get("span_index")
        attempt["filtering_policy"] = job.get("filtering_policy")
    return attempts


def _write_live_checkpoint(
    paths: Mapping[str, Path],
    results: Sequence[GeneratedTraceResult],
    jobs: Sequence[Mapping[str, Any]],
    traces: Sequence[Mapping[str, Any]],
) -> None:
    write_records(list(traces), paths["traces"])
    write_records(_attempt_payloads(results, jobs), paths["attempts"])


def _gate_failure_report(
    *,
    error: Exception,
    approved_budget_usd: float,
    request_cap: int,
) -> dict[str, Any]:
    return {
        "artifact": "v2_1_downstream_filtering_report",
        "scope": V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY,
        "status": V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_GATE,
        "GLOBAL_pass": False,
        "failure_codes": [V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_GATE],
        "failure_reason": f"{type(error).__name__}: {error}",
        "api_execution_performed": False,
        "api_attempts": 0,
        "planned_api_calls": 40,
        "max_api_requests": int(request_cap),
        "request_within_cap": True,
        "approved_budget_usd": float(approved_budget_usd),
        "cost_used_usd": 0.0,
        "cost_within_budget": True,
        "valid_pair_count": 0,
        "paired_metrics": {"pooled": {"n": 0, "mean_advantage": 0.0}, "per_task": {}},
        "current_status_remains": "PILOT_BLOCKED",
        "claim_upgrade_allowed": False,
        "full_validation_claim_allowed": False,
        "deterministic_replay_claim_allowed": False,
        "prm_filtering_superiority_claim_allowed": False,
        "forbidden_claim_scope": [
            "full validation claim",
            "deterministic replay claim",
            "top-tier-ready claim",
            "submission-ready claim",
            "PRM/filtering superiority claim",
            "v2.4 route claim",
        ],
        "next_allowed_step": "ABANDON_MINI_DOWNSTREAM_FILTERING_ROUTE",
    }


def _cost_report(
    report: Mapping[str, Any],
    *,
    attempts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for attempt in attempts or []:
        usage = attempt.get("usage") or {}
        usage_totals["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        usage_totals["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        usage_totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    return {
        "scope": report.get("scope"),
        "status": report.get("status"),
        "api_attempts": report.get("api_attempts", 0),
        "request_cap": report.get("max_api_requests", DEFAULT_MAX_API_REQUESTS),
        "approved_budget_usd": report.get("approved_budget_usd", DEFAULT_BUDGET_USD),
        "cost_used_usd": report.get("cost_used_usd", 0.0),
        "budget_gate_pass": report.get("cost_within_budget", False),
        "usage_totals": usage_totals,
        "current_status_remains": "PILOT_BLOCKED",
    }


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise V2_1DownstreamFilteringError(f"required JSON artifact missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise V2_1DownstreamFilteringError(f"{path} must contain a JSON object.")
    return value


def _load_required_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise V2_1DownstreamFilteringError(f"required record artifact missing: {path}")
    return load_records(path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
