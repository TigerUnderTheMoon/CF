from __future__ import annotations

import json

import pytest

from fma.eval.counterfactual_attribution import (
    dataclass_to_dict,
    find_minimal_sufficient_subset,
    minimal_subset_curves,
)
from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
)


def make_annotation(
    idx: int,
    utility: UtilityLabel,
    attribution_type: str | None,
    trace_id: str = "t1",
) -> UtilityAnnotation:
    return UtilityAnnotation(
        trace_id=trace_id,
        reflection_idx=idx,
        utility=utility,
        outcome_delta=OutcomeDelta.UNCHANGED,
        degradation_score=0.0,
        annotation_confidence=1.0,
        attribution_type=attribution_type,
        attribution_alignment=AttributionAlignment.PARTIAL,
        intervention_type="delete",
        reflection_category="VERIFICATION",
        correctness_preserved=True,
    )


def test_minimal_subset_removes_lowest_necessity_then_lowest_attribution() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        make_annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
        make_annotation(2, UtilityLabel.NEUTRAL, "vague"),
    ]

    result = find_minimal_sufficient_subset(annotations, utility_threshold=0.9)

    assert result.steps_removed == [1, 2]
    assert result.steps_retained == [0]
    assert result.compression_ratio == pytest.approx(2 / 3)


def test_minimal_subset_preserves_threshold() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        make_annotation(1, UtilityLabel.HARMFUL, "reasoning_gap"),
    ]

    result = find_minimal_sufficient_subset(annotations, utility_threshold=0.9)

    assert result.steps_removed == [1]
    assert result.utility_retained >= 0.9


def test_minimal_subset_uses_absolute_threshold_for_nonpositive_original() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.NEUTRAL, "irrelevant"),
        make_annotation(1, UtilityLabel.HARMFUL, "factual_error"),
    ]

    result = find_minimal_sufficient_subset(annotations, utility_threshold=0.9)

    assert result.steps_removed == [1]
    assert result.steps_retained == [0]
    assert result.utility_retained == pytest.approx(0.0)


def test_minimal_subset_curve_is_nonincreasing_for_neutral_removals() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        make_annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
        make_annotation(2, UtilityLabel.NEUTRAL, "vague"),
    ]

    curve = minimal_subset_curves(annotations, utility_threshold=0.9)
    utilities = [point["utility_retained"] for point in curve]

    assert utilities == sorted(utilities, reverse=True)


def test_minimal_subset_result_is_json_serializable() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        make_annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
    ]

    result = find_minimal_sufficient_subset(annotations)
    payload = dataclass_to_dict(result)

    assert json.loads(json.dumps(payload))["trace_id"] == "t1"
