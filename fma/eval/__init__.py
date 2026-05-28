"""Evaluation utilities for FMA."""

from fma.eval.attribution_metrics import (
    build_phase1_eval_report,
    intervention_sensitivity,
    utility_calibration,
    write_phase1_eval_report,
)
from fma.eval.attribution_utility_correlation import evaluate_attribution_utility_correlation
from fma.eval.counterfactual_attribution import (
    ABLATION_STRATEGIES,
    ATTRIBUTION_SCORE_MAP,
    UTILITY_NUMERIC,
    CounterfactualAblationResult,
    FaithfulnessMetrics,
    MinimalSubsetResult,
    NecessityScore,
    RedundancyAnalysis,
    analyze_redundancy,
    compute_faithfulness_metrics,
    compute_necessity_scores,
    compute_trace_utility,
    find_minimal_sufficient_subset,
    run_minimal_subset_analysis,
    run_single_step_ablations,
)
from fma.eval.functional_validity import evaluate_functional_validity, utility_bucket_warnings
from fma.eval.locality_stress_test import LocalityStressResult, LocalityStressTester
from fma.eval.stability import StabilityAnalyzer, bounded_stability
from fma.eval.stratified_eval import (
    MIN_BUCKET_SIZE,
    MIN_UTILITY_BUCKET_SIZE,
    BucketMetrics,
    StratifiedBucket,
    StratifiedEvaluator,
)
from fma.eval.taxonomy_coverage import TaxonomyCoverageAnalyzer, TaxonomyReport
from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
    annotate_utility_records,
)

__all__ = [
    "ABLATION_STRATEGIES",
    "ATTRIBUTION_SCORE_MAP",
    "BucketMetrics",
    "CounterfactualAblationResult",
    "FaithfulnessMetrics",
    "LocalityStressResult",
    "LocalityStressTester",
    "MIN_BUCKET_SIZE",
    "MIN_UTILITY_BUCKET_SIZE",
    "MinimalSubsetResult",
    "NecessityScore",
    "RedundancyAnalysis",
    "AttributionAlignment",
    "OutcomeDelta",
    "StabilityAnalyzer",
    "StratifiedBucket",
    "StratifiedEvaluator",
    "TaxonomyCoverageAnalyzer",
    "TaxonomyReport",
    "UtilityAnnotation",
    "UtilityLabel",
    "UTILITY_NUMERIC",
    "analyze_redundancy",
    "annotate_utility_records",
    "bounded_stability",
    "build_phase1_eval_report",
    "compute_faithfulness_metrics",
    "compute_necessity_scores",
    "compute_trace_utility",
    "evaluate_attribution_utility_correlation",
    "evaluate_functional_validity",
    "find_minimal_sufficient_subset",
    "intervention_sensitivity",
    "run_minimal_subset_analysis",
    "run_single_step_ablations",
    "utility_bucket_warnings",
    "utility_calibration",
    "write_phase1_eval_report",
]
