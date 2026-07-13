from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_countries_kg_label_validation.py"


def test_countries_kg_label_validation_writes_cache_and_scalability_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "countries_kg_label_validation"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
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

    report_path = output_dir / "countries_kg_label_validation_report.json"
    cache_path = output_dir / "countries_kg_labels_cached.json"
    assert report_path.exists()
    assert cache_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    cache = json.loads(cache_path.read_text(encoding="utf-8"))

    assert report["seed"] == 20260711
    assert report["kg_metadata"]["num_entities"] == 30
    assert report["kg_metadata"]["num_triples"] == 189
    assert report["thresholds"]["redundancy_jaccard"] == 0.85
    assert report["baseline_names"]["tfidf"] == "Semantic-Similarity Baseline (TF-IDF)"
    assert report["baseline_names"]["betweenness"] == "Betweenness Centrality"
    assert report["baseline_names"]["out_closeness"] == "Directed Out-Closeness Centrality"
    assert report["countries_kg"]["redundancy_positive_count"] >= 5
    assert report["countries_kg"]["limited_redundancy_positive_warning"] is False
    assert report["countries_kg"]["bottleneck_f1"] >= 0.8
    assert report["countries_kg"]["redundancy_f1"] >= 0.8
    assert math.isfinite(report["countries_kg"]["tfidf_bottleneck_f1"])
    assert math.isfinite(report["countries_kg"]["tfidf_redundancy_f1"])
    assert math.isfinite(report["countries_kg"]["betweenness_bottleneck_f1"])
    assert math.isfinite(report["countries_kg"]["out_closeness_bottleneck_f1"])

    assert report["synthetic_scalability"]["sizes"] == [100, 200, 500, 1000, 5000]
    for size in ("100", "200", "500", "1000", "5000"):
        row = report["synthetic_scalability"]["runs"][size]
        assert math.isfinite(row["bottleneck_f1"])
        assert math.isfinite(row["redundancy_f1"])
        assert math.isfinite(row["average_path_length_to_covered_descendants"])

    assert cache["seed"] == 20260711
    assert cache["thresholds"]["redundancy_jaccard"] == 0.85
    assert "kg_metadata_hash" in cache
    assert cache["synthetic_dag"]["seed"] == 20260711
    assert cache["synthetic_dag"]["sizes"] == [100, 200, 500, 1000, 5000]

    first_trace = cache["traces"][0]
    first_node = first_trace["nodes"][0]
    assert {"trace_id", "node_id", "is_bottleneck", "is_redundant", "redundancy_group_id", "downstream_impact_count", "auditable", "betweenness_centrality", "out_closeness_centrality"} <= set(first_node)
