"""Run the approved s_FMA_v2.1 full stochastic validation with hard guards."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.archive_paths import v2_1_failed_provenance_root
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot._archived.fresh_holdout_v2_1 import V2_1_CONTRACT_CLEAN
from fma.real_task_pilot._archived.fresh_preflight import (
    attempt_payloads_from_results,
    select_preflight_records,
)
from fma.real_task_pilot._archived.fresh_preflight_v2_1 import estimate_attempt_cost_usd
from fma.real_task_pilot._archived.fresh_smoke_v2_1 import (
    aggregate_v2_1_delta_u_by_span,
    build_v2_1_stochastic_smoke_generation_config as _build_smoke_generation_config,
    build_v2_1_stochastic_smoke_prefixes,
)
from fma.real_task_pilot.generation import GeneratedTraceResult, load_prompt_template
from fma.real_task_pilot.replay import missing_replay_jobs
from scripts.run_s_fma_v2_1_fresh_holdout_preflight import (
    SingleRequestOpenAITraceAdapter,
    generate_trace_once,
)
from scripts.run_s_fma_v2_1_pilot_stochastic_validation import (
    _attempt_quality,
    _prompt_version,
    _quality_gates_pass,
    _replay_alias_policy_active,
    _spearman_metrics,
    _usage_totals,
)


V2_1_FULL_STOCHASTIC_VALIDATION_ONLY = "V2_1_FULL_STOCHASTIC_VALIDATION_ONLY"
V2_1_FULL_STOCHASTIC_PASS = "V2_1_FULL_STOCHASTIC_PASS"
V2_1_FULL_STOCHASTIC_FAIL_COST = "V2_1_FULL_STOCHASTIC_FAIL_COST"
V2_1_FULL_STOCHASTIC_FAIL_REQUEST_LIMIT = (
    "V2_1_FULL_STOCHASTIC_FAIL_REQUEST_LIMIT"
)
V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS = (
    "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS"
)
V2_1_FULL_STOCHASTIC_FAIL_GENERATION = "V2_1_FULL_STOCHASTIC_FAIL_GENERATION"
V2_1_FULL_STOCHASTIC_FAIL_ELIGIBLE_SPANS = (
    "V2_1_FULL_STOCHASTIC_FAIL_ELIGIBLE_SPANS"
)
V2_1_FULL_STOCHASTIC_FAIL_REPLAY = "V2_1_FULL_STOCHASTIC_FAIL_REPLAY"
V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL = (
    "V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL"
)
V2_1_FULL_STOCHASTIC_FAIL_RANK_SIGNAL = (
    "V2_1_FULL_STOCHASTIC_FAIL_RANK_SIGNAL"
)


class V2_1FullStochasticError(RuntimeError):
    """Raised when a hard v2.1 full stochastic boundary is violated."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded V2_1_FULL_STOCHASTIC_VALIDATION_ONLY."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_1_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-full-stochastic-validation-only",
        action="store_true",
        help="Required explicit guard for the approved v2.1 full stochastic validation.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="User-approved hard budget ceiling. Must match the full request.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    output_root = Path(
        config.get("experiment", {}).get(
            "output_dir", "outputs/s_fma_v2_1_fresh_holdout"
        )
    )
    output_root = v2_1_failed_provenance_root(output_root)
    full_paths = v2_1_full_stochastic_paths(output_root)
    paths = {
        "manifest": output_root / "fresh_manifest.json",
        "overlap": output_root / "manifest_overlap_audit.json",
        "contract": output_root / "v2_1_contract_audit.json",
        "pilot_report": output_root / "v2_1_pilot_stochastic_report.json",
        "approval": output_root / "v2_1_full_stochastic_validation_approval_request.json",
        "readiness": Path("outputs") / "real_task_pilot" / "readiness_audit.json",
        **full_paths,
    }

    manifest = _load_required_records(paths["manifest"])
    overlap_audit = _load_required_json(paths["overlap"])
    contract_audit = _load_required_json(paths["contract"])
    pilot_report = _load_required_json(paths["pilot_report"])
    approval_request = _load_required_json(paths["approval"])
    current_readiness = _load_required_json(paths["readiness"])
    prompt_file = Path(
        config.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        )
    )
    current_prompt_version = _prompt_version(prompt_file)

    readiness = validate_v2_1_full_stochastic_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=overlap_audit,
        contract_audit=contract_audit,
        pilot_report=pilot_report,
        approval_request=approval_request,
        current_readiness=current_readiness,
        allow_full_stochastic_validation_only=args.allow_full_stochastic_validation_only,
        approved_budget_usd=args.approved_budget_usd,
        current_prompt_version=current_prompt_version,
    )
    selected = select_preflight_records(
        manifest,
        samples_per_task=200,
        task_order=["gsm8k", "hotpotqa"],
    )
    live_config = build_v2_1_full_generation_config(config, readiness=readiness)
    generation_prompt = load_prompt_template(live_config["generation"]["prompt_file"])
    replay_prompt = load_prompt_template(
        live_config.get("stochastic_smoke", {}).get(
            "replay_prompt_file", "prompts/real_task_replay.txt"
        )
    )
    adapter = SingleRequestOpenAITraceAdapter()

    original_attempts = _load_records_if_exists(paths["original_attempts"])
    original_records = _load_records_if_exists(paths["original_traces"])
    replay_attempts = _load_records_if_exists(paths["replay_attempts"])
    replay_results = _load_records_if_exists(paths["replay_results"])
    prefixes = _load_records_if_exists(paths["prefixes"])
    delta_rows: list[dict[str, Any]] = []
    expected_replay_jobs = 0
    budget_stop_triggered = False
    request_stop_triggered = False

    if len(original_attempts) > len(selected):
        raise V2_1FullStochasticError(
            "full original checkpoint has more attempts than selected records."
        )
    if len(original_attempts) < len(selected):
        existing_attempt_count = len(original_attempts)
        existing_records = list(original_records)
        new_results: list[GeneratedTraceResult] = []
        remaining_selected = selected[existing_attempt_count:]
        for sample in remaining_selected:
            if len(original_attempts) + len(replay_attempts) >= int(
                readiness["max_api_requests"]
            ):
                request_stop_triggered = True
                break
            if _estimate_cost_usd(
                live_config,
                [*original_attempts, *replay_attempts],
            ) >= float(readiness["approved_budget_usd"]):
                budget_stop_triggered = True
                break
            new_results.append(
                generate_trace_once(
                    sample,
                    adapter=adapter,
                    config=live_config,
                    prompt_template=generation_prompt,
                )
            )
            original_attempts = [
                *original_attempts[:existing_attempt_count],
                *attempt_payloads_from_results(
                    new_results,
                    role="full_original",
                    samples=remaining_selected,
                ),
            ]
            original_records = [
                *existing_records,
                *[result.record for result in new_results if result.record is not None],
            ]
            _write_original_checkpoint(paths, original_attempts, original_records)

    if (
        not budget_stop_triggered
        and not request_stop_triggered
        and _valid_traces_by_task_pass(original_records, readiness)
    ):
        if not prefixes:
            prefixes = build_v2_1_stochastic_smoke_prefixes(
                original_records,
                config=live_config,
                mask_token=str(
                    live_config.get("stochastic_smoke", {}).get(
                        "mask_token", "[REASONING_MASK]"
                    )
                ),
            )
            _write_records_checkpoint(prefixes, paths["prefixes"])
        repeats = int(readiness["stochastic_repeats_per_span"])
        replay_plan = _full_replay_job_plan(prefixes, replay_results, repeats=repeats)
        jobs = replay_plan["missing_jobs"]
        expected_replay_jobs = int(replay_plan["expected_replay_jobs"])
        if len(original_attempts) + len(replay_attempts) + len(jobs) > int(
            readiness["max_api_requests"]
        ):
            raise V2_1FullStochasticError(
                "planned full stochastic replay jobs exceed the 2800-request scope."
            )

        for job in jobs:
            if len(original_attempts) + len(replay_attempts) >= int(
                readiness["max_api_requests"]
            ):
                request_stop_triggered = True
                break
            if _estimate_cost_usd(
                live_config,
                [*original_attempts, *replay_attempts],
            ) >= float(readiness["approved_budget_usd"]):
                budget_stop_triggered = True
                break
            result = generate_trace_once(
                job,
                adapter=adapter,
                config=live_config,
                prompt_template=replay_prompt,
            )
            replay_attempts.append(_replay_attempt_payload(job, result))
            if result.record is not None:
                replay_results.append(_replay_result_payload(job, result))
            _write_replay_checkpoint(paths, replay_attempts, replay_results)

        delta_rows = aggregate_v2_1_delta_u_by_span(original_records, replay_results)
        _write_records_checkpoint(delta_rows, paths["delta_u"])
    else:
        _write_records_checkpoint(prefixes, paths["prefixes"])
        _write_records_checkpoint(delta_rows, paths["delta_u"])

    cost_used = _estimate_cost_usd(live_config, [*original_attempts, *replay_attempts])
    rank_signal = build_v2_1_full_rank_signal_report(
        delta_rows,
        resamples=int(
            config.get("nondeterministic_protocol", {})
            .get("bootstrap", {})
            .get("resamples", 10000)
        ),
        confidence_level=float(
            config.get("nondeterministic_protocol", {})
            .get("bootstrap", {})
            .get("confidence_level", 0.95)
        ),
        seed=int(
            config.get("nondeterministic_protocol", {})
            .get("bootstrap", {})
            .get("random_seed", 20260530)
        )
        + 3100,
    )
    report = build_v2_1_full_stochastic_report(
        original_records=original_records,
        original_attempts=original_attempts,
        replay_results=replay_results,
        replay_attempts=replay_attempts,
        delta_rows=delta_rows,
        rank_signal=rank_signal,
        readiness=readiness,
        cost_used_usd=cost_used,
        expected_replay_jobs=expected_replay_jobs,
    )
    report.update(
        {
            "approval_source": str(paths["approval"]),
            "manifest_source": str(paths["manifest"]),
            "source_pilot_report": str(paths["pilot_report"]),
            "api_execution_performed": True,
            "budget_stop_triggered": budget_stop_triggered,
            "request_stop_triggered": request_stop_triggered,
            "original_attempt_count": len(original_attempts),
            "original_valid_trace_count": len(original_records),
            "target_prefix_count": len(prefixes),
            "stochastic_repeats_per_span": int(readiness["stochastic_repeats_per_span"]),
        }
    )
    _write_json(paths["rank_signal"], rank_signal)
    _write_json(paths["report"], report)
    _write_json(
        paths["cost"],
        {
            "cost_used_usd": cost_used,
            "approved_budget_usd": float(readiness["approved_budget_usd"]),
            "api_attempts": len(original_attempts) + len(replay_attempts),
            "usage_totals": _usage_totals([*original_attempts, *replay_attempts]),
            "request_cap": int(readiness["max_api_requests"]),
            "scope": readiness["scope"],
            "approved_scope": V2_1_FULL_STOCHASTIC_VALIDATION_ONLY,
            "budget_gate_pass": cost_used <= float(readiness["approved_budget_usd"]),
        },
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "api_attempts": report["api_attempts"],
                "cost_used_usd": report["cost_used_usd"],
                "valid_original_traces": report["valid_original_traces"],
                "replay_success_rate": report["replay_success_rate"],
                "nonzero_delta_u_pooled_count": report[
                    "nonzero_delta_u_pooled_count"
                ],
                "nonzero_delta_u_by_task": report["nonzero_delta_u_by_task"],
                "TASK_SPECIFIC_pass": report["TASK_SPECIFIC_pass"],
                "GLOBAL_pass": report["GLOBAL_pass"],
                "prm_filtering_validation_approval_request_allowed": report[
                    "prm_filtering_validation_approval_request_allowed"
                ],
                "current_status_remains": report["current_status_remains"],
            },
            sort_keys=True,
        )
    )


