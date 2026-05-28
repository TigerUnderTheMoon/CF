from __future__ import annotations

import math

from fma.eval.locality_stress_test import (
    LocalityStressTester,
    compute_trace_utility,
    normalized_levenshtein_on_category_sequence,
)
from fma.generation import DiverseReflectionGenerator, ReflectionStyle
from fma.intervention import InterventionType, StructuralInterventionEngine


def make_trace():
    return DiverseReflectionGenerator().generate_chain(
        [
            ReflectionStyle.DECOMPOSITION,
            ReflectionStyle.PLANNING,
            ReflectionStyle.VERIFICATION,
        ],
        seed=13,
        n=1,
    )[0]


def test_trace_utility_bounded() -> None:
    utility = compute_trace_utility(make_trace())
    assert 0.0 <= utility <= 1.0


def test_locality_metrics_are_finite_for_each_intervention_type() -> None:
    trace = make_trace()
    engine = StructuralInterventionEngine()
    tester = LocalityStressTester()
    for index, intervention_type in enumerate(InterventionType):
        result = tester.evaluate(
            trace,
            engine,
            seed=100 + index,
            intervention_type=intervention_type,
            target_index=1 if intervention_type is not InterventionType.SHUFFLE else None,
        )
        values = [
            result.edit_distance,
            result.utility_before,
            result.utility_after,
            result.utility_shift,
            result.locality_ratio,
        ]
        assert all(math.isfinite(value) for value in values)


def test_normalized_category_edit_distance_bounded() -> None:
    distance = normalized_levenshtein_on_category_sequence(
        ["PLANNING", "VERIFICATION"],
        ["PLANNING", "CONTRADICTION", "VERIFICATION"],
    )
    assert 0.0 <= distance <= 1.0
