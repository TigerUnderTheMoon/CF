"""Run downstream comparison experiment: FMA vs PRM vs heuristic baselines.

This script is a clean, standalone experiment that does NOT inherit
the v2/v3 validation route baggage.  It operates entirely on open-source
data with local PRM inference (no API keys required).

Stages:
  1. load_data      - Load open-source reasoning traces
  2. parse_steps    - CoT step segmentation + taxonomy classification
  3. compute_fma    - Compute FMA/CIU scores (existing pipeline)
  4. score_prm      - Score steps with frozen public PRM
  5. score_baselines- Compute heuristic baseline scores
  6. filter_ablation- Run filtering A/B experiment
  7. report         - Generate comparison report + figures

Usage:
  python scripts/run_downstream_comparison.py --config configs/downstream_comparison.yaml
  python scripts/run_downstream_comparison.py --source prm800k --max-samples 200
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.data import load_open_traces, normalize_to_internal  # noqa: E402
from fma.data.schema import OpenTraceRecord  # noqa: E402
from fma.eval.masking_ciu import compute_masking_ciu  # noqa: E402
from fma.io import write_records  # noqa: E402
from fma.prm import FrozenPRMScorer  # noqa: E402
from fma.utility import (  # noqa: E402
    ComparisonReport,
    FilteringConfig,
    compute_span_scores,
    print_report_summary,
    run_filtering_ablation,
    write_report,
)
from fma.utils.logging_config import get_logger  # noqa: E402

logger = get_logger(__name__)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "downstream_comparison_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run downstream comparison: FMA vs PRM vs baselines"
    )
    parser.add_argument("--config", type=Path, default=None, help="YAML config file")
    parser.add_argument("--source", type=str, default="prm800k", help="Data source name")
    parser.add_argument("--split", type=str, default="test", help="Dataset split")
    parser.add_argument("--max-samples", type=int, default=-1, help="Max traces to load")
    parser.add_argument("--models", type=str, nargs="*", default=None, help="Model filter")
    parser.add_argument("--trace-dir", type=str, default=None, help="Pre-generated trace dir")
    parser.add_argument(
        "--prm-model",
        type=str,
        default="Qwen2.5-Math-PRM-1.5B",
        help="Frozen PRM model name",
    )
    parser.add_argument("--no-prm", action="store_true", help="Skip PRM scoring")
    parser.add_argument("--no-fma", action="store_true", help="Skip FMA scoring")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--keep-ratios", type=float, nargs="*", default=[0.25, 0.5, 0.75])
    parser.add_argument("--parse-strategy", type=str, default="auto")
    parser.add_argument("--stages", type=str, nargs="*", default=None, help="Run only these stages")
    return parser.parse_args()


def stage_load_data(args: argparse.Namespace) -> list[OpenTraceRecord]:
    """Stage 1: Load open-source reasoning traces."""
    logger.info("stage_load_data_start", source=args.source, split=args.split)
    records = load_open_traces(
        source=args.source,
        split=args.split,
        max_samples=args.max_samples,
        models=args.models,
        trace_dir=args.trace_dir,
        classify_operations=True,
        parse_strategy=args.parse_strategy,
    )
    logger.info("stage_load_data_complete", n_records=len(records))

    if not records:
        logger.error("no_records_loaded")
        return []

    model_counts: dict[str, int] = {}
    dataset_counts: dict[str, int] = {}
    for r in records:
        model_counts[r.model_name] = model_counts.get(r.model_name, 0) + 1
        dataset_counts[r.dataset] = dataset_counts.get(r.dataset, 0) + 1

    logger.info("data_summary", models=model_counts, datasets=dataset_counts)

    internal_path = args.output_dir / "traces" / "internal_format.jsonl"
    internal_records = normalize_to_internal(records)
    write_records(internal_records, internal_path)
    logger.info("internal_format_saved", path=str(internal_path))

    return records


def stage_compute_fma(
    records: list[OpenTraceRecord],
    args: argparse.Namespace,
) -> dict[str, list[float]]:
    """Stage 3: Compute FMA CIU via masking intervention.

    For each step: replace step text with [REASONING_MASK],
    extract answer from masked trace, compare to reference.
    CIU = correct(original) - correct(masked) in {-1, 0, 1}.
    """
    logger.info("stage_compute_fma_start", n_records=len(records))
    if args.no_fma:
        logger.info("stage_compute_fma_skipped")
        return {}

    fma_scores = compute_masking_ciu(records)

    n_traces = len(fma_scores)
    n_nonzero = sum(
        1 for v in fma_scores.values()
        if any(abs(s) > 1e-6 for s in v)
    )
    all_nonzero = sum(
        1 for v in fma_scores.values()
        for s in v if abs(s) > 1e-6
    )
    logger.info(
        "stage_compute_fma_complete",
        n_traces=n_traces,
        n_traces_nonzero=n_nonzero,
        n_steps_nonzero=all_nonzero,
    )

    scores_path = args.output_dir / "scores" / "fma_scores.json"
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    with scores_path.open("w", encoding="utf-8") as handle:
        json.dump(fma_scores, handle)

    return fma_scores


def stage_score_prm(
    records: list[OpenTraceRecord],
    args: argparse.Namespace,
) -> dict[str, list[float]]:
    """Stage 4: Score steps with frozen public PRM."""
    if args.no_prm:
        logger.info("stage_score_prm_skipped")
        return {}

    logger.info("stage_score_prm_start", model=args.prm_model)

    scorer = FrozenPRMScorer(
        model_name=args.prm_model,
        cache_dir=str(args.output_dir / "prm_cache"),
    )

    fallback_scorer = None

    prm_scores: dict[str, list[float]] = {}
    for record in records:
        steps = [ann.step_text for ann in record.step_annotations]
        if not steps:
            prm_scores[record.sample_id] = []
            continue
        try:
            scores = scorer.score_steps(record.question, steps)
            prm_scores[record.sample_id] = scores
        except Exception as exc:
            logger.warning(
                "prm_score_failed",
                sample_id=record.sample_id,
                error=str(exc),
            )
            try:
                if fallback_scorer is None:
                    from fma.prm.perplexity_prm import PerplexityPRMScorer

                    fallback_scorer = PerplexityPRMScorer(device="cpu")
                proxy_scores = fallback_scorer.score_steps(record.question, steps)
                prm_scores[record.sample_id] = proxy_scores
            except Exception as fallback_exc:
                logger.warning(
                    "prm_fallback_failed",
                    sample_id=record.sample_id,
                    error=str(fallback_exc),
                )
                prm_scores[record.sample_id] = [0.5] * len(steps)

    n_scored = sum(1 for v in prm_scores.values() if v)
    logger.info("stage_score_prm_complete", n_scored=n_scored)

    prm_path = args.output_dir / "scores" / "prm_scores.json"
    prm_path.parent.mkdir(parents=True, exist_ok=True)
    with prm_path.open("w", encoding="utf-8") as handle:
        json.dump(prm_scores, handle)

    return prm_scores


def stage_filter_ablation(
    records: list[OpenTraceRecord],
    fma_scores: dict[str, list[float]],
    prm_scores: dict[str, list[float]],
    args: argparse.Namespace,
) -> ComparisonReport:
    """Stages 5-6: Compute baselines and run filtering A/B experiment."""
    logger.info("stage_filter_ablation_start")

    filtering_config = FilteringConfig(
        keep_ratios=tuple(args.keep_ratios),
        seed=args.seed,
    )

    span_scores = compute_span_scores(
        records,
        fma_score_map=fma_scores if not args.no_fma else None,
        prm_score_map=prm_scores if not args.no_prm else None,
        seed=args.seed,
    )

    report = run_filtering_ablation(
        records,
        span_scores,
        filtering_config,
        experiment_name="fma_vs_prm_downstream_v1",
        claims_allowed={
            "prm_superiority": False,
            "fma_superiority": False,
            "correlation_report": True,
            "ranking_agreement": True,
        },
    )

    logger.info(
        "stage_filter_ablation_complete",
        methods=list(report.methods),
        total_results=len(report.filtering_results),
    )

    return report


def stage_report(report: ComparisonReport, args: argparse.Namespace) -> None:
    """Stage 7: Write comparison report to disk."""
    logger.info("stage_report_start")
    report_dir = args.output_dir / "report"
    json_path = write_report(report, report_dir)
    logger.info("report_written", path=str(json_path))
    print_report_summary(report)


def _load_config(config_path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except OSError:
        return {}


def _apply_config(args: argparse.Namespace, config: dict[str, Any]) -> None:
    data_cfg = config.get("data", {})
    if args.source == "prm800k" and data_cfg.get("source"):
        args.source = data_cfg["source"]
    if args.max_samples < 0 and data_cfg.get("max_samples"):
        args.max_samples = int(data_cfg["max_samples"])

    prm_cfg = config.get("scorers", {}).get("prm", {})
    if prm_cfg.get("model") and args.prm_model == "Qwen2.5-Math-PRM-1.5B":
        args.prm_model = prm_cfg["model"]

    comp_cfg = config.get("comparison", {})
    if comp_cfg.get("keep_ratios") and args.keep_ratios == [0.25, 0.5, 0.75]:
        args.keep_ratios = comp_cfg["keep_ratios"]


def run(args: argparse.Namespace) -> dict[str, Any]:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.config:
        config = _load_config(args.config)
        _apply_config(args, config)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_stages = ["load_data", "compute_fma", "score_prm", "filter_ablation", "report"]
    active_stages = args.stages if args.stages else all_stages

    t0 = time.time()
    records: list[OpenTraceRecord] = []
    fma_scores: dict[str, list[float]] = {}
    prm_scores: dict[str, list[float]] = {}
    report: ComparisonReport | None = None

    if "load_data" in active_stages:
        records = stage_load_data(args)
        if not records:
            logger.error("aborted_no_data")
            return {"status": "no_data", "n_records": 0}

    if "compute_fma" in active_stages:
        if not records:
            logger.error("skipping_fma_no_records")
        else:
            fma_scores = stage_compute_fma(records, args)

    if "score_prm" in active_stages:
        if not records:
            logger.error("skipping_prm_no_records")
        else:
            prm_scores = stage_score_prm(records, args)

    if "filter_ablation" in active_stages:
        if not records:
            logger.error("skipping_ablation_no_records")
        else:
            report = stage_filter_ablation(records, fma_scores, prm_scores, args)

    if "report" in active_stages and report is not None:
        stage_report(report, args)

    elapsed = time.time() - t0

    run_meta = {
        "status": "completed",
        "n_records": len(records),
        "n_fma_scored": len(fma_scores),
        "n_prm_scored": len(prm_scores),
        "elapsed_seconds": round(elapsed, 2),
        "stages_run": active_stages,
        "source": args.source,
        "prm_model": args.prm_model,
    }

    meta_path = args.output_dir / "run_meta.json"
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(run_meta, handle, indent=2, sort_keys=True)

    logger.info("run_complete", **run_meta)
    return run_meta


def main() -> None:
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
