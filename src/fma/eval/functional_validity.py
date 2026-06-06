"""Aggregate functional-validity metrics from utility annotations."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Sequence

import numpy as np

from fma.eval.utility_annotation import AttributionAlignment, OutcomeDelta, UtilityAnnotation, UtilityLabel


def evaluate_functional_validity(annotations: Sequence[UtilityAnnotation]) -> dict[str, Any]:
    """Compute outcome-grounded functional validity metrics."""
    if annotations is None:
        raise ValueError("annotations must not be None.")

    total = len(annotations)
    utility_counts = Counter(annotation.utility for annotation in annotations)
    alignment_counts = Counter(annotation.attribution_alignment for annotation in annotations)
    degradation_scores = [annotation.degradation_score for annotation in annotations]

    return {
        "utility_distribution": {
            f"{label.value}_ratio": _ratio(utility_counts[label], total)
            for label in UtilityLabel
        },
        "harmful_by_intervention": _harmful_by_intervention(annotations),
        "category_conditioned_utility": _category_conditioned_utility(annotations),
        "degradation_metrics": {
            "mean_degradation_score": float(np.mean(degradation_scores)) if degradation_scores else 0.0,
            "max_degradation": float(np.max(degradation_scores)) if degradation_scores else 0.0,
            "recovery_rate": _ratio(
                sum(
                    1
                    for annotation in annotations
                    if annotation.correctness_preserved
                    and annotation.outcome_delta in {OutcomeDelta.IMPROVED, OutcomeDelta.UNCHANGED}
                ),
                total,
            ),
            "false_correction_rate": _ratio(utility_counts[UtilityLabel.SPURIOUS], total),
        },
        "alignment_metrics": {
            "alignment_accuracy": _ratio(alignment_counts[AttributionAlignment.CORRECT], total),
            "misattribution_rate": _ratio(alignment_counts[AttributionAlignment.INCORRECT], total),
            "partial_alignment_rate": _ratio(alignment_counts[AttributionAlignment.PARTIAL], total),
        },
    }


def utility_bucket_warnings(
    annotations: Sequence[UtilityAnnotation],
    min_bucket_size: int = 5,
) -> list[str]:
    """Return deterministic warnings for sparse utility/category buckets."""
    if min_bucket_size <= 0:
        raise ValueError("min_bucket_size must be positive.")

    categories = sorted({annotation.reflection_category for annotation in annotations})
    counts: Counter[tuple[str, str]] = Counter(
        (annotation.reflection_category, annotation.utility.value)
        for annotation in annotations
    )
    warnings: list[str] = []
    for category in categories:
        for utility in (label.value for label in UtilityLabel):
            count = counts[(category, utility)]
            if count >= min_bucket_size:
                continue
            warnings.append(
                f"utility bucket {category}:{utility} has {count} samples; required {min_bucket_size}."
            )
    return warnings


def _harmful_by_intervention(annotations: Sequence[UtilityAnnotation]) -> dict[str, float]:
    grouped: dict[str, list[UtilityAnnotation]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation.intervention_type or "unknown"].append(annotation)
    return {
        intervention: _ratio(
            sum(1 for annotation in group if annotation.utility is UtilityLabel.HARMFUL),
            len(group),
        )
        for intervention, group in sorted(grouped.items())
    }


def _category_conditioned_utility(annotations: Sequence[UtilityAnnotation]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[UtilityAnnotation]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation.reflection_category].append(annotation)

    report: dict[str, dict[str, float]] = {}
    for category, group in sorted(grouped.items()):
        counts = Counter(annotation.utility for annotation in group)
        metrics: dict[str, float] = {
            f"{label.value}_ratio": _ratio(counts[label], len(group))
            for label in UtilityLabel
        }
        metrics["sample_count"] = float(len(group))
        report[category] = metrics
    return report


def _ratio(count: int, total: int) -> float:
    return float(count / total) if total else 0.0


__all__ = ["evaluate_functional_validity", "utility_bucket_warnings"]
