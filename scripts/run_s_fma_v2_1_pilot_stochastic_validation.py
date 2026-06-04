"""Run the approved s_FMA_v2.1 pilot stochastic validation with hard guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.eval.diagnostics.correlation_metrics import spearman
from fma.io import load_records, write_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_holdout_v2_1 import V2_1_CONTRACT_CLEAN
from fma.real_task_pilot.fresh_preflight import (
    attempt_payloads_from_results,
    select_preflight_records,
)
from fma.real_task_pilot.fresh_preflight_v2_1 import estimate_attempt_cost_usd
from fma.real_task_pilot.fresh_smoke_v2_1 import (
    V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST,
    V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX,
    aggregate_v2_1_delta_u_by_span,
    build_v2_1_stochastic_smoke_generation_config,
    build_v2_1_stochastic_smoke_prefixes,
)
from fma.real_task_pilot.generation import GeneratedTraceResult, load_prompt_template
from fma.real_task_pilot.replay import missing_replay_jobs
from scripts.run_s_fma_v2_1_fresh_holdout_preflight import (
    SingleRequestOpenAITraceAdapter,
    generate_trace_once,
)


V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY = "V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY"
V2_1_PILOT_STOCHASTIC_PASS = "V2_1_PILOT_STOCHASTIC_PASS"
V2_1_PILOT_STOCHASTIC_FAIL_SCHEMA_OR_TAGS = (
    "V2_1_PILOT_STOCHASTIC_FAIL_SCHEMA_OR_TAGS"
)
V2_1_PILOT_STOCHASTIC_FAIL_GENERATION = "V2_1_PILOT_STOCHASTIC_FAIL_GENERATION"
V2_1_PILOT_STOCHASTIC_FAIL_REPLAY = "V2_1_PILOT_STOCHASTIC_FAIL_REPLAY"
V2_1_PILOT_STOCHASTIC_FAIL_SPARSE_SIGNAL = (
    "V2_1_PILOT_STOCHASTIC_FAIL_SPARSE_SIGNAL"
)
V2_1_PILOT_STOCHASTIC_FAIL_RANK_SIGNAL = (
    "V2_1_PILOT_STOCHASTIC_FAIL_RANK_SIGNAL"
)
V2_1_PILOT_STOCHASTIC_FAIL_COST = "V2_1_PILOT_STOCHASTIC_FAIL_COST"
V2_1_PILOT_STOCHASTIC_FAIL_REQUEST_LIMIT = (
    "V2_1_PILOT_STOCHASTIC_FAIL_REQUEST_LIMIT"
)


class V2_1PilotStochasticError(RuntimeError):
    """Raised when a hard v2.1 pilot stochastic boundary is violated."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_1_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-pilot-stochastic-validation-only",
        action="store_true",
        help="Required explicit guard for the approved v2.1 stochastic pilot.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="User-approved hard budget ceiling. Must match the pilot request.",
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
    pilot_paths = v2_1_pilot_stochastic_paths(output_root)
    paths = {
        "manifest": output_root / "fresh_manifest.json",
        "overlap": output_root / "manifest_overlap_audit.json",
        "contract": output_root / "v2_1_contract_audit.json",
        "smoke_report": output_root / "stochastic_smoke_report.json",
        "approval": output_root / "v2_1_pilot_stochastic_approval_request.json",
        "readiness": Path("outputs") / "real_task_pilot" / "readiness_audit.json",
        **pilot_paths,
    }

    manifest = _load_required_records(paths["manifest"])
    overlap_audit = _load_required_json(paths["overlap"])
    contract_audit = _load_required_json(paths["contract"])
    smoke_report = _load_required_json(paths["smoke_report"])
    approval_request = _load_required_json(paths["approval"])
    current_readiness = _load_required_json(paths["readiness"])
    prompt_file = Path(
        config.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        )
    )
    current_prompt_version = _prompt_version(prompt_file)

    readiness = validate_v2_1_pilot_stochastic_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=overlap_audit,
        contract_audit=contract_audit,
        smoke_report=smoke_report,
        approval_request=approval_request,
        current_readiness=current_readiness,
        allow_pilot_stochastic_validation_only=args.allow_pilot_stochastic_validation_only,
        approved_budget_usd=args.approved_budget_usd,
        current_prompt_version=current_prompt_version,
    )
    selected = select_preflight_records(
        manifest,
        samples_per_task=50,
        task_order=["gsm8k", "hotpotqa"],
    )
    live_config = build_v2_1_stochastic_smoke_generation_config(config, readiness=readiness)
    generation_prompt = load_prompt_template(live_config["generation"]["prompt_file"])
    replay_prompt = load_prompt_template(
        live_config.get("stochastic_smoke", {}).get(
            "replay_prompt_file", "prompts/real_task_replay.txt"
        )
    )
    adapter = SingleRequestOpenAITraceAdapter()

    original_results: list[GeneratedTraceResult] = []
    replay_attempts: list[dict[str, Any]] = []
    replay_results: list[dict[str, Any]] = []
    prefixes: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    expected_replay_jobs = 0
    budget_stop_triggered = False
    request_stop_triggered = False

    for sample in selected:
        if len(original_results) >= int(readiness["max_api_requests"]):
            request_stop_triggered = True
            break
        original_results.append(
            generate_trace_once(
                sample,
                adapter=adapter,
                config=live_config,
                prompt_template=generation_prompt,
            )
        )
        _write_original_checkpoint(paths, original_results, selected)
        if _cost_used(original_results, replay_attempts, selected, live_config) >= float(
            readiness["approved_budget_usd"]
        ):
            budget_stop_triggered = True
            break

    original_attempts = attempt_payloads_from_results(
        original_results,
        role="pilot_original",
        samples=selected,
    )
    original_records = [result.record for result in original_results if result.record is not None]

    if (
        not budget_stop_triggered
        and not request_stop_triggered
        and len(original_records) >= int(readiness["valid_original_traces_min"])
    ):
        prefixes = build_v2_1_stochastic_smoke_prefixes(
            original_records,
            config=live_config,
            mask_token=str(
                live_config.get("stochastic_smoke", {}).get(
                    "mask_token", "[REASONING_MASK]"
                )
            ),
        )
        write_records(prefixes, paths["prefixes"])
        repeats = int(readiness["stochastic_repeats_per_span"])
        jobs = missing_replay_jobs(prefixes, [], repeats=repeats)
        expected_replay_jobs = len(jobs)
        if len(original_attempts) + len(jobs) > int(readiness["max_api_requests"]):
            raise V2_1PilotStochasticError(
                "planned pilot replay jobs exceed the 700-request scope."
            )

        for job in jobs:
            if len(original_attempts) + len(replay_attempts) >= int(
                readiness["max_api_requests"]
            ):
                request_stop_triggered = True
                break
            if _cost_used(original_results, replay_attempts, selected, live_config) >= float(
                readiness["approved_budget_usd"]
            ):
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
        write_records(delta_rows, paths["delta_u"])
    else:
        write_records(prefixes, paths["prefixes"])
        write_records(delta_rows, paths["delta_u"])

    cost_used = _estimate_cost_usd(live_config, [*original_attempts, *replay_attempts])
    rank_signal = build_v2_1_pilot_rank_signal_report(
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
        + 2100,
    )
    report = build_v2_1_pilot_stochastic_report(
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
            "source_smoke_report": str(paths["smoke_report"]),
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
            "approved_scope": V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY,
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
                "current_status_remains": report["current_status_remains"],
            },
            sort_keys=True,
        )
    )


