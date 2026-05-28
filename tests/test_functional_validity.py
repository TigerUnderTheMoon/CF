from __future__ import annotations

from pathlib import Path

import pytest

from fma.eval.attribution_utility_correlation import evaluate_attribution_utility_correlation
from fma.eval.functional_validity import evaluate_functional_validity
from fma.eval.stratified_eval import StratifiedEvaluator
from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
    annotate_utility_records,
    assign_utility_label,
    evaluate_attribution_alignment,
    extract_attribution,
    infer_degradation_score,
    infer_outcome_delta,
)
from fma.generation import (
    SUPPORTED_TEMPLATE_ATTRIBUTIONS,
    SUPPORTED_TEMPLATE_INTERVENTIONS,
    TEMPLATE_POOLS,
    ReflectionStyle,
)
from fma.types import AttributionRecord, ReflectionAnnotation, ReflectionCategory, ReflectionTrace, StratifiedInput
from fma.visualization.validity_plots import plot_validity_suite


def make_annotation(
    trace_id: str,
    utility: UtilityLabel,
    alignment: AttributionAlignment,
    intervention: str = "delete",
    category: str = "VERIFICATION",
    confidence: float = 0.8,
    degradation: float = 0.0,
) -> UtilityAnnotation:
    return UtilityAnnotation(
        trace_id=trace_id,
        reflection_idx=0,
        utility=utility,
        outcome_delta=OutcomeDelta.UNCHANGED if degradation == 0.0 else OutcomeDelta.DEGRADED,
        degradation_score=degradation,
        annotation_confidence=confidence,
        attribution_type="reasoning_gap",
        attribution_alignment=alignment,
        intervention_type=intervention,
        reflection_category=category,
        correctness_preserved=degradation == 0.0,
    )


def test_template_metadata_present_for_every_template() -> None:
    for style in ReflectionStyle:
        for template in TEMPLATE_POOLS[style]:
            assert template.attribution_type in SUPPORTED_TEMPLATE_ATTRIBUTIONS
            assert template.expected_intervention in SUPPORTED_TEMPLATE_INTERVENTIONS
            assert 0.0 <= template.confidence <= 1.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I made a calculation error.", "factual_error"),
        ("There is missing information.", "reasoning_gap"),
        ("I should think more carefully.", "metacognitive"),
        ("I was wrong.", "vague"),
        ("This note is unrelated.", "irrelevant"),
    ],
)
def test_regex_attribution_extraction(text: str, expected: str) -> None:
    signal = extract_attribution(text)
    assert signal.attribution_type == expected
    assert 0.0 <= signal.confidence <= 1.0


def test_alignment_uses_source_cues_not_intervention_name_only() -> None:
    assert (
        evaluate_attribution_alignment("This conclusion contradicts the condition.", "contradict", "factual_error")
        is AttributionAlignment.CORRECT
    )
    assert (
        evaluate_attribution_alignment("I miscalculated the number.", "contradict", "factual_error")
        is AttributionAlignment.INCORRECT
    )
    assert (
        evaluate_attribution_alignment("This is unrelated to the task.", "delete", "irrelevant")
        is AttributionAlignment.INCORRECT
    )


def test_utility_labels_are_outcome_grounded() -> None:
    assert (
        assign_utility_label(
            outcome_delta=OutcomeDelta.UNCHANGED,
            degradation_score=0.0,
            attribution_type="factual_error",
            attribution_alignment=AttributionAlignment.CORRECT,
            correctness_preserved=True,
        )
        is UtilityLabel.HELPFUL
    )
    assert (
        assign_utility_label(
            outcome_delta=OutcomeDelta.DEGRADED,
            degradation_score=1.0,
            attribution_type="factual_error",
            attribution_alignment=AttributionAlignment.CORRECT,
            correctness_preserved=False,
        )
        is UtilityLabel.SPURIOUS
    )
    assert (
        assign_utility_label(
            outcome_delta=OutcomeDelta.DEGRADED,
            degradation_score=1.0,
            attribution_type=None,
            attribution_alignment=AttributionAlignment.INCORRECT,
            correctness_preserved=False,
        )
        is UtilityLabel.HARMFUL
    )


def test_outcome_delta_and_degradation_prefer_correctness() -> None:
    trace = {"trace_id": "t1", "correctness": True}
    outcome = {"trace_id": "t1", "counterfactual_correctness": False, "utility_delta": 0.1}
    assert infer_outcome_delta(trace, outcome) is OutcomeDelta.DEGRADED
    assert infer_degradation_score(trace, outcome) == pytest.approx(1.0)


