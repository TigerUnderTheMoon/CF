from __future__ import annotations

from fma.graph.kg_ontology_pilot import run_kg_pilot


def test_kg_pilot_produces_valid_report():
    report = run_kg_pilot()

    assert report["evidence_level"] == "pilot"
    assert report["uses_real_ontology"] is True
    assert report["validated_kbs_workflow"] is False
    assert report["trace_generation"]["num_traces"] == 30
    assert report["kg_metadata"]["num_entities"] > 0
    assert report["kg_metadata"]["num_triples"] > 0
    assert report["summary"]["num_traces"] == 30
    assert report["summary"]["kg_added_edge_count"] > 0
    assert 0.0 <= report["comparison"]["bottleneck_top1_overlap"] <= 1.0
    assert report["comparison"]["all_kg_graphs_are_dags"] is True


def test_kg_pilot_deterministic():
    r1 = run_kg_pilot(seed=42)
    r2 = run_kg_pilot(seed=42)
    assert r1["trace_generation"]["num_traces"] == r2["trace_generation"]["num_traces"]


def test_kg_pilot_ontology_edges():
    report = run_kg_pilot()
    assert report["summary"]["kg_added_edge_count"] > 0
    assert len(report.get("kg_edges_sample", [])) > 0


def test_kg_pilot_relation_types():
    report = run_kg_pilot()
    kg_rel_counts = report["summary"]["kg_relation_counts"]
    assert "depends_on_concept" in kg_rel_counts
    assert kg_rel_counts["depends_on_concept"] > 0


def test_kg_pilot_comparison_fields():
    report = run_kg_pilot()
    comp = report["comparison"]
    assert "mean_abs_structural_necessity_delta" in comp
    assert "structural_necessity_spearman" in comp
    assert "bottleneck_top1_overlap" in comp