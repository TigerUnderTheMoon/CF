from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABEL_SCRIPT = ROOT / "scripts" / "run_countries_kg_label_validation.py"
AUDIT_SCRIPT = ROOT / "scripts" / "run_jiis_audit_case.py"


def _run_label_validation(tmp_path: Path) -> Path:
    output_dir = tmp_path / "labels"
    result = subprocess.run(
        [
            sys.executable,
            str(LABEL_SCRIPT),
            "--output-dir",
            str(output_dir),
            "--seed",
            "20260711",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    cache_path = output_dir / "countries_kg_labels_cached.json"
    assert cache_path.exists()
    return cache_path


def test_jiis_audit_case_uses_cached_labels_and_impact_coverage(tmp_path: Path) -> None:
    cache_path = _run_label_validation(tmp_path)
    output_dir = tmp_path / "audit_case"

    result = subprocess.run(
        [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--n-traces",
            "600",
            "--seed",
            "20260711",
            "--budget",
            "0.25",
            "--label-cache",
            str(cache_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads((output_dir / "jiis_audit_case_report.json").read_text(encoding="utf-8"))
    assert report["label_cache"]["path"] == str(cache_path)
    assert report["label_cache"]["recomputed_label_count"] == 0
    assert report["table_2_title"].startswith("Impact Coverage@K")
    assert report["metrics"]["impact_coverage_at_k"]["mean"] >= 0.0
    assert report["metrics"]["average_path_length_to_covered_descendants"]["mean"] >= 0.0
    assert report["metrics"]["early_truncation_rate"]["mean"] >= 0.0
    assert report["baselines"]["flat_top_k"]["score_source"] == "raw_risk_score"
    assert report["baselines"]["random_stratified"]["score_source"] == "shuffled_structural_labels"
    assert report["baselines"]["no_fallback_ablation"]["enabled"] is True
    assert report["policy"]["name"] == "Life-Saving First"
    assert report["policy"]["layers"] == [
        "Critical Bottleneck",
        "Unique Evidence",
        "Redundancy Group Samples",
        "Fallback",
    ]
    assert report["policy"]["raw_risk_score_role"] == "tie_breaker_only_within_layer"
    assert report["metrics"]["impact_coverage_at_k"]["definition"] == "reachable_descendants_transitive_closure"

    trace = report["trace_reports"][0]
    assert trace["selection"]["overflow_stopped_within_layer"] in {True, False}
    assert "selected_layers" in trace["selection"]
    assert "critical_bottleneck" in trace["selection"]["selected_layers"]
    assert "random_stratified" in trace["metrics"]