def test_annotate_records_emits_one_row_per_reflection_step() -> None:
    traces = [
        {
            "trace_id": "t1",
            "correctness": True,
            "reflection_chain": [
                {"category": "ERROR_CORRECTION", "text": "Correct the inconsistent step before moving on."},
                {"category": "PLANNING", "text": "Decide which operation should come next."},
            ],
        }
    ]
    outcomes = [{"trace_id": "t1", "intervention_type": "contradict", "counterfactual_correctness": True}]

    annotations = annotate_utility_records(traces, outcomes)

    assert len(annotations) == 2
    assert annotations[0].trace_id == "t1"
    assert annotations[0].reflection_idx == 0
    assert annotations[0].utility is UtilityLabel.HELPFUL
    assert annotations[0].attribution_alignment is AttributionAlignment.CORRECT


def test_annotation_intervention_type_alone_does_not_force_harmful() -> None:
    traces = [
        {
            "trace_id": "t1",
            "correctness": True,
            "reflection_text": "This conclusion contradicts the earlier condition.",
            "category": "VERIFICATION",
        }
    ]
    outcomes = [{"trace_id": "t1", "intervention_type": "contradict", "counterfactual_correctness": True}]

    annotation = annotate_utility_records(traces, outcomes)[0]

    assert annotation.utility is UtilityLabel.HELPFUL
    assert annotation.correctness_preserved is True


def test_functional_validity_report_shape() -> None:
    annotations = [
        make_annotation("a", UtilityLabel.HELPFUL, AttributionAlignment.CORRECT),
        make_annotation("b", UtilityLabel.HARMFUL, AttributionAlignment.INCORRECT, degradation=1.0),
        make_annotation("c", UtilityLabel.SPURIOUS, AttributionAlignment.PARTIAL, degradation=0.5),
        make_annotation("d", UtilityLabel.NEUTRAL, AttributionAlignment.INCORRECT),
    ]

    report = evaluate_functional_validity(annotations)

    assert set(report) == {
        "utility_distribution",
        "harmful_by_intervention",
        "category_conditioned_utility",
        "degradation_metrics",
        "alignment_metrics",
    }
    assert report["utility_distribution"]["helpful_ratio"] == pytest.approx(0.25)
    assert report["alignment_metrics"]["misattribution_rate"] == pytest.approx(0.5)


def test_attribution_utility_correlation_reports_mismatches() -> None:
    annotations = [
        make_annotation("a", UtilityLabel.HELPFUL, AttributionAlignment.CORRECT, intervention="delete"),
        make_annotation("b", UtilityLabel.HARMFUL, AttributionAlignment.INCORRECT, intervention="replace", degradation=1.0),
    ]

    report = evaluate_attribution_utility_correlation(annotations)

    assert "reasoning_gap" in report["correlation_by_attribution"]
    assert report["intervention_attribution_mismatch"][0]["trace_id"] == "b"
    assert "wrong_substitution" in report["attribution_confusion_matrix"]
    assert 0.0 <= report["calibration_error"] <= 1.0


def test_validity_plots_are_written(tmp_path: Path) -> None:
    annotations = [
        make_annotation("a", UtilityLabel.HELPFUL, AttributionAlignment.CORRECT, intervention="delete"),
        make_annotation("b", UtilityLabel.HARMFUL, AttributionAlignment.INCORRECT, intervention="replace", degradation=1.0),
        make_annotation("c", UtilityLabel.SPURIOUS, AttributionAlignment.PARTIAL, intervention="truncate", degradation=0.5),
    ]

    plot_validity_suite(annotations, tmp_path)

    for filename in (
        "utility_distribution.png",
        "degradation_heatmap.png",
        "attribution_utility_scatter.png",
        "utility_by_category.png",
    ):
        path = tmp_path / filename
        assert path.exists()
        assert path.stat().st_size > 0


def test_stratified_buckets_include_utility_status() -> None:
    records: list[AttributionRecord] = []
    annotations: dict[str, ReflectionAnnotation] = {}
    traces: dict[str, ReflectionTrace] = {}
    for index in range(5):
        trace_id = f"t{index}"
        records.append(
            AttributionRecord(
                trace_id=trace_id,
                attribution_score=0.5,
                utility_delta=0.1,
                intervention_type="delete",
                is_local=True,
            )
        )
        annotations[trace_id] = ReflectionAnnotation(
            category=ReflectionCategory.VERIFICATION,
            confidence=1.0,
            rationale="test",
        )
        traces[trace_id] = ReflectionTrace(
            trace_id=trace_id,
            reflection_text="verify the result",
            task_id=trace_id,
            task_difficulty=2,
            intervention_magnitude=0.2,
            locality_score=0.9,
        )

    metrics = StratifiedEvaluator().evaluate(
        StratifiedInput(records=records, annotations=annotations, traces=traces)
    )

    assert metrics["category"]["VERIFICATION"].utility_status == "ok"
    assert metrics["category"]["OTHER"].utility_status == "insufficient_samples"
