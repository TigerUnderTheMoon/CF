from __future__ import annotations

import math

import pytest

from fma.eval.stratified_eval import StratifiedEvaluator
from fma.types import (
    AttributionRecord,
    ReflectionAnnotation,
    ReflectionCategory,
    ReflectionTrace,
    StratifiedInput,
)


def make_input(
    scores: list[float],
    utilities: list[float],
    categories: list[ReflectionCategory] | None = None,
    missing_annotations: set[int] | None = None,
) -> StratifiedInput:
    records: list[AttributionRecord] = []
    annotations: dict[str, ReflectionAnnotation] = {}
    traces: dict[str, ReflectionTrace] = {}
    categories = categories or [ReflectionCategory.VERIFICATION] * len(scores)
    missing_annotations = missing_annotations or set()

    for index, (score, utility, category) in enumerate(zip(scores, utilities, categories, strict=True)):
        trace_id = f"trace_{index}"
        records.append(
            AttributionRecord(
                trace_id=trace_id,
                attribution_score=score,
                utility_delta=utility,
                intervention_type="masking",
                is_local=index % 2 == 0,
            )
        )
        traces[trace_id] = ReflectionTrace(
            trace_id=trace_id,
            reflection_text="verify the intermediate result",
            task_id=f"task_{index}",
            task_difficulty=1 + (index % 5),
            intervention_magnitude=[0.2, 0.5, 0.9][index % 3],
            locality_score=[0.9, 0.6, 0.2][index % 3],
        )
        if index not in missing_annotations:
            annotations[trace_id] = ReflectionAnnotation(
                category=category,
                confidence=1.0,
                rationale="test annotation",
            )

    return StratifiedInput(records=records, annotations=annotations, traces=traces)


def test_empty_bucket_nan() -> None:
    inputs = make_input([0.2, 0.4], [0.0, 1.0])
    metrics = StratifiedEvaluator().evaluate(inputs)
    assert metrics["category"]["VERIFICATION"].n_samples == 2
    assert metrics["category"]["VERIFICATION"].status == "insufficient_samples"
    assert metrics["category"]["VERIFICATION"].required == 5
    assert math.isnan(metrics["category"]["VERIFICATION"].mean_utility_delta)
    assert metrics["category"]["DECOMPOSITION"].n_samples == 0
    assert metrics["category"]["DECOMPOSITION"].status == "insufficient_samples"
    assert math.isnan(metrics["category"]["DECOMPOSITION"].mean_utility_delta)


def test_missing_annotation_skipped() -> None:
    inputs = make_input([0.2, 0.3, 0.4, 0.5, 0.6, 0.7], [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], missing_annotations={5})
    metrics = StratifiedEvaluator().evaluate(inputs)
    assert metrics["category"]["VERIFICATION"].n_samples == 5
    assert metrics["category"]["VERIFICATION"].status == "ok"
    assert metrics["category"]["VERIFICATION"].mean_utility_delta == pytest.approx(0.4)


def test_all_empty_raises() -> None:
    inputs = make_input([0.2, 0.3], [0.0, 0.2], missing_annotations={0, 1})
    with pytest.raises(ValueError, match="no valid evaluation data"):
        StratifiedEvaluator().evaluate(inputs)


def test_instability_detection() -> None:
    inputs = make_input([0.1, 0.1, 0.9], [0.0, 0.0, 1.0])
    cases = StratifiedEvaluator().get_instability_cases(inputs, threshold=0.4)
    assert [case["trace_id"] for case in cases] == ["trace_2"]
    assert cases[0]["bucket"] == "category:VERIFICATION"


def test_reproducibility() -> None:
    inputs = make_input([0.2, 0.4, 0.6, 0.8, 1.0], [0.0, 0.2, 0.4, 0.6, 0.8])
    first = StratifiedEvaluator(random_seed=7).evaluate(inputs)
    second = StratifiedEvaluator(random_seed=7).evaluate(inputs)
    assert first["category"]["VERIFICATION"].mean_utility_delta == second["category"]["VERIFICATION"].mean_utility_delta
    assert first["category"]["VERIFICATION"].attribution_stability == second["category"]["VERIFICATION"].attribution_stability
    assert 0.0 < first["category"]["VERIFICATION"].attribution_stability <= 1.0
