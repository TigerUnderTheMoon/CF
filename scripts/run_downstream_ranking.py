"""Downstream comparison runner: SC-FMA vs baseline families on step ranking.

Evaluates SC-FMA variants against 6 baseline families on the step importance
ranking task. Uses synthetic + PRM800K data. Produces comparison report JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from fma.calibration import scfma_calibrate, scfma_calibrate_ridge
from fma.ranking import (
    compare_methods,
    compute_ranking_metrics,
    list_methods,
    rank_steps_by_method,
)

DEFAULT_OUTPUT_DIR = Path("outputs") / "downstream_ranking"


def _generate_synthetic_ranking_data(
    n_samples: int = 200,
    seed: int = 42,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    samples: list[dict[str, Any]] = []

    for i in range(n_samples):
        n_steps = rng.integers(3, 8)
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
            "task_type": "gsm8k" if i < n_samples // 2 else "math",
            "n_steps": n_steps,
            "ground_truth_scores": gt.tolist(),
            "ciu_scores": ciu.tolist(),
            "necessity_scores": nec.tolist(),
            "redundancy_matrix": red_mat.tolist(),
            "bottleneck_indices": sorted(bottlenecks),
            "span_lengths": rng.integers(5, 50, n_steps).tolist(),
            "step_indices": list(range(n_steps)),
        })

    return samples


def run_comparison(
    samples: list[dict[str, Any]],
    methods: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    if methods is None:
        standard = [
            "scfma_qp", "scfma_ridge", "scfma_projection",
            "raw_ciu", "random", "span_length", "relative_position",
        ]
        methods = standard

    report = compare_methods(samples, methods=methods)

    result: dict[str, Any] = {
        "experiment": report.experiment_name,
        "n_samples": report.n_samples,
        "n_total_steps": report.n_total_steps,
        "methods": report.methods,
        "method_rankings": report.method_rankings,
        "aggregate_metrics": report.aggregate_metrics,
        "friedman_test": report.friedman_result,
        "pairwise_tests": report.pairwise_tests,
    }

    top_methods = sorted(report.method_rankings.items(), key=lambda x: -x[1])
    result["best_method"] = top_methods[0][0] if top_methods else "none"
    result["best_spearman"] = top_methods[0][1] if top_methods else 0.0

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "comparison_report.json"
        report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        summary_path = output_dir / "summary.md"
        lines = [
            "# SC-FMA Step Importance Ranking Results",
            "",
            f"**Samples**: {report.n_samples}",
            f"**Total steps**: {report.n_total_steps}",
            f"**Methods compared**: {len(report.methods)}",
            "",
            "## Method Rankings (Mean Spearman ρ)",
            "",
        ]
        for method, rho in sorted(report.method_rankings.items(), key=lambda x: -x[1]):
            lines.append(f"- **{method}**: {rho:.4f}")

        lines.append("")
        lines.append("## Friedman Test")
        f = report.friedman_result
        lines.append(f"- χ² = {f.get('statistic', 0):.4f}, p = {f.get('p_value', 1):.6f}")
        lines.append(f"- n_methods = {f.get('n_methods', 0)}, n_samples = {f.get('n_samples', 0)}")

        summary_path.write_text("\n".join(lines), encoding="utf-8")

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SC-FMA downstream comparison on step importance ranking."
    )
    parser.add_argument("--n-samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--methods", nargs="*", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    samples = _generate_synthetic_ranking_data(n_samples=args.n_samples, seed=args.seed)
    result = run_comparison(
        samples,
        methods=args.methods,
        output_dir=args.output_dir,
    )

    print(f"Best method: {result['best_method']} "
          f"(Spearman ρ = {result['best_spearman']:.4f})")
    print(f"Friedman p = {result['friedman_test'].get('p_value', 1):.6f}")
    if args.output_dir:
        print(f"Report written to {args.output_dir / 'comparison_report.json'}")


if __name__ == "__main__":
    main()
