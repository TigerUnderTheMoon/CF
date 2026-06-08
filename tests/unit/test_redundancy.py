from __future__ import annotations

import pytest

from fma.eval.redundancy.distributedness import (
    distributedness_index,
    gini_coefficient,
    summarize_distributedness,
)
from fma.eval.redundancy.overlap import NodeProfile
from fma.eval.redundancy.overlap import hybrid_similarity
from fma.eval.redundancy.redundancy_density import compute_redundancy


def profile(
    node_id: str,
    task_id: str = "trace-1",
    downstream_nodes: tuple[str, ...] = ("shared",),
    necessity: float = 1.0,
) -> NodeProfile:
    return NodeProfile(
        task_id=task_id,
        node_id=node_id,
        step_idx=0,
        taxonomy="VERIFICATION",
        source_role="source_node",
        attribution_score=1.0,
        prune_necessity=necessity,
        cascade_necessity=necessity,
        bypass_necessity=necessity,
        downstream_nodes=downstream_nodes,
    )


def test_redundancy_density_clusters_similar_nodes_within_trace() -> None:
    profiles = [
        profile("a"),
        profile("b"),
        profile("c", downstream_nodes=("other",), necessity=0.0),
    ]
    summary = compute_redundancy(
        profiles,
        similarity_threshold=0.75,
    )

    pair_ab = hybrid_similarity(profiles[0], profiles[1])
    pair_ac = hybrid_similarity(profiles[0], profiles[2])
    pair_bc = hybrid_similarity(profiles[1], profiles[2])

    assert pair_ab == pytest.approx(1.0)
    assert pair_ac == pytest.approx(0.25)
    assert pair_bc == pytest.approx(0.25)
    assert summary["cluster_sizes"] == [2, 1]
    assert summary["density"] == pytest.approx((1.0 + 0.25 + 0.25) / 3.0)
    assert summary["redundancy_degree_by_node"]["a"] == pytest.approx(0.625)
    assert summary["redundancy_degree_by_node"]["b"] == pytest.approx(0.625)
    assert summary["redundancy_degree_by_node"]["c"] == pytest.approx(0.25)
    assert summary["cluster_density"] == pytest.approx(0.5)


def test_redundancy_density_is_task_conditioned() -> None:
    summary = compute_redundancy([profile("a", task_id="t1"), profile("b", task_id="t2")])

    assert summary["density"] == pytest.approx(0.0)
    assert summary["cluster_sizes"] == [1, 1]
    assert set(summary["per_trajectory"]) == {"t1", "t2"}


def test_distributedness_index_is_one_minus_gini() -> None:
    assert gini_coefficient([1.0, 0.0, 0.0]) == pytest.approx(2.0 / 3.0)
    assert distributedness_index([1.0, 0.0, 0.0]) == pytest.approx(1.0 / 3.0)
    assert distributedness_index([1.0, 1.0, 1.0]) == pytest.approx(1.0)
    assert distributedness_index([]) == pytest.approx(0.0)


def test_summarize_distributedness_reports_global_and_per_trace_indices() -> None:
    profiles = [
        profile("a", task_id="t1", necessity=1.0),
        profile("b", task_id="t1", necessity=1.0),
        profile("c", task_id="t2", necessity=1.0),
        profile("d", task_id="t2", necessity=0.0),
    ]

    summary = summarize_distributedness(profiles)

    assert summary["per_trajectory"]["t1"] == pytest.approx(1.0)
    assert summary["per_trajectory"]["t2"] == pytest.approx(0.5)
    assert summary["global_index"] == pytest.approx(0.75)
