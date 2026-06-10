"""Run the approved s_FMA_v2.1 stochastic smoke rerun with hard guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.archive_paths import v2_1_failed_provenance_root
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_preflight import attempt_payloads_from_results, select_preflight_records
from fma.real_task_pilot.fresh_preflight_v2_1 import estimate_attempt_cost_usd
from fma.real_task_pilot.fresh_smoke_v2_1 import (
    V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX,
    V2_1StochasticSmokeError,
    aggregate_v2_1_delta_u_by_span,
    build_v2_1_stochastic_smoke_generation_config,
    build_v2_1_stochastic_smoke_prefixes,
    build_v2_1_stochastic_smoke_report,
    validate_v2_1_stochastic_smoke_readiness,
)
from fma.real_task_pilot.generation import GeneratedTraceResult, load_prompt_template
from fma.real_task_pilot.replay import missing_replay_jobs
from scripts.run_s_fma_v2_1_fresh_holdout_preflight import (
    SingleRequestOpenAITraceAdapter,
    generate_trace_once,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run guarded V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX "
            "for the s_FMA_v2.1 fresh holdout."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_1_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-stochastic-smoke-only",
        action="store_true",
        help="Required explicit guard for the v2.1 stochastic smoke run.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="User-approved hard budget ceiling. Must match the smoke request ceiling.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    output_root = Path(
        config.get("experiment", {}).get("output_dir", "outputs/s_fma_v2_1_fresh_holdout")
    )
    output_root = v2_1_failed_provenance_root(output_root)
    smoke_paths = v2_1_stochastic_smoke_paths(output_root)
    paths = {
        "manifest": output_root / "fresh_manifest.json",
        "overlap": output_root / "manifest_overlap_audit.json",
        "contract": output_root / "v2_1_contract_audit.json",
        "preflight": output_root / "api_preflight_report.json",
        "canary": output_root / "transport_canary_report.json",
        "drift_audit": output_root / "api_preflight_drift_failure_audit.json",
        "approval": output_root / "stochastic_smoke_rerun_approval_request.json",
        "readiness": Path("outputs") / "real_task_pilot" / "readiness_audit.json",
        **smoke_paths,
    }

    manifest = _load_required_records(paths["manifest"])
    overlap_audit = _load_required_json(paths["overlap"])
    contract_audit = _load_required_json(paths["contract"])
    preflight_report = _load_required_json(paths["preflight"])
    transport_canary_report = _load_required_json(paths["canary"])
    drift_failure_audit = _load_required_json(paths["drift_audit"])
    approval_request = _load_required_json(paths["approval"])
    current_readiness = _load_required_json(paths["readiness"])
    prompt_file = Path(
        config.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        )
    )
    current_prompt_version = _prompt_version(prompt_file)

    readiness = validate_v2_1_stochastic_smoke_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=overlap_audit,
        contract_audit=contract_audit,
        preflight_report=preflight_report,
        transport_canary_report=transport_canary_report,
        drift_failure_audit=drift_failure_audit,
        approval_request=approval_request,
        current_readiness=current_readiness,
        allow_stochastic_smoke_only=args.allow_stochastic_smoke_only,
        approved_budget_usd=args.approved_budget_usd,
        current_prompt_version=current_prompt_version,
    )
    selected = select_preflight_records(
        manifest,
        samples_per_task=10,
        task_order=["gsm8k", "hotpotqa"],
    )
    live_config = build_v2_1_stochastic_smoke_generation_config(config, readiness=readiness)
    generation_prompt = load_prompt_template(live_config["generation"]["prompt_file"])
    replay_prompt = load_prompt_template(
        live_config.get("stochastic_smoke", {}).get("replay_prompt_file", "prompts/real_task_replay.txt")
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
        role="smoke_original",
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
            mask_token=str(live_config.get("stochastic_smoke", {}).get("mask_token", "[REASONING_MASK]")),
        )
        write_records(prefixes, paths["prefixes"])
        repeats = int(readiness["stochastic_repeats_per_span"])
        jobs = missing_replay_jobs(prefixes, [], repeats=repeats)
        expected_replay_jobs = len(jobs)
        if len(original_attempts) + len(jobs) > int(readiness["max_api_requests"]):
            raise V2_1StochasticSmokeError("planned smoke replay jobs exceed the 140-request scope.")

        for job in jobs:
            if len(original_attempts) + len(replay_attempts) >= int(readiness["max_api_requests"]):
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
    report = build_v2_1_stochastic_smoke_report(
        original_records=original_records,
        original_attempts=original_attempts,
        replay_results=replay_results,
        replay_attempts=replay_attempts,
        delta_rows=delta_rows,
        readiness=readiness,
        cost_used_usd=cost_used,
        expected_replay_jobs=expected_replay_jobs,
    )
    report.update(
        {
            "approval_source": str(paths["approval"]),
            "manifest_source": str(paths["manifest"]),
            "preflight_report_source": str(paths["preflight"]),
            "transport_canary_report_source": str(paths["canary"]),
            "drift_failure_audit_source": str(paths["drift_audit"]),
            "api_execution_performed": True,
            "budget_stop_triggered": budget_stop_triggered,
            "request_stop_triggered": request_stop_triggered,
            "original_attempt_count": len(original_attempts),
            "original_valid_trace_count": len(original_records),
            "target_prefix_count": len(prefixes),
            "stochastic_repeats_per_span": int(readiness["stochastic_repeats_per_span"]),
        }
    )
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
            "approved_scope": V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX,
        },
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "api_attempts": report["api_attempts"],
                "cost_used_usd": report["cost_used_usd"],
                "valid_original_traces": report["sample_count"],
                "replay_success_rate": report["replay_success_rate"],
                "nonzero_delta_u_pooled_count": report["nonzero_delta_u_pooled_count"],
                "nonzero_delta_u_by_task": report["nonzero_delta_u_by_task"],
                "current_status_remains": report["current_status_remains"],
            },
            sort_keys=True,
        )
    )


def v2_1_stochastic_smoke_paths(output_root: Path) -> dict[str, Path]:
    """Return only the approved v2.1 stochastic smoke output paths."""

    output_root = v2_1_failed_provenance_root(output_root)
    return {
        "original_attempts": output_root / "stochastic_smoke_original_attempts.jsonl",
        "original_traces": output_root / "stochastic_smoke_original_traces.jsonl",
        "prefixes": output_root / "stochastic_smoke_replay_prefixes.jsonl",
        "replay_attempts": output_root / "stochastic_smoke_replay_attempts.jsonl",
        "replay_results": output_root / "stochastic_smoke_replay_results.jsonl",
        "delta_u": output_root / "stochastic_smoke_delta_u.jsonl",
        "report": output_root / "stochastic_smoke_report.json",
        "cost": output_root / "logs" / "stochastic_smoke_cost_report.json",
    }


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
            role="smoke_original",
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
        "attempt_role": "smoke_replay",
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
            "intervention_type": job.get("intervention_type", "api_length_preserving_masked_prefix"),
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
        role="smoke_original",
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
