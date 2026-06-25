"""SCU stress-test ablation: component contribution when proxy labels encode structure.

This script mirrors ``run_scu_component_contribution.py`` but generates synthetic
traces whose proxy labels *depend on* redundancy and bottleneck structure. The
original component-contribution benchmark uses structure-independent labels, so
the redundancy penalty and bottleneck log-barrier contribute ~0 to ranking
metrics there. This stress-test constructs the regime those terms are designed
for: the ground-truth label rewards redundancy-awareness (only one of a
redundant pair should be weighted highly) and bottleneck-protection (bottleneck
steps should stay visible). Under this regime, removing each structural term is
expected to degrade ranking, confirming the terms contribute when labels encode
structural preference.

Evidence level: ``mechanism_ablation``. Claim boundary: ``synthetic_calibration_only``.
"""

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


DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "scu_stress_test"

# Label-coupling strengths. REDUNDANCY_DEMOTE shrinks members of redundant
# pairs; BOTTLENECK_BOOST enlarges bottleneck steps. FIDELITY_BLEND controls how
# much of the structural adjustment leaks into the fidelity input (0 = fidelity
# is a noisy copy of the pre-adjustment base label and is structurally blind; 1
# = fidelity fully tracks the adjusted label and the structural terms add
# little). A low blend keeps fidelity useful but makes the structural terms
# visibly corrective.
REDUNDANCY_DEMOTE = 0.10
BOTTLENECK_BOOST = 2.2
REDUNDANCY_PROB = 0.20  # slightly denser pairs than the original generator
REDUNDANCY_WEIGHT_LOW = 0.3
REDUNDANCY_WEIGHT_HIGH = 0.8
NECESSITY_ZERO_PROB = 0.3
FIDELITY_BLEND = 0.20
STRESS_REDUNDANCY_GAMMA = 0.6

CONFIGS = {
    "full_scu": {
        "report_name": "Full SCU",
        "params": {"alpha": 1.0, "beta": 0.5, "gamma": STRESS_REDUNDANCY_GAMMA, "delta": 0.1},
    },
    "no_fidelity": {
        "report_name": "Contribution of fidelity anchor",
        "params": {"alpha": 0.0, "beta": 0.5, "gamma": STRESS_REDUNDANCY_GAMMA, "delta": 0.1},
    },
    "no_structure": {
        "report_name": "Contribution of graph necessity",
        "params": {"alpha": 1.0, "beta": 0.0, "gamma": STRESS_REDUNDANCY_GAMMA, "delta": 0.1},
    },
    "no_redundancy": {
        "report_name": "Contribution of redundancy control",
        "params": {"alpha": 1.0, "beta": 0.5, "gamma": 0.0, "delta": 0.1},
    },
    "no_bottleneck": {
        "report_name": "Contribution of bottleneck protection",
        "params": {"alpha": 1.0, "beta": 0.5, "gamma": STRESS_REDUNDANCY_GAMMA, "delta": 0.0},
    },
}


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

    seed_results: dict[str, list[dict[str, float]]] = {name: [] for name in CONFIGS}
    per_seed_tables: list[dict[str, Any]] = []
    for seed in SEED_LIST:
        samples = generate_structural_synthetic_data(
            seed=seed,
            n_samples=args.samples_per_seed,
            redundancy_demote=args.redundancy_demote,
            bottleneck_boost=args.bottleneck_boost,
            fidelity_blend=args.fidelity_blend,
        )
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
            source_artifacts=["synthetic_structural_stress_test_fixture"],
        ),
        "claim_boundary": "synthetic_calibration_only",
        "experiment": "scu_stress_test",
        "title": "SCU Component Contribution on a Structural Stress-Test Benchmark",
        "label_design": {
            "redundancy_demote": args.redundancy_demote,
            "bottleneck_boost": args.bottleneck_boost,
            "fidelity_blend": args.fidelity_blend,
            "redundancy_pair_probability": REDUNDANCY_PROB,
            "redundancy_weight_range": [REDUNDANCY_WEIGHT_LOW, REDUNDANCY_WEIGHT_HIGH],
            "description": (
                "Proxy labels reward redundancy-awareness (redundant members "
                "demoted) and bottleneck-protection (bottleneck steps boosted). "
                "The fidelity input is a blend of the adjusted label and the "
                "pre-adjustment base label, so it is the dominant anchor but is "
                "partially structurally blind, leaving the structural terms "
                "corrective work."
            ),
        },
        "samples_per_seed": args.samples_per_seed,
        "elapsed_seconds": timer.elapsed(),
        "variants": variants,
        "per_seed": per_seed_tables,
    }
    write_json(args.output_dir / "scu_stress_test.json", report)
    write_markdown(
        args.output_dir / "scu_stress_test.md",
        render_markdown(report),
    )
    print(f"Wrote {args.output_dir / 'scu_stress_test.json'}")
    print(f"Wrote {args.output_dir / 'scu_stress_test.md'}")


