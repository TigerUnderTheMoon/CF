"""Run s_FMA_v2 fresh-holdout API preflight-only."""

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
from fma.real_task_pilot._archived.fresh_preflight import (
    FreshPreflightError,
    attempt_payloads_from_results,
    build_budget_blocked_report,
    select_preflight_records,
    summarize_fresh_preflight,
    validate_preflight_readiness,
)
from fma.real_task_pilot.generation import (
    GeneratedTraceResult,
    generate_trace_with_fallback,
    load_prompt_template,
)
from fma.real_task_pilot.openai_client import OpenAIResponsesAdapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded API preflight-only for the s_FMA_v2 fresh holdout."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-api-preflight-only",
        action="store_true",
        help="Required explicit guard for the small fresh-holdout API preflight.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    output_root = Path(
        config.get("fresh_holdout", {}).get("output_root", "outputs/s_fma_v2_fresh_holdout")
    )
    manifest_path = Path(
        config.get("fresh_holdout", {}).get("manifest_path", output_root / "fresh_manifest.json")
    )
    audit_path = output_root / "manifest_overlap_audit.json"
    plan_path = Path(config.get("experiment", {}).get("plan_file", "paper/s_fma_v2_fresh_holdout_plan.md"))
    report_path = output_root / "api_preflight_report.json"
    traces_path = output_root / "api_preflight_traces.jsonl"
    attempts_path = output_root / "api_preflight_attempts.jsonl"

    manifest = _load_required_records(manifest_path)
    audit = _load_required_json(audit_path)
    plan_text = _load_required_text(plan_path)
    readiness = validate_preflight_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=audit,
        plan_text=plan_text,
        allow_api_preflight_only=args.allow_api_preflight_only,
    )
    api_preflight = config.get("api_preflight", {})
    selected = select_preflight_records(
        manifest,
        samples_per_task=int(api_preflight.get("samples_per_task", 10)),
        task_order=list(config.get("fresh_holdout", {}).get("tasks", {}).keys()),
    )

    if not readiness["api_call_allowed"]:
        write_records([], traces_path)
        write_records([], attempts_path)
        report = build_budget_blocked_report(
            config=config,
            selected_records=selected,
            readiness=readiness,
        )
        _write_json(report_path, report)
        _write_optional_cost_log(output_root, report)
        print(json.dumps({"status": report["status"], "records_evaluated": 0}, sort_keys=True))
        return

    adapter = OpenAIResponsesAdapter()
    prompt_template = load_prompt_template(config["generation"]["prompt_file"])
    preflight_results: list[GeneratedTraceResult] = []
    for sample in selected:
        preflight_results.append(
            generate_trace_with_fallback(
                sample,
                adapter=adapter,
                config=config,
                prompt_template=prompt_template,
            )
        )
        _write_live_checkpoint(
            traces_path=traces_path,
            attempts_path=attempts_path,
            preflight_results=preflight_results,
            determinism_results=[],
        )

    determinism_results: list[GeneratedTraceResult] = []
    drift_repeats = int(api_preflight.get("determinism_probe_repeats", 0) or 0)
    if selected and drift_repeats > 0:
        probe_sample = selected[0]
        for _index in range(drift_repeats):
            determinism_results.append(
                generate_trace_with_fallback(
                    probe_sample,
                    adapter=adapter,
                    config=config,
                    prompt_template=prompt_template,
                )
            )
            _write_live_checkpoint(
                traces_path=traces_path,
                attempts_path=attempts_path,
                preflight_results=preflight_results,
                determinism_results=determinism_results,
            )

    preflight_attempts = attempt_payloads_from_results(preflight_results, role="preflight_record")
    determinism_attempts = attempt_payloads_from_results(
        determinism_results,
        role="determinism_probe",
    )
    drift_outputs = [
        str(result.record.get("observable_trace"))
        if result.record is not None
        else result.raw_output
        for result in determinism_results
    ]
    report = summarize_fresh_preflight(
        preflight_attempts,
        selected_records=selected,
        drift_outputs=drift_outputs,
        config=config,
        cost_attempts=preflight_attempts + determinism_attempts,
    )
    _write_json(report_path, report)
    _write_optional_cost_log(output_root, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "records_evaluated": report["records_evaluated"],
                "api_attempts": report["api_attempts"],
            },
            sort_keys=True,
        )
    )


def _write_live_checkpoint(
    *,
    traces_path: Path,
    attempts_path: Path,
    preflight_results: list[GeneratedTraceResult],
    determinism_results: list[GeneratedTraceResult],
) -> None:
    valid_records = [result.record for result in preflight_results if result.record is not None]
    attempts = attempt_payloads_from_results(preflight_results, role="preflight_record")
    attempts.extend(
        attempt_payloads_from_results(determinism_results, role="determinism_probe")
    )
    write_records(valid_records, traces_path)
    write_records(attempts, attempts_path)


def _load_required_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FreshPreflightError(f"required manifest does not exist: {path}")
    return load_records(path)


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FreshPreflightError(f"required JSON does not exist: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FreshPreflightError(f"{path} must contain a JSON object.")
    return value


def _load_required_text(path: Path) -> str:
    if not path.exists():
        raise FreshPreflightError(f"required plan file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_optional_cost_log(output_root: Path, report: dict[str, Any]) -> None:
    log_dir = output_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _write_json(log_dir / "api_preflight_cost_report.json", report.get("cost_report", {}))


if __name__ == "__main__":
    main()
