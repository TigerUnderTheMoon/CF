from __future__ import annotations

import pytest

from fma.graph.reflection_graph import RemovalMode, ReflectionGraph, ReflectionNode


def node(node_id: str, step: int, utility: float = 1.0, label: str = "VERIFICATION") -> ReflectionNode:
    return ReflectionNode(
        node_id=node_id,
        trace_id="t1",
        step_index=step,
        taxonomy_label=label,
        utility_score=utility,
        structural_influence=0.0,
        content=node_id,
    )


def chain_graph() -> ReflectionGraph:
    graph = ReflectionGraph("t1")
    graph.add_node(node("a", 0, label="DECOMPOSITION"))
    graph.add_node(node("b", 1, label="PLANNING"))
    graph.add_node(node("c", 2, label="VERIFICATION"))
    graph.add_edge("a", "b", "decomposes")
    graph.add_edge("b", "c", "verifies")
    graph.freeze_sources(["a"])
    return graph


def test_add_edge_rejects_cycles() -> None:
    graph = chain_graph()

    with pytest.raises(ValueError):
        graph.add_edge("c", "a", "revises")


def test_add_edge_rejects_duplicate_ordered_pair() -> None:
    graph = chain_graph()

    with pytest.raises(ValueError):
        graph.add_edge("a", "b", "revises")


def test_prune_removes_node_but_keeps_unreachable_descendant() -> None:
    graph = chain_graph()

    pruned = graph.remove_node("b", RemovalMode.PRUNE)

    assert "b" not in pruned.nodes
    assert "c" in pruned.nodes
    assert pruned.reachable_nodes() == {"a"}


def test_cascade_removes_descendants() -> None:
    graph = chain_graph()

    cascaded = graph.remove_node("b", RemovalMode.CASCADE)

    assert set(cascaded.nodes) == {"a"}
    assert cascaded.reachable_nodes() == {"a"}


def test_bypass_connects_parents_to_children_without_cycle() -> None:
    graph = chain_graph()

    bypassed = graph.remove_node("b", RemovalMode.BYPASS)

    assert "b" not in bypassed.nodes
    assert bypassed.has_edge("a", "c")
    assert bypassed.reachable_nodes() == {"a", "c"}


def test_edge_removal_preserves_original_sources() -> None:
    graph = chain_graph()

    ablated = graph.remove_edge("a", "b")

    assert ablated.source_nodes() == ["a"]
    assert ablated.reachable_nodes() == {"a"}


def test_graph_serialization_round_trips() -> None:
    graph = chain_graph()

    restored = ReflectionGraph.from_dict(graph.to_dict())

    assert restored.to_dict() == graph.to_dict()
