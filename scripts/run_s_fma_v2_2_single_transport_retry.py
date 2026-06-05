"""Run the approved v2.2 single-record API preflight transport retry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_preflight import attempt_payloads_from_results, select_preflight_records
from fma.real_task_pilot.fresh_preflight_v2_2 import (
    V2_2PreflightError,
    build_v2_2_generation_config,
    build_v2_2_preflight_report,
    estimate_attempt_cost_usd,
)
from fma.real_task_pilot.generation import GeneratedTraceResult, load_prompt_template
from scripts.run_s_fma_v2_1_fresh_holdout_preflight import (
    SingleRequestOpenAITraceAdapter,
    generate_trace_once,
)


V2_2_API_PREFLIGHT_SINGLE_TRANSPORT_RETRY_ONLY = (
    "V2_2_API_PREFLIGHT_SINGLE_TRANSPORT_RETRY_ONLY"
)
TARGET_SAMPLE_ID = "hotpotqa-00240"


def merge_single_retry_attempt(
    attempts: Sequence[Mapping[str, Any]],
    retry_attempt: Mapping[str, Any],
    *,
    target_sample_id: str,
) -> tuple[list[dict[str, Any]], int]:
    """Replace exactly one target preflight attempt with the retry result."""

    if retry_attempt.get("sample_id") != target_sample_id:
        raise V2_2PreflightError("retry attempt target must match the approved sample_id.")
    merged: list[dict[str, Any]] = []
    replaced = 0
    for attempt in attempts:
        current = dict(attempt)
        if current.get("sample_id") == target_sample_id:
            if current.get("attempt_role") != "preflight_record":
                raise V2_2PreflightError("target retry can only replace a preflight_record attempt.")
            merged.append(dict(retry_attempt))
            replaced += 1
        else:
            merged.append(current)
    if replaced != 1:
        raise V2_2PreflightError(
            f"expected exactly one source attempt for {target_sample_id}, found {replaced}."
        )
    return merged, replaced


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run only the approved v2.2 single transport retry for hotpotqa-00240."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_2_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-single-transport-retry",
        action="store_true",
        help="Required explicit guard for V2_2_API_PREFLIGHT_SINGLE_TRANSPORT_RETRY_ONLY.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="Hard budget ceiling for this single transport retry.",
    )
    parser.add_argument(
        "--max-api-requests",
        type=int,
        required=True,
        help="Hard request cap for this single target record retry.",
    )
    parser.add_argument(
        "--target-sample-id",
        default=TARGET_SAMPLE_ID,
        help="Must be hotpotqa-00240.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    output_root = Path(
        config.get("experiment", {}).get("output_dir", "outputs/s_fma_v2_2_fresh_holdout")
    )
    paths = {
        "manifest": output_root / "fresh_manifest.json",
        "single_retry_approval": output_root / "api_preflight_single_retry_approval_request.json",
        "failure_audit": output_root / "api_preflight_failure_audit.json",
        "source_report": output_root / "api_preflight_report.json",
        "attempts": output_root / "api_preflight_attempts.jsonl",
        "traces": output_root / "api_preflight_traces.jsonl",
        "cost": output_root / "logs" / "api_preflight_cost_report.json",
        "readiness": Path("outputs") / "real_task_pilot" / "readiness_audit.json",
    }

    manifest = _load_required_records(paths["manifest"])
    approval_request = _load_required_json(paths["single_retry_approval"])
    failure_audit = _load_required_json(paths["failure_audit"])
    source_report = _load_required_json(paths["source_report"])
    current_readiness = _load_required_json(paths["readiness"])
    source_attempts = _load_required_records(paths["attempts"])
    preflight_attempts = [
        attempt for attempt in source_attempts if attempt.get("attempt_role") == "preflight_record"
    ]
    determinism_attempts = [
        attempt for attempt in source_attempts if attempt.get("attempt_role") == "determinism_probe"
    ]

    _validate_single_retry_readiness(
        approval_request=approval_request,
        failure_audit=failure_audit,
        source_report=source_report,
        current_readiness=current_readiness,
        preflight_attempts=preflight_attempts,
        allow_single_transport_retry=args.allow_single_transport_retry,
        approved_budget_usd=args.approved_budget_usd,
        max_api_requests=args.max_api_requests,
        target_sample_id=args.target_sample_id,
    )

    selected_records = select_preflight_records(
        manifest,
        samples_per_task=10,
        task_order=["gsm8k", "hotpotqa"],
    )
    target_record = _select_target_record(selected_records, args.target_sample_id)
    retry_live_config = build_v2_2_generation_config(
        config,
        readiness={
            "approved_budget_usd": float(args.approved_budget_usd),
            "max_api_requests": int(args.max_api_requests),
            "planned_api_requests": int(args.max_api_requests),
            "determinism_probe_repeats": 0,
            "selected_records": 1,
        },
    )
    prompt_template = load_prompt_template(retry_live_config["generation"]["prompt_file"])
    adapter = SingleRequestOpenAITraceAdapter()

    retry_results: list[GeneratedTraceResult] = []
    budget_stop_triggered = False
    for _index in range(int(args.max_api_requests)):
        retry_results.append(
            generate_trace_once(
                target_record,
                adapter=adapter,
                config=retry_live_config,
                prompt_template=prompt_template,
            )
        )
        retry_attempts_so_far = attempt_payloads_from_results(
            retry_results,
            role="preflight_record",
            samples=[target_record] * len(retry_results),
        )
        retry_cost = estimate_attempt_cost_usd(retry_attempts_so_far, config=retry_live_config)
        if retry_cost is not None and retry_cost > float(args.approved_budget_usd):
            budget_stop_triggered = True
            break
        if retry_results[-1].record is not None:
            break

    retry_attempts = attempt_payloads_from_results(
        retry_results,
        role="preflight_record",
        samples=[target_record] * len(retry_results),
    )
    final_retry_attempt = _select_final_retry_attempt(retry_attempts)
    merged_preflight_attempts, replaced_count = merge_single_retry_attempt(
        preflight_attempts,
        final_retry_attempt,
        target_sample_id=args.target_sample_id,
    )

    drift_outputs = [_attempt_observable_output(attempt) for attempt in determinism_attempts]
    recompute_config = build_v2_2_generation_config(
        config,
        readiness={
            "approved_budget_usd": float(args.approved_budget_usd),
            "max_api_requests": int(source_report.get("max_api_requests") or 25)
            + int(args.max_api_requests),
            "planned_api_requests": len(source_attempts) + len(retry_attempts),
            "determinism_probe_repeats": len(determinism_attempts),
            "selected_records": int(source_report.get("records_expected") or len(selected_records)),
        },
    )
    report = build_v2_2_preflight_report(
        merged_preflight_attempts,
        selected_records=selected_records,
        drift_outputs=drift_outputs,
        config=recompute_config,
        readiness={
            "approved_budget_usd": float(args.approved_budget_usd),
            "max_api_requests": int(source_report.get("max_api_requests") or 25)
            + int(args.max_api_requests),
            "selected_records": int(source_report.get("records_expected") or len(selected_records)),
        },
        cost_attempts=list(source_attempts) + retry_attempts,
    )

    single_retry_cost = estimate_attempt_cost_usd(retry_attempts, config=retry_live_config)
    report.update(
        {
            "single_retry_scope": V2_2_API_PREFLIGHT_SINGLE_TRANSPORT_RETRY_ONLY,
            "single_retry_target_sample_id": args.target_sample_id,
            "single_retry_replaced_preflight_attempts": replaced_count,
            "single_retry_api_attempts": len(retry_attempts),
            "single_retry_request_cap": int(args.max_api_requests),
            "single_retry_request_within_cap": len(retry_attempts) <= int(args.max_api_requests),
            "single_retry_budget_ceiling_usd": float(args.approved_budget_usd),
            "single_retry_cost_used_usd": single_retry_cost,
            "single_retry_budget_gate_pass": (
                single_retry_cost is not None
                and single_retry_cost <= float(args.approved_budget_usd)
            ),
            "single_retry_result_status": (
                "success" if final_retry_attempt.get("record") is not None else "failed"
            ),
            "single_retry_budget_stop_triggered": budget_stop_triggered,
            "preflight_rerun_performed": False,
            "determinism_probe_rerun_performed": False,
            "smoke_performed": False,
            "replay_performed": False,
            "scoring_performed": False,
            "validation_performed": False,
            "prm_or_filtering_performed": False,
            "drift_outputs_reused_from_source_preflight": True,
            "source_drift_status": source_report.get("drift_status"),
            "drift_failure_must_not_be_rewritten": True,
            "current_status_remains": "PILOT_BLOCKED",
        }
    )
    cost_report = dict(report.get("cost_report") or {})
    cost_report.update(
        {
            "single_retry_scope": V2_2_API_PREFLIGHT_SINGLE_TRANSPORT_RETRY_ONLY,
            "single_retry_target_sample_id": args.target_sample_id,
            "single_retry_api_attempts": len(retry_attempts),
            "single_retry_request_cap": int(args.max_api_requests),
            "single_retry_cost_used_usd": single_retry_cost,
            "single_retry_budget_ceiling_usd": float(args.approved_budget_usd),
            "single_retry_budget_gate_pass": report["single_retry_budget_gate_pass"],
            "preflight_rerun_performed": False,
            "determinism_probe_rerun_performed": False,
        }
    )
    report["cost_report"] = cost_report

    write_records(merged_preflight_attempts + determinism_attempts, paths["attempts"])
    write_records(_valid_records_from_attempts(merged_preflight_attempts), paths["traces"])
    _write_json(paths["source_report"], report)
    _write_json(paths["cost"], cost_report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "drift_status": report.get("drift_status"),
                "failure_codes": report.get("failure_codes"),
                "single_retry_result_status": report["single_retry_result_status"],
                "single_retry_api_attempts": report["single_retry_api_attempts"],
                "single_retry_cost_used_usd": report["single_retry_cost_used_usd"],
                "actual_api_requests": report.get("actual_api_requests"),
                "actual_cost_usd": report.get("actual_cost_usd"),
                "current_status_remains": report["current_status_remains"],
            },
            sort_keys=True,
        )
    )


def _validate_single_retry_readiness(
    *,
    approval_request: Mapping[str, Any],
    failure_audit: Mapping[str, Any],
    source_report: Mapping[str, Any],
    current_readiness: Mapping[str, Any],
    preflight_attempts: Sequence[Mapping[str, Any]],
    allow_single_transport_retry: bool,
    approved_budget_usd: float,
    max_api_requests: int,
    target_sample_id: str,
) -> None:
    if not allow_single_transport_retry:
        raise V2_2PreflightError(
            "v2.2 single transport retry requires --allow-single-transport-retry."
        )
    if target_sample_id != TARGET_SAMPLE_ID:
        raise V2_2PreflightError("single retry target must be hotpotqa-00240.")
    if approval_request.get("requested_scope") != V2_2_API_PREFLIGHT_SINGLE_TRANSPORT_RETRY_ONLY:
        raise V2_2PreflightError("single retry approval request has the wrong scope.")
    if approval_request.get("approval_status") != "REQUEST_ONLY_NOT_APPROVED":
        raise V2_2PreflightError("single retry approval artifact must remain request-only provenance.")
    if approval_request.get("api_execution_authorized_by_this_request") is not False:
        raise V2_2PreflightError("request-only artifact must not self-authorize API execution.")
    proposed = dict(approval_request.get("proposed_retry_design") or {})
    if proposed.get("target_record") != TARGET_SAMPLE_ID:
        raise V2_2PreflightError("single retry approval target changed.")
    if int(proposed.get("max_api_requests") or 0) != 3 or int(max_api_requests) > 3:
        raise V2_2PreflightError("single retry request cap must be at most 3.")
    if float(proposed.get("budget_ceiling_usd") or 0) != 1.0 or float(approved_budget_usd) > 1.0:
        raise V2_2PreflightError("single retry budget ceiling must be at most USD 1.")
    if current_readiness.get("status") != "PILOT_BLOCKED":
        raise V2_2PreflightError("current readiness must remain PILOT_BLOCKED before retry.")
    if current_readiness.get("pilot_pass") is True:
        raise V2_2PreflightError("current readiness must not report pilot_pass=true before retry.")
    if source_report.get("current_status_remains") != "PILOT_BLOCKED":
        raise V2_2PreflightError("source preflight report must keep PILOT_BLOCKED.")
    if source_report.get("drift_status") != "PREFLIGHT_FAIL_DRIFT":
        raise V2_2PreflightError("single retry cannot run unless source drift failure is frozen.")
    failed_attempts = [
        attempt
        for attempt in preflight_attempts
        if attempt.get("sample_id") == target_sample_id
        and attempt.get("record") is None
        and "APIConnectionError" in " ".join(map(str, attempt.get("validation_errors") or []))
    ]
    if len(failed_attempts) != 1:
        raise V2_2PreflightError("source failed target attempt must remain one APIConnectionError.")
    audit_target = (
        failure_audit.get("failure_source_audit", {})
        .get("failed_preflight_record", {})
        .get("sample_id")
    )
    if audit_target != TARGET_SAMPLE_ID:
        raise V2_2PreflightError("failure audit target must remain hotpotqa-00240.")


def _select_target_record(
    selected_records: Sequence[Mapping[str, Any]],
    target_sample_id: str,
) -> dict[str, Any]:
    matches = [dict(record) for record in selected_records if record.get("sample_id") == target_sample_id]
    if len(matches) != 1:
        raise V2_2PreflightError("target record must be exactly one selected preflight record.")
    return matches[0]


def _select_final_retry_attempt(retry_attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    for attempt in retry_attempts:
        if attempt.get("record") is not None:
            return dict(attempt)
    if not retry_attempts:
        raise V2_2PreflightError("no retry attempts were produced.")
    return dict(retry_attempts[-1])


def _attempt_observable_output(attempt: Mapping[str, Any]) -> str:
    record = attempt.get("record")
    if isinstance(record, Mapping) and record.get("observable_trace") is not None:
        return str(record.get("observable_trace"))
    return str(attempt.get("raw_output") or "")


def _valid_records_from_attempts(attempts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(attempt["record"])
        for attempt in attempts
        if isinstance(attempt.get("record"), Mapping)
    ]


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
