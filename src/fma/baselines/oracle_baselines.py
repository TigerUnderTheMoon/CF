"""Oracle and ground-truth baselines for step importance ranking.

Family F: Oracle / Upper Bound
  - Load ground-truth step labels from annotated datasets (PRM800K, ProcessBench)
  - Compute oracle step scores from correctness deltas
  - Provides ceiling performance for method comparison
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def load_oracle_labels(
    records: list[dict[str, Any]],
    label_key: str = "ground_truth_importance",
    step_scores_key: str = "step_scores",
) -> list[float]:
    all_scores: list[float] = []
    for record in records:
        if label_key in record and record[label_key] is not None:
            all_scores.append(float(record[label_key]))
        elif step_scores_key in record:
            scores = record[step_scores_key]
            if isinstance(scores, list):
                all_scores.extend([float(s) for s in scores])
    return all_scores


def compute_oracle_step_scores(
    step_correctness: list[bool],
    normalize: bool = True,
) -> list[float]:
    n = len(step_correctness)
    if n == 0:
        return []

    scores = [1.0 if c else 0.0 for c in step_correctness]
    if normalize and sum(scores) > 0:
        total = sum(scores)
        scores = [s / total for s in scores]
    elif normalize:
        scores = [1.0 / n] * n if n > 0 else []

    return scores


def linear_oracle_ensemble(
    step_scores_list: list[list[float]],
    weights: list[float] | None = None,
    normalize: bool = True,
) -> list[float]:
    if not step_scores_list:
        return []

    n = len(step_scores_list[0])
    if weights is None:
        weights = [1.0 / len(step_scores_list)] * len(step_scores_list)

    result = np.zeros(n)
    for scores, w in zip(step_scores_list, weights):
        arr = np.array(scores)
        result += w * arr

    if normalize:
        total = np.sum(np.abs(result))
        if total > 1e-10:
            result = result / total
        else:
            result = np.ones(n) / n

    return [float(v) for v in result]
