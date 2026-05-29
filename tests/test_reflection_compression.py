from __future__ import annotations

import json

import pytest

from fma.eval.reflection_compression import (
    compress_graphs,
    compress_reflection_graph,
    compute_subgraph_utility_ratio,
    dataclass_to_dict,
    result_from_mapping,
)
from fma.graph.reflection_graph import ReflectionGraph, ReflectionNode


def node(node_id: str, step: int, utility: float) -> ReflectionNode:
    return ReflectionNode(node_id, "t1", step, "VERIFICATION", utility, 0.0, node_id)


def zero_tail_graph(graph_id: str = "t1") -> ReflectionGraph:
    graph = ReflectionGraph(graph_id)
    graph.add_node(node(f"{graph_id}:a", 0, 1.0))
    graph.add_node(node(f"{graph_id}:b", 1, 0.0))
    graph.add_node(node(f"{graph_id}:c", 2, 0.0))
    graph.add_edge(f"{graph_id}:a", f"{graph_id}:b", "verifies")
    graph.add_edge(f"{graph_id}:b", f"{graph_id}:c", "verifies")
    graph.freeze_sources([f"{graph_id}:a"])
    return graph


def useful_pair_graph() -> ReflectionGraph:
    graph = ReflectionGraph("useful")
    graph.add_node(node("a", 0, 1.0))
    graph.add_node(node("b", 1, 1.0))
    graph.add_edge("a", "b", "verifies")
    graph.freeze_sources(["a"])
    return graph


def test_compression_removes_lowest_necessity_nodes_with_recomputation() -> None:
    result = compress_reflection_graph(zero_tail_graph(), utility_threshold=0.9)

    assert result.removed_node_ids == ["t1:b", "t1:c"]
    assert result.retained_node_ids == ["t1:a"]
    assert result.utility_retained >= 0.9
    assert [point["iteration"] for point in result.curve] == [0, 1, 2]


def test_compression_threshold_blocks_useful_deletion() -> None:
    result = compress_reflection_graph(useful_pair_graph(), utility_threshold=0.9)

    assert result.removed_node_ids == []
    assert result.retained_node_count == 2
    assert result.compression_ratio == pytest.approx(0.0)


def test_subgraph_utility_ratio_uses_reachable_structural_utility() -> None:
    original = zero_tail_graph()
    compressed = original.remove_node("t1:b")

    assert compute_subgraph_utility_ratio(compressed, original) == pytest.approx(1.0)


def test_compression_result_is_json_serializable_and_restorable() -> None:
    result = compress_reflection_graph(zero_tail_graph(), utility_threshold=0.9)
    payload = dataclass_to_dict(result)

    assert json.loads(json.dumps(payload))["trace_id"] == "t1"
    assert result_from_mapping(payload) == result


def test_invalid_compression_threshold_raises() -> None:
    with pytest.raises(ValueError):
        compress_reflection_graph(zero_tail_graph(), utility_threshold=1.1)


def test_compress_graphs_sorts_results_by_graph_id() -> None:
    results = compress_graphs([zero_tail_graph("b"), zero_tail_graph("a")])

    assert [result.trace_id for result in results] == ["a", "b"]
