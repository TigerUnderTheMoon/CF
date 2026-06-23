"""S1: Efficiency benchmark — wall-clock time per ranking method.

Times each ranking method on the synthetic benchmark (seed 42, 200 samples).
Reports mean wall-clock per sample and total wall-clock per method.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fma.ranking import rank_steps_by_method

SEED = 42
N_SAMPLES = 200
METHODS = [
    "scfma_qp",
    "scfma_ridge",
    "scfma_projection",
    "raw_ciu",
    "random",
    "span_length",
    "relative_position",
]
N_REPEATS = 3  # Repeat to get stable timing


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
            "span_lengths": [10] * n_steps,
            "step_indices": list(range(n_steps)),
        })
    return samples


def time_method(samples: list[dict], method: str, n_repeats: int = 3) -> dict:
    """Time a single method across all samples, repeated for stability."""
    times_per_repeat = []
    for _ in range(n_repeats):
        t0 = time.perf_counter()
        n_processed = 0
        for sample in samples:
            ciu = sample["ciu_scores"]
            nec = sample["necessity_scores"]
            R = sample["redundancy_matrix"]
            bot = set(sample["bottleneck_indices"])
            try:
                scores = rank_steps_by_method(
                    method, ciu, nec, R, bot,
                    sample_id=sample["sample_id"],
                    span_lengths=sample["span_lengths"],
                    step_indices=sample["step_indices"],
                    seed=42,
                )
                n_processed += 1
            except Exception:
                continue
        t1 = time.perf_counter()
        times_per_repeat.append(t1 - t0)

    total_steps = sum(s["n_steps"] for s in samples)
    return {
        "method": method,
        "n_samples": len(samples),
        "n_processed": n_processed,
        "n_total_steps": total_steps,
        "mean_wall_clock_s": float(np.mean(times_per_repeat)),
        "std_wall_clock_s": float(np.std(times_per_repeat, ddof=1)) if len(times_per_repeat) > 1 else 0.0,
        "min_wall_clock_s": float(np.min(times_per_repeat)),
        "max_wall_clock_s": float(np.max(times_per_repeat)),
        "per_sample_ms": float(np.mean(times_per_repeat) / len(samples) * 1000),
        "per_step_ms": float(np.mean(times_per_repeat) / total_steps * 1000) if total_steps > 0 else 0.0,
        "raw_times": times_per_repeat,
    }


def main() -> None:
    print("=" * 90)
    print("S1: Efficiency Benchmark — Wall-Clock Time Per Ranking Method")
    print("=" * 90)
    print(f"\nSeed: {SEED}, Samples: {N_SAMPLES}, Repeats: {N_REPEATS}")

    samples = generate_synthetic_data(seed=SEED, n_samples=N_SAMPLES)
    total_steps = sum(s["n_steps"] for s in samples)
    print(f"Generated {len(samples)} samples, {total_steps} total steps\n")

    results = {}
    for method in METHODS:
        print(f"Timing {method}...", end=" ", flush=True)
        r = time_method(samples, method, n_repeats=N_REPEATS)
        results[method] = r
        print(f"{r['mean_wall_clock_s']:.4f}s ± {r['std_wall_clock_s']:.4f}s "
              f"({r['per_sample_ms']:.3f} ms/sample, {r['per_step_ms']:.3f} ms/step)")

    # Summary table
    print("\n" + "=" * 90)
    print("Efficiency Results Summary")
    print("=" * 90)
    print(f"\n{'Method':<25} {'Total (s)':>10} {'Std (s)':>10} {'Per Sample (ms)':>16} {'Per Step (ms)':>14} {'Rel to QP':>11}")
    print("-" * 90)

    qp_time = results["scfma_qp"]["mean_wall_clock_s"]
    for method in METHODS:
        r = results[method]
        rel = r["mean_wall_clock_s"] / qp_time if qp_time > 0 else 0.0
        print(f"{method:<25} {r['mean_wall_clock_s']:>10.4f} {r['std_wall_clock_s']:>10.4f} "
              f"{r['per_sample_ms']:>16.3f} {r['per_step_ms']:>14.3f} {rel:>10.2f}x")

    # Speed ranking
    print("\n## Speed Ranking (fastest to slowest)\n")
    sorted_methods = sorted(results.items(), key=lambda x: x[1]["mean_wall_clock_s"])
    for rank, (method, r) in enumerate(sorted_methods, 1):
        print(f"  {rank}. {method:<25} {r['mean_wall_clock_s']:.4f}s")

    # Save
    summary = {
        "experiment": "S1_efficiency_benchmark",
        "seed": SEED,
        "n_samples": N_SAMPLES,
        "n_total_steps": total_steps,
        "n_repeats": N_REPEATS,
        "methods": results,
    }
    out_path = PROJECT_ROOT / "outputs" / "s1_efficiency_benchmark.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSummary saved to {out_path}")


if __name__ == "__main__":
    main()
