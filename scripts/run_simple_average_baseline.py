"""Run simple_average baseline on synthetic and PRM800K benchmarks.

Computes unweighted mean of normalized CIU and structural necessity for
step-importance ranking. Produces Spearman rho, Kendall tau, and NDCG metrics.

No API calls. Uses frozen synthetic data and frozen PRM800K v3.6 artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from fma.baselines.simple_average import simple_average_baseline
from fma.ranking.metrics import compute_ndcg, compute_ranking_metrics
from fma.eval.prm800k_audit_prioritization import ndcg_at_budget

EPSILON = 1e-10
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "baselines" / "simple_average_results.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", choices=["synthetic", "prm800k", "all"],
                        default="all", help="Which benchmark to run (default: all)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output JSON path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--skip-prm800k-download", action="store_true",
                        help="Skip PRM800K download (use cached results only)")
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Synthetic benchmark
# ---------------------------------------------------------------------------

def _generate_synthetic_ranking_data(
    n_samples: int = 200,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate synthetic ranking data matching KBS calibration benchmark."""
    rng = np.random.default_rng(seed)
    samples: list[dict[str, Any]] = []

    for i in range(n_samples):
        n_steps = rng.integers(3, 8)
        gt = np.abs(rng.normal(0.5, 0.3, n_steps))
        gt = gt / np.sum(gt)

        # CIU: ground truth + noise
        ciu = gt + rng.normal(0, 0.15, n_steps)
        ciu = np.clip(ciu, 0.0, 1.0)

        # Necessity: ground truth + noise, with some steps zeroed
        nec = gt + rng.normal(0, 0.2, n_steps)
        nec = np.clip(nec, 0.0, 1.0)
        for j in range(n_steps - 1):
            if rng.random() < 0.3:
                nec[j] = 0.0

        samples.append({
            "sample_id": f"synth_{i:04d}",
            "n_steps": int(n_steps),
            "ground_truth_scores": [float(v) for v in gt],
            "ciu_scores": [float(v) for v in ciu],
            "necessity_scores": [float(v) for v in nec],
        })

    return samples


def run_synthetic(seed: int = 42) -> dict[str, Any]:
    samples = _generate_synthetic_ranking_data(n_samples=200, seed=seed)
    total_steps = sum(s["n_steps"] for s in samples)

    all_spearman: list[float] = []
    all_kendall: list[float] = []
    all_ndcg3: list[float] = []
    all_ndcg5: list[float] = []

    for sample in samples:
        ciu = sample["ciu_scores"]
        nec = sample["necessity_scores"]
        gt = sample["ground_truth_scores"]

        weights = simple_average_baseline(ciu, nec)
        metrics = compute_ranking_metrics(weights, gt, k_values=(3, 5))

        all_spearman.append(metrics["spearman_rho"])
        all_kendall.append(metrics["kendall_tau"])
        all_ndcg3.append(metrics["ndcg_3"])
        all_ndcg5.append(metrics["ndcg_5"])

    return {
        "benchmark": "synthetic",
        "n_samples": len(samples),
        "n_steps": total_steps,
        "seed": seed,
        "mean_spearman_rho": float(np.mean(all_spearman)),
        "std_spearman_rho": float(np.std(all_spearman, ddof=1)),
        "mean_kendall_tau": float(np.mean(all_kendall)),
        "std_kendall_tau": float(np.std(all_kendall, ddof=1)),
        "mean_ndcg_3": float(np.mean(all_ndcg3)),
        "std_ndcg_3": float(np.std(all_ndcg3, ddof=1)),
        "mean_ndcg_5": float(np.mean(all_ndcg5)),
        "std_ndcg_5": float(np.std(all_ndcg5, ddof=1)),
    }


# ---------------------------------------------------------------------------
# PRM800K benchmark
# ---------------------------------------------------------------------------

