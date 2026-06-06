from __future__ import annotations

import json
from pathlib import Path

from fma.eval.structural_attribution import compute_node_necessity
from fma.graph.build_reflection_graph import build_reflection_graphs


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "reflection_traces_subset_10.jsonl"


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_fixture_subset_builds_graphs_and_structural_scores_without_api() -> None:
    traces = load_jsonl(FIXTURE_PATH)
    phase5_scores = [
        {
            "trace_id": trace["trace_id"],
            "step_idx": 0,
            "attribution_score": 0.6,
            "necessity_normalized": 1.0,
        }
        for trace in traces
    ]

    graphs = build_reflection_graphs(traces, phase5_scores)
    node_scores = [
        score
        for graph in graphs
        for score in compute_node_necessity(graph)
    ]

    assert len(traces) == 10
    assert len(graphs) == 10
    assert len(node_scores) == 10
    assert {score.removal_mode for score in node_scores} == {"PRUNE"}
    assert all(score.necessity == 1.0 for score in node_scores)
