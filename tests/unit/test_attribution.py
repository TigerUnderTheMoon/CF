from __future__ import annotations

import pytest

from fma.eval.counterfactual_attribution import (
    ATTRIBUTION_TOP_K,
    build_counterfactual_summary,
    compute_faithfulness_metrics,
    compute_necessity_scores,
    run_single_step_ablations,
)
from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
)


def annotation(
    idx: int,
    utility: UtilityLabel,
    attribution_type: str,
) -> UtilityAnnotation:
    return UtilityAnnotation(
        trace_id="trace-1",
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


def test_counterfactual_necessity_uses_original_minus_ablated_utility() -> None:
    annotations = [
        annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
        annotation(2, UtilityLabel.HARMFUL, "reasoning_gap"),
    ]

    scores = {score.step_idx: score for score in compute_necessity_scores(annotations)}

    assert scores[0].necessity == pytest.approx(1.5)
    assert scores[0].necessity_normalized == pytest.approx(0.75)
    assert scores[1].necessity == pytest.approx(0.0)
    assert scores[2].necessity == pytest.approx(0.0)


def test_top_attribution_ablation_reports_expected_delta() -> None:
    annotations = [
        annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
        annotation(2, UtilityLabel.HARMFUL, "reasoning_gap"),
    ]

    results = run_single_step_ablations(
        traces=[
            {
                "trace_id": "trace-1",
                "reflection_chain": [{"text": "a"}, {"text": "b"}, {"text": "c"}],
            }
        ],
        annotations=annotations,
        strategies=[ATTRIBUTION_TOP_K],
    )

    first = results[0]
    assert first.removed_step_idx == 0
    assert first.original_utility == pytest.approx(1.0)
    assert first.ablated_utility == pytest.approx(-0.5)
    assert first.delta_utility == pytest.approx(1.5)
    assert first.attribution_score_of_removed == pytest.approx(0.9)


def test_counterfactual_summary_aggregates_numeric_fields() -> None:
    annotations = [
        annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
        annotation(2, UtilityLabel.HARMFUL, "reasoning_gap"),
    ]
    scores = compute_necessity_scores(annotations)
    ablations = run_single_step_ablations(
        traces=[
            {
                "trace_id": "trace-1",
                "reflection_chain": [{"text": "a"}, {"text": "b"}, {"text": "c"}],
            }
        ],
        annotations=annotations,
        strategies=[ATTRIBUTION_TOP_K],
    )
    faithfulness = compute_faithfulness_metrics(scores)

    summary = build_counterfactual_summary(
        traces=[{"trace_id": "trace-1"}],
        ablation_results=ablations,
        necessity_scores=scores,
        faithfulness=faithfulness,
        redundancy=[],
        minimal_subsets=[],
    )

    assert summary["num_traces"] == 1
    assert summary["num_ablations"] == 3
    assert summary["num_ablation_runs_by_strategy"][ATTRIBUTION_TOP_K] == 3
    assert summary["mean_necessity"] == pytest.approx(0.5)
