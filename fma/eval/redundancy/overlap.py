"""Shared profile and overlap helpers for Phase 7 redundancy analysis."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


MODE_ORDER: tuple[str, ...] = ("PRUNE", "CASCADE", "BYPASS")


@dataclass(frozen=True)
class NodeProfile:
    task_id: str
    node_id: str
    step_idx: int
    taxonomy: str
    source_role: str
    attribution_score: float
    prune_necessity: float
    cascade_necessity: float
    bypass_necessity: float
    downstream_nodes: tuple[str, ...]

    def necessity(self, mode: str) -> float:
        mode_key = str(mode).upper()
        if mode_key == "PRUNE":
            return float(self.prune_necessity)
        if mode_key == "CASCADE":
            return float(self.cascade_necessity)
        if mode_key == "BYPASS":
            return float(self.bypass_necessity)
        raise ValueError(f"unsupported removal mode {mode!r}")

    def necessity_profile(self) -> tuple[float, float, float]:
        return (
            float(self.prune_necessity),
            float(self.cascade_necessity),
            float(self.bypass_necessity),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["downstream_nodes"] = list(self.downstream_nodes)
        return payload


def profiles_from_graphs(
    graphs: Sequence[Any],
    attribution_records: Sequence[Mapping[str, Any]],
    node_necessity_records: Sequence[Mapping[str, Any]],
) -> list[NodeProfile]:
    """Join stored graph topology with attribution and per-mode necessity rows."""
    attribution_by_key = {
        (str(row.get("trace_id")), int(row.get("step_idx", 0))): float(
            row.get("attribution_score", row.get("utility_score", 0.0))
        )
        for row in attribution_records
        if "trace_id" in row and "step_idx" in row
    }
    necessity_by_key: dict[tuple[str, str, str], float] = {}
    for row in node_necessity_records:
        mode = str(row.get("removal_mode", "PRUNE")).upper()
        if mode not in MODE_ORDER:
            continue
        necessity_by_key[
            (mode, str(row.get("trace_id")), str(row.get("node_id")))
        ] = max(0.0, float(row.get("necessity", row.get("necessity_normalized", 0.0))))

    profiles: list[NodeProfile] = []
    for graph in sorted(graphs, key=lambda item: item.graph_id):
        source_ids = set(graph.source_nodes())
        for node in graph.sorted_nodes():
            key = (str(node.trace_id), int(node.step_index))
            profiles.append(
                NodeProfile(
                    task_id=str(node.trace_id),
                    node_id=str(node.node_id),
                    step_idx=int(node.step_index),
                    taxonomy=str(node.taxonomy_label),
                    source_role="source_node"
                    if node.node_id in source_ids
                    else "non_source_node",
                    attribution_score=float(
                        attribution_by_key.get(key, getattr(node, "utility_score", 0.0))
                    ),
                    prune_necessity=necessity_by_key.get(
                        ("PRUNE", str(node.trace_id), str(node.node_id)),
                        0.0,
                    ),
                    cascade_necessity=necessity_by_key.get(
                        ("CASCADE", str(node.trace_id), str(node.node_id)),
                        0.0,
                    ),
                    bypass_necessity=necessity_by_key.get(
                        ("BYPASS", str(node.trace_id), str(node.node_id)),
                        0.0,
                    ),
                    downstream_nodes=tuple(sorted(graph.descendants(node.node_id))),
                )
            )
    return profiles


def profile_by_node(profiles: Sequence[NodeProfile]) -> dict[str, NodeProfile]:
    return {profile.node_id: profile for profile in profiles}


def profiles_by_task(profiles: Sequence[NodeProfile]) -> dict[str, list[NodeProfile]]:
    grouped: dict[str, list[NodeProfile]] = {}
    for profile in profiles:
        grouped.setdefault(profile.task_id, []).append(profile)
    return {
        task_id: sorted(group, key=lambda item: (item.step_idx, item.node_id))
        for task_id, group in sorted(grouped.items())
    }


def overall_necessity(profile: NodeProfile) -> float:
    return max(0.0, *profile.necessity_profile())


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("cosine vectors must have the same length.")
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    value = sum(lv * rv for lv, rv in zip(left_values, right_values)) / (
        left_norm * right_norm
    )
    return clamp01(value)


def jaccard_overlap(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 0.0
    return float(len(left_set & right_set) / len(union))


def hybrid_similarity(left: NodeProfile, right: NodeProfile) -> float:
    left_profile = (left.attribution_score, *left.necessity_profile())
    right_profile = (right.attribution_score, *right.necessity_profile())
    return 0.5 * cosine_similarity(left_profile, right_profile) + 0.5 * jaccard_overlap(
        left.downstream_nodes,
        right.downstream_nodes,
    )


def min_max_normalize(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    floats = [float(value) for value in values]
    min_value = min(floats)
    max_value = max(floats)
    if max_value == min_value:
        fill = 1.0 if max_value > 0.0 else 0.0
        return [fill for _value in floats]
    return [(value - min_value) / (max_value - min_value) for value in floats]


def mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def clamp01(value: float) -> float:
    if not math.isfinite(float(value)):
        return 0.0
    return min(1.0, max(0.0, float(value)))


__all__ = [
    "MODE_ORDER",
    "NodeProfile",
    "clamp01",
    "cosine_similarity",
    "hybrid_similarity",
    "jaccard_overlap",
    "mean",
    "min_max_normalize",
    "overall_necessity",
    "profile_by_node",
    "profiles_by_task",
    "profiles_from_graphs",
]
