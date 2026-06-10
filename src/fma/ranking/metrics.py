"""Ranking metrics for step importance evaluation.

Computes rank correlation between predicted importance scores and
ground-truth step labels across multiple metrics:
  - Spearman rho (rank correlation)
  - Kendall tau (ordinal association)
  - NDCG@k (top-k ranking quality)
  - Top-k overlap (agreement on most important steps)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats  # type: ignore[import-untyped]


def _rankdata(scores: list[float]) -> np.ndarray:
    arr = np.array(scores, dtype=float)
    order = np.argsort(np.argsort(-arr)).astype(float)
    return order


def compute_ranking_metrics(
    predicted: list[float],
    ground_truth: list[float],
    k_values: tuple[int, ...] = (3, 5, 10),
) -> dict[str, float]:
    n = len(predicted)
    if n < 2:
        return {
            "spearman_rho": 0.0,
            "kendall_tau": 0.0,
            "ndcg_3": 0.0,
            "ndcg_5": 0.0,
            "ndcg_10": 0.0,
            "topk_overlap_3": 0.0,
            "topk_overlap_5": 0.0,
            "topk_overlap_10": 0.0,
        }

    pred_arr = np.array(predicted, dtype=float)
    gt_arr = np.array(ground_truth, dtype=float)

    rho, _ = stats.spearmanr(pred_arr, gt_arr)
    tau, _ = stats.kendalltau(pred_arr, gt_arr)

    metrics: dict[str, float] = {
        "spearman_rho": float(rho) if not math.isnan(rho) else 0.0,
        "kendall_tau": float(tau) if not math.isnan(tau) else 0.0,
    }

    for k in k_values:
        if k < 1:
            continue
        k_eff = min(k, n)
        ndcg_val = compute_ndcg(pred_arr, gt_arr, k_eff)
        metrics[f"ndcg_{k}"] = ndcg_val
        overlap = compute_topk_overlap(predicted, ground_truth, k_eff)
        metrics[f"topk_overlap_{k}"] = overlap

    return metrics


def compute_ndcg(
    predicted: np.ndarray,
    ground_truth: np.ndarray,
    k: int,
) -> float:
    n = len(predicted)
    if k > n:
        k = n
    if k == 0:
        return 0.0

    pred_order = np.argsort(-predicted)
    gt_sorted = ground_truth[pred_order[:k]]

    dcg = 0.0
    for i, rel in enumerate(gt_sorted):
        dcg += (2.0 ** float(rel) - 1.0) / math.log2(float(i + 2))

    ideal_order = np.argsort(-ground_truth)
    ideal_sorted = ground_truth[ideal_order[:k]]
    idcg = 0.0
    for i, rel in enumerate(ideal_sorted):
        idcg += (2.0 ** float(rel) - 1.0) / math.log2(float(i + 2))

    if idcg < 1e-10:
        return 0.0
    return float(dcg / idcg)


def compute_topk_overlap(
    predicted: list[float],
    ground_truth: list[float],
    k: int,
) -> float:
    n = len(predicted)
    if n == 0 or k == 0:
        return 0.0
    k = min(k, n)

    pred_top = set(np.argsort(-np.array(predicted))[:k].tolist())
    gt_top = set(np.argsort(-np.array(ground_truth))[:k].tolist())
    if not gt_top:
        return 0.0
    return float(len(pred_top & gt_top)) / float(k)
