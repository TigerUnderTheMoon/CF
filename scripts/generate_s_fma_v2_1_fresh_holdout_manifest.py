"""Generate s_FMA_v2.1 manifest-only artifacts and non-API audits."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_holdout import row_overlap_keys
from fma.real_task_pilot.fresh_holdout_v2_1 import (
    build_v2_1_api_preflight_approval_request,
    build_v2_1_contract_audit,
    build_v2_1_fresh_holdout_manifest,
    write_v2_1_outputs,
)


TASK_SOURCE_PATHS = {
    "gsm8k": Path("data/real_task_pilot/gsm8k_test.jsonl"),
    "hotpotqa": Path("data/real_task_pilot/hotpotqa_validation.jsonl"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate planned-only s_FMA_v2.1 fresh manifest and non-API audits."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_1_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    _assert_current_task_boundary(config)

    prompt_file = args.prompt_file or Path(
        config.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        )
    )
    prompt_text = prompt_file.read_text(encoding="utf-8")
    prompt_version = _prompt_version(prompt_file)

    configured_tasks = config.get("fresh_selection_policy", {}).get("tasks", {})
    source_rows = {
        task_type: load_records(path)
        for task_type, path in TASK_SOURCE_PATHS.items()
        if task_type in configured_tasks
    }
    overlap_source_paths = _overlap_source_paths(config)
    overlap_sources = {
        source: _load_overlap_source_records(Path(source))
        for source in overlap_source_paths
    }

    manifest, manifest_audit = build_v2_1_fresh_holdout_manifest(
        source_rows,
        config=config,
        overlap_sources=overlap_sources,
        prompt_version=prompt_version,
    )
    manifest_audit["config_path"] = str(args.config)
    manifest_audit["plan_file"] = str(config.get("experiment", {}).get("plan_file") or "")
    manifest_audit["prompt_file"] = str(prompt_file)
    manifest_audit["overlap_source_paths"] = overlap_source_paths

    plan_path = Path(config.get("experiment", {}).get("plan_file", ""))
    plan_text = plan_path.read_text(encoding="utf-8")
    contract_audit = build_v2_1_contract_audit(
        config=config,
        plan_text=plan_text,
        prompt_text=prompt_text,
        prompt_version=prompt_version,
        manifest_audit=manifest_audit,
    )
    contract_audit["config_path"] = str(args.config)
    contract_audit["plan_file"] = str(plan_path)
    contract_audit["prompt_file"] = str(prompt_file)

    output_root = Path(config.get("experiment", {}).get("output_dir", "outputs/s_fma_v2_1_fresh_holdout"))
    approval_request = build_v2_1_api_preflight_approval_request(
        config=config,
        manifest_audit=manifest_audit,
        contract_audit=contract_audit,
        prompt_version=prompt_version,
        output_root=output_root,
    )
    write_v2_1_outputs(
        manifest=manifest,
        manifest_audit=manifest_audit,
        contract_audit=contract_audit,
        approval_request=approval_request,
        output_root=output_root,
    )
    print(
        json.dumps(
            {
                "approval_status": approval_request["approval_status"],
                "audit_status": manifest_audit["status"],
                "contract_status": contract_audit["status"],
                "manifest_rows": len(manifest),
                "output_root": str(output_root),
                "prompt_version": prompt_version,
            },
            sort_keys=True,
        )
    )


def _assert_current_task_boundary(config: dict[str, Any]) -> None:
    experiment = config.get("experiment", {})
    required_true = (
        "no_api_execution_without_user_approval",
        "no_api_run_in_current_task",
        "no_full_api_generation_in_current_task",
        "no_v2_scoring_in_current_task",
        "no_replay_in_current_task",
    )
    for key in required_true:
        if experiment.get(key) is not True:
            raise RuntimeError(f"config must keep {key}=true")
    if experiment.get("user_approved_budget_usd") is not None:
        raise RuntimeError("config must keep user_approved_budget_usd unset for this non-API task")
    if experiment.get("current_task_scope") != "evidence_target_revision_non_api":
        raise RuntimeError("config current_task_scope must be evidence_target_revision_non_api")
    if config.get("smoke_gate", {}).get("api_authorized_by_this_config") is not False:
        raise RuntimeError("smoke_gate.api_authorized_by_this_config must be false")
    if config.get("future_execution_boundary", {}).get("api_calls_authorized") is not False:
        raise RuntimeError("future_execution_boundary.api_calls_authorized must be false")
    current_status = set(config.get("claim_policy", {}).get("current_status_must_remain", []))
    required_status = {
        "PILOT_BLOCKED",
        "v2_1_planned_only",
        "no_api_authorized",
        "no_v2_1_validation",
        "no_prm_claim",
    }
    missing = sorted(required_status - current_status)
    if missing:
        raise RuntimeError("claim_policy.current_status_must_remain missing: " + ", ".join(missing))


def _overlap_source_paths(config: dict[str, Any]) -> list[str]:
    frozen = config.get("frozen_boundary", {}).get("exclude_from_final_validation", {})
    paths: list[str] = []
    for value in frozen.values():
        if isinstance(value, list):
            paths.extend(str(path) for path in value)
    return sorted(dict.fromkeys(paths))


def _load_overlap_source_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        return load_records(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return _extract_overlap_records(payload)
    return []


def _extract_overlap_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if row_overlap_keys(value):
            records.append(dict(value))
        for child in value.values():
            records.extend(_extract_overlap_records(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_extract_overlap_records(child))
    return records


def _prompt_version(path: Path) -> str:
    return "prompt-sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