def v2_1_pilot_stochastic_paths(output_root: Path) -> dict[str, Path]:
    """Return only the approved v2.1 pilot stochastic output paths."""

    return {
        "original_attempts": output_root / "v2_1_pilot_stochastic_original_attempts.jsonl",
        "original_traces": output_root / "v2_1_pilot_stochastic_original_traces.jsonl",
        "prefixes": output_root / "v2_1_pilot_stochastic_replay_prefixes.jsonl",
        "replay_attempts": output_root / "v2_1_pilot_stochastic_replay_attempts.jsonl",
        "replay_results": output_root / "v2_1_pilot_stochastic_replay_results.jsonl",
        "delta_u": output_root / "v2_1_pilot_stochastic_delta_u.jsonl",
        "rank_signal": output_root / "v2_1_pilot_stochastic_rank_signal_report.json",
        "report": output_root / "v2_1_pilot_stochastic_report.json",
        "cost": output_root / "logs" / "v2_1_pilot_stochastic_cost_report.json",
    }


def validate_v2_1_pilot_stochastic_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    smoke_report: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    current_readiness: Mapping[str, Any],
    allow_pilot_stochastic_validation_only: bool,
    approved_budget_usd: float,
    current_prompt_version: str | None,
) -> dict[str, Any]:
    """Validate all user-approved gates before any stochastic pilot API call."""

    if not allow_pilot_stochastic_validation_only:
        raise V2_1PilotStochasticError(
            "v2.1 pilot requires explicit --allow-pilot-stochastic-validation-only."
        )
    if approval_request.get("requested_scope") != V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY:
        raise V2_1PilotStochasticError(
            "v2_1_pilot_stochastic_approval_request.json must request "
            f"{V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY}."
        )
    if approval_request.get("approval_status") != "REQUEST_ONLY_NOT_APPROVED":
        raise V2_1PilotStochasticError(
            "v2.1 pilot request artifact must remain REQUEST_ONLY_NOT_APPROVED."
        )
    if current_readiness.get("status") != "PILOT_BLOCKED":
        raise V2_1PilotStochasticError("current readiness status must remain PILOT_BLOCKED.")
    if current_readiness.get("pilot_pass") is True:
        raise V2_1PilotStochasticError("current readiness must not report pilot_pass=true.")

    _validate_manifest_and_overlap(config=config, manifest=manifest, overlap_audit=overlap_audit)
    _validate_contract(contract_audit)
    _validate_prompt_version(
        manifest=manifest,
        contract_audit=contract_audit,
        current_prompt_version=current_prompt_version,
    )
    if not _replay_alias_policy_active(config):
        raise V2_1PilotStochasticError("v2.1 replay alias policy must be active.")
    _validate_smoke_consistency(smoke_report, approval_request)

    design = approval_request.get("proposed_pilot_stochastic_validation_design", {})
    thresholds = approval_request.get("pilot_gate_thresholds", {})
    sample_count = int(design.get("records_total", 0) or 0)
    records_per_task = dict(design.get("records_by_task") or {})
    repeats = int(design.get("stochastic_repeats_per_eligible_span", 0) or 0)
    max_requests = int(design.get("max_api_requests", 0) or 0)
    max_spans = int(design.get("target_spans_per_trace_max", 0) or 0)
    recommended_budget = float(
        design.get("budget_ceiling_recommendation_usd", 0.0) or 0.0
    )
    if sample_count != 100 or records_per_task != {"gsm8k": 50, "hotpotqa": 50}:
        raise V2_1PilotStochasticError(
            "v2.1 pilot stochastic validation must be exactly 100 records, 50 per task."
        )
    if max_requests != 700:
        raise V2_1PilotStochasticError("v2.1 pilot max_api_requests must be exactly 700.")
    if repeats != 3:
        raise V2_1PilotStochasticError("v2.1 pilot repeats per eligible span must be 3.")
    if max_spans != 2:
        raise V2_1PilotStochasticError("v2.1 pilot max target spans per trace must be 2.")
    if float(approved_budget_usd) != recommended_budget:
        raise V2_1PilotStochasticError(
            "approved budget must match the pilot request budget ceiling."
        )

    return {
        "scope": V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY,
        "api_call_allowed": True,
        "sample_count": sample_count,
        "sample_count_by_task": records_per_task,
        "approved_budget_usd": float(approved_budget_usd),
        "max_api_requests": max_requests,
        "stochastic_repeats_per_span": repeats,
        "max_target_spans_per_trace": max_spans,
        "valid_original_trace_rate_min": float(
            thresholds.get("original_valid_trace_rate_min") or 0.95
        ),
        "valid_original_traces_min": math.ceil(
            sample_count * float(thresholds.get("original_valid_trace_rate_min") or 0.95)
        ),
        "min_replay_success_rate": float(
            thresholds.get("replay_success_rate_min") or 0.85
        ),
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
        "min_nonzero_delta_u_pooled": 3,
        "min_nonzero_delta_u_per_task": 1,
        "rank_signal_ci_lower_must_exceed": 0.0,
        "budget_gate_pass": True,
        "manifest_overlap_clean": True,
        "v2_1_contract_clean": True,
        "replay_alias_policy_active": True,
        "current_status_remains": "PILOT_BLOCKED",
        "deterministic_replay_claim_allowed": False,
        "claim_upgrade_allowed": False,
    }