def v2_1_full_stochastic_paths(output_root: Path) -> dict[str, Path]:
    """Return only the approved v2.1 full stochastic output paths."""

    output_root = v2_1_failed_provenance_root(output_root)
    return {
        "original_attempts": output_root / "v2_1_full_stochastic_original_attempts.jsonl",
        "original_traces": output_root / "v2_1_full_stochastic_original_traces.jsonl",
        "prefixes": output_root / "v2_1_full_stochastic_replay_prefixes.jsonl",
        "replay_attempts": output_root / "v2_1_full_stochastic_replay_attempts.jsonl",
        "replay_results": output_root / "v2_1_full_stochastic_replay_results.jsonl",
        "delta_u": output_root / "v2_1_full_stochastic_delta_u.jsonl",
        "rank_signal": output_root / "v2_1_full_stochastic_rank_signal_report.json",
        "report": output_root / "v2_1_full_stochastic_report.json",
        "cost": output_root / "logs" / "v2_1_full_stochastic_cost_report.json",
    }


def validate_v2_1_full_stochastic_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    pilot_report: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    current_readiness: Mapping[str, Any],
    allow_full_stochastic_validation_only: bool,
    approved_budget_usd: float,
    current_prompt_version: str | None,
) -> dict[str, Any]:
    """Validate all user-approved gates before any full stochastic API call."""

    if not allow_full_stochastic_validation_only:
        raise V2_1FullStochasticError(
            "v2.1 full validation requires explicit "
            "--allow-full-stochastic-validation-only."
        )
    if (
        approval_request.get("requested_execution_scope")
        != V2_1_FULL_STOCHASTIC_VALIDATION_ONLY
    ):
        raise V2_1FullStochasticError(
            "v2_1_full_stochastic_validation_approval_request.json must request "
            f"{V2_1_FULL_STOCHASTIC_VALIDATION_ONLY}."
        )
    if approval_request.get("approval_status") != "REQUEST_ONLY_NOT_APPROVED":
        raise V2_1FullStochasticError(
            "v2.1 full request artifact must remain REQUEST_ONLY_NOT_APPROVED."
        )
    if approval_request.get("approval_granted") is not False:
        raise V2_1FullStochasticError("v2.1 full request must still be not approved.")
    if approval_request.get("request_only") is not True:
        raise V2_1FullStochasticError("v2.1 full request artifact must be request-only.")
    if current_readiness.get("status") != "PILOT_BLOCKED":
        raise V2_1FullStochasticError("current readiness status must remain PILOT_BLOCKED.")
    if current_readiness.get("pilot_pass") is True:
        raise V2_1FullStochasticError("current readiness must not report pilot_pass=true.")

    _validate_manifest_and_overlap(config=config, manifest=manifest, overlap_audit=overlap_audit)
    _validate_contract(contract_audit)
    _validate_prompt_version(
        manifest=manifest,
        contract_audit=contract_audit,
        current_prompt_version=current_prompt_version,
    )
    if not _replay_alias_policy_active(config):
        raise V2_1FullStochasticError("v2.1 replay alias policy must be active.")
    _validate_current_pilot_summary(pilot_report, approval_request)

    design = approval_request.get("proposed_full_stochastic_validation_design", {})
    thresholds = approval_request.get("full_validation_gate_thresholds", {})
    sample_count = int(design.get("records_total", 0) or 0)
    records_per_task = dict(design.get("records_by_task") or {})
    repeats = int(design.get("stochastic_repeats_per_eligible_span", 0) or 0)
    max_requests = int(design.get("max_api_requests", 0) or 0)
    max_spans = int(design.get("target_spans_per_trace_max", 0) or 0)
    recommended_budget = float(
        design.get("budget_ceiling_recommendation_usd", 0.0) or 0.0
    )
    route = str(design.get("route") or "")
    if sample_count != 400 or records_per_task != {"gsm8k": 200, "hotpotqa": 200}:
        raise V2_1FullStochasticError(
            "v2.1 full stochastic validation must be exactly 400 records, 200 per task."
        )
    if max_requests != 2800:
        raise V2_1FullStochasticError("v2.1 full max_api_requests must be exactly 2800.")
    if repeats != 3:
        raise V2_1FullStochasticError("v2.1 full repeats per eligible span must be 3.")
    if max_spans != 2:
        raise V2_1FullStochasticError("v2.1 full max target spans per trace must be 2.")
    if recommended_budget != 150.0 or float(approved_budget_usd) != recommended_budget:
        raise V2_1FullStochasticError(
            "approved budget must match the full request budget ceiling."
        )
    if route != "stochastic repeated replay only":
        raise V2_1FullStochasticError("v2.1 full route must be stochastic repeated replay only.")

    selected = select_preflight_records(
        manifest,
        samples_per_task=200,
        task_order=["gsm8k", "hotpotqa"],
    )
    selected_counts = Counter(str(row.get("task_type") or "") for row in selected)
    if len(selected) != sample_count or dict(selected_counts) != records_per_task:
        raise V2_1FullStochasticError("balanced full selection did not match approval scope.")

    min_valid_per_task = int(thresholds.get("min_valid_traces_per_task") or 190)
    min_eligible_per_task = int(thresholds.get("min_eligible_spans_per_task") or 150)
    min_nonzero_per_task = int(thresholds.get("min_nonzero_delta_u_per_task") or 20)
    return {
        "scope": V2_1_FULL_STOCHASTIC_VALIDATION_ONLY,
        "api_call_allowed": True,
        "sample_count": sample_count,
        "sample_count_by_task": records_per_task,
        "approved_budget_usd": float(approved_budget_usd),
        "max_api_requests": max_requests,
        "stochastic_repeats_per_span": repeats,
        "max_target_spans_per_trace": max_spans,
        "min_valid_traces_per_task": min_valid_per_task,
        "min_eligible_spans_per_task": min_eligible_per_task,
        "min_nonzero_delta_u_pooled": min_nonzero_per_task * len(records_per_task),
        "min_nonzero_delta_u_per_task": min_nonzero_per_task,
        "min_replay_success_rate": float(thresholds.get("min_replay_success_rate") or 0.85),
        "required_json_parse_success_rate": float(
            thresholds.get("json_parse_success_rate_required") or 1.0
        ),
        "required_schema_success_rate": float(
            thresholds.get("schema_success_rate_required") or 1.0
        ),
        "required_tag_extraction_success_rate": float(
            thresholds.get("tag_extraction_success_rate_required") or 1.0
        ),
        "required_final_answer_parse_success_rate": float(
            thresholds.get("final_answer_parse_success_rate_required") or 1.0
        ),
        "rank_signal_ci_lower_must_exceed": 0.0,
        "budget_gate_pass": True,
        "manifest_overlap_clean": True,
        "v2_1_contract_clean": True,
        "replay_alias_policy_active": True,
        "current_status_remains": "PILOT_BLOCKED",
        "deterministic_replay_claim_allowed": False,
        "submission_ready_claim_allowed": False,
        "claim_upgrade_allowed": False,
    }


