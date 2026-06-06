"""Correlation diagnostics between attribution signals and utility labels."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Sequence

import numpy as np

from fma.eval.utility_annotation import (
    AttributionAlignment,
    UtilityAnnotation,
    UtilityLabel,
    expected_source_for_intervention,
)


def evaluate_attribution_utility_correlation(
    annotations: Sequence[UtilityAnnotation],
) -> dict[str, Any]:
    """Compute attribution/utility calibration and mismatch diagnostics."""
    if annotations is None:
        raise ValueError("annotations must not be None.")

    return {
        "correlation_by_attribution": _correlation_by_attribution(annotations),
        "calibration_error": _calibration_error(annotations),
        "intervention_attribution_mismatch": _mismatches(annotations),
        "attribution_confusion_matrix": _confusion_matrix(annotations),
    }


def utility_quality(annotation: UtilityAnnotation) -> float:
    """Map utility labels to a deterministic scalar quality score."""
    return {
        UtilityLabel.HELPFUL: 1.0,
        UtilityLabel.NEUTRAL: 0.5,
        UtilityLabel.SPURIOUS: 0.25,
        UtilityLabel.HARMFUL: 0.0,
    }[annotation.utility]


def _correlation_by_attribution(
    annotations: Sequence[UtilityAnnotation],
) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[str, list[UtilityAnnotation]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation.attribution_type or "none"].append(annotation)

    report: dict[str, dict[str, float | int | None]] = {}
    for attribution_type, group in sorted(grouped.items()):
        confidence = [annotation.annotation_confidence for annotation in group]
        quality = [utility_quality(annotation) for annotation in group]
        helpful_count = sum(1 for annotation in group if annotation.utility is UtilityLabel.HELPFUL)
        harmful_count = sum(1 for annotation in group if annotation.utility is UtilityLabel.HARMFUL)
        report[attribution_type] = {
            "n": len(group),
            "mean_confidence": float(np.mean(confidence)) if confidence else 0.0,
            "mean_utility_quality": float(np.mean(quality)) if quality else 0.0,
            "helpful_ratio": helpful_count / len(group) if group else 0.0,
            "harmful_ratio": harmful_count / len(group) if group else 0.0,
            "confidence_utility_correlation": _pearson(confidence, quality),
        }
    return report


def _calibration_error(annotations: Sequence[UtilityAnnotation]) -> float:
    if not annotations:
        return 0.0
    errors = [
        abs(annotation.annotation_confidence - utility_quality(annotation))
        for annotation in annotations
    ]
    return float(np.mean(errors))


def _mismatches(annotations: Sequence[UtilityAnnotation]) -> list[dict[str, str]]:
    mismatches: list[dict[str, str]] = []
    for annotation in annotations:
        if annotation.attribution_alignment is not AttributionAlignment.INCORRECT:
            continue
        mismatches.append(
            {
                "trace_id": annotation.trace_id,
                "intervention": annotation.intervention_type or "unknown",
                "expected_attribution": expected_source_for_intervention(annotation.intervention_type) or "unknown",
                "actual_attribution": annotation.attribution_type or "none",
                "utility": annotation.utility.value,
            }
        )
    return sorted(
        mismatches,
        key=lambda item: (
            item["trace_id"],
            item["intervention"],
            item["actual_attribution"],
            item["utility"],
        ),
    )


def _confusion_matrix(annotations: Sequence[UtilityAnnotation]) -> dict[str, dict[str, int]]:
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for annotation in annotations:
        expected = expected_source_for_intervention(annotation.intervention_type) or "unknown"
        actual = annotation.attribution_type or "none"
        matrix[expected][actual] += 1
    return {
        expected: dict(sorted(actual_counts.items()))
        for expected, actual_counts in sorted(matrix.items())
    }


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    left_std = float(np.std(left_array))
    right_std = float(np.std(right_array))
    if not math.isfinite(left_std) or not math.isfinite(right_std) or left_std == 0.0 or right_std == 0.0:
        return None
    return float(np.corrcoef(left_array, right_array)[0, 1])


__all__ = ["evaluate_attribution_utility_correlation", "utility_quality"]
