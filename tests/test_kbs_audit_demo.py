"""Tests for scripts/run_kbs_audit_demo.py — G1 (zero API calls) and structural checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "kbs_audit_demo"
REPORT_PATH = OUTPUT_DIR / "audit_demo_report.json"
SUMMARY_PATH = OUTPUT_DIR / "audit_demo_summary.md"
FROZEN_DIR = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash"

REQUIRED_FIELDS = {
    "scenario",
    "methods",
    "config",
    "evidence_level",
    "validated_kbs_workflow",
}

REQUIRED_METHODS = {"w_struct", "scfma_ridge", "raw_local_utility", "random"}
REQUIRED_METRICS = {"top1_hit", "mass25", "ndcg25"}


def _run_script() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "run_kbs_audit_demo.py")],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=120,
    )
    combined = result.stdout + result.stderr
    return result.returncode


def test_script_produces_valid_json_with_all_required_fields():
    """Run the KBS audit demo script and verify the report JSON is well-formed
    with every required field."""
    returncode = _run_script()
    assert returncode == 0, f"Script exited with code {returncode}"

    assert REPORT_PATH.exists(), f"{REPORT_PATH} was not created"
    assert SUMMARY_PATH.exists(), f"{SUMMARY_PATH} was not created"

    report = _load_report(REPORT_PATH)

    # -- required top-level fields ---------------------------------------
    missing = REQUIRED_FIELDS - set(report.keys())
    assert not missing, f"Missing top-level fields: {sorted(missing)}"

    # -- scenario --------------------------------------------------------
    assert isinstance(report["scenario"], str) and len(report["scenario"]) > 50, (
        "scenario should be a non-trivial string"
    )

    # -- methods ----------------------------------------------------------
    methods = report["methods"]
    assert isinstance(methods, dict), "methods must be a dict"
    missing_methods = REQUIRED_METHODS - set(methods.keys())
    assert not missing_methods, f"Missing methods: {sorted(missing_methods)}"

    for method_name, metrics in methods.items():
        assert isinstance(metrics, dict), f"{method_name} value must be a dict"
        for key in REQUIRED_METRICS:
            assert key in metrics, f"{method_name} missing metric '{key}'"
            assert isinstance(metrics[key], (int, float)), (
                f"{method_name}.{key} must be numeric"
            )

    # -- config -----------------------------------------------------------
    config = report["config"]
    assert isinstance(config, dict), "config must be a dict"
    assert config.get("review_budget_fraction") == 0.25
    assert config.get("locked_samples", 0) > 0
    assert config.get("total_steps", 0) > 0

    # -- evidence_level ---------------------------------------------------
    assert report["evidence_level"] == "demonstration", (
        f"evidence_level should be 'demonstration', got {report['evidence_level']!r}"
    )

    # -- validated_kbs_workflow -------------------------------------------
    assert report["validated_kbs_workflow"] is False, (
        "validated_kbs_workflow must be False"
    )


def test_zero_api_calls_no_frozen_files_modified():
    """Record mtimes of all frozen v3.6 files, run the script, then verify
    no existing files under the frozen directory were modified.

    This is the G1 gate: zero API calls, zero mutation of locked artifacts.
    """
    # 1. snapshot mtimes
    mtimes_before = _snapshot_mtimes(FROZEN_DIR)
    assert mtimes_before, f"No files found under {FROZEN_DIR}"

    # 2. run the script
    returncode = _run_script()
    assert returncode == 0, f"Script exited with code {returncode}"

    # 3. snapshot mtimes after
    mtimes_after = _snapshot_mtimes(FROZEN_DIR)

    # 4. verify no existing files changed
    modified: list[str] = []
    for rel_path, mtime_before in mtimes_before.items():
        mtime_after = mtimes_after.get(rel_path)
        if mtime_after is None:
            # File was deleted — should not happen
            modified.append(f"{rel_path} (DELETED)")
        elif mtime_after != mtime_before:
            modified.append(f"{rel_path} (mtime {mtime_before} → {mtime_after})")

    # Also check no new files appeared
    new_files = set(mtimes_after.keys()) - set(mtimes_before.keys())
    if new_files:
        modified.extend(f"{f} (NEW)" for f in sorted(new_files))

    assert not modified, (
        f"Frozen v3.6 files were modified or created — G1 violation:\n"
        + "\n".join(f"  - {entry}" for entry in modified)
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _load_report(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise TypeError(f"Expected JSON object in {path}")
    return payload


def _snapshot_mtimes(root: Path) -> dict[str, float]:
    """Return {relative_path: mtime_float} for all files under *root*."""
    if not root.is_dir():
        return {}
    snapshot: dict[str, float] = {}
    for entry in root.rglob("*"):
        if entry.is_file():
            rel = str(entry.relative_to(root))
            snapshot[rel] = entry.stat().st_mtime
    return snapshot