def generate_structural_synthetic_data(
    seed: int,
    n_samples: int,
    redundancy_demote: float,
    bottleneck_boost: float,
    fidelity_blend: float,
) -> list[dict[str, Any]]:
    """Generate traces whose proxy label depends on redundancy/bottleneck structure.

    The label is constructed so the two structural SCU terms have genuine work to
    do (their inputs do not already encode the structural preference):

    - **Redundancy alignment:** steps that participate in redundant pairs are
      marked LOW priority in the label (``redundancy_demote``), but their
      ``ciu`` stays high (a noisy copy of the pre-adjustment base label). The
      redundancy penalty therefore must pull weight *off* duplicate checks;
      with ``no_redundancy`` the weights follow the misleading ``ciu`` and rank
      redundant members too highly, degrading Spearman.

    - **Bottleneck alignment:** bottleneck steps (high structural necessity)
      carry a WEAK local signal (``ciu`` set low, simulating a rare check with
      weak local utility) but are marked HIGH priority in the label
      (``bottleneck_boost``), above low-``ciu`` filler steps. Without the
      bottleneck log-barrier, low-``ciu`` bottlenecks collapse toward zero and
      tie with the filler steps at the bottom of the ranking; the barrier lifts
      them above that tie, matching the label. This is the regime the barrier is
      designed for -- it keeps structurally critical steps visible rather than
      promoting them outright.

    ``necessity`` is a noisy structural diagnostic correlated with the base label
    but independent of the redundancy/bottleneck label adjustments, so the
    fidelity and necessity inputs are informative yet imperfect.
    """
    rng = np.random.default_rng(seed)
    samples: list[dict[str, Any]] = []
    for index in range(n_samples):
        n_steps = int(rng.integers(4, 8))  # slightly longer traces for richer structure
        gt_base = np.abs(rng.normal(0.5, 0.3, n_steps))

        # Structural necessity: noisy copy of base label, with some zeroing.
        necessity = np.clip(gt_base + rng.normal(0, 0.2, n_steps), 0.0, 1.0)
        for step in range(n_steps - 1):
            if rng.random() < NECESSITY_ZERO_PROB:
                necessity[step] = 0.0

        # Redundancy matrix (same construction as the original generator).
        redundancy = np.zeros((n_steps, n_steps), dtype=float)
        for left in range(n_steps):
            for right in range(left + 1, n_steps):
                if rng.random() < REDUNDANCY_PROB:
                    value = float(
                        rng.random() * (REDUNDANCY_WEIGHT_HIGH - REDUNDANCY_WEIGHT_LOW)
                        + REDUNDANCY_WEIGHT_LOW
                    )
                    redundancy[left, right] = value
                    redundancy[right, left] = value

        # Members of redundant pairs are the ones the label demotes. This aligns
        # with the symmetric redundancy penalty in the SCU objective.
        redundant_steps = {
            step
            for left in range(n_steps)
            for right in range(left + 1, n_steps)
            if redundancy[left, right] > 0.0
            for step in (left, right)
        }

        # Bottleneck indicators: high structural necessity (decoupled from gt_base).
        bottlenecks = [step for step in range(n_steps) if necessity[step] > 0.7]

        # Adjust the label to encode structural preference.
        gt = gt_base.copy()
        for step in redundant_steps:
            gt[step] *= redundancy_demote  # redundant steps are low priority
        for step in bottlenecks:
            gt[step] *= bottleneck_boost  # bottlenecks are high priority
        gt = gt / np.sum(gt)

        # Fidelity input: a blend of the adjusted label (tracks the structural
        # preference) and the pre-adjustment base label (structurally blind), plus
        # noise. The blend keeps fidelity the dominant anchor while leaving it
        # partially structurally blind, so the redundancy and bottleneck terms have
        # corrective work to do. Bottlenecks carry a weaker local signal to
        # simulate a rare check with low local utility.
        ciu_raw = fidelity_blend * gt + (1.0 - fidelity_blend) * gt_base
        ciu = np.clip(ciu_raw + rng.normal(0, 0.12, n_steps), 0.0, 1.0)
        for step in bottlenecks:
            # Weaken but do not zero the bottleneck local signal.
            ciu[step] *= 0.4

        samples.append(
            {
                "sample_id": f"stress_{seed}_{index:04d}",
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
        "# SCU Component Contribution on a Structural Stress-Test Benchmark",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Evidence level: `{report['evidence_level']}`",
        f"- Seeds: `{', '.join(str(seed) for seed in report['seed_list'])}`",
        f"- Label design: redundancy_demote={report['label_design']['redundancy_demote']}, "
        f"bottleneck_boost={report['label_design']['bottleneck_boost']}",
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
            "Labels encode structural preference (redundancy-awareness and bottleneck-protection). "
            "This is mechanism-ablation evidence for SCU component contribution in the regime the "
            "structural terms are designed for, not external validation.",
        ]
    )
    return lines


if __name__ == "__main__":
    main()
