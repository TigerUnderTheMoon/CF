"""Statistical significance tests for method comparison in step ranking.

Provides:
  - Bootstrap confidence intervals
  - Friedman test (omnibus across methods)
  - Wilcoxon signed-rank pairwise comparisons
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats  # type: ignore[import-untyped]


def bootstrap_ci(
    data: np.ndarray,
    confidence: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> dict[str, float]:
    if len(data) == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "std": 0.0}
    rng = np.random.default_rng(seed)
    n = len(data)
    boot_means = np.array([
        float(np.mean(data[rng.integers(0, n, n)]))
        for _ in range(n_bootstrap)
    ])
    alpha = (1.0 - confidence) / 2.0
    return {
        "mean": float(np.mean(data)),
        "ci_lower": float(np.percentile(boot_means, 100 * alpha)),
        "ci_upper": float(np.percentile(boot_means, 100 * (1 - alpha))),
        "std": float(np.std(data, ddof=1)),
    }


def friedman_test(
    method_scores: dict[str, list[float]],
) -> dict[str, float]:
    names = sorted(method_scores.keys())
    if len(names) < 2:
        return {"statistic": 0.0, "p_value": 1.0, "n_methods": len(names)}

    min_len = min(len(method_scores[n]) for n in names)
    if min_len < 2:
        return {"statistic": 0.0, "p_value": 1.0, "n_methods": len(names)}

    matrix = np.array([method_scores[n][:min_len] for n in names])

    ranks = np.zeros_like(matrix, dtype=float)
    for j in range(min_len):
        col = matrix[:, j]
        col_ranks = stats.rankdata(-col)
        ranks[:, j] = col_ranks

    rank_means = np.mean(ranks, axis=1)
    grand_mean = (len(names) + 1.0) / 2.0
    ss_total = np.sum((rank_means - grand_mean) ** 2)

    if ss_total < 1e-15:
        return {"statistic": 0.0, "p_value": 1.0, "n_methods": len(names)}

    chi2 = 12.0 * min_len / (len(names) * (len(names) + 1.0)) * ss_total * float(len(names))
    df = len(names) - 1

    from scipy.stats import chi2 as chi2_dist
    p_value = 1.0 - float(chi2_dist.cdf(chi2, df))

    return {"statistic": float(chi2), "p_value": p_value, "n_methods": len(names), "n_samples": min_len}


def wilcoxon_pairs(
    method_scores: dict[str, list[float]],
    reference_method: str | None = None,
) -> list[dict[str, float]]:
    names = sorted(method_scores.keys())
    results: list[dict[str, float]] = []

    compare_names = names
    if reference_method and reference_method in names:
        compare_names = [reference_method]
        names = [n for n in names if n != reference_method]

    for m1 in compare_names:
        for m2 in names:
            if m1 >= m2:
                continue
            s1 = method_scores[m1]
            s2 = method_scores[m2]
            min_len = min(len(s1), len(s2))
            if min_len < 3:
                results.append({"method_1": m1, "method_2": m2, "statistic": 0.0, "p_value": 1.0})
                continue

            diff = np.array(s1[:min_len]) - np.array(s2[:min_len])
            nonzero = diff[diff != 0]
            if len(nonzero) < 2:
                results.append({"method_1": m1, "method_2": m2, "statistic": 0.0, "p_value": 1.0})
                continue

            try:
                w, p = stats.wilcoxon(s1[:min_len], s2[:min_len], zero_method="wilcox")
                results.append({
                    "method_1": m1,
                    "method_2": m2,
                    "statistic": float(w),
                    "p_value": float(p) if not math.isnan(p) else 1.0,
                })
            except Exception:
                results.append({"method_1": m1, "method_2": m2, "statistic": 0.0, "p_value": 1.0})

    return results
