"""Run s_FMA_v2.2 V2_2_API_PREFLIGHT_ONLY with explicit budget guards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_preflight import attempt_payloads_from_results, select_preflight_records
from fma.real_task_pilot.fresh_preflight_v2_2 import (
    build_v2_2_generation_config,
    build_v2_2_preflight_report,
    estimate_attempt_cost_usd,
    prompt_bundle_hash_from_config,
    validate_v2_2_preflight_readiness,
)
from fma.real_task_pilot.generation import GeneratedTraceResult, load_prompt_template
from scripts.run_s_fma_v2_1_fresh_holdout_preflight import (
    SingleRequestOpenAITraceAdapter,
    generate_trace_once,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded API preflight-only for the s_FMA_v2.2 fresh holdout."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_2_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-api-preflight-only",
        action="store_true",
        help="Required explicit guard for the v2.2 API preflight-only run.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="User-approved hard budget ceiling for this V2_2_API_PREFLIGHT_ONLY run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    output_root = Path(config.get("experiment", {}).get("output_dir", "outputs/s_fma_v2_2_fresh_holdout"))
    paths = {
        "manifest": output_root / "fresh_manifest.json",
        "overlap": output_root / "manifest_overlap_audit.json",
        "contract": output_root / "v2_2_contract_audit.json",
        "approval": output_root / "api_preflight_approval_request.json",
        "failure": Path("outputs") / "s_fma_v2_1_fresh_holdout" / "v2_1_full_validation_failure_audit.json",
        "readiness": Path("outputs") / "real_task_pilot" / "readiness_audit.json",
        "report": output_root / "api_preflight_report.json",
        "attempts": output_root / "api_preflight_attempts.jsonl",
        "traces": output_root / "api_preflight_traces.jsonl",
        "cost": output_root / "logs" / "api_preflight_cost_report.json",
    }
    manifest = _load_required_records(paths["manifest"])
    overlap_audit = _load_required_json(paths["overlap"])
    contract_audit = _load_required_json(paths["contract"])
    approval_request = _load_required_json(paths["approval"])
    failure_audit = _load_required_json(paths["failure"])
    current_readiness = _load_required_json(paths["readiness"])
    current_prompt_version = prompt_bundle_hash_from_config(config)

    readiness = validate_v2_2_preflight_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=overlap_audit,
        contract_audit=contract_audit,
        approval_request=approval_request,
        failure_audit=failure_audit,
        current_readiness=current_readiness,
        allow_api_preflight_only=args.allow_api_preflight_only,
        approved_budget_usd=args.approved_budget_usd,
        current_prompt_version=current_prompt_version,
    )
    selected = select_preflight_records(
        manifest,
        samples_per_task=10,
        task_order=["gsm8k", "hotpotqa"],
    )
    live_config = build_v2_2_generation_config(config, readiness=readiness)
    prompt_template = load_prompt_template(live_config["generation"]["prompt_file"])
    adapter = SingleRequestOpenAITraceAdapter()

    preflight_results: list[GeneratedTraceResult] = []
    determinism_results: list[GeneratedTraceResult] = []
    budget_stop_triggered = False
    request_stop_triggered = False

    for sample in selected:
        if _attempt_count(preflight_results, determinism_results) >= readiness["max_api_requests"]:
            request_stop_triggered = True
            break
        preflight_results.append(
            generate_trace_once(
                sample,
                adapter=adapter,
                config=live_config,
                prompt_template=prompt_template,
            )
        )
        _write_live_checkpoint(
            traces_path=paths["traces"],
            attempts_path=paths["attempts"],
            selected_records=selected,
            preflight_results=preflight_results,
            determinism_results=determinism_results,
        )
        if _budget_reached(
            preflight_results=preflight_results,
            determinism_results=determinism_results,
            selected_records=selected,
            config=live_config,
            approved_budget_usd=float(readiness["approved_budget_usd"]),
        ):
            budget_stop_triggered = True
            break

    drift_repeats = int(readiness.get("determinism_probe_repeats", 3))
    if not budget_stop_triggered and not request_stop_triggered and selected:
        probe_sample = selected[0]
        for _index in range(drift_repeats):
            if _attempt_count(preflight_results, determinism_results) >= readiness["max_api_requests"]:
                request_stop_triggered = True
                break
            determinism_results.append(
                generate_trace_once(
                    probe_sample,
                    adapter=adapter,
                    config=live_config,
                    prompt_template=prompt_template,
                )
            )
            _write_live_checkpoint(
                traces_path=paths["traces"],
                attempts_path=paths["attempts"],
                selected_records=selected,
                preflight_results=preflight_results,
                determinism_results=determinism_results,
            )
            if _budget_reached(
                preflight_results=preflight_results,
                determinism_results=determinism_results,
                selected_records=selected,
                config=live_config,
                approved_budget_usd=float(readiness["approved_budget_usd"]),
            ):
                budget_stop_triggered = True
                break

    preflight_attempts = attempt_payloads_from_results(
        preflight_results,
        role="preflight_record",
        samples=selected,
    )
    determinism_attempts = attempt_payloads_from_results(
        determinism_results,
        role="determinism_probe",
        samples=[selected[0]] * len(determinism_results) if selected else [],
    )
    drift_outputs = [
        str(result.record.get("observable_trace"))
        if result.record is not None
        else result.raw_output
        for result in determinism_results
    ]
    report = build_v2_2_preflight_report(
        preflight_attempts,
        selected_records=selected,
        drift_outputs=drift_outputs,
        config=live_config,
        readiness=readiness,
        cost_attempts=preflight_attempts + determinism_attempts,
    )
    report["budget_stop_triggered"] = budget_stop_triggered
    report["request_stop_triggered"] = request_stop_triggered
    report["api_execution_performed"] = True
    _write_json(paths["report"], report)
    _write_json(paths["cost"], report.get("cost_report", {}))
    print(
        json.dumps(
            {
                "status": report["status"],
                "records_evaluated": report["records_evaluated"],
                "api_attempts": report["api_attempts"],
                "cost_used_usd": report.get("cost_used_usd"),
            },
            sort_keys=True,
        )
    )


def _write_live_checkpoint(
    *,
    traces_path: Path,
    attempts_path: Path,
    selected_records: list[dict[str, Any]],
    preflight_results: list[GeneratedTraceResult],
    determinism_results: list[GeneratedTraceResult],
) -> None:
    valid_records = [result.record for result in preflight_results if result.record is not None]
    attempts = attempt_payloads_from_results(
        preflight_results,
        role="preflight_record",
        samples=selected_records,
    )
    attempts.extend(
        attempt_payloads_from_results(
            determinism_results,
            role="determinism_probe",
            samples=[selected_records[0]] * len(determinism_results) if selected_records else [],
        )
    )
    write_records(valid_records, traces_path)
    write_records(attempts, attempts_path)


def _budget_reached(
    *,
    preflight_results: list[GeneratedTraceResult],
    determinism_results: list[GeneratedTraceResult],
    selected_records: list[dict[str, Any]],
    config: dict[str, Any],
    approved_budget_usd: float,
) -> bool:
    attempts = attempt_payloads_from_results(
        preflight_results,
        role="preflight_record",
        samples=selected_records,
    )
    attempts.extend(
        attempt_payloads_from_results(
            determinism_results,
            role="determinism_probe",
            samples=[selected_records[0]] * len(determinism_results) if selected_records else [],
        )
    )
    cost = estimate_attempt_cost_usd(attempts, config=config)
    return cost is not None and cost >= approved_budget_usd


def _attempt_count(
    preflight_results: list[GeneratedTraceResult],
    determinism_results: list[GeneratedTraceResult],
) -> int:
    return len(preflight_results) + len(determinism_results)


def _load_required_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"required manifest does not exist: {path}")
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
