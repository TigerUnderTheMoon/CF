from __future__ import annotations

from pathlib import Path

from fma.graph.kg_ontology_pilot import run_kg_pilot


def test_kg_ontology_pilot_uses_real_kg_structure_and_remains_bounded(
    tmp_path: Path,
) -> None:
    output_json = tmp_path / "kg_pilot_report.json"

    report = run_kg_pilot(num_traces=9, seed=42, output_json=output_json)

    assert report["evidence_level"] == "pilot"
    assert report["validated_kbs_workflow"] is False
    assert report["uses_real_ontology"] is True
    assert report["kg_metadata"]["num_entities"] == 30
    assert report["kg_metadata"]["num_triples"] == 189
    assert report["summary"]["kg_added_edge_count"] > 0
    assert report["comparison"]["all_kg_graphs_are_dags"] is True
    assert "not a deployed KBS validation" in report["claim_boundary"]
    assert output_json.exists()
