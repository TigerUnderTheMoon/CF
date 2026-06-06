"""Deterministic correlation helpers for structural diagnostics."""

from __future__ import annotations

import math
from typing import Any, Hashable, Sequence

import numpy as np


def pearson(left: Sequence[float], right: Sequence[float]) -> float:
    """Return Pearson correlation over finite paired values."""
    left_values, right_values = _finite_pairs(left, right)
    if len(left_values) < 2:
        return 0.0
    left_array = np.asarray(left_values, dtype=float)
    right_array = np.asarray(right_values, dtype=float)
    if float(np.std(left_array)) == 0.0 or float(np.std(right_array)) == 0.0:
        return 0.0
    value = float(np.corrcoef(left_array, right_array)[0, 1])
    return value if math.isfinite(value) else 0.0


def spearman(left: Sequence[float], right: Sequence[float]) -> float:
    """Return Spearman rank correlation with average ranks for ties."""
    left_values, right_values = _finite_pairs(left, right)
    if len(left_values) < 2:
        return 0.0
    return pearson(_ranks(left_values), _ranks(right_values))


def kendall_tau(left: Sequence[float], right: Sequence[float]) -> float:
    """Return Kendall tau-b correlation with deterministic tie handling."""
    left_values, right_values = _finite_pairs(left, right)
    if len(left_values) < 2:
        return 0.0

    concordant = 0
    discordant = 0
    tied_left = 0
    tied_right = 0
    for left_index in range(len(left_values)):
        for right_index in range(left_index + 1, len(left_values)):
            left_cmp = _compare(left_values[left_index], left_values[right_index])
            right_cmp = _compare(right_values[left_index], right_values[right_index])
            if left_cmp == 0 and right_cmp == 0:
                continue
            if left_cmp == 0:
                tied_left += 1
            elif right_cmp == 0:
                tied_right += 1
            elif left_cmp == right_cmp:
                concordant += 1
            else:
                discordant += 1

    denominator = math.sqrt(
        (concordant + discordant + tied_left)
        * (concordant + discordant + tied_right)
    )
    if denominator == 0.0:
        return 0.0
    value = (concordant - discordant) / denominator
    return float(value) if math.isfinite(value) else 0.0


def top_k_overlap(
    left: Sequence[float],
    right: Sequence[float],
    k: int,
    keys: Sequence[Hashable] | None = None,
) -> float:
    """Return top-k set overlap between two score vectors."""
    if k <= 0:
        raise ValueError("k must be positive.")
    keyed = _finite_keyed_pairs(left, right, keys)
    if not keyed:
        return 0.0
    limit = min(k, len(keyed))
    left_top = _top_keys(keyed, value_index=1, limit=limit)
    right_top = _top_keys(keyed, value_index=2, limit=limit)
    return float(len(left_top & right_top) / limit)


def correlation_summary(
    left: Sequence[float],
    right: Sequence[float],
    keys: Sequence[Hashable] | None = None,
    top_k_values: Sequence[int] = (3, 5, 10),
) -> dict[str, Any]:
    """Return the correlation diagnostics used in structural reports."""
    left_values, right_values = _finite_pairs(left, right)
    return {
        "num_samples": len(left_values),
        "pearson": pearson(left_values, right_values),
        "spearman": spearman(left_values, right_values),
        "kendall_tau": kendall_tau(left_values, right_values),
        "top_k_overlap": {
            str(k): top_k_overlap(left, right, k, keys=keys)
            for k in top_k_values
        },
    }


def scatter_summary(left: Sequence[float], right: Sequence[float]) -> dict[str, Any]:
    """Summarize paired scatter data without changing the underlying scores."""
    left_values, right_values = _finite_pairs(left, right)
    return {
        "num_samples": len(left_values),
        "attribution_score": distribution_summary(left_values),
        "structural_necessity": distribution_summary(right_values),
    }


def distribution_summary(values: Sequence[float]) -> dict[str, float]:
    """Return deterministic descriptive statistics for a numeric vector."""
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return {
            "count": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "p25": 0.0,
            "median": 0.0,
            "p75": 0.0,
            "max": 0.0,
        }
    array = np.asarray(finite, dtype=float)
    return {
        "count": float(len(finite)),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "min": float(np.min(array)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.percentile(array, 50)),
        "p75": float(np.percentile(array, 75)),
        "max": float(np.max(array)),
    }


def _finite_pairs(
    left: Sequence[float],
    right: Sequence[float],
) -> tuple[list[float], list[float]]:
    if len(left) != len(right):
        raise ValueError("left and right must have the same length.")
    left_values: list[float] = []
    right_values: list[float] = []
    for left_value, right_value in zip(left, right):
        left_float = float(left_value)
        right_float = float(right_value)
        if not math.isfinite(left_float) or not math.isfinite(right_float):
            continue
        left_values.append(left_float)
        right_values.append(right_float)
    return left_values, right_values


def _finite_keyed_pairs(
    left: Sequence[float],
    right: Sequence[float],
    keys: Sequence[Hashable] | None,
) -> list[tuple[Hashable, float, float]]:
    if len(left) != len(right):
        raise ValueError("left and right must have the same length.")
    if keys is not None and len(keys) != len(left):
        raise ValueError("keys must have the same length as score vectors.")
    keyed: list[tuple[Hashable, float, float]] = []
    for index, (left_value, right_value) in enumerate(zip(left, right)):
        left_float = float(left_value)
        right_float = float(right_value)
        if not math.isfinite(left_float) or not math.isfinite(right_float):
            continue
        key = keys[index] if keys is not None else index
        keyed.append((key, left_float, right_float))
    return keyed


def _top_keys(
    keyed: Sequence[tuple[Hashable, float, float]],
    value_index: int,
    limit: int,
) -> set[Hashable]:
    ordered = sorted(
        keyed,
        key=lambda item: (-float(item[value_index]), repr(item[0])),
    )
    return {item[0] for item in ordered[:limit]}


def _ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(
        enumerate(float(value) for value in values),
        key=lambda item: (item[1], item[0]),
    )
    ranks = [0.0] * len(indexed)
    position = 0
    while position < len(indexed):
        end = position + 1
        while end < len(indexed) and indexed[end][1] == indexed[position][1]:
            end += 1
        average_rank = (position + 1 + end) / 2.0
        for offset in range(position, end):
            ranks[indexed[offset][0]] = average_rank
        position = end
    return ranks


def _compare(left: float, right: float) -> int:
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


__all__ = [
    "correlation_summary",
    "distribution_summary",
    "kendall_tau",
    "pearson",
    "scatter_summary",
    "spearman",
    "top_k_overlap",
]
