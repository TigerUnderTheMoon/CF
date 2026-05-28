from __future__ import annotations

from collections import Counter

import pytest

from fma.eval.counterfactual_attribution import (
    ABLATION_STRATEGIES,
    ATTRIBUTION_BOTTOM_K,
    ATTRIBUTION_SCORE_MAP,
    ATTRIBUTION_TOP_K,
    CATEGORY_MATCHED_RANDOM,
    RANDOM_K,
    ablate_step,
    attribution_score_for_type,
    compute_trace_utility,
    run_single_step_ablations,
    strategy_order,
)
from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
)


def make_annotation(
    idx: int,
    utility: UtilityLabel = UtilityLabel.NEUTRAL,
    attribution_type: str | None = None,
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


def make_trace(trace_id: str = "t1") -> dict[str, object]:
    return {
        "trace_id": trace_id,
        "reflection_chain": [
            {"category": "VERIFICATION", "text": "check arithmetic"},
            {"category": "PLANNING", "text": "plan next move"},
            {"category": "RETRIEVAL", "text": "recall condition"},
        ],
        "reflection_categories": ["VERIFICATION", "PLANNING", "RETRIEVAL"],
        "reflection_spans": [
            {"content": "check arithmetic", "step_index": 0},
            {"content": "plan next move", "step_index": 1},
            {"content": "recall condition", "step_index": 2},
        ],
        "reasoning_trace": "check arithmetic plan next move recall condition",
        "reflection_text": "check arithmetic plan next move recall condition",
    }


def test_phase4_attribution_score_mapping_is_exact() -> None:
    assert ATTRIBUTION_SCORE_MAP == {
        "factual_error": 0.90,
        "reasoning_gap": 0.75,
        "metacognitive": 0.60,
        "vague": 0.30,
        "irrelevant": 0.10,
    }
    assert attribution_score_for_type(None) == 0.0
    assert attribution_score_for_type("unknown") == 0.0


def test_trace_utility_uses_helpful_ceiling_and_empty_neutral() -> None:
    assert compute_trace_utility([]) == 0.0
    assert compute_trace_utility(
        [
            make_annotation(0, UtilityLabel.HELPFUL),
            make_annotation(1, UtilityLabel.HARMFUL),
        ]
    ) == 1.0
    assert compute_trace_utility(
        [
            make_annotation(0, UtilityLabel.SPURIOUS),
            make_annotation(1, UtilityLabel.HARMFUL),
        ]
    ) == pytest.approx(-0.75)


def test_ablate_step_removes_reflection_without_mutating_original() -> None:
    trace = make_trace()
    ablated = ablate_step(trace, 1)

    assert len(trace["reflection_chain"]) == 3
    assert [step["text"] for step in ablated["reflection_chain"]] == [
        "check arithmetic",
        "recall condition",
    ]
    assert ablated["reflection_categories"] == ["VERIFICATION", "RETRIEVAL"]
    assert [span["step_index"] for span in ablated["reflection_spans"]] == [0, 1]
    assert "plan next move" not in ablated["reasoning_trace"]


def test_ablation_strategy_orders_are_deterministic() -> None:
    annotations = [
        make_annotation(0, attribution_type="vague"),
        make_annotation(1, attribution_type="factual_error"),
        make_annotation(2, attribution_type="irrelevant"),
    ]

    assert strategy_order(annotations, ATTRIBUTION_TOP_K, seed=7) == [1, 0, 2]
    assert strategy_order(annotations, ATTRIBUTION_BOTTOM_K, seed=7) == [2, 0, 1]
    assert strategy_order(annotations, RANDOM_K, seed=7) == strategy_order(annotations, RANDOM_K, seed=7)
    assert strategy_order(annotations, CATEGORY_MATCHED_RANDOM, seed=7) == strategy_order(
        annotations,
        CATEGORY_MATCHED_RANDOM,
        seed=7,
    )


def test_single_step_ablations_emit_one_run_per_strategy_and_step() -> None:
    annotations = [
        make_annotation(0, UtilityLabel.HELPFUL, "factual_error"),
        make_annotation(1, UtilityLabel.NEUTRAL, "irrelevant"),
        make_annotation(2, UtilityLabel.HARMFUL, "reasoning_gap"),
    ]

    results = run_single_step_ablations([make_trace()], annotations, seed=11)

    assert len(results) == len(ABLATION_STRATEGIES) * len(annotations)
    assert Counter(result.strategy for result in results) == {
        strategy: len(annotations) for strategy in ABLATION_STRATEGIES
    }
    assert all(result.trace_id == "t1" for result in results)