def build_v2_1_full_generation_config(
    config: Mapping[str, Any],
    *,
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a live full-validation config without mutating the planned-only YAML."""

    cloned = _build_smoke_generation_config(config, readiness=readiness)
    experiment = dict(cloned.get("experiment", {}))
    experiment["current_task_scope"] = V2_1_FULL_STOCHASTIC_VALIDATION_ONLY
    cloned["experiment"] = experiment
    pricing = dict(cloned.get("pricing", {}))
    pricing["basis"] = "s_FMA_v2.1 full stochastic ceiling"
    cloned["pricing"] = pricing
    return cloned


def build_v2_1_full_rank_signal_report(
    delta_rows: Sequence[Mapping[str, Any]],
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Rank diagnostic over observed full validation rows only."""

    task_types = sorted({str(row.get("task_type") or "unknown") for row in delta_rows})
    paired = [
        (
            float(row.get("original_score", 0.0) or 0.0),
            float(row.get("delta_u", 0.0) or 0.0),
            str(row.get("task_type") or "unknown"),
        )
        for row in delta_rows
    ]
    pooled = _spearman_metrics(
        [(left, right) for left, right, _task in paired],
        resamples=resamples,
        confidence_level=confidence_level,
        seed=seed,
    )
    per_task = {}
    for index, task_type in enumerate(task_types):
        per_task[task_type] = _spearman_metrics(
            [
                (left, right)
                for left, right, row_task_type in paired
                if row_task_type == task_type
            ],
            resamples=resamples,
            confidence_level=confidence_level,
            seed=seed + index + 1,
        )
    return {
        "metric": "original_primary_score_vs_delta_u_spearman",
        "estimand_boundary": "full stochastic repeated replay only",
        "primary_signal": {
            "available": bool(delta_rows),
            "name": "original_primary_score_vs_delta_u",
            "n": len(delta_rows),
            "target_leakage_status": "observed_full_validation_metric_not_candidate_score",
        },
        "pooled": pooled,
        "per_task": per_task,
        "bootstrap": {
            "resamples": resamples,
            "confidence_level": confidence_level,
            "random_seed": seed,
        },
    }


def build_v2_1_full_stochastic_report(
    *,
    original_records: Sequence[Mapping[str, Any]],
    original_attempts: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
    replay_attempts: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
    rank_signal: Mapping[str, Any],
    readiness: Mapping[str, Any],
    cost_used_usd: float,
    expected_replay_jobs: int,
) -> dict[str, Any]:
    """Build a conservative v2.1 full stochastic report."""

    all_attempts = [*original_attempts, *replay_attempts]
    attempt_quality = _attempt_quality(all_attempts)
    actual_requests = len(all_attempts)
    max_requests = int(readiness["max_api_requests"])
    approved_budget = float(readiness["approved_budget_usd"])
    successful_replays = [
        row for row in replay_results if row.get("status") in {None, "success", "replayed"}
    ]
    replay_success_rate = (
        len(successful_replays) / expected_replay_jobs if expected_replay_jobs else 0.0
    )
    valid_by_task = Counter(str(record.get("task_type") or "") for record in original_records)
    expected_by_task = dict(readiness.get("sample_count_by_task") or {})
    eligible_by_task = Counter(str(row.get("task_type") or "") for row in delta_rows)
    nonzero_delta_rows = [
        row for row in delta_rows if abs(float(row.get("delta_u", 0.0) or 0.0)) > 0.0
    ]
    nonzero_by_task = Counter(str(row.get("task_type") or "") for row in nonzero_delta_rows)
    task_pass = _full_task_pass_map(
        expected_by_task=expected_by_task,
        valid_by_task=valid_by_task,
        eligible_by_task=eligible_by_task,
        nonzero_by_task=nonzero_by_task,
        replay_success_rate=replay_success_rate,
        attempt_quality=attempt_quality,
        rank_signal=rank_signal,
        readiness=readiness,
    )
    task_specific_pass = all(task_pass.values()) if task_pass else False
    pooled_rank_pass = bool(
        rank_signal.get("pooled", {}).get("spearman_ci_lower_gt_zero") is True
    )
    per_task_rank_pass = all(
        bool(
            rank_signal.get("per_task", {})
            .get(task_type, {})
            .get("spearman_ci_lower_gt_zero")
            is True
        )
        for task_type in expected_by_task
    )
    global_pass = task_specific_pass and pooled_rank_pass

    failure_codes = []
    if float(cost_used_usd) > approved_budget:
        failure_codes.append(V2_1_FULL_STOCHASTIC_FAIL_COST)
    if actual_requests > max_requests:
        failure_codes.append(V2_1_FULL_STOCHASTIC_FAIL_REQUEST_LIMIT)
    if not _quality_gates_pass(attempt_quality, readiness):
        failure_codes.append(V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS)
    if any(
        int(valid_by_task.get(task_type, 0))
        < int(readiness["min_valid_traces_per_task"])
        for task_type in expected_by_task
    ):
        failure_codes.append(V2_1_FULL_STOCHASTIC_FAIL_GENERATION)
    if any(
        int(eligible_by_task.get(task_type, 0))
        < int(readiness["min_eligible_spans_per_task"])
        for task_type in expected_by_task
    ):
        failure_codes.append(V2_1_FULL_STOCHASTIC_FAIL_ELIGIBLE_SPANS)
    if replay_success_rate < float(readiness["min_replay_success_rate"]):
        failure_codes.append(V2_1_FULL_STOCHASTIC_FAIL_REPLAY)
    sparse_signal = (
        len(nonzero_delta_rows) < int(readiness["min_nonzero_delta_u_pooled"])
        or any(
            int(nonzero_by_task.get(task_type, 0))
            < int(readiness["min_nonzero_delta_u_per_task"])
            for task_type in expected_by_task
        )
    )
    if sparse_signal:
        failure_codes.append(V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL)
    if not (pooled_rank_pass and per_task_rank_pass):
        failure_codes.append(V2_1_FULL_STOCHASTIC_FAIL_RANK_SIGNAL)

    status = V2_1_FULL_STOCHASTIC_PASS if not failure_codes else failure_codes[0]
    downstream_approval_request_allowed = global_pass and status == V2_1_FULL_STOCHASTIC_PASS
    return {
        "artifact": "v2_1_full_stochastic_report",
        "scope": str(readiness.get("scope") or V2_1_FULL_STOCHASTIC_VALIDATION_ONLY),
        "status": status,
        "failure_codes": failure_codes,
        "sample_count": int(readiness["sample_count"]),
        "sample_count_by_task": expected_by_task,
        "valid_original_traces": len(original_records),
        "valid_original_traces_by_task": {
            "gsm8k": int(valid_by_task.get("gsm8k", 0)),
            "hotpotqa": int(valid_by_task.get("hotpotqa", 0)),
        },
        "eligible_span_count_by_task": {
            "gsm8k": int(eligible_by_task.get("gsm8k", 0)),
            "hotpotqa": int(eligible_by_task.get("hotpotqa", 0)),
        },
        "expected_replay_jobs": expected_replay_jobs,
        "replay_attempt_count": len(replay_attempts),
        "successful_replay_count": len(successful_replays),
        "replay_success_rate": replay_success_rate,
        "delta_rows": len(delta_rows),
        "nonzero_delta_rows": len(nonzero_delta_rows),
        "nonzero_delta_u_pooled_count": len(nonzero_delta_rows),
        "nonzero_delta_u_by_task": {
            "gsm8k": int(nonzero_by_task.get("gsm8k", 0)),
            "hotpotqa": int(nonzero_by_task.get("hotpotqa", 0)),
        },
        "rank_signal": dict(rank_signal),
        "rank_signal_metric": rank_signal.get("metric"),
        "TASK_SPECIFIC_pass_by_task": task_pass,
        "TASK_SPECIFIC_pass": task_specific_pass,
        "GLOBAL_pass": global_pass,
        "cost_used_usd": float(cost_used_usd),
        "approved_budget_usd": approved_budget,
        "cost_within_budget": float(cost_used_usd) <= approved_budget,
        "api_attempts": actual_requests,
        "max_api_requests": max_requests,
        "request_within_cap": actual_requests <= max_requests,
        "json_parse_success_rate": attempt_quality["json_parse_success_rate"],
        "schema_success_rate": attempt_quality["schema_success_rate"],
        "tag_extraction_success_rate": attempt_quality["tag_extraction_success_rate"],
        "final_answer_parse_success_rate": attempt_quality[
            "final_answer_parse_success_rate"
        ],
        "output_extraction_diagnostics_complete": attempt_quality[
            "output_extraction_diagnostics_complete"
        ],
        "current_status_remains": "PILOT_BLOCKED",
        "full_validation_completion_report": True,
        "deterministic_replay_claim_allowed": False,
        "prm_filtering_validation_approval_request_allowed": downstream_approval_request_allowed,
        "prm_filtering_validation_execution_allowed": False,
        "prm_filtering_performed": False,
        "submission_ready_claim_allowed": False,
        "top_tier_ready_claim_allowed": False,
        "claim_upgrade_allowed": False,
        "allowed_claim_scope": [
            "full stochastic repeated-replay validation diagnostics",
            "task-specific full gate status if directly passed by this artifact",
            "global full gate status if directly passed by this artifact",
            "downstream PRM/filtering approval request only if GLOBAL_pass is true",
        ],
        "forbidden_claim_scope": [
            "deterministic replay claim",
            "top-tier-ready claim",
            "submission-ready claim",
            "PRM/filtering execution or superiority claim without separate approval",
            "historical failed artifact rewrite",
        ],
    }


def _full_task_pass_map(
    *,
    expected_by_task: Mapping[str, int],
    valid_by_task: Mapping[str, int],
    eligible_by_task: Mapping[str, int],
    nonzero_by_task: Mapping[str, int],
    replay_success_rate: float,
    attempt_quality: Mapping[str, Any],
    rank_signal: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> dict[str, bool]:
    task_pass = {}
    for task_type in expected_by_task:
        rank_pass = bool(
            rank_signal.get("per_task", {})
            .get(task_type, {})
            .get("spearman_ci_lower_gt_zero")
            is True
        )
        task_pass[task_type] = bool(
            int(valid_by_task.get(task_type, 0))
            >= int(readiness["min_valid_traces_per_task"])
            and int(eligible_by_task.get(task_type, 0))
            >= int(readiness["min_eligible_spans_per_task"])
            and replay_success_rate >= float(readiness["min_replay_success_rate"])
            and _quality_gates_pass(attempt_quality, readiness)
            and int(nonzero_by_task.get(task_type, 0))
            >= int(readiness["min_nonzero_delta_u_per_task"])
            and rank_pass
        )
    return task_pass


def _valid_traces_by_task_pass(
    original_records: Sequence[Mapping[str, Any]],
    readiness: Mapping[str, Any],
) -> bool:
    valid_by_task = Counter(str(record.get("task_type") or "") for record in original_records)
    return all(
        int(valid_by_task.get(task_type, 0)) >= int(readiness["min_valid_traces_per_task"])
        for task_type in dict(readiness.get("sample_count_by_task") or {})
    )


def _validate_manifest_and_overlap(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
) -> None:
    expected_by_task = {
        str(task_type): int(task_config.get("sample_count", 0) or 0)
        for task_type, task_config in (
            config.get("fresh_selection_policy", {}).get("tasks", {}) or {}
        ).items()
    }
    expected_total = sum(expected_by_task.values())
    if expected_total and len(manifest) != expected_total:
        raise V2_1FullStochasticError(
            f"v2.1 fresh manifest row count is {len(manifest)}, expected {expected_total}."
        )
    if overlap_audit.get("status") != "MANIFEST_OVERLAP_CLEAN":
        raise V2_1FullStochasticError(
            "manifest overlap audit must be MANIFEST_OVERLAP_CLEAN."
        )
    selected_overlaps = dict(
        overlap_audit.get("overlap_summary", {}).get("selected_overlaps_by_key", {})
    )
    required = {
        "sample_id",
        "task_id",
        "dataset_config_split_source_index",
        "normalized_question_hash",
        "reference_answer_hash",
        "alias_hash",
    }
    missing = required.difference(selected_overlaps)
    nonzero = {
        key: value for key, value in selected_overlaps.items() if int(value or 0) != 0
    }
    if missing or nonzero:
        raise V2_1FullStochasticError(
            "manifest overlap audit must be clean on all six selected keys."
        )


def _validate_contract(contract_audit: Mapping[str, Any]) -> None:
    if contract_audit.get("status") != V2_1_CONTRACT_CLEAN:
        raise V2_1FullStochasticError(
            "v2_1_contract_audit.json must be V2_1_CONTRACT_CLEAN."
        )
    if contract_audit.get("claim_upgrade_allowed") is not False:
        raise V2_1FullStochasticError(
            "v2.1 contract audit must not allow claim upgrade."
        )


def _validate_prompt_version(
    *,
    manifest: Sequence[Mapping[str, Any]],
    contract_audit: Mapping[str, Any],
    current_prompt_version: str | None,
) -> None:
    if current_prompt_version is None:
        raise V2_1FullStochasticError("current prompt version is required.")
    manifest_versions = {row.get("prompt_version") for row in manifest if row.get("prompt_version")}
    contract_version = contract_audit.get("prompt_version")
    if manifest_versions and manifest_versions != {current_prompt_version}:
        raise V2_1FullStochasticError("v2.1 prompt version lock mismatch before full validation.")
    if contract_version and contract_version != current_prompt_version:
        raise V2_1FullStochasticError("v2.1 contract prompt version mismatch before full validation.")


def _validate_current_pilot_summary(
    pilot_report: Mapping[str, Any],
    approval_request: Mapping[str, Any],
) -> None:
    if pilot_report.get("TASK_SPECIFIC_pass") is not True:
        raise V2_1FullStochasticError("current pilot TASK_SPECIFIC_pass must be true.")
    if pilot_report.get("GLOBAL_pass") is not True:
        raise V2_1FullStochasticError("current pilot GLOBAL_pass must be true.")
    if pilot_report.get("full_validation_approval_request_allowed") is not True:
        raise V2_1FullStochasticError(
            "current pilot must allow a full validation approval request."
        )
    if pilot_report.get("deterministic_replay_claim_allowed") is not False:
        raise V2_1FullStochasticError(
            "current pilot must forbid deterministic replay claims."
        )
    if pilot_report.get("current_status_remains") != "PILOT_BLOCKED":
        raise V2_1FullStochasticError("current pilot status must remain PILOT_BLOCKED.")

    summary = approval_request.get("source_pilot_summary") or {}
    mapping = {
        "source_scope": ("scope",),
        "source_status": ("status",),
        "recomputed_after_scope": ("recomputed_after_scope",),
        "actual_api_requests": ("api_attempts", "actual_api_requests"),
        "actual_cost_usd": ("cost_used_usd", "actual_cost_usd"),
        "valid_original_traces": ("valid_original_traces",),
        "valid_original_traces_by_task": ("valid_original_traces_by_task",),
        "replay_success": ("replay_success",),
        "replay_success_rate": ("replay_success_rate",),
        "json_parse_success_rate": ("json_parse_success_rate",),
        "schema_success_rate": ("schema_success_rate",),
        "tag_extraction_success_rate": ("tag_extraction_success_rate",),
        "final_answer_parse_success_rate": ("final_answer_parse_success_rate",),
        "nonzero_delta_u_pooled_count": ("nonzero_delta_u_pooled_count",),
        "nonzero_delta_u_by_task": ("nonzero_delta_u_by_task",),
        "TASK_SPECIFIC_pass": ("TASK_SPECIFIC_pass",),
        "GLOBAL_pass": ("GLOBAL_pass",),
        "full_validation_approval_request_allowed": (
            "full_validation_approval_request_allowed",
        ),
        "deterministic_replay_claim_allowed": ("deterministic_replay_claim_allowed",),
        "current_status_remains": ("current_status_remains",),
    }
    for summary_key, report_keys in mapping.items():
        report_value = _first_present(pilot_report, report_keys)
        if summary.get(summary_key) != report_value:
            raise V2_1FullStochasticError(
                "approval request must match current pilot stochastic artifact."
            )


def _first_present(payload: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _write_original_checkpoint(
    paths: Mapping[str, Path],
    original_attempts: Sequence[Mapping[str, Any]],
    original_records: Sequence[Mapping[str, Any]],
) -> None:
    _write_records_checkpoint(list(original_records), paths["original_traces"])
    _write_records_checkpoint(list(original_attempts), paths["original_attempts"])


def _write_replay_checkpoint(
    paths: Mapping[str, Path],
    replay_attempts: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
) -> None:
    _write_records_checkpoint(list(replay_attempts), paths["replay_attempts"])
    _write_records_checkpoint(list(replay_results), paths["replay_results"])


def _write_records_checkpoint(
    records: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    attempts: int = 5,
    base_delay_seconds: float = 0.25,
) -> None:
    """Write checkpoint rows with bounded retries for transient Windows file errors."""

    for index in range(attempts):
        try:
            write_records([dict(record) for record in records], path)
            return
        except OSError:
            if index == attempts - 1:
                raise
            time.sleep(base_delay_seconds * (index + 1))


def _full_replay_job_plan(
    prefixes: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
    *,
    repeats: int,
) -> dict[str, Any]:
    expected_replay_jobs = len(prefixes) * repeats
    return {
        "expected_replay_jobs": expected_replay_jobs,
        "missing_jobs": missing_replay_jobs(prefixes, replay_results, repeats=repeats),
    }


def _replay_attempt_payload(
    job: Mapping[str, Any],
    result: GeneratedTraceResult,
) -> dict[str, Any]:
    generation_config = result.record.get("generation_config", {}) if result.record else {}
    return {
        "preflight_attempt": False,
        "attempt_role": "full_replay",
        "sample_id": job.get("sample_id"),
        "task_id": job.get("task_id"),
        "task_type": job.get("task_type"),
        "span_index": int(job.get("span_index", 0) or 0),
        "repeat_index": int(job.get("repeat_index", 0) or 0),
        "status": "success" if result.record is not None else "failed",
        "record": result.record,
        "raw_output": result.raw_output,
        "usage": result.usage,
        "model_name": result.model_name,
        "structured_output_mode": result.structured_output_mode
        or generation_config.get("structured_output_mode"),
        "system_fingerprint": result.system_fingerprint,
        "response_id": result.response_id or generation_config.get("response_id"),
        "output_extraction_diagnostics": dict(result.output_extraction_diagnostics or {}),
        "validation_errors": list(result.validation_errors),
        "fallback_events": list(result.fallback_events),
    }


def _replay_result_payload(
    job: Mapping[str, Any],
    result: GeneratedTraceResult,
) -> dict[str, Any]:
    record = dict(result.record or {})
    record.update(
        {
            "sample_id": job.get("sample_id"),
            "task_id": job.get("task_id"),
            "task_type": job.get("task_type"),
            "span_index": int(job.get("span_index", 0) or 0),
            "repeat_index": int(job.get("repeat_index", 0) or 0),
            "status": "success",
            "intervention_type": job.get(
                "intervention_type", "api_length_preserving_masked_prefix"
            ),
            "target_span": job.get("target_span"),
        }
    )
    return record


def _cost_used(
    original_results: Sequence[GeneratedTraceResult],
    replay_attempts: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> float:
    original_attempts = attempt_payloads_from_results(
        original_results,
        role="full_original",
        samples=selected,
    )
    return _estimate_cost_usd(config, [*original_attempts, *replay_attempts])


def _estimate_cost_usd(config: Mapping[str, Any], attempts: Sequence[Mapping[str, Any]]) -> float:
    cost = estimate_attempt_cost_usd(attempts, config=config)
    return round(float(cost or 0.0), 6)


def _load_required_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"required records file does not exist: {path}")
    return load_records(path)


def _load_records_if_exists(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_records(path)


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required JSON does not exist: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
