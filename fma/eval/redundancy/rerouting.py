"""Rerouting summaries derived from Phase 7 intervention deltas."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from fma.eval.redundancy.compensation import InterventionDelta
from fma.eval.redundancy.overlap import MODE_ORDER, NodeProfile, mean, profile_by_node


@dataclass(frozen=True)
class ReroutingRecord:
    task_id: str
    mode: str
    removed_node: str
    attribution_score: float
    rerouting_entropy: float
    rerouting_depth: float
    rerouting_breadth: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_rerouting_records(
    profiles: Sequence[NodeProfile],
    deltas: Sequence[InterventionDelta],
) -> list[ReroutingRecord]:
    profiles_by_node_id = profile_by_node(profiles)
    records: list[ReroutingRecord] = []
    for delta in deltas:
        profile = profiles_by_node_id.get(delta.removed_node)
        if profile is None:
            continue
        positive = [
            affected
            for affected in delta.affected_nodes
            if affected.necessity_delta > 0.0
        ]
        records.append(
            ReroutingRecord(
                task_id=delta.task_id,
                mode=str(delta.mode).upper(),
                removed_node=delta.removed_node,
                attribution_score=profile.attribution_score,
                rerouting_entropy=redistribution_entropy(
                    [affected.necessity_delta for affected in positive]
                ),
                rerouting_depth=float(max((affected.distance for affected in positive), default=0)),
                rerouting_breadth=float(len(positive)),
            )
        )
    return records


def redistribution_entropy(values: Sequence[float]) -> float:
    positive = [float(value) for value in values if value > 0.0]
    if len(positive) <= 1:
        return 0.0
    total = sum(positive)
    if total <= 0.0:
        return 0.0
    probabilities = [value / total for value in positive]
    entropy = -sum(prob * math.log(prob) for prob in probabilities if prob > 0.0)
    return float(entropy / math.log(len(probabilities)))


def summarize_rerouting(
    records: Sequence[ReroutingRecord],
    modes: Sequence[str] = MODE_ORDER,
) -> dict[str, Any]:
    return {
        "mean_entropy": mean([record.rerouting_entropy for record in records]),
        "mean_depth": mean([record.rerouting_depth for record in records]),
        "mean_breadth": mean([record.rerouting_breadth for record in records]),
        "mode_comparison": {
            str(mode).lower(): _mode_summary(records, str(mode).upper())
            for mode in modes
        },
    }


def _mode_summary(records: Sequence[ReroutingRecord], mode: str) -> dict[str, float]:
    mode_records = [record for record in records if record.mode == mode]
    return {
        "mean_entropy": mean([record.rerouting_entropy for record in mode_records]),
        "mean_depth": mean([record.rerouting_depth for record in mode_records]),
        "mean_breadth": mean([record.rerouting_breadth for record in mode_records]),
        "count": float(len(mode_records)),
    }


__all__ = [
    "ReroutingRecord",
    "compute_rerouting_records",
    "redistribution_entropy",
    "summarize_rerouting",
]
