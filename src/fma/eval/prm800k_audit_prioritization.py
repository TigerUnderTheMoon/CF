from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MethodAuditSummary:
    method: str
    mean_top1_hit: float
    mean_mass_at_25: float
    mean_mass_at_50: float
    mean_ndcg_at_25: float
    mean_ndcg_at_50: float


def keep_count(n_steps: int, keep_fraction: float) -> int:
    if n_steps <= 0:
        return 0
    return max(1, min(n_steps, int(math.ceil(n_steps * keep_fraction))))


def selected_indices(scores: Sequence[float], keep_fraction: float) -> list[int]:
    scores_array = np.asarray(scores, dtype=float)
    k = keep_count(len(scores_array), keep_fraction)
    if k == 0:
        return []
    order = np.argsort(-scores_array, kind="mergesort")
    return [int(i) for i in order[:k]]


def max_label_hit_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    if labels_array.size == 0:
        return 0.0
    selected = selected_indices(scores, keep_fraction)
    max_label = float(np.max(labels_array))
    return 1.0 if any(float(labels_array[i]) == max_label for i in selected) else 0.0


def label_mass_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    total = float(np.sum(labels_array))
    if total <= 0.0:
        return 0.0
    selected = selected_indices(scores, keep_fraction)
    return float(np.sum(labels_array[selected]) / total)


def ndcg_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    selected = selected_indices(scores, keep_fraction)
    if not selected:
        return 0.0
    gains = np.power(2.0, labels_array[selected]) - 1.0
    discounts = 1.0 / np.log2(np.arange(2, len(selected) + 2))
    dcg = float(np.sum(gains * discounts))
    ideal = np.sort(labels_array)[::-1][: len(selected)]
    ideal_gains = np.power(2.0, ideal) - 1.0
    ideal_dcg = float(np.sum(ideal_gains * discounts))
    return 0.0 if ideal_dcg <= 0.0 else dcg / ideal_dcg


def summarize_audit_prioritization(
    rows: Sequence[Mapping[str, object]],
    *,
    methods: Sequence[str],
) -> list[MethodAuditSummary]:
    summaries: list[MethodAuditSummary] = []
    for method in methods:
        top1_hits: list[float] = []
        mass25: list[float] = []
        mass50: list[float] = []
        ndcg25: list[float] = []
        ndcg50: list[float] = []
        for row in rows:
            labels = row["labels"]
            scores_by_method = row["scores_by_method"]
            if not isinstance(labels, Sequence):
                continue
            if not isinstance(scores_by_method, Mapping) or method not in scores_by_method:
                continue
            scores = scores_by_method[method]
            if not isinstance(scores, Sequence):
                continue
            top1_hits.append(
                max_label_hit_at_budget(
                    scores,
                    labels,
                    keep_fraction=1.0 / len(labels),
                )
            )
            mass25.append(label_mass_at_budget(scores, labels, keep_fraction=0.25))
            mass50.append(label_mass_at_budget(scores, labels, keep_fraction=0.50))
            ndcg25.append(ndcg_at_budget(scores, labels, keep_fraction=0.25))
            ndcg50.append(ndcg_at_budget(scores, labels, keep_fraction=0.50))
        summaries.append(
            MethodAuditSummary(
                method=method,
                mean_top1_hit=float(np.mean(top1_hits)) if top1_hits else 0.0,
                mean_mass_at_25=float(np.mean(mass25)) if mass25 else 0.0,
                mean_mass_at_50=float(np.mean(mass50)) if mass50 else 0.0,
                mean_ndcg_at_25=float(np.mean(ndcg25)) if ndcg25 else 0.0,
                mean_ndcg_at_50=float(np.mean(ndcg50)) if ndcg50 else 0.0,
            )
        )
    return summaries
