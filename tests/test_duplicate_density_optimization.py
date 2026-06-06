"""Tests for _duplicate_density exact vs fast approximation."""

from __future__ import annotations

import pytest
from scipy.stats import spearmanr

from fma.eval.counterfactual_attribution import (
    _duplicate_density,
    _duplicate_density_exact,
    _duplicate_density_fast,
)
from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
)


def _make_annotation(
    idx: int,
    attribution_type: str = "factual_error",
    trace_id: str = "t1",
) -> UtilityAnnotation:
    return UtilityAnnotation(
        trace_id=trace_id,
        reflection_idx=idx,
        utility=UtilityLabel.NEUTRAL,
        outcome_delta=OutcomeDelta.UNCHANGED,
        degradation_score=0.0,
        annotation_confidence=1.0,
        attribution_type=attribution_type,
        attribution_alignment=AttributionAlignment.PARTIAL,
        intervention_type="delete",
        reflection_category="VERIFICATION",
        correctness_preserved=True,
    )


def test_exact_vs_fast_small_input() -> None:
    """On small inputs (<50), default should use exact version."""
    annotations = [
        _make_annotation(0, "factual_error"),
        _make_annotation(1, "factual_error"),
        _make_annotation(2, "reasoning_gap"),
    ]
    texts = ["check the math carefully", "check the math carefully", "plan the approach"]

    result_default = _duplicate_density(annotations, texts)
    result_exact = _duplicate_density_exact(annotations, texts)

    assert result_default == result_exact


def test_fast_approximate_flag() -> None:
    """approximate=True should always use fast version."""
    annotations = [_make_annotation(i, "factual_error") for i in range(10)]
    texts = [f"step text {i}" for i in range(10)]

    result_fast = _duplicate_density(annotations, texts, approximate=True)
    result_fast_direct = _duplicate_density_fast(annotations, texts)

    assert result_fast == result_fast_direct


def test_exact_fast_correlation() -> None:
    """Fast and exact versions should have Spearman > 0.95 correlation."""
    import random

    rng = random.Random(42)
    types = ["factual_error", "reasoning_gap", "metacognitive", "vague", "irrelevant"]
    base_texts = [
        "verify the calculation step by step",
        "check arithmetic operations carefully",
        "plan the next reasoning move",
        "recall the relevant condition",
        "diagnose the error in reasoning",
        "reflect on the strategy used",
        "evaluate the correctness of the answer",
        "consider alternative approaches",
    ]

    results_exact = []
    results_fast = []

    for trial in range(30):
        n = rng.randint(5, 40)
        annotations = [
            _make_annotation(i, types[rng.randint(0, len(types) - 1)])
            for i in range(n)
        ]
        texts = [base_texts[rng.randint(0, len(base_texts) - 1)] for _ in range(n)]

        exact_val = _duplicate_density_exact(annotations, texts)
        fast_val = _duplicate_density_fast(annotations, texts)
        results_exact.append(exact_val)
        results_fast.append(fast_val)

    if len(set(results_exact)) < 2 or len(set(results_fast)) < 2:
        pytest.skip("Insufficient variance for correlation test")

    correlation, p_value = spearmanr(results_exact, results_fast)
    assert correlation > 0.95, f"Spearman correlation {correlation} < 0.95"


def test_duplicate_density_empty() -> None:
    """Empty annotations should return 0.0."""
    assert _duplicate_density([], []) == 0.0
    assert _duplicate_density_exact([], []) == 0.0
    assert _duplicate_density_fast([], []) == 0.0


def test_duplicate_density_single() -> None:
    """Single annotation should return 0.0."""
    ann = [_make_annotation(0)]
    assert _duplicate_density(ann, ["text"]) == 0.0
    assert _duplicate_density_exact(ann, ["text"]) == 0.0
    assert _duplicate_density_fast(ann, ["text"]) == 0.0


def test_duplicate_density_all_duplicates() -> None:
    """Identical texts with same type should yield high density."""
    annotations = [_make_annotation(i, "factual_error") for i in range(5)]
    texts = ["check the math carefully"] * 5

    density = _duplicate_density_exact(annotations, texts)
    assert density == 1.0


def test_duplicate_density_no_duplicates() -> None:
    """Completely different texts should yield 0.0 density."""
    annotations = [_make_annotation(i, "factual_error") for i in range(4)]
    texts = [
        "check arithmetic",
        "plan next steps",
        "recall conditions",
        "verify result",
    ]

    density = _duplicate_density_exact(annotations, texts)
    assert density == 0.0


def test_automatic_threshold_switch() -> None:
    """Inputs > 50 should automatically use fast version."""
    annotations = [_make_annotation(i, "factual_error") for i in range(60)]
    texts = [f"step text {i % 10}" for i in range(60)]

    result = _duplicate_density(annotations, texts)
    fast_result = _duplicate_density_fast(annotations, texts)

    assert result == fast_result


def test_exact_preserved_for_small_explicit() -> None:
    """approximate=False with small input should use exact."""
    annotations = [_make_annotation(i, "factual_error") for i in range(5)]
    texts = ["check math"] * 5

    result = _duplicate_density(annotations, texts, approximate=False)
    exact_result = _duplicate_density_exact(annotations, texts)

    assert result == exact_result
