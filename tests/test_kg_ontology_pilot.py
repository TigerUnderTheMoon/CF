from __future__ import annotations

from fma.graph import kg_ontology_pilot
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
    assert r1["summary"] == r2["summary"]


def test_location_query_neighbors_are_order_stable(monkeypatch):
    class FakeRng:
        def sample(self, countries, k):
            return ["alpha", "target"]

        def uniform(self, start, end):
            return start

    monkeypatch.setitem(kg_ontology_pilot._KG_NEIGHBOR_SET, "target", {"zeta", "beta", "alpha"})
    monkeypatch.setitem(kg_ontology_pilot._KG_LOCATED_IN, "target", "region")
    monkeypatch.setitem(kg_ontology_pilot._KG_LOCATED_IN, "zeta", "region")
    monkeypatch.setitem(kg_ontology_pilot._KG_LOCATED_IN, "beta", "region")
    monkeypatch.setitem(kg_ontology_pilot._KG_LOCATED_IN, "alpha", "region")

    trace = kg_ontology_pilot._generate_location_query_trace(
        "region",
        ["alpha", "target"],
        "trace_stable",
        FakeRng(),
    )

    neighbor_step = trace["reflection_chain"][-2]
    assert neighbor_step["concept_id"] == "alpha"
    assert "alpha, beta" in neighbor_step["text"]


def test_kg_pilot_ontology_edges():
    report = run_kg_pilot()
    assert report["summary"]["kg_added_edge_count"] > 0
    assert len(report.get("kg_edges_sample", [])) > 0


def test_kg_pilot_relation_types():
    report = run_kg_pilot()
    kg_rel_counts = report["summary"]["kg_relation_counts"]
    assert "depends_on_concept" in kg_rel_counts
    assert kg_rel_counts["depends_on_concept"] > 0


def test_kg_pilot_default_summary_is_stable():
    report = run_kg_pilot()
    assert report["summary"] == {
        "num_traces": 30,
        "baseline_edge_count": 310,
        "kg_graph_edge_count": 320,
        "kg_candidate_edge_count": 304,
        "kg_added_edge_count": 196,
        "kg_relation_counts": {
            "depends_on_concept": 211,
            "neighbor_concept": 8,
            "same_constraint": 85,
        },
        "functional_edge_type_counts": {
            "elaborates": 219,
            "verifies": 85,
        },
    }


def test_kg_pilot_comparison_fields():
    report = run_kg_pilot()
    comp = report["comparison"]
    assert "mean_abs_structural_necessity_delta" in comp
    assert "structural_necessity_spearman" in comp
    assert "bottleneck_top1_overlap" in comp
