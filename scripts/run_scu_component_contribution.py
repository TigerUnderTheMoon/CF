"""Reviewer V2 component-contribution analysis for the SCU objective."""

from __future__ import annotations

import argparse
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


DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "scu_component_contribution"
CONFIGS = {
    "full_scu": {
        "report_name": "Full SCU",
        "params": {"alpha": 1.0, "beta": 0.5, "gamma": 0.2, "delta": 0.1},
    },
    "no_fidelity": {
        "report_name": "Contribution of fidelity anchor",
        "params": {"alpha": 0.0, "beta": 0.5, "gamma": 0.2, "delta": 0.1},
    },
    "no_structure": {
        "report_name": "Contribution of graph necessity",
        "params": {"alpha": 1.0, "beta": 0.0, "gamma": 0.2, "delta": 0.1},
    },
    "no_redundancy": {
        "report_name": "Contribution of redundancy control",
        "params": {"alpha": 1.0, "beta": 0.5, "gamma": 0.0, "delta": 0.1},
    },
    "no_bottleneck": {
        "report_name": "Contribution of bottleneck protection",
        "params": {"alpha": 1.0, "beta": 0.5, "gamma": 0.2, "delta": 0.0},
    },
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--samples-per-seed", type=int, default=200)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    timer = Timer.start()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    seed_results: dict[str, list[dict[str, float]]] = {name: [] for name in CONFIGS}
    per_seed_tables: list[dict[str, Any]] = []
    for seed in SEED_LIST:
        samples = generate_synthetic_data(seed=seed, n_samples=args.samples_per_seed)
        seed_row: dict[str, Any] = {"seed": seed, "n_samples": len(samples)}
        for name, config in CONFIGS.items():
            metrics = run_config(samples, **config["params"])
            seed_results[name].append(metrics)
            seed_row[name] = metrics
        per_seed_tables.append(seed_row)

    full_mean = mean([row["spearman"] for row in seed_results["full_scu"]])
    variants: dict[str, dict[str, Any]] = {}
    for name, config in CONFIGS.items():
        rows = seed_results[name]
        spearman_values = [row["spearman"] for row in rows]
        kendall_values = [row["kendall"] for row in rows]
        convergence_values = [row["convergence_rate"] for row in rows]
        spearman_mean = mean(spearman_values)
        full_values = [row["spearman"] for row in seed_results["full_scu"]]
        variants[name] = {
            "report_name": config["report_name"],
            "params": config["params"],
            "spearman_mean": spearman_mean,
            "spearman_std": std(spearman_values),
            "spearman_bootstrap_ci": bootstrap_ci(spearman_values),
            "kendall_mean": mean(kendall_values),
            "kendall_std": std(kendall_values),
            "kendall_bootstrap_ci": bootstrap_ci(kendall_values),
            "convergence_rate": mean(convergence_values),
            "delta_spearman_vs_full": spearman_mean - full_mean,
            "effect_size_vs_full": effect_size(spearman_values, full_values),
        }

    report = {
        **common_metadata(
            output_dir=args.output_dir,
            evidence_level="mechanism_ablation",
            source_artifacts=["synthetic_component_contribution_fixture"],
        ),
        "experiment": "scu_component_contribution",
        "title": "Component Contribution of the SCU Objective",
        "samples_per_seed": args.samples_per_seed,
        "elapsed_seconds": timer.elapsed(),
        "variants": variants,
        "per_seed": per_seed_tables,
    }
    write_json(args.output_dir / "scu_component_contribution.json", report)
    write_markdown(
        args.output_dir / "scu_component_contribution.md",
        render_markdown(report),
    )
    print(f"Wrote {args.output_dir / 'scu_component_contribution.json'}")
    print(f"Wrote {args.output_dir / 'scu_component_contribution.md'}")


def generate_synthetic_data(seed: int, n_samples: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    samples: list[dict[str, Any]] = []
    for index in range(n_samples):
        n_steps = int(rng.integers(3, 8))
        gt = np.abs(rng.normal(0.5, 0.3, n_steps))
        gt = gt / np.sum(gt)
        ciu = np.clip(gt + rng.normal(0, 0.15, n_steps), 0.0, 1.0)
        necessity = np.clip(gt + rng.normal(0, 0.2, n_steps), 0.0, 1.0)
        for step in range(n_steps - 1):
            if rng.random() < 0.3:
                necessity[step] = 0.0
        redundancy = np.zeros((n_steps, n_steps), dtype=float)
        for left in range(n_steps):
            for right in range(left + 1, n_steps):
                if rng.random() < 0.15:
                    value = float(rng.random() * 0.5 + 0.3)
                    redundancy[left, right] = value
                    redundancy[right, left] = value
        bottlenecks = [
            step
            for step in range(n_steps)
            if necessity[step] > 0.7 and gt[step] > 0.5
        ]
        samples.append(
            {
                "sample_id": f"synth_{seed}_{index:04d}",
                "ground_truth": gt,
                "ciu": ciu,
                "necessity": necessity,
                "redundancy": redundancy,
                "bottlenecks": bottlenecks,
            }
        )
    return samples


def run_config(samples: Sequence[Mapping[str, Any]], **params: float) -> dict[str, float]:
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
            **params,
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


def bootstrap_ci(values: Sequence[float], *, seed: int = 42, n_bootstrap: int = 1000) -> dict[str, float]:
    if not values:
        return {"ci_lower": 0.0, "ci_upper": 0.0}
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    means = []
    for _ in range(n_bootstrap):
        sample = rng.choice(arr, size=len(arr), replace=True)
        means.append(float(np.mean(sample)))
    return {
        "ci_lower": float(np.percentile(means, 2.5)),
        "ci_upper": float(np.percentile(means, 97.5)),
    }


def effect_size(values: Sequence[float], baseline: Sequence[float]) -> float:
    if not values or not baseline:
        return 0.0
    diffs = np.asarray(values, dtype=float) - np.asarray(baseline, dtype=float)
    if len(diffs) < 2:
        return float(np.mean(diffs))
    denom = float(np.std(diffs, ddof=1))
    if denom == 0.0:
        return 0.0
    return float(np.mean(diffs) / denom)


def render_markdown(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "# Component Contribution of the SCU Objective",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Evidence level: `{report['evidence_level']}`",
        f"- Seeds: `{', '.join(str(seed) for seed in report['seed_list'])}`",
        "",
        "| Variant | Report Name | Spearman mean+-std | Spearman CI | Kendall mean+-std | Effect Size | Convergence | Delta vs Full |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in report["variants"].items():
        ci = metrics["spearman_bootstrap_ci"]
        lines.append(
            f"| `{name}` | {metrics['report_name']} | "
            f"{metrics['spearman_mean']:.4f}+-{metrics['spearman_std']:.4f} | "
            f"[{ci['ci_lower']:.4f}, {ci['ci_upper']:.4f}] | "
            f"{metrics['kendall_mean']:.4f}+-{metrics['kendall_std']:.4f} | "
            f"{metrics['effect_size_vs_full']:.4f} | "
            f"{metrics['convergence_rate']:.3f} | "
            f"{metrics['delta_spearman_vs_full']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This is mechanism-ablation evidence for SCU component contribution, not external validation.",
        ]
    )
    return lines


if __name__ == "__main__":
    main()
