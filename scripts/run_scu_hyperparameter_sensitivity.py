"""Gamma/delta sensitivity for the SCU structural-stress benchmark.

This script sweeps the QP-only redundancy penalty (gamma) and bottleneck
log-barrier (delta) on the existing structural stress-test generator. It is a
supplementary robustness diagnostic: it checks whether the selected QP
diagnostic default is stable across nearby hyperparameters. It is not positive
external validation and does not change the Ridge recommendation for
strong-fidelity real-data settings.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from fma.calibration import BottleneckConstraint, scfma_calibrate  # noqa: E402
from reviewer_v2_common import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    SEED_LIST,
    Timer,
    common_metadata,
    mean,
    safe_corr,
    std,
    write_json,
    write_markdown,
)
from run_scu_stress_test import (  # noqa: E402
    BOTTLENECK_BOOST,
    FIDELITY_BLEND,
    REDUNDANCY_DEMOTE,
    generate_structural_synthetic_data,
)


DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "scu_hyperparameter_sensitivity"
GAMMA_VALUES = [0.0, 0.1, 0.2, 0.5, 0.8]
DELTA_VALUES = [0.0, 0.05, 0.1, 0.2, 0.4]
DEFAULT_GAMMA = 0.2
DEFAULT_DELTA = 0.1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--samples-per-seed", type=int, default=200)
    parser.add_argument("--redundancy-demote", type=float, default=REDUNDANCY_DEMOTE)
    parser.add_argument("--bottleneck-boost", type=float, default=BOTTLENECK_BOOST)
    parser.add_argument("--fidelity-blend", type=float, default=FIDELITY_BLEND)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    timer = Timer.start()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    samples_by_seed = {
        seed: generate_structural_synthetic_data(
            seed=seed,
            n_samples=args.samples_per_seed,
            redundancy_demote=args.redundancy_demote,
            bottleneck_boost=args.bottleneck_boost,
            fidelity_blend=args.fidelity_blend,
        )
        for seed in SEED_LIST
    }

    grid: list[dict[str, Any]] = []
    for gamma in GAMMA_VALUES:
        for delta in DELTA_VALUES:
            seed_rows = [
                run_config(samples, gamma=gamma, delta=delta)
                for samples in samples_by_seed.values()
            ]
            grid.append(summarize_grid_cell(gamma, delta, seed_rows))

    default_row = next(
        row
        for row in grid
        if row["gamma"] == DEFAULT_GAMMA and row["delta"] == DEFAULT_DELTA
    )
    default_spearman = float(default_row["spearman_mean"])
    for row in grid:
        row["delta_spearman_vs_default"] = float(
            row["spearman_mean"] - default_spearman
        )

    report = {
        **common_metadata(
            output_dir=args.output_dir,
            evidence_level="mechanism_ablation",
            source_artifacts=["synthetic_structural_stress_test_fixture"],
        ),
        "experiment": "scu_hyperparameter_sensitivity",
        "title": "SCU Gamma/Delta Hyperparameter Sensitivity",
        "samples_per_seed": args.samples_per_seed,
        "elapsed_seconds": timer.elapsed(),
        "gamma_values": GAMMA_VALUES,
        "delta_values": DELTA_VALUES,
        "fixed_params": {"alpha": 1.0, "beta": 0.5},
        "recommended_default": {
            "gamma": DEFAULT_GAMMA,
            "delta": DEFAULT_DELTA,
            "selection_role": "synthetic structural-stress default for QP diagnostics",
        },
        "label_design": {
            "redundancy_demote": args.redundancy_demote,
            "bottleneck_boost": args.bottleneck_boost,
            "fidelity_blend": args.fidelity_blend,
        },
        "grid": grid,
        "interpretation": (
            "The gamma/delta grid is a supplementary QP sensitivity diagnostic. "
            "It checks that the structural-stress result is not a single-point "
            "hyperparameter artifact. It is not positive external validation and "
            "does not make QP the default real-data variant."
        ),
    }

    write_json(args.output_dir / "scu_hyperparameter_sensitivity.json", report)
    write_markdown(
        args.output_dir / "scu_hyperparameter_sensitivity.md",
        render_markdown(report),
    )
    write_csv(args.output_dir / "gamma_delta_grid.csv", grid)
    print(f"Wrote {args.output_dir / 'scu_hyperparameter_sensitivity.json'}")
    print(f"Wrote {args.output_dir / 'scu_hyperparameter_sensitivity.md'}")
    print(f"Wrote {args.output_dir / 'gamma_delta_grid.csv'}")


def run_config(
    samples: Sequence[Mapping[str, Any]], *, gamma: float, delta: float
) -> dict[str, float]:
    spearman_values: list[float] = []
    kendall_values: list[float] = []
    converged = 0
    total = 0
    for sample in samples:
        total += 1
        result = scfma_calibrate(
            np.asarray(sample["ciu"], dtype=float),
            np.asarray(sample["necessity"], dtype=float),
            np.asarray(sample["redundancy"], dtype=float),
            bottleneck_constraints=[
                BottleneckConstraint(int(index), 0.01)
                for index in sample["bottlenecks"]
            ],
            sample_id=str(sample["sample_id"]),
            alpha=1.0,
            beta=0.5,
            gamma=gamma,
            delta=delta,
        )
        if result.converged:
            converged += 1
        weights = (
            list(result.weights[0].weights)
            if result.weights
            else [1.0 / len(sample["ground_truth"])] * len(sample["ground_truth"])
        )
        gt = [float(value) for value in sample["ground_truth"]]
        spearman_values.append(safe_corr(weights, gt, "spearman"))
        kendall_values.append(safe_corr(weights, gt, "kendall"))
    return {
        "spearman": mean(spearman_values),
        "kendall": mean(kendall_values),
        "convergence_rate": float(converged / total) if total else 0.0,
    }


def summarize_grid_cell(
    gamma: float, delta: float, seed_rows: Sequence[Mapping[str, float]]
) -> dict[str, Any]:
    spearman_values = [float(row["spearman"]) for row in seed_rows]
    kendall_values = [float(row["kendall"]) for row in seed_rows]
    convergence_values = [float(row["convergence_rate"]) for row in seed_rows]
    return {
        "gamma": gamma,
        "delta": delta,
        "spearman_mean": mean(spearman_values),
        "spearman_std": std(spearman_values),
        "kendall_mean": mean(kendall_values),
        "kendall_std": std(kendall_values),
        "convergence_rate": mean(convergence_values),
        "delta_spearman_vs_default": 0.0,
    }


def render_markdown(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "# SCU Hyperparameter Sensitivity",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Evidence level: `{report['evidence_level']}`",
        f"- Seeds: `{', '.join(str(seed) for seed in report['seed_list'])}`",
        f"- Samples per seed: `{report['samples_per_seed']}`",
        "- Interpretation: this is not positive external validation and does not "
        "make QP the default real-data variant.",
        "",
        "## Gamma/Delta Grid",
        "",
        "| gamma | delta | Spearman mean | Spearman std | Kendall mean | Convergence | Delta vs default |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["grid"]:
        lines.append(
            f"| {row['gamma']:.2f} | {row['delta']:.2f} | "
            f"{row['spearman_mean']:.4f} | {row['spearman_std']:.4f} | "
            f"{row['kendall_mean']:.4f} | {row['convergence_rate']:.3f} | "
            f"{row['delta_spearman_vs_default']:+.4f} |"
        )

    default = report["recommended_default"]
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "The selected diagnostic default "
            f"($\\gamma={default['gamma']}$, $\\delta={default['delta']}$) "
            "is used for synthetic structural-stress QP diagnostics. The grid "
            "shows whether the stress-test behavior is robust to nearby "
            "redundancy and bottleneck weights. The real-data recommendation "
            "remains Ridge when a strong learned fidelity signal is available; "
            "QP is reserved for high-structure-conflict settings.",
        ]
    )
    return lines


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "gamma",
        "delta",
        "spearman_mean",
        "spearman_std",
        "kendall_mean",
        "kendall_std",
        "convergence_rate",
        "delta_spearman_vs_default",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fieldnames})


if __name__ == "__main__":
    main()
