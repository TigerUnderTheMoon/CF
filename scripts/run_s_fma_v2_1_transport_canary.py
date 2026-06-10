"""Run s_FMA_v2.1 TRANSPORT_CANARY_ONLY with explicit budget/request guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.archive_paths import v2_1_failed_provenance_root
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_preflight import (
    attempt_payloads_from_results,
    select_preflight_records,
)
from fma.real_task_pilot.fresh_preflight_v2_1 import estimate_attempt_cost_usd
from fma.real_task_pilot.fresh_transport_canary import (
    TransportCanaryError,
    build_transport_canary_generation_config,
    build_transport_canary_report,
    transport_canary_paths,
    validate_transport_canary_readiness,
)
from fma.real_task_pilot.generation import (
    GeneratedTraceResult,
    load_prompt_template,
)
from scripts.run_s_fma_v2_1_fresh_holdout_preflight import (
    SingleRequestOpenAITraceAdapter,
    generate_trace_once,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded transport/output-extraction canary for s_FMA_v2.1."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_1_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-transport-canary-only",
        action="store_true",
        help="Required explicit guard for the v2.1 transport canary.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="User-approved hard budget ceiling; must be 0.5 for this canary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    output_root = v2_1_failed_provenance_root(
        Path(
            config.get("experiment", {}).get(
                "output_dir", "outputs/s_fma_v2_1_fresh_holdout"
            )
        )
    )
    paths = {
        "manifest": output_root / "fresh_manifest.json",
        "overlap": output_root / "manifest_overlap_audit.json",
        "contract": output_root / "v2_1_contract_audit.json",
        "approval": output_root / "api_preflight_approval_request.json",
        "empty_audit": output_root / "api_preflight_empty_output_failure_audit.json",
        "readiness": Path("outputs") / "real_task_pilot" / "readiness_audit.json",
        **transport_canary_paths(output_root),
    }

    manifest = _load_required_records(paths["manifest"])
    overlap_audit = _load_required_json(paths["overlap"])
    contract_audit = _load_required_json(paths["contract"])
    approval_request = _load_required_json(paths["approval"])
    empty_audit = _load_required_json(paths["empty_audit"])
    current_readiness = _load_required_json(paths["readiness"])
    prompt_file = Path(
        config.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        )
    )
    current_prompt_version = _prompt_version(prompt_file)

    readiness = validate_transport_canary_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=overlap_audit,
        contract_audit=contract_audit,
        approval_request=approval_request,
        empty_output_failure_audit=empty_audit,
        current_readiness=current_readiness,
        allow_transport_canary_only=args.allow_transport_canary_only,
        approved_budget_usd=args.approved_budget_usd,
        current_prompt_version=current_prompt_version,
    )
    selected = select_preflight_records(
        manifest,
        samples_per_task=1,
        task_order=["gsm8k", "hotpotqa"],
    )
    live_config = build_transport_canary_generation_config(config, readiness=readiness)
    prompt_template = load_prompt_template(live_config["generation"]["prompt_file"])
    adapter = SingleRequestOpenAITraceAdapter()

    results: list[GeneratedTraceResult] = []
    budget_stop_triggered = False
    request_stop_triggered = False

    for sample in selected:
        if len(results) >= int(readiness["max_api_requests"]):
            request_stop_triggered = True
            break
        results.append(
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
            results=results,
        )
        if _budget_reached(
            results=results,
            selected_records=selected,
            config=live_config,
            approved_budget_usd=float(readiness["approved_budget_usd"]),
        ):
            budget_stop_triggered = True
            break

    attempts = attempt_payloads_from_results(
        results,
        role="transport_canary_record",
        samples=selected,
    )
    report = build_transport_canary_report(
        attempts,
        selected_records=selected,
        config=live_config,
        readiness=readiness,
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
                "api_attempts": report["api_attempts"],
                "cost_used_usd": report.get("cost_used_usd"),
                "raw_output_nonempty_count": report.get("raw_output_nonempty_count"),
                "json_parse_success_count": report.get("json_parse_success_count"),
            },
            sort_keys=True,
        )
    )


def _write_live_checkpoint(
    *,
    traces_path: Path,
    attempts_path: Path,
    selected_records: list[dict[str, Any]],
    results: list[GeneratedTraceResult],
) -> None:
    valid_records = [result.record for result in results if result.record is not None]
    attempts = attempt_payloads_from_results(
        results,
        role="transport_canary_record",
        samples=selected_records,
    )
    write_records(valid_records, traces_path)
    write_records(attempts, attempts_path)


def _budget_reached(
    *,
    results: list[GeneratedTraceResult],
    selected_records: list[dict[str, Any]],
    config: Mapping[str, Any],
    approved_budget_usd: float,
) -> bool:
    attempts = attempt_payloads_from_results(
        results,
        role="transport_canary_record",
        samples=selected_records,
    )
    cost = estimate_attempt_cost_usd(attempts, config=config)
    return cost is not None and cost >= approved_budget_usd


def _prompt_version(path: Path) -> str:
    return "prompt-sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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