def run_prm800k() -> dict[str, Any]:
    import run_scfma_variants_prm800k as variants

    config_path = variants.DEFAULT_CONFIG
    config = variants.load_config(config_path)

    print("Loading PRM800K data (streaming from source, ~456MB total)...")
    pool_rows = variants.load_pool_rows(config)
    pool_samples = variants.build_samples(
        pool_rows, split_name="pool",
        row_start=int(config["data"]["pool"]["start_row"]),
    )
    dev_samples, locked_samples = variants.split_samples(
        pool_samples,
        config["data"]["split_strategy"],
    )
    print(
        f"Pool: {len(pool_samples)}, Dev: {len(dev_samples)}, "
        f"Locked: {len(locked_samples)}"
    )

    print("Fitting w_struct model on dev split...")
    model = variants.fit_w_struct_model(
        dev_samples,
        ridge_lambda=float(config["model"]["ridge_lambda"]),
    )

    all_spearman: list[float] = []
    all_ndcg25: list[float] = []
    raw_spearman: list[float] = []
    necessity_spearman: list[float] = []
    total_steps = 0

    print(f"Computing simple_average on {len(locked_samples)} locked samples...")
    for idx, sample in enumerate(locked_samples):
        ciu = list(sample.raw_local_utility)
        necessity = variants.compute_necessity_vector(sample, model).tolist()
        labels = list(sample.labels)
        n_steps = len(labels)
        total_steps += n_steps

        weights = simple_average_baseline(ciu, necessity)
        pred_arr = np.array(weights, dtype=float)
        gt_arr = np.array(labels, dtype=float)

        rho, _ = stats.spearmanr(pred_arr, gt_arr)
        rho_val = float(rho) if not np.isnan(rho) else 0.0
        all_spearman.append(rho_val)

        raw_rho, _ = stats.spearmanr(np.array(ciu, dtype=float), gt_arr)
        raw_spearman.append(float(raw_rho) if not np.isnan(raw_rho) else 0.0)

        necessity_rho, _ = stats.spearmanr(np.array(necessity, dtype=float), gt_arr)
        necessity_spearman.append(
            float(necessity_rho) if not np.isnan(necessity_rho) else 0.0
        )

        ndcg_val = ndcg_at_budget(weights, labels, keep_fraction=0.25)
        all_ndcg25.append(ndcg_val)

        if (idx + 1) % 1000 == 0:
            print(f"  Processed {idx + 1}/{len(locked_samples)} samples...")

    return {
        "benchmark": "prm800k",
        "n_samples": len(locked_samples),
        "n_steps": total_steps,
        "mean_spearman_rho": float(np.mean(all_spearman)),
        "std_spearman_rho": float(np.std(all_spearman, ddof=1)),
        "component_mean_spearman_rho": {
            "raw_local_utility": float(np.mean(raw_spearman)),
            "structural_necessity": float(np.mean(necessity_spearman)),
        },
        "mean_ndcg_at_25": float(np.mean(all_ndcg25)),
        "std_ndcg_at_25": float(np.std(all_ndcg25, ddof=1)),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "method": "simple_average",
        "description": (
            "Element-wise mean of normalized CIU and structural necessity, "
            "simplex-normalized to step-importance weights."
        ),
    }

    if args.benchmark in ("synthetic", "all"):
        print("=" * 60)
        print("Running simple_average on SYNTHETIC benchmark...")
        started = time.time()
        results["synthetic_metrics"] = run_synthetic(seed=args.seed)
        results["synthetic_metrics"]["elapsed_seconds"] = round(time.time() - started, 2)
        print(f"  Spearman rho: {results['synthetic_metrics']['mean_spearman_rho']:.4f}")
        print(f"  Kendall tau:  {results['synthetic_metrics']['mean_kendall_tau']:.4f}")
        print(f"  NDCG@3:       {results['synthetic_metrics']['mean_ndcg_3']:.4f}")
        print(f"  NDCG@5:       {results['synthetic_metrics']['mean_ndcg_5']:.4f}")

    if args.benchmark in ("prm800k", "all"):
        print("=" * 60)
        print("Running simple_average on PRM800K benchmark...")
        started = time.time()
        results["prm800k_metrics"] = run_prm800k()
        results["prm800k_metrics"]["elapsed_seconds"] = round(time.time() - started, 2)
        print(f"  Spearman rho: {results['prm800k_metrics']['mean_spearman_rho']:.4f}")
        print(f"  NDCG@25%:     {results['prm800k_metrics']['mean_ndcg_at_25']:.4f}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
