from __future__ import annotations

import pytest

from fma.eval.redundancy.bottleneck import compute_bottlenecks
from fma.eval.redundancy.compensation import (
    AffectedNodeDelta,
    InterventionDelta,
    compute_compensation_records,
    stratify_compensation,
)
from fma.eval.redundancy.distributedness import distributedness_index
from fma.eval.redundancy.overlap import NodeProfile
from fma.eval.redundancy.redundancy_density import compute_redundancy
from fma.eval.redundancy.rerouting import compute_rerouting_records, summarize_rerouting
from fma.eval.redundancy.resilience import is_monotonic_degradation, resilience_curve


def profile(
    node_id: str,
    step: int,
    attribution: float = 0.0,
    necessity: float = 0.0,
    downstream: tuple[str, ...] = (),
    taxonomy: str = "VERIFICATION",
) -> NodeProfile:
    return NodeProfile(
        task_id="t1",
        node_id=node_id,
        step_idx=step,
        taxonomy=taxonomy,
        source_role="source_node" if step == 0 else "non_source_node",
        attribution_score=attribution,
        prune_necessity=necessity,
        cascade_necessity=necessity,
        bypass_necessity=necessity,
        downstream_nodes=downstream,
    )


def test_compensation_all_zero() -> None:
    profiles = [
        profile("a", 0, downstream=("b",)),
        profile("b", 1),
    ]
    deltas = [
        InterventionDelta(
            task_id="t1",
            mode="PRUNE",
            removed_node="a",
            affected_nodes=(
                AffectedNodeDelta("b", 0.0, 0.0, 0.0, 1),
            ),
        )
    ]

    records = compute_compensation_records(profiles, deltas)

    assert records[0].positive_redistribution == pytest.approx(0.0)
    assert records[0].compensation_ratio == pytest.approx(0.0)


def test_redundancy_single_step() -> None:
    summary = compute_redundancy([profile("a", 0, attribution=1.0, necessity=1.0)])

    assert summary["density"] == pytest.approx(0.0)
    assert summary["cluster_sizes"] == [1]
    assert summary["mean_cluster_size"] == pytest.approx(1.0)


def test_bottleneck_none() -> None:
    profiles = [profile("a", 0), profile("b", 1)]
    summary = compute_bottlenecks(profiles, {"a": 0.0, "b": 0.0})

    assert summary["bottleneck_count"] == 0
    assert summary["frequency"] == pytest.approx(0.0)


def test_rerouting_no_downstream() -> None:
    profiles = [profile("a", 0)]
    deltas = [InterventionDelta("t1", "PRUNE", "a", ())]
    records = compute_rerouting_records(profiles, deltas)
    summary = summarize_rerouting(records)

    assert records[0].rerouting_entropy == pytest.approx(0.0)
    assert records[0].rerouting_depth == pytest.approx(0.0)
    assert summary["mean_breadth"] == pytest.approx(0.0)


def test_resilience_monotonic_degradation() -> None:
    profiles = [
        profile("a", 0, necessity=1.0),
        profile("b", 1, necessity=0.5),
        profile("c", 2, necessity=0.0),
    ]

    curve = resilience_curve(profiles, "necessity_first")

    assert is_monotonic_degradation(curve)
    assert curve[0]["remaining_total_necessity"] == pytest.approx(1.0)
    assert curve[-1]["remaining_total_necessity"] == pytest.approx(0.0)


def test_compensation_stratified_empty() -> None:
    assert stratify_compensation([], "taxonomy") == {}


def test_distributedness_uniform() -> None:
    assert distributedness_index([1.0, 1.0, 1.0]) == pytest.approx(1.0)


def test_distributedness_single_bottleneck() -> None:
    assert distributedness_index([1.0, 0.0, 0.0]) == pytest.approx(1.0 / 3.0)
