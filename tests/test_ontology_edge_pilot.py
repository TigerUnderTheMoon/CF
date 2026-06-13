from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fma.graph.ontology_edge_pilot import (
    DEFAULT_FIXTURE_TRACES,
    build_ontology_edge_graph,
    run_ontology_edge_pilot,
)
from fma.graph.reflection_graph import SUPPORTED_EDGE_TYPES


def test_ontology_edge_graph_uses_supported_functional_edge_types() -> None:
    graph, ontology_edges = build_ontology_edge_graph(DEFAULT_FIXTURE_TRACES[0])

    assert ontology_edges
    assert any(edge["ontology_relation"] == "same_constraint" for edge in ontology_edges)
    assert all(edge["edge_type"] in SUPPORTED_EDGE_TYPES for edge in ontology_edges)
    assert {"is_a", "part_of"}.isdisjoint({edge.edge_type for edge in graph.sorted_edges()})
    assert graph.topological_order()


def test_ontology_pilot_report_is_diagnostic_and_writes_artifacts(tmp_path: Path) -> None:
    output_json = tmp_path / "diagnostic_report.json"
    output_md = tmp_path / "diagnostic_report.md"

    report = run_ontology_edge_pilot(output_json=output_json, output_md=output_md)

    assert report["evidence_level"] == "diagnostic"
    assert report["validated_kbs_workflow"] is False
    assert report["summary"]["num_traces"] == len(DEFAULT_FIXTURE_TRACES)
    assert report["summary"]["ontology_added_edge_count"] > 0
    assert report["comparison"]["all_ontology_graphs_are_dags"] is True
    assert report["comparison"]["mean_abs_structural_necessity_delta"] >= 0.0
    assert output_json.exists()
    assert output_md.exists()
    markdown = output_md.read_text(encoding="utf-8")
    assert "not a deployed KBS validation" in markdown
    assert "validated_kbs_workflow: false" in markdown


def test_ontology_pilot_module_cli_writes_artifacts(tmp_path: Path) -> None:
    output_json = tmp_path / "diagnostic_report.json"
    output_md = tmp_path / "diagnostic_report.md"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path.cwd() / "src")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "fma.graph.ontology_edge_pilot",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        cwd=Path.cwd(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_json.exists()
    assert output_md.exists()
