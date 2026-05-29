from __future__ import annotations

import pytest

from fma.eval.structural_attribution import (
    compute_edge_necessity,
    compute_graph_utility,
    compute_node_necessity,
    compute_structural_faithfulness,
    compute_structural_influence,
    compute_structural_metrics,
)
from fma.graph.reflection_graph import ReflectionGraph, ReflectionNode


def node(node_id: str, step: int, utility: float, label: str = "VERIFICATION") -> ReflectionNode:
    return ReflectionNode(node_id, "t1", step, label, utility, 0.0, node_id)


def make_chain(utilities: tuple[float, float, float] = (0.0, 1.0, 1.0)) -> ReflectionGraph:
    graph = ReflectionGraph("t1")
    graph.add_node(node("a", 0, utilities[0], "DECOMPOSITION"))
    graph.add_node(node("b", 1, utilities[1], "ERROR_CORRECTION"))
    graph.add_node(node("c", 2, utilities[2], "VERIFICATION"))
    graph.add_edge("a", "b", "decomposes")
    graph.add_edge("b", "c", "verifies")
    graph.freeze_sources(["a"])
    return graph


def test_edge_removal_disconnects_subgraph() -> None:
    graph = make_chain((1.0, 1.0, 1.0))
    baseline = compute_graph_utility(graph)

    ablated = graph.remove_edge("a", "b")

    assert compute_graph_utility(ablated) < baseline


def test_bridge_node_high_influence() -> None:
    graph = make_chain((0.0, 1.0, 1.0))
    influence = compute_structural_influence(graph)

    assert influence["b"] > influence["a"]
    assert influence["b"] > influence["c"]


def test_propagation_decay() -> None:
    graph = make_chain((0.0, 0.0, 1.0))
    influence = compute_structural_influence(graph, lambda_propagation=1.0, gamma_decay=0.5)

    assert influence["b"] == pytest.approx(0.5)
    assert influence["a"] == pytest.approx(0.25)


def test_reachability_constraint() -> None:
    graph = ReflectionGraph("t1")
    graph.add_node(node("a", 0, 1.0))
    graph.add_node(node("b", 1, 1.0))
    graph.add_node(node("isolated", 2, 10.0))
    graph.add_edge("a", "b", "verifies")

    assert compute_graph_utility(graph) == pytest.approx(2.4)


def test_node_necessity_is_positive_for_bridge_node() -> None:
    graph = make_chain((1.0, 1.0, 1.0))
    scores = {row.node_id: row for row in compute_node_necessity(graph)}

    assert scores["b"].necessity > 0.0
    assert scores["b"].removal_mode == "PRUNE"


def test_edge_necessity_is_meaningful_for_critical_edge() -> None:
    graph = make_chain((1.0, 1.0, 1.0))
    scores = {(row.source, row.target): row for row in compute_edge_necessity(graph)}

    assert scores[("a", "b")].necessity > 0.0
    assert scores[("b", "c")].necessity > 0.0


def test_structural_faithfulness_uses_phase5_attribution_pairs() -> None:
    graph = make_chain((1.0, 0.5, 0.0))
    node_scores = compute_node_necessity(graph)
    phase5_scores = [
        {"trace_id": "t1", "step_idx": row.step_idx, "attribution_score": row.necessity}
        for row in node_scores
    ]

    report = compute_structural_faithfulness(node_scores, phase5_scores)

    assert report["pearson"] == pytest.approx(1.0)
    assert report["num_samples"] == 3


def test_structural_metrics_include_revised_phase6_fields() -> None:
    graph = make_chain((1.0, 1.0, 1.0))

    metrics = compute_structural_metrics(graph)

    assert set(metrics) == {
        "structural_influence_mean",
        "reachable_ratio",
        "influence_depth",
        "bridge_node_fraction",
    }
    assert metrics["reachable_ratio"] == pytest.approx(1.0)
    assert metrics["bridge_node_fraction"] > 0.0
