"""Bootstrap confidence intervals and statistical tests for FMA vs baselines."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np


def bootstrap_accuracy_ci(
    correct_array: np.ndarray,
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> dict[str, float]:
    """Compute bootstrap confidence interval for accuracy.

    Args:
        correct_array: 1D array of 0/1 correctness values.
        n_bootstrap: Number of resamples.
        ci_level: Confidence level (default 0.95).
        seed: Random seed.

    Returns:
        Dict with mean, ci_low, ci_high, std_err keys.
    """
    rng = np.random.RandomState(seed)
    n = len(correct_array)
    means = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.randint(0, n, n)
        means[i] = correct_array[idx].mean()
    alpha = (1.0 - ci_level) / 2.0
    ci_low = np.percentile(means, alpha * 100)
    ci_high = np.percentile(means, (1.0 - alpha) * 100)
    return {
        "mean": float(correct_array.mean()),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "std_err": float(means.std()),
        "n": n,
        "n_bootstrap": n_bootstrap,
    }


def mcnemar_test(
    correct_a: np.ndarray,
    correct_b: np.ndarray,
) -> dict[str, float]:
    """McNemar test for paired binary data.

    Args:
        correct_a: 0/1 correctness for method A.
        correct_b: 0/1 correctness for method B.

    Returns:
        Dict with chi2, p_value, contingency_table keys.
    """
    n_both_correct = ((correct_a == 1) & (correct_b == 1)).sum()
    n_a_only = ((correct_a == 1) & (correct_b == 0)).sum()
    n_b_only = ((correct_a == 0) & (correct_b == 1)).sum()
    n_neither = ((correct_a == 0) & (correct_b == 0)).sum()

    b = n_a_only
    c = n_b_only
    if b + c == 0:
        return {"chi2": 0.0, "p_value": 1.0, "significant": False}

    chi2 = (b - c) ** 2 / (b + c)
    from scipy.stats import chi2 as chi2_dist

    p_value = float(1.0 - chi2_dist.cdf(chi2, df=1))

    return {
        "chi2": float(chi2),
        "p_value": p_value,
        "significant": p_value < 0.05,
        "contingency": {
            "both_correct": int(n_both_correct),
            "a_only": int(n_a_only),
            "b_only": int(n_b_only),
            "neither": int(n_neither),
        },
        "direction": "A > B" if n_a_only > n_b_only else "B > A" if n_b_only > n_a_only else "equal",
    }


def cohens_d(effect: np.ndarray) -> float:
    """Cohen's d effect size."""
    if len(effect) < 2:
        return 0.0
    d = effect.mean() / max(effect.std(), 1e-6)
    return float(d)


def compute_ci_for_filtering_results(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute bootstrap CIs and significance for filtering experiment results.

    Args:
        results: List of FilteringResult dicts from comparison report.

    Returns:
        Dict with per-method-ratio CIs and pairwise McNemar tests.
    """
    grouped: dict[str, dict[str, list[int]]] = {}
    for r in results:
        method = r["method_name"]
        ratio = str(r["keep_ratio"])
        try:
            ratio = f"keep_{float(r['keep_ratio']):.2f}"
        except (ValueError, TypeError):
            pass
        grouped.setdefault(method, {}).setdefault(ratio, [])
        grouped[method][ratio].append(1 if r["is_correct_after"] else 0)

    ci_report: dict[str, Any] = {}
    for method in sorted(grouped):
        ci_report[method] = {}
        for ratio in sorted(grouped[method]):
            arr = np.array(grouped[method][ratio], dtype=float)
            ci = bootstrap_accuracy_ci(arr)
            ci_report[method][ratio] = ci

    pairwise: dict[str, Any] = {}
    methods_list = sorted(grouped.keys())
    for ratio in sorted(set().union(*(grouped[m].keys() for m in methods_list))):
        for i, method_a in enumerate(methods_list):
            for method_b in methods_list[i + 1 :]:
                if ratio in grouped[method_a] and ratio in grouped[method_b]:
                    arr_a = np.array(grouped[method_a][ratio], dtype=float)
                    arr_b = np.array(grouped[method_b][ratio], dtype=float)
                    key = f"{method_a}_vs_{method_b}_{ratio}"
                    mc = mcnemar_test(arr_a, arr_b)
                    if key not in pairwise:
                        pairwise[key] = mc

    return {"bootstrap_ci": ci_report, "mcnemar_tests": pairwise}


def run_stats_from_report(report_path: Path) -> None:
    """Read existing comparison report and compute statistics."""
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        return

    with report_path.open("r", encoding="utf-8") as f:
        report = json.load(f)

    results = report.get("filtering_results", [])
    if not results:
        print("No filtering results in report")
        return

    stats = compute_ci_for_filtering_results(results)

    out_dir = report_path.parent
    stats_path = out_dir / "statistical_report.json"
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, sort_keys=True)

    print(f"Stats saved: {stats_path}")
    _print_stats_summary(stats)


def _print_stats_summary(stats: dict[str, Any]) -> None:
    ci = stats["bootstrap_ci"]
    mc = stats["mcnemar_tests"]

    print("\n=== Bootstrap 95% CI ===")
    for method in sorted(ci):
        for ratio in sorted(ci[method]):
            r = ci[method][ratio]
            print(
                f"  {method:20s} {ratio:10s}: "
                f"{r['mean']:.3f} [{r['ci_low']:.3f}, {r['ci_high']:.3f}]"
            )

    print("\n=== McNemar Test (significant at p < 0.05) ===")
    sig_count = 0
    for key, test in sorted(mc.items()):
        if test["significant"]:
            sig_count += 1
            print(
                f"  {key}: chi2={test['chi2']:.2f} p={test['p_value']:.4f} {test['direction']}"
            )
    if sig_count == 0:
        print("  No significant differences found")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "outputs/downstream_comparison_v1/report/comparison_report.json"
        ),
    )
    args = parser.parse_args()
    run_stats_from_report(args.report)
