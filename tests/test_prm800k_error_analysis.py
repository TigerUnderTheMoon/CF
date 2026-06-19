"""Contracts for the PRM800K error case analysis script."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "analyze_prm800k_error_cases.py"
FROZEN_DIR = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash"


def test_script_runs_and_produces_json(tmp_path: Path) -> None:
    """Fixture-mode run produces JSON with expected top-level fields."""
    output_dir = tmp_path / "error_case_output"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--fixture",
            "--fixture-size",
            "100",
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, (
        f"Script failed (rc={result.returncode}):\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
    )

    json_path = output_dir / "error_case_analysis.json"
    assert json_path.exists(), f"Expected output not found: {json_path}"

    data = json.loads(json_path.read_text(encoding="utf-8"))
    expected_fields = {
        "stratified_summary",
        "variant_comparison",
        "case_studies",
    }
    missing = expected_fields - set(data)
    assert not missing, f"Missing expected fields: {missing}"

    # Validate sub-structure
    assert isinstance(data["stratified_summary"], dict)
    assert "strata" in data["stratified_summary"]
    assert "overall" in data["stratified_summary"]

    assert isinstance(data["variant_comparison"], dict)

    assert isinstance(data["case_studies"], list)
    assert len(data["case_studies"]) == 3, (
        f"Expected 3 case studies, got {len(data['case_studies'])}"
    )

    # Verify at least one case study has step-level data
    has_step_data = any(
        isinstance(cs, dict) and "step_level" in cs
        for cs in data["case_studies"]
    )
    assert has_step_data, "No case study has step-level data"

    # Verify markdown output exists
    md_path = output_dir / "error_case_analysis.md"
    assert md_path.exists(), f"Expected markdown not found: {md_path}"
    md_content = md_path.read_text(encoding="utf-8")
    assert "Concrete Finding" in md_content
    assert "Stratified Error Analysis" in md_content
    assert "Variant Behavior Comparison" in md_content
    assert "Case Studies" in md_content


def test_zero_api_calls_frozen_artifacts_untouched(tmp_path: Path) -> None:
    """Fixture-mode run leaves frozen artifacts unchanged — no API calls."""
    # Record mtimes of all files in the frozen artifact dir BEFORE the run
    pre_mtimes: dict[str, float] = {}
    if FROZEN_DIR.exists():
        for root, _dirs, files in os.walk(str(FROZEN_DIR)):
            for fname in files:
                fpath = os.path.join(root, fname)
                pre_mtimes[fpath] = os.path.getmtime(fpath)

    output_dir = tmp_path / "zero_api_output"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--fixture",
            "--fixture-size",
            "50",
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, (
        f"Script failed (rc={result.returncode}):\nSTDERR:\n{result.stderr}"
    )

    # Verify that all previously existing files in frozen artifact dir are unchanged
    modified: list[str] = []
    missing: list[str] = []
    for fpath, old_mtime in pre_mtimes.items():
        if not os.path.exists(fpath):
            missing.append(fpath)
        else:
            new_mtime = os.path.getmtime(fpath)
            if abs(new_mtime - old_mtime) > 0.001:
                modified.append(
                    f"{fpath} (old={old_mtime}, new={new_mtime})"
                )

    assert not missing, (
        f"Frozen artifact files went missing: {missing}"
    )
    assert not modified, (
        f"Frozen artifact files were modified — API call detected? {modified}"
    )

    # Verify output was produced in tmp_path (not frozen dir)
    json_path = output_dir / "error_case_analysis.json"
    assert json_path.exists(), f"Output JSON not found: {json_path}"

    # Confirm script did NOT produce output in the frozen artifacts directory
    frozen_json = FROZEN_DIR / "error_case_analysis.json"
    frozen_md = FROZEN_DIR / "error_case_analysis.md"
    assert not frozen_json.exists(), (
        f"Script wrote to frozen dir: {frozen_json}"
    )
    assert not frozen_md.exists(), (
        f"Script wrote to frozen dir: {frozen_md}"
    )

    # Smoke-check JSON content
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data.get("n_samples", 0) > 0, "Zero samples analyzed"