def build_v2_1_pilot_rank_signal_report(
    delta_rows: Sequence[Mapping[str, Any]],
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Rank diagnostic over observed pilot rows only."""

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
        "estimand_boundary": "pilot stochastic repeated replay only",
        "primary_signal": {
            "available": bool(delta_rows),
            "name": "original_primary_score_vs_delta_u",
            "n": len(delta_rows),
            "target_leakage_status": "observed_pilot_metric_not_candidate_score",
        },
        "pooled": pooled,
        "per_task": per_task,
        "bootstrap": {
            "resamples": resamples,
            "confidence_level": confidence_level,
            "random_seed": seed,
        },
    }


def build_v2_1_pilot_stochastic_report(
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
    """Build a claim-safe v2.1 pilot stochastic report."""

    all_attempts = [*original_attempts, *replay_attempts]
    attempt_quality = _attempt_quality(all_attempts)
    actual_requests = len(all_attempts)
    max_requests = int(readiness["max_api_requests"])
    approved_budget = float(readiness["approved_budget_usd"])
    successful_replays = [
        row for row in replay_results if row.get("status") in {None, "success", "replayed"}
    ]
    replay_success_rate = (
        len(successful_replays) / len(replay_attempts) if replay_attempts else 0.0
    )
    valid_originals = len(original_records)
    valid_by_task = Counter(str(record.get("task_type") or "") for record in original_records)
    expected_by_task = dict(readiness.get("sample_count_by_task") or {})
    nonzero_delta_rows = [
        row for row in delta_rows if abs(float(row.get("delta_u", 0.0) or 0.0)) > 0.0
    ]
    nonzero_by_task = Counter(str(row.get("task_type") or "") for row in nonzero_delta_rows)
    task_pass = _task_pass_map(
        expected_by_task=expected_by_task,
        valid_by_task=valid_by_task,
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
    global_pass = task_specific_pass and pooled_rank_pass

    failure_codes = []
    if float(cost_used_usd) > approved_budget:
        failure_codes.append(V2_1_PILOT_STOCHASTIC_FAIL_COST)
    if actual_requests > max_requests:
        failure_codes.append(V2_1_PILOT_STOCHASTIC_FAIL_REQUEST_LIMIT)
    if not _quality_gates_pass(attempt_quality, readiness):
        failure_codes.append(V2_1_PILOT_STOCHASTIC_FAIL_SCHEMA_OR_TAGS)
    if valid_originals < _valid_original_traces_min(readiness):
        failure_codes.append(V2_1_PILOT_STOCHASTIC_FAIL_GENERATION)
    if replay_success_rate < float(readiness["min_replay_success_rate"]):
        failure_codes.append(V2_1_PILOT_STOCHASTIC_FAIL_REPLAY)
    sparse_signal = (
        len(nonzero_delta_rows) < int(readiness["min_nonzero_delta_u_pooled"])
        or any(
            int(nonzero_by_task.get(task_type, 0))
            < int(readiness["min_nonzero_delta_u_per_task"])
            for task_type in expected_by_task
        )
    )
    if sparse_signal:
        failure_codes.append(V2_1_PILOT_STOCHASTIC_FAIL_SPARSE_SIGNAL)
    if not global_pass:
        failure_codes.append(V2_1_PILOT_STOCHASTIC_FAIL_RANK_SIGNAL)

    status = V2_1_PILOT_STOCHASTIC_PASS if not failure_codes else failure_codes[0]
    return {
        "artifact": "v2_1_pilot_stochastic_report",
        "scope": str(readiness.get("scope") or V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY),
        "status": status,
        "failure_codes": failure_codes,
        "sample_count": int(readiness["sample_count"]),
        "sample_count_by_task": expected_by_task,
        "valid_original_traces": valid_originals,
        "valid_original_traces_by_task": {
            "gsm8k": int(valid_by_task.get("gsm8k", 0)),
            "hotpotqa": int(valid_by_task.get("hotpotqa", 0)),
        },
        "original_valid_trace_rate": (
            valid_originals / int(readiness["sample_count"])
            if int(readiness["sample_count"])
            else 0.0
        ),
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
        "full_validation_approval_request_allowed": global_pass,
        "prm_filtering_validation_design_allowed": False,
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
        "deterministic_replay_claim_allowed": False,
        "task_specific_pass_claim_allowed": global_pass,
        "global_pass_claim_allowed": global_pass,
        "v2_1_full_validation_request_allowed": global_pass,
        "claim_upgrade_allowed": False,
        "no_full_validation": True,
        "no_prm_claim": True,
        "allowed_claim_scope": [
            "pilot stochastic repeated-replay diagnostics",
            "task-specific pilot gate status if directly passed by this artifact",
            "global pilot gate status if directly passed by this artifact",
        ],
        "forbidden_claim_scope": [
            "full validation claim",
            "deterministic replay claim",
            "top-tier-ready claim",
            "PRM/filtering claim",
            "historical failed artifact rewrite",
        ],
    }


def _task_pass_map(
    *,
    expected_by_task: Mapping[str, int],
    valid_by_task: Mapping[str, int],
    nonzero_by_task: Mapping[str, int],
    replay_success_rate: float,
    attempt_quality: Mapping[str, Any],
    rank_signal: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> dict[str, bool]:
    task_pass = {}
    valid_rate_min = float(readiness["valid_original_trace_rate_min"])
    min_nonzero = int(readiness["min_nonzero_delta_u_per_task"])
    for task_type, expected_count in expected_by_task.items():
        valid_min = math.ceil(int(expected_count) * valid_rate_min)
        rank_pass = bool(
            rank_signal.get("per_task", {})
            .get(task_type, {})
            .get("spearman_ci_lower_gt_zero")
            is True
        )
        task_pass[task_type] = bool(
            int(valid_by_task.get(task_type, 0)) >= valid_min
            and replay_success_rate >= float(readiness["min_replay_success_rate"])
            and _quality_gates_pass(attempt_quality, readiness)
            and int(nonzero_by_task.get(task_type, 0)) >= min_nonzero
            and rank_pass
        )
    return task_pass


def _valid_original_traces_min(readiness: Mapping[str, Any]) -> int:
    if "valid_original_traces_min" in readiness:
        return int(readiness["valid_original_traces_min"])
    return math.ceil(
        int(readiness["sample_count"]) * float(readiness["valid_original_trace_rate_min"])
    )


def _quality_gates_pass(
    attempt_quality: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> bool:
    return bool(
        attempt_quality["json_parse_success_rate"]
        >= float(readiness["required_json_parse_success_rate"])
        and attempt_quality["schema_success_rate"]
        >= float(readiness["required_schema_success_rate"])
        and attempt_quality["tag_extraction_success_rate"]
        >= float(readiness["required_tag_extraction_success_rate"])
        and attempt_quality["final_answer_parse_success_rate"]
        >= float(readiness["required_final_answer_parse_success_rate"])
    )


def _attempt_quality(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(attempts)
    if total == 0:
        return {
            "output_extraction_diagnostics_present_count": 0,
            "output_extraction_diagnostics_complete": False,
            "json_parse_success_rate": 0.0,
            "schema_success_rate": 0.0,
            "tag_extraction_success_rate": 0.0,
            "final_answer_parse_success_rate": 0.0,
        }
    diagnostics_present = sum(
        1 for attempt in attempts if attempt.get("output_extraction_diagnostics")
    )
    json_success = sum(1 for attempt in attempts if attempt.get("record") is not None)
    schema_success = sum(
        1
        for attempt in attempts
        if attempt.get("record") is not None and not attempt.get("validation_errors")
    )
    tag_success = sum(
        1
        for attempt in attempts
        if (attempt.get("record") or {}).get("reflection_spans")
    )
    final_answer_success = sum(
        1
        for attempt in attempts
        if str((attempt.get("record") or {}).get("final_answer") or "").strip()
    )
    return {
        "output_extraction_diagnostics_present_count": diagnostics_present,
        "output_extraction_diagnostics_complete": diagnostics_present == total,
        "json_parse_success_rate": json_success / total,
        "schema_success_rate": schema_success / total,
        "tag_extraction_success_rate": tag_success / total,
        "final_answer_parse_success_rate": final_answer_success / total,
    }


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
        raise V2_1PilotStochasticError(
            f"v2.1 fresh manifest row count is {len(manifest)}, expected {expected_total}."
        )
    if overlap_audit.get("status") != "MANIFEST_OVERLAP_CLEAN":
        raise V2_1PilotStochasticError(
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
        raise V2_1PilotStochasticError(
            "manifest overlap audit must be clean on all six selected keys."
        )


def _validate_contract(contract_audit: Mapping[str, Any]) -> None:
    if contract_audit.get("status") != V2_1_CONTRACT_CLEAN:
        raise V2_1PilotStochasticError(
            "v2_1_contract_audit.json must be V2_1_CONTRACT_CLEAN."
        )
    if contract_audit.get("claim_upgrade_allowed") is not False:
        raise V2_1PilotStochasticError(
            "v2.1 contract audit must not allow claim upgrade."
        )


def _validate_prompt_version(
    *,
    manifest: Sequence[Mapping[str, Any]],
    contract_audit: Mapping[str, Any],
    current_prompt_version: str | None,
) -> None:
    if current_prompt_version is None:
        raise V2_1PilotStochasticError("current prompt version is required.")
    manifest_versions = {row.get("prompt_version") for row in manifest if row.get("prompt_version")}
    contract_version = contract_audit.get("prompt_version")
    if manifest_versions and manifest_versions != {current_prompt_version}:
        raise V2_1PilotStochasticError("v2.1 prompt version lock mismatch before pilot.")
    if contract_version and contract_version != current_prompt_version:
        raise V2_1PilotStochasticError("v2.1 contract prompt version mismatch before pilot.")


def _replay_alias_policy_active(config: Mapping[str, Any]) -> bool:
    policy = (
        config.get("stochastic_smoke", {}).get("replay_reflection_type_policy", {})
        if isinstance(config.get("stochastic_smoke", {}), Mapping)
        else {}
    )
    aliases = policy.get("alias_canonicalization") or {}
    allowed = set(policy.get("allowed_types") or [])
    return bool(
        policy.get("policy_name") == "v2_1_replay_schema_compatibility"
        and aliases.get("final_check") == "verification"
        and aliases.get("correction") == "error_diagnosis"
        and policy.get("unknown_type_policy") == "reject"
        and {"verification", "error_diagnosis", "plan_revision", "self-evaluation"}.issubset(allowed)
    )


def _validate_smoke_consistency(
    smoke_report: Mapping[str, Any],
    approval_request: Mapping[str, Any],
) -> None:
    if smoke_report.get("status") != V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST:
        raise V2_1PilotStochasticError("current smoke report must be feasible for pilot request.")
    if smoke_report.get("scope") != V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX:
        raise V2_1PilotStochasticError("current smoke report scope is not the rerun scope.")
    summary = approval_request.get("source_smoke_summary") or {}
    mapping = {
        "source_scope": "scope",
        "source_status": "status",
        "source_records": "sample_count",
        "source_records_by_task": "sample_count_by_task",
        "source_api_requests": "api_attempts",
        "source_cost_used_usd": "cost_used_usd",
        "source_json_parse_success_rate": "json_parse_success_rate",
        "source_schema_success_rate": "schema_success_rate",
        "source_tag_extraction_success_rate": "tag_extraction_success_rate",
        "source_final_answer_parse_success_rate": "final_answer_parse_success_rate",
        "source_replay_success_rate": "replay_success_rate",
        "source_nonzero_delta_u_pooled_count": "nonzero_delta_u_pooled_count",
        "source_nonzero_delta_u_by_task": "nonzero_delta_u_by_task",
        "source_next_allowed_step": "next_allowed_step",
        "source_v2_1_pilot_request_allowed": "v2_1_pilot_request_allowed",
        "source_global_pass_claim_allowed": "global_pass_claim_allowed",
        "source_task_specific_pass_claim_allowed": "task_specific_pass_claim_allowed",
        "source_prm_filtering_claim_allowed": "prm_filtering_claim_allowed",
        "source_current_status_remains": "current_status_remains",
    }
    for summary_key, report_key in mapping.items():
        if summary.get(summary_key) != smoke_report.get(report_key):
            raise V2_1PilotStochasticError(
                "approval request must match current smoke feasible artifact."
            )


def _write_original_checkpoint(
    paths: Mapping[str, Path],
    original_results: Sequence[GeneratedTraceResult],
    selected: Sequence[Mapping[str, Any]],
) -> None:
    write_records(
        [result.record for result in original_results if result.record is not None],
        paths["original_traces"],
    )
    write_records(
        attempt_payloads_from_results(
            original_results,
            role="pilot_original",
            samples=selected,
        ),
        paths["original_attempts"],
    )


def _write_replay_checkpoint(
    paths: Mapping[str, Path],
    replay_attempts: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
) -> None:
    write_records(replay_attempts, paths["replay_attempts"])
    write_records(replay_results, paths["replay_results"])


def _replay_attempt_payload(
    job: Mapping[str, Any],
    result: GeneratedTraceResult,
) -> dict[str, Any]:
    generation_config = result.record.get("generation_config", {}) if result.record else {}
    return {
        "preflight_attempt": False,
        "attempt_role": "pilot_replay",
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
        role="pilot_original",
        samples=selected,
    )
    return _estimate_cost_usd(config, [*original_attempts, *replay_attempts])


def _estimate_cost_usd(config: Mapping[str, Any], attempts: Sequence[Mapping[str, Any]]) -> float:
    cost = estimate_attempt_cost_usd(attempts, config=config)
    return round(float(cost or 0.0), 6)


def _usage_totals(attempts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    for attempt in attempts:
        usage = attempt.get("usage") or {}
        input_tokens += int(usage.get("input_tokens", 0) or 0)
        output_tokens += int(usage.get("output_tokens", 0) or 0)
        total_tokens += int(usage.get("total_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _spearman_metrics(
    paired: Sequence[tuple[float, float]],
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    rho = spearman(
        [item[0] for item in paired],
        [item[1] for item in paired],
    ) if len(paired) >= 2 else 0.0
    ci95 = _bootstrap_spearman_ci(
        paired,
        resamples=resamples,
        confidence_level=confidence_level,
        seed=seed,
    )
    return {
        "n": len(paired),
        "spearman_rho": rho,
        "spearman_ci95": ci95,
        "spearman_ci_lower_gt_zero": bool(ci95[0] > 0.0),
    }


def _bootstrap_spearman_ci(
    paired: Sequence[tuple[float, float]],
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> list[float]:
    if len(paired) < 2 or resamples <= 0:
        value = spearman(
            [item[0] for item in paired],
            [item[1] for item in paired],
        ) if paired else 0.0
        return [float(value), float(value)]
    rng = random.Random(seed)
    values = []
    for _index in range(resamples):
        sample = [paired[rng.randrange(len(paired))] for _item in paired]
        values.append(
            spearman(
                [item[0] for item in sample],
                [item[1] for item in sample],
            )
        )
    values.sort()
    alpha = max(0.0, min(1.0, 1.0 - confidence_level))
    low_index = int((alpha / 2.0) * (len(values) - 1))
    high_index = int((1.0 - alpha / 2.0) * (len(values) - 1))
    return [float(values[low_index]), float(values[high_index])]


def _prompt_version(path: Path) -> str:
    return "prompt-sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_required_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"required records file does not exist: {path}")
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
