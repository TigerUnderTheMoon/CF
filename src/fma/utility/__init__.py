"""Downstream evaluation and comparison framework for FMA vs PRM vs baselines."""

from .comparison_report import ComparisonReport, print_report_summary, write_report
from .downstream_eval import (
    FilteringConfig,
    FilteringResult,
    check_correctness,
    evaluate_filtering,
    extract_answer,
    filter_spans_by_scores,
    filter_spans_random,
)
from .filtering_experiment import (
    SpanScores,
    compute_span_scores,
    run_filtering_ablation,
)

__all__ = [
    "ComparisonReport",
    "FilteringConfig",
    "FilteringResult",
    "SpanScores",
    "check_correctness",
    "compute_span_scores",
    "evaluate_filtering",
    "extract_answer",
    "filter_spans_by_scores",
    "filter_spans_random",
    "print_report_summary",
    "run_filtering_ablation",
    "write_report",
]
