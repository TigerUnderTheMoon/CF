"""Generate s_FMA_v2 fresh-holdout manifest and hard overlap audit."""

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
from fma.real_task_pilot.fresh_holdout import (
    build_fresh_holdout_manifest,
    write_fresh_manifest_outputs,
)


REQUIRED_CURRENT_PILOT_SOURCES = (
    "outputs/real_task_pilot/sample_manifest.json",
    "outputs/real_task_pilot/pilot_traces.jsonl",
    "outputs/real_task_pilot/real_task_delta_u.jsonl",
    "outputs/real_task_pilot/real_task_replay_results.jsonl",
    "outputs/real_task_pilot/structurally_calibrated_fma_scores.jsonl",
)

TASK_SOURCE_PATHS = {
    "gsm8k": Path("data/real_task_pilot/gsm8k_test.jsonl"),
    "hotpotqa": Path("data/real_task_pilot/hotpotqa_validation.jsonl"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the planned-only s_FMA_v2 fresh manifest and overlap audit."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=Path("prompts") / "real_task_reflection_generation.txt",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    _assert_current_task_boundary(config)

    source_rows = {
        task_type: load_records(path)
        for task_type, path in TASK_SOURCE_PATHS.items()
        if task_type in config.get("fresh_holdout", {}).get("tasks", {})
    }
    current_pilot_source_paths = _current_pilot_sources(config)
    current_pilot_sources = {
        source: load_records(source)
        for source in current_pilot_source_paths
    }
    prompt_version = _prompt_version(args.prompt_file)
    manifest, audit = build_fresh_holdout_manifest(
        source_rows,
        config=config,
        current_pilot_sources=current_pilot_sources,
        prompt_version=prompt_version,
    )
    audit["config_path"] = str(args.config)
    audit["plan_file"] = str(config.get("experiment", {}).get("plan_file") or "")
    audit["prompt_file"] = str(args.prompt_file)
    audit["current_pilot_sources_required_by_task"] = list(REQUIRED_CURRENT_PILOT_SOURCES)
    audit["config_current_pilot_overlap_sources"] = list(
        config.get("fresh_holdout", {}).get("current_pilot_overlap_sources", [])
    )

    output_root = Path(config.get("fresh_holdout", {}).get("output_root", "outputs/s_fma_v2_fresh_holdout"))
    manifest_path = Path(config.get("fresh_holdout", {}).get("manifest_path", output_root / "fresh_manifest.json"))
    audit_json_path = output_root / "manifest_overlap_audit.json"
    audit_markdown_path = output_root / "manifest_overlap_audit.md"
    write_fresh_manifest_outputs(
        manifest,
        audit,
        manifest_path=manifest_path,
        audit_json_path=audit_json_path,
        audit_markdown_path=audit_markdown_path,
    )
    print(json.dumps({"manifest_rows": len(manifest), "audit_status": audit["status"]}, sort_keys=True))


def _assert_current_task_boundary(config: dict[str, Any]) -> None:
    experiment = config.get("experiment", {})
    if not experiment.get("no_api_execution_without_user_approval", False):
        raise RuntimeError("config must keep no_api_execution_without_user_approval enabled")
    if experiment.get("no_manifest_generation_in_current_task", False):
        raise RuntimeError("config disallows manifest generation for the current task")
    if config.get("claim_policy", {}).get("C_S_FMA_V2_FRESH_HOLDOUT") != "planned":
        raise RuntimeError("s_FMA_v2 fresh holdout must remain planned-only for this step")


def _current_pilot_sources(config: dict[str, Any]) -> list[str]:
    configured = list(config.get("fresh_holdout", {}).get("current_pilot_overlap_sources", []))
    missing = [source for source in REQUIRED_CURRENT_PILOT_SOURCES if source not in configured]
    if missing:
        raise RuntimeError("config is missing required current-pilot overlap sources: " + ", ".join(missing))
    return configured


def _prompt_version(path: Path) -> str:
    payload = path.read_bytes()
    return "prompt-sha256:" + hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    main()
