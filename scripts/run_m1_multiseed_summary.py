"""M1: Collect 5-seed synthetic ranking results into a summary table.

Reads outputs/downstream_ranking/seed_{42,123,456,789,1024}/comparison_report.json
and produces a manuscript-ready multi-seed variance table.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEEDS = [42, 123, 456, 789, 1024]
BASE_DIR = PROJECT_ROOT / "outputs" / "downstream_ranking"

# Methods that are NOT stubs (others fall through to raw_ciu default)
REAL_METHODS = [
    "scfma_qp",
    "scfma_ridge",
    "scfma_projection",
    "raw_ciu",
    "random",
    "span_length",
    "relative_position",
]


def main() -> None:
    results: dict[int, dict] = {}
    for seed in SEEDS:
        report_path = BASE_DIR / f"seed_{seed}" / "comparison_report.json"
        if not report_path.exists():
            print(f"WARNING: {report_path} not found, skipping seed {seed}")
            continue
        data = json.loads(report_path.read_text(encoding="utf-8"))
        results[seed] = data

    if not results:
        print("ERROR: No results found")
        return

    # Collect per-method Spearman across seeds
    method_seeds: dict[str, list[float]] = {m: [] for m in REAL_METHODS}
    n_steps_list: list[int] = []
    for seed, data in results.items():
        n_steps_list.append(data["n_total_steps"])
        rankings = data["method_rankings"]
        for m in REAL_METHODS:
            if m in rankings:
                method_seeds[m].append(rankings[m])

    # Print summary table
    print("\n" + "=" * 90)
    print("M1: Multi-Seed Synthetic Ranking Variance (5 seeds)")
    print("=" * 90)
    print(f"\nSeeds: {SEEDS}")
    print(f"Samples per seed: {results[SEEDS[0]]['n_samples']}")
    print(f"Steps per seed: {n_steps_list} (mean={np.mean(n_steps_list):.0f}, std={np.std(n_steps_list):.0f})")

    print(f"\n{'Method':<25} {'Mean ρ':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'Range':>8}")
    print("-" * 75)
    for m in REAL_METHODS:
        vals = method_seeds[m]
        if vals:
            mean_v = np.mean(vals)
            std_v = np.std(vals, ddof=1) if len(vals) > 1 else 0.0
            min_v = np.min(vals)
            max_v = np.max(vals)
            print(f"{m:<25} {mean_v:>8.4f} {std_v:>8.4f} {min_v:>8.4f} {max_v:>8.4f} {max_v - min_v:>8.4f}")

    # Per-seed detail
    print(f"\n{'Method':<25}", end="")
    for s in SEEDS:
        print(f"  seed={s}", end="")
    print()
    print("-" * 90)
    for m in REAL_METHODS:
        print(f"{m:<25}", end="")
        for s in SEEDS:
            if s in results and m in results[s]["method_rankings"]:
                print(f"  {results[s]['method_rankings'][m]:>9.4f}", end="")
            else:
                print(f"  {'N/A':>9}", end="")
        print()

    # Best method per seed
    print(f"\n{'Seed':<10} {'Best Method':<20} {'Best ρ':>10}")
    print("-" * 45)
    for s in SEEDS:
        if s in results:
            best = results[s].get("best_method", "N/A")
            best_rho = results[s].get("best_spearman", 0.0)
            print(f"{s:<10} {best:<20} {best_rho:>10.4f}")

    # SC-FMA QP vs Raw CIU gap per seed
    print(f"\n{'Seed':<10} {'QP ρ':>10} {'Raw CIU ρ':>12} {'Gap':>10} {'QP wins?':>10}")
    print("-" * 55)
    for s in SEEDS:
        if s in results:
            qp = results[s]["method_rankings"].get("scfma_qp", 0)
            raw = results[s]["method_rankings"].get("raw_ciu", 0)
            gap = qp - raw
            wins = "YES" if gap > 0 else "NO"
            print(f"{s:<10} {qp:>10.4f} {raw:>12.4f} {gap:>10.4f} {wins:>10}")

    # Save summary JSON
    summary = {
        "experiment": "M1_multiseed_synthetic_ranking",
        "seeds": SEEDS,
        "n_samples": results[SEEDS[0]]["n_samples"],
        "n_steps_per_seed": n_steps_list,
        "method_summary": {},
        "per_seed_results": {},
    }
    for m in REAL_METHODS:
        vals = method_seeds[m]
        summary["method_summary"][m] = {
            "mean_spearman": float(np.mean(vals)),
            "std_spearman": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
            "min_spearman": float(np.min(vals)),
            "max_spearman": float(np.max(vals)),
            "per_seed": vals,
        }
    for s in SEEDS:
        if s in results:
            summary["per_seed_results"][str(s)] = {
                "best_method": results[s].get("best_method"),
                "best_spearman": results[s].get("best_spearman"),
                "method_rankings": results[s].get("method_rankings"),
                "n_total_steps": results[s].get("n_total_steps"),
            }

    summary_path = BASE_DIR / "m1_multiseed_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
