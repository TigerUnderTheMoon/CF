"""Generate s_FMA_v2.2 manifest-only artifacts and non-overlap audits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot._archived.fresh_holdout import row_overlap_keys
from fma.real_task_pilot._archived.fresh_holdout_v2_2 import (
    S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT,
    build_v2_2_contract_audit,
    build_v2_2_fresh_holdout_manifest,
    write_v2_2_outputs,
)


TASK_SOURCE_PATHS = {
    "gsm8k": Path("data/real_task_pilot/gsm8k_test.jsonl"),
    "hotpotqa": Path("data/real_task_pilot/hotpotqa_validation.jsonl"),
}

DEFAULT_OVERLAP_SOURCE_PATHS = (
    "outputs/real_task_pilot/sample_manifest.json",
    "outputs/real_task_pilot/pilot_traces.jsonl",
    "outputs/real_task_pilot/real_task_delta_u.jsonl",
    "outputs/real_task_pilot/real_task_replay_results.jsonl",
    "outputs/real_task_pilot/structurally_calibrated_fma_scores.jsonl",
    "outputs/archive/s_fma_v2_fresh_holdout/fresh_manifest.json",
    "outputs/archive/s_fma_v2_fresh_holdout/api_preflight_traces.jsonl",
    "outputs/archive/s_fma_v2_fresh_holdout/stochastic_smoke_original_traces.jsonl",
    "outputs/archive/s_fma_v2_fresh_holdout/stochastic_smoke_replay_results.jsonl",
    "outputs/archive/s_fma_v2_1_fresh_holdout/fresh_manifest.json",
    "outputs/archive/s_fma_v2_1_fresh_holdout/api_preflight_traces.jsonl",
    "outputs/archive/s_fma_v2_1_fresh_holdout/stochastic_smoke_original_traces.jsonl",
    "outputs/archive/s_fma_v2_1_fresh_holdout/stochastic_smoke_replay_results.jsonl",
    "outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_original_traces.jsonl",
    "outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_replay_results.jsonl",
    "outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_original_traces.jsonl",
    "outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_replay_results.jsonl",
    "outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_delta_u.jsonl",
)

ALLOWED_OUTPUT_FILES = {
    "api_preflight_approval_request.json",
    "api_preflight_approval_request.md",
    "fresh_manifest.json",
    "manifest_overlap_audit.json",
    "manifest_overlap_audit.md",
    "v2_2_contract_audit.json",
    "v2_2_contract_audit.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate s_FMA_v2.2 fresh manifest and manifest-only audits."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_2_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--task-scope",
        default=S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    _assert_current_task_boundary(config, task_scope=args.task_scope)

    configured_tasks = config.get("fresh_split_policy", {}).get("tasks", {})
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

    manifest, manifest_audit = build_v2_2_fresh_holdout_manifest(
        source_rows,
        config=config,
        overlap_sources=overlap_sources,
    )
    manifest_audit["config_path"] = str(args.config)
    manifest_audit["plan_file"] = str(config.get("experiment", {}).get("plan_file") or "")
    manifest_audit["transition_audit_file"] = str(
        config.get("experiment", {}).get("transition_audit_file") or ""
    )
    manifest_audit["overlap_source_paths"] = overlap_source_paths

    plan_path = Path(config.get("experiment", {}).get("plan_file", ""))
    transition_path = Path(config.get("experiment", {}).get("transition_audit_file", ""))
    failure_audit_path = Path(
        config.get("provenance_boundary", {})
        .get("source_artifacts", {})
        .get("failure_audit_json", "")
    )
    plan_text = plan_path.read_text(encoding="utf-8")
    transition_text = transition_path.read_text(encoding="utf-8")
    failure_audit = json.loads(failure_audit_path.read_text(encoding="utf-8"))

    contract_audit = build_v2_2_contract_audit(
        config=config,
        preregistration_plan_text=plan_text,
        transition_audit_text=transition_text,
        failure_audit=failure_audit,
        manifest_audit=manifest_audit,
        task_scope=args.task_scope,
        current_submission_ready=_current_submission_ready(),
    )
    contract_audit["config_path"] = str(args.config)
    contract_audit["plan_file"] = str(plan_path)
    contract_audit["transition_audit_file"] = str(transition_path)
    contract_audit["failure_audit_file"] = str(failure_audit_path)

    output_root = Path(config.get("experiment", {}).get("output_dir", "outputs/s_fma_v2_2_fresh_holdout"))
    _assert_output_root_allowed(output_root)
    write_v2_2_outputs(
        manifest=manifest,
        manifest_audit=manifest_audit,
        contract_audit=contract_audit,
        output_root=output_root,
    )
    print(
        json.dumps(
            {
                "audit_status": manifest_audit["status"],
                "contract_status": contract_audit["status"],
                "manifest_rows": len(manifest),
                "output_root": str(output_root),
                "task_scope": args.task_scope,
            },
            sort_keys=True,
        )
    )


def _assert_current_task_boundary(
    config: dict[str, Any],
    *,
    task_scope: str,
) -> None:
    if task_scope != S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT:
        raise RuntimeError(
            "task_scope must be " + S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT
        )
    experiment = config.get("experiment", {})
    required_true = (
        "no_api_execution_without_user_approval",
        "no_api_run_in_current_task",
        "no_full_api_generation_in_current_task",
        "no_replay_in_current_task",
        "no_scoring_in_current_task",
        "no_prm_filtering_in_current_task",
    )
    for key in required_true:
        if experiment.get(key) is not True:
            raise RuntimeError(f"config must keep {key}=true")
    if experiment.get("user_approved_budget_usd") is not None:
        raise RuntimeError("config must keep user_approved_budget_usd unset for manifest-only task")
    future = config.get("future_execution_boundary", {})
    required_false = (
        "api_calls_authorized",
        "replay_authorized",
        "scoring_authorized",
        "prm_filtering_authorized",
    )
    for key in required_false:
        if future.get(key) is not False:
            raise RuntimeError(f"future_execution_boundary.{key} must be false")
    if config.get("provenance_boundary", {}).get("current_project_status") != "PILOT_BLOCKED":
        raise RuntimeError("provenance_boundary.current_project_status must remain PILOT_BLOCKED")


def _overlap_source_paths(config: dict[str, Any]) -> list[str]:
    source_artifacts = config.get("provenance_boundary", {}).get("source_artifacts", {})
    configured = [
        str(path)
        for path in source_artifacts.values()
        if isinstance(path, str) and Path(path).suffix.lower() in {".json", ".jsonl"}
    ]
    return sorted(dict.fromkeys([*DEFAULT_OVERLAP_SOURCE_PATHS, *configured]))


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


def _assert_output_root_allowed(output_root: Path) -> None:
    if not output_root.exists():
        return
    disallowed = [
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name not in ALLOWED_OUTPUT_FILES
    ]
    if disallowed:
        raise RuntimeError(
            "outputs/s_fma_v2_2_fresh_holdout contains disallowed files: "
            + ", ".join(str(path) for path in disallowed)
        )


def _current_submission_ready() -> bool:
    path = Path("paper/submission_readiness_audit.md")
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8").lower()
    blocked_markers = [
        "not submission-ready",
        "not submission ready",
        "pilot_blocked",
        "not ready for submission",
    ]
    ready_markers = [
        "submission-ready",
        "submission ready",
        "ready for submission",
    ]
    if any(marker in text for marker in blocked_markers):
        return False
    return any(marker in text for marker in ready_markers)


if __name__ == "__main__":
    main()
