"""Run Phase 5 counterfactual functional attribution analysis."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.eval.counterfactual_attribution import (
    ABLATION_STRATEGIES,
    analyze_redundancy,
    build_counterfactual_summary,
    compute_faithfulness_metrics,
    compute_necessity_scores,
    dataclass_to_dict,
    minimal_subset_curves,
    run_minimal_subset_analysis,
    run_single_step_ablations,
    utility_annotations_from_records,
)
from fma.io import load_records, write_records
from fma.visualization.validity_plots import plot_counterfactual_suite


DEFAULT_TRACE_PATH = PROJECT_ROOT / "data" / "traces" / "synthetic_100x8.json"
DEFAULT_UTILITY_ANNOTATIONS_PATH = PROJECT_ROOT / "outputs" / "utility_annotations.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"
LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 5 counterfactual attribution.")
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--utility-annotations", type=Path, default=DEFAULT_UTILITY_ANNOTATIONS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--utility-threshold", type=float, default=0.9)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    traces = load_records(args.traces)
    annotation_records = load_records(args.utility_annotations)
    annotations = utility_annotations_from_records(annotation_records)

    necessity_scores = compute_necessity_scores(annotations)
    ablation_results = run_single_step_ablations(
        traces=traces,
        annotations=annotations,
        seed=args.seed,
        strategies=ABLATION_STRATEGIES,
    )
    faithfulness = compute_faithfulness_metrics(necessity_scores)
    redundancy = analyze_redundancy(annotations, necessity_scores, traces=traces)
    minimal_subsets = run_minimal_subset_analysis(
        annotations,
        utility_threshold=args.utility_threshold,
    )
    curves = minimal_subset_curves(annotations, utility_threshold=args.utility_threshold)
    summary = build_counterfactual_summary(
        traces=traces,
        ablation_results=ablation_results,
        necessity_scores=necessity_scores,
        faithfulness=faithfulness,
        redundancy=redundancy,
        minimal_subsets=minimal_subsets,
    )

    if args.dry_run:
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "dry_run": True,
                    "traces": str(args.traces),
                    "utility_annotations": str(args.utility_annotations),
                    "output_dir": str(args.output_dir),
                    "figures_dir": str(args.figures_dir),
                    "summary": summary,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
        )
        return summary

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_records(
        [dataclass_to_dict(result) for result in ablation_results],
        args.output_dir / "counterfactual_ablation_results.jsonl",
    )
    write_records(
        [dataclass_to_dict(score) for score in necessity_scores],
        args.output_dir / "necessity_scores.jsonl",
    )
    write_json(args.output_dir / "faithfulness_report.json", dataclass_to_dict(faithfulness))
    write_json(
        args.output_dir / "redundancy_report.json",
        [dataclass_to_dict(result) for result in redundancy],
    )
    write_json(
        args.output_dir / "minimal_subset_report.json",
        [dataclass_to_dict(result) for result in minimal_subsets],
    )
    write_json(args.output_dir / "counterfactual_summary.json", summary)
    plot_counterfactual_suite(
        ablation_results=ablation_results,
        necessity_scores=necessity_scores,
        annotations=annotations,
        redundancy=redundancy,
        curves=curves,
        output_dir=args.figures_dir,
    )
    LOGGER.info("Wrote counterfactual attribution outputs to %s", args.output_dir)
    return summary


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
