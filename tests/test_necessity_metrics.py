from __future__ import annotations

import pytest

from fma.eval.counterfactual_attribution import (
    NecessityScore,
    analyze_redundancy,
    compute_faithfulness_metrics,
    compute_necessity_scores,
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


def test_necessity_scores_match_hand_verified_three_step_trace() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        make_annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
        make_annotation(2, UtilityLabel.HARMFUL, "reasoning_gap"),
    ]

    scores = {score.step_idx: score for score in compute_necessity_scores(annotations)}

    assert scores[0].necessity == pytest.approx(1.5)
    assert scores[0].necessity_normalized == pytest.approx(0.75)
    assert scores[0].attribution_score == pytest.approx(0.9)
    assert scores[1].necessity == pytest.approx(0.0)
    assert scores[2].necessity == pytest.approx(0.0)


def test_necessity_normalization_uses_neutral_floor_without_harmful_steps() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        make_annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
    ]

    scores = {score.step_idx: score for score in compute_necessity_scores(annotations)}

    assert scores[0].necessity == pytest.approx(1.0)
    assert scores[0].necessity_normalized == pytest.approx(1.0)
    assert scores[1].necessity == pytest.approx(0.0)
    assert scores[1].necessity_normalized == pytest.approx(0.0)


def test_faithfulness_metrics_are_stable_for_monotonic_scores() -> None:
    scores = [
        NecessityScore("t1", 0, 0.1, 0.0, 0.0),
        NecessityScore("t1", 1, 0.3, 0.2, 0.2),
        NecessityScore("t1", 2, 0.6, 0.5, 0.5),
        NecessityScore("t1", 3, 0.75, 0.7, 0.7),
        NecessityScore("t1", 4, 0.9, 1.0, 1.0),
    ]

    metrics = compute_faithfulness_metrics(scores)

    assert metrics.pearson > 0.98
    assert metrics.spearman == pytest.approx(1.0)
    assert metrics.rank_agreement == pytest.approx(1.0)
    assert metrics.top_k_overlap[3] == pytest.approx(1.0)


def test_redundancy_detects_high_attribution_low_necessity_step() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.NEUTRAL, "factual_error"),
        make_annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
    ]
    scores = compute_necessity_scores(annotations)

    report = analyze_redundancy(annotations, scores)[0]

    assert report.redundancy_ratio == pytest.approx(0.5)
    assert report.attribution_inflation_score > 0.0


def test_duplicate_density_compares_text_when_attribution_types_match() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.NEUTRAL, "factual_error"),
        make_annotation(1, UtilityLabel.NEUTRAL, "factual_error"),
    ]
    traces = [
        {
            "trace_id": "t1",
            "reflection_chain": [
                {"text": "verify same arithmetic error"},
                {"text": "verify same arithmetic error"},
            ],
        }
    ]
    scores = compute_necessity_scores(annotations)

    report = analyze_redundancy(annotations, scores, traces=traces)[0]

    assert report.duplicate_verification_density == pytest.approx(1.0)
