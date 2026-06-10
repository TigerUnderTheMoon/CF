"""Topology-resilience curves over stored structural necessity profiles."""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

import numpy as np

from fma.eval.redundancy.overlap import NodeProfile, overall_necessity


STRATEGIES: tuple[str, ...] = (
    "sequential",
    "random",
    "attribution_first",
    "necessity_first",
)


def resilience_curve(
    profiles: Sequence[NodeProfile],
    strategy: str,
) -> list[dict[str, float]]:
    ordered = _ordered_profiles(profiles, strategy)
    total_nodes = len(ordered)
    total_necessity = sum(overall_necessity(profile) for profile in ordered)
    remaining = total_necessity
    curve = [{"normalized_removal_step": 0.0, "remaining_total_necessity": 1.0}]
    if total_nodes == 0:
        return curve

    for index, profile in enumerate(ordered, start=1):
        remaining -= overall_necessity(profile)
        if total_necessity <= 0.0:
            remaining_ratio = 1.0
        else:
            remaining_ratio = max(0.0, remaining / total_necessity)
        curve.append(
            {
                "normalized_removal_step": float(index / total_nodes),
                "remaining_total_necessity": float(remaining_ratio),
            }
        )
    return curve


def topology_resilience(curve: Sequence[dict[str, float]]) -> float:
    if len(curve) < 2:
        return 0.0
    xs = [point["normalized_removal_step"] for point in curve]
    ys = [point["remaining_total_necessity"] for point in curve]
    return float(np.trapezoid(ys, xs))


def summarize_resilience(profiles: Sequence[NodeProfile]) -> dict[str, Any]:
    curves = {
        strategy: resilience_curve(profiles, strategy)
        for strategy in STRATEGIES
    }
    aucs = {strategy: topology_resilience(curve) for strategy, curve in curves.items()}
    return {
        "sequential_removal_auc": aucs["sequential"],
        "random_removal_auc": aucs["random"],
        "attribution_first_auc": aucs["attribution_first"],
        "necessity_first_auc": aucs["necessity_first"],
        "sequential_degradation_auc": 1.0 - aucs["sequential"],
        "random_degradation_auc": 1.0 - aucs["random"],
        "attribution_first_degradation_auc": 1.0 - aucs["attribution_first"],
        "necessity_first_degradation_auc": 1.0 - aucs["necessity_first"],
        "curves": curves,
    }


def is_monotonic_degradation(curve: Sequence[dict[str, float]]) -> bool:
    values = [point["remaining_total_necessity"] for point in curve]
    return all(left >= right for left, right in zip(values, values[1:]))


def _ordered_profiles(
    profiles: Sequence[NodeProfile],
    strategy: str,
) -> list[NodeProfile]:
    strategy_key = str(strategy).lower()
    if strategy_key == "sequential":
        return sorted(profiles, key=lambda item: (item.task_id, item.step_idx, item.node_id))
    if strategy_key == "random":
        return sorted(profiles, key=lambda item: (_stable_hash(item.node_id), item.node_id))
    if strategy_key == "attribution_first":
        return sorted(
            profiles,
            key=lambda item: (-item.attribution_score, item.task_id, item.step_idx, item.node_id),
        )
    if strategy_key == "necessity_first":
        return sorted(
            profiles,
            key=lambda item: (-overall_necessity(item), item.task_id, item.step_idx, item.node_id),
        )
    raise ValueError(f"unsupported resilience strategy {strategy!r}")


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "STRATEGIES",
    "is_monotonic_degradation",
    "resilience_curve",
    "summarize_resilience",
    "topology_resilience",
]
