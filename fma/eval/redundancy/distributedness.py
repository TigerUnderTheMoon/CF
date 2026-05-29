"""Distributedness metrics for reflection necessity distributions."""

from __future__ import annotations

from typing import Any, Sequence

from fma.eval.redundancy.overlap import NodeProfile, overall_necessity, profiles_by_task


def gini_coefficient(values: Sequence[float]) -> float:
    nonnegative = [max(0.0, float(value)) for value in values]
    if not nonnegative:
        return 0.0
    total = sum(nonnegative)
    if total == 0.0:
        return 0.0
    ordered = sorted(nonnegative)
    count = len(ordered)
    numerator = sum((2 * index - count - 1) * value for index, value in enumerate(ordered, start=1))
    return float(numerator / (count * total))


def distributedness_index(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(1.0 - gini_coefficient(values))


def summarize_distributedness(profiles: Sequence[NodeProfile]) -> dict[str, Any]:
    per_trajectory: dict[str, float] = {}
    for task_id, group in profiles_by_task(profiles).items():
        per_trajectory[task_id] = distributedness_index(
            [overall_necessity(profile) for profile in group]
        )
    return {
        "global_index": distributedness_index(
            [overall_necessity(profile) for profile in profiles]
        ),
        "per_trajectory": per_trajectory,
    }


__all__ = [
    "distributedness_index",
    "gini_coefficient",
    "summarize_distributedness",
]
