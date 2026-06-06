from __future__ import annotations

import networkx as nx

from fma.graph import GraphIntervention, RemovalMode
from fma.graph.reflection_graph import ReflectionEdge, ReflectionGraph, ReflectionNode


def node(node_id: str, step_idx: int) -> ReflectionNode:
    return ReflectionNode(
        node_id=node_id,
        trace_id="trace-1",
        step_index=step_idx,
        taxonomy_label="VERIFICATION",
        utility_score=1.0,
        structural_influence=0.0,
        content=node_id,
    )


def make_diamond_graph() -> ReflectionGraph:
    return ReflectionGraph(
        "trace-1",
        nodes=[node("a", 0), node("b", 1), node("c", 2), node("d", 3)],
        edges=[
            ReflectionEdge("a", "b", "decomposes"),
            ReflectionEdge("a", "c", "decomposes"),
            ReflectionEdge("b", "d", "verifies"),
            ReflectionEdge("c", "d", "verifies"),
        ],
        source_ids=["a"],
    )


def as_networkx(graph: ReflectionGraph) -> nx.DiGraph:
    nx_graph = nx.DiGraph()
    nx_graph.add_nodes_from(graph.nodes)
    nx_graph.add_edges_from((edge.source, edge.target) for edge in graph.sorted_edges())
    return nx_graph


def test_prune_removes_only_target_node_and_incident_edges() -> None:
    graph = make_diamond_graph()

    pruned = GraphIntervention("b", RemovalMode.PRUNE).apply(graph)
    nx_graph = as_networkx(pruned)

    assert set(nx_graph.nodes) == {"a", "c", "d"}
    assert set(nx_graph.edges) == {("a", "c"), ("c", "d")}
    assert nx.is_directed_acyclic_graph(nx_graph)
    assert "d" in pruned.reachable_nodes()


def test_cascade_removes_target_node_and_all_descendants() -> None:
    graph = make_diamond_graph()

    cascaded = GraphIntervention("b", RemovalMode.CASCADE).apply(graph)
    nx_graph = as_networkx(cascaded)

    assert set(nx_graph.nodes) == {"a", "c"}
    assert set(nx_graph.edges) == {("a", "c")}
    assert nx.is_directed_acyclic_graph(nx_graph)


def test_bypass_reconnects_parents_to_children_without_cycles() -> None:
    graph = make_diamond_graph()

    bypassed = GraphIntervention("b", RemovalMode.BYPASS).apply(graph)
    nx_graph = as_networkx(bypassed)

    assert set(nx_graph.nodes) == {"a", "c", "d"}
    assert ("a", "d") in nx_graph.edges
    assert ("a", "c") in nx_graph.edges
    assert ("c", "d") in nx_graph.edges
    assert nx.is_directed_acyclic_graph(nx_graph)
    assert list(nx.topological_sort(nx_graph))[0] == "a"
