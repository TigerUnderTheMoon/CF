from __future__ import annotations

from fma.generation import DiverseReflectionGenerator, ReflectionStyle
from fma.intervention import InterventionType, StructuralInterventionEngine


def make_trace():
    return DiverseReflectionGenerator().generate_chain(
        [ReflectionStyle.PLANNING, ReflectionStyle.VERIFICATION, ReflectionStyle.RETRIEVAL],
        seed=5,
        n=1,
    )[0]


def test_structural_intervention_reproducible() -> None:
    trace = make_trace()
    engine = StructuralInterventionEngine()
    first, first_meta = engine.apply(trace, InterventionType.REPLACE, seed=17)
    second, second_meta = engine.apply(trace, InterventionType.REPLACE, seed=17)
    assert first == second
    assert first_meta == second_meta


def test_interventions_do_not_mutate_input_trace() -> None:
    trace = make_trace()
    original = trace.to_dict()
    engine = StructuralInterventionEngine()
    engine.apply(trace, InterventionType.DELETE, seed=3, target_index=1)
    assert trace.to_dict() == original


def test_each_intervention_semantics() -> None:
    trace = make_trace()
    engine = StructuralInterventionEngine()

    deleted, _ = engine.apply(trace, InterventionType.DELETE, seed=1, target_index=1)
    assert deleted.categories() == ["PLANNING", "RETRIEVAL"]

    shuffled, _ = engine.apply(trace, InterventionType.SHUFFLE, seed=2)
    assert sorted(shuffled.categories()) == sorted(trace.categories())

    replaced, _ = engine.apply(trace, InterventionType.REPLACE, seed=3, target_index=0)
    assert len(replaced) == len(trace)
    assert replaced.categories()[0] != "PLANNING"

    truncated, _ = engine.apply(trace, InterventionType.TRUNCATE, seed=4, target_index=1)
    assert truncated.categories() == ["PLANNING", "VERIFICATION"]

    contradicted, _ = engine.apply(trace, InterventionType.CONTRADICT, seed=5, target_index=1)
    assert contradicted.categories() == ["PLANNING", "VERIFICATION", "CONTRADICTION", "RETRIEVAL"]


def test_metadata_hashes_change_after_edit() -> None:
    trace = make_trace()
    _edited, metadata = StructuralInterventionEngine().apply(
        trace,
        InterventionType.CONTRADICT,
        seed=9,
        target_index=0,
    )
    assert metadata.intervention_type == "contradict"
    assert metadata.target_index == 0
    assert metadata.before_hash != metadata.after_hash


def test_destructive_interventions_are_marked_proxy_only() -> None:
    trace = make_trace()
    engine = StructuralInterventionEngine()

    for intervention_type in (
        InterventionType.DELETE,
        InterventionType.SHUFFLE,
        InterventionType.REPLACE,
        InterventionType.TRUNCATE,
        InterventionType.CONTRADICT,
    ):
        _edited, metadata = engine.apply(
            trace,
            intervention_type,
            seed=11,
            target_index=0 if intervention_type is not InterventionType.SHUFFLE else None,
        )

        assert metadata.details["structure_preserving"] is False
        assert metadata.details["primary_ciu_allowed"] is False
        assert metadata.details["proxy_only"] is True
        assert metadata.details["evidence_role"] == "destructive_diagnostic"
