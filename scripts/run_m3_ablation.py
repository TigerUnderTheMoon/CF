"""M3: Ablation study — each SCU constraint term's contribution to ranking.

Runs SC-FMA QP with 4 configurations on the synthetic benchmark (seed 42):
  1. Full: alpha=1.0, beta=0.5, gamma=0.2, delta=0.1
  2. -redundancy: gamma=0.0 (disable redundancy penalty)
  3. -bottleneck: delta=0.0 (disable bottleneck protection)
  4. -structure: beta=0.0 (disable structural necessity)

Outputs Spearman rho for each config, showing each term's contribution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats as scipy_stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fma.calibration import scfma_calibrate
from fma.calibration.types import BottleneckConstraint

SEED = 42
N_SAMPLES = 200
CONFIGS = {
    "full": {"alpha": 1.0, "beta": 0.5, "gamma": 0.2, "delta": 0.1},
    "minus_redundancy": {"alpha": 1.0, "beta": 0.5, "gamma": 0.0, "delta": 0.1},
    "minus_bottleneck": {"alpha": 1.0, "beta": 0.5, "gamma": 0.2, "delta": 0.0},
    "minus_structure": {"alpha": 1.0, "beta": 0.0, "gamma": 0.2, "delta": 0.1},
    "minus_fidelity": {"alpha": 0.0, "beta": 0.5, "gamma": 0.2, "delta": 0.1},
}


def generate_synthetic_data(seed: int = 42, n_samples: int = 200) -> list[dict]:
    """Same generation logic as run_downstream_ranking.py."""
    rng = np.random.default_rng(seed)
    samples = []
    for i in range(n_samples):
        n_steps = int(rng.integers(3, 8))
        gt = np.abs(rng.normal(0.5, 0.3, n_steps))
        gt = gt / np.sum(gt)
        ciu = gt + rng.normal(0, 0.15, n_steps)
        ciu = np.clip(ciu, 0.0, 1.0)
        nec = gt + rng.normal(0, 0.2, n_steps)
        nec = np.clip(nec, 0.0, 1.0)
        for j in range(n_steps - 1):
            if rng.random() < 0.3:
                nec[j] = 0.0
        red_mat = np.zeros((n_steps, n_steps))
        for a in range(n_steps):
            for b in range(a + 1, n_steps):
                if rng.random() < 0.15:
                    sim = float(rng.random() * 0.5 + 0.3)
                    red_mat[a, b] = sim
                    red_mat[b, a] = sim
        bottlenecks = set()
        for j in range(n_steps):
            if nec[j] > 0.7 and gt[j] > 0.5:
                bottlenecks.add(j)
        samples.append({
            "sample_id": f"synth_{i:04d}",
            "n_steps": n_steps,
            "ground_truth_scores": gt.tolist(),
            "ciu_scores": ciu.tolist(),
            "necessity_scores": nec.tolist(),
            "redundancy_matrix": red_mat,
            "bottleneck_indices": sorted(bottlenecks),
        })
    return samples


def run_ablation_config(
    samples: list[dict],
    alpha: float,
    beta: float,
    gamma: float,
    delta: float,
) -> dict:
    """Run SC-FMA QP with given parameters on all samples, return metrics."""
    spearman_vals = []
    kendall_vals = []
    n_total_steps = 0

    for sample in samples:
        ciu = np.array(sample["ciu_scores"])
        nec = np.array(sample["necessity_scores"])
        gt = sample["ground_truth_scores"]
        R = np.array(sample["redundancy_matrix"])
        n = len(ciu)
        n_total_steps += n

        bottlenecks = [
            BottleneckConstraint(node_index=i, floor_weight=0.01)
            for i in sample["bottleneck_indices"]
        ]

        result = scfma_calibrate(
            ciu, nec, R,
            bottleneck_constraints=bottlenecks,
            sample_id=sample["sample_id"],
            alpha=alpha, beta=beta, gamma=gamma, delta=delta,
        )

        weights = result.weights[0].to_list() if result.weights else [1.0 / n] * n

        # Compute Spearman and Kendall
        if len(set(weights)) > 1 and len(set(gt)) > 1:
            rho, _ = scipy_stats.spearmanr(weights, gt)
            tau, _ = scipy_stats.kendalltau(weights, gt)
            spearman_vals.append(float(rho))
            kendall_vals.append(float(tau))

    return {
        "n_samples": len(samples),
        "n_total_steps": n_total_steps,
        "mean_spearman": float(np.mean(spearman_vals)) if spearman_vals else 0.0,
        "std_spearman": float(np.std(spearman_vals, ddof=1)) if len(spearman_vals) > 1 else 0.0,
        "mean_kendall": float(np.mean(kendall_vals)) if kendall_vals else 0.0,
        "n_valid": len(spearman_vals),
    }


def main() -> None:
    print("=" * 80)
    print("M3: Ablation Study — SCU Constraint Term Contributions")
    print("=" * 80)
    print(f"\nSeed: {SEED}, Samples: {N_SAMPLES}")

    samples = generate_synthetic_data(seed=SEED, n_samples=N_SAMPLES)
    print(f"Generated {len(samples)} samples, {sum(s['n_steps'] for s in samples)} total steps")

    results = {}
    for config_name, params in CONFIGS.items():
        print(f"\nRunning config: {config_name} ({params})...")
        metrics = run_ablation_config(samples, **params)
        results[config_name] = {**metrics, "params": params}
        print(f"  Spearman ρ = {metrics['mean_spearman']:.4f} ± {metrics['std_spearman']:.4f}")
        print(f"  Kendall τ  = {metrics['mean_kendall']:.4f}")
        print(f"  Converged samples: {metrics['n_valid']}/{metrics['n_samples']}")

    # Summary table
    print("\n" + "=" * 80)
    print("Ablation Results Summary")
    print("=" * 80)
    print(f"\n{'Config':<25} {'Spearman ρ':>12} {'Std':>8} {'Kendall τ':>12} {'Δρ vs Full':>12}")
    print("-" * 75)
    full_rho = results["full"]["mean_spearman"]
    for config_name, m in results.items():
        delta = m["mean_spearman"] - full_rho
        print(f"{config_name:<25} {m['mean_spearman']:>12.4f} {m['std_spearman']:>8.4f} {m['mean_kendall']:>12.4f} {delta:>+12.4f}")

    # Contribution ranking
    print("\n## Term Contribution Ranking (by Spearman drop when removed)\n")
    drops = []
    for config_name in ["minus_redundancy", "minus_bottleneck", "minus_structure", "minus_fidelity"]:
        drop = full_rho - results[config_name]["mean_spearman"]
        term = config_name.replace("minus_", "")
        drops.append((term, drop, results[config_name]["mean_spearman"]))

    drops.sort(key=lambda x: -x[1])
    print(f"{'Term Removed':<20} {'Spearman ρ':>12} {'Drop from Full':>15} {'Contribution':>15}")
    print("-" * 65)
    for term, drop, rho in drops:
        contribution = "Largest" if drop == drops[0][1] else ""
        print(f"{term:<20} {rho:>12.4f} {drop:>15.4f} {contribution:>15}")

    # Save
    summary = {
        "experiment": "M3_ablation_study",
        "seed": SEED,
        "n_samples": N_SAMPLES,
        "configs": results,
        "full_spearman": full_rho,
        "term_contributions": [
            {"term": t, "drop": d, "spearman_without": r} for t, d, r in drops
        ],
    }
    out_path = PROJECT_ROOT / "outputs" / "m3_ablation_study.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSummary saved to {out_path}")


if __name__ == "__main__":
    main()
