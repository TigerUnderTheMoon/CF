from __future__ import annotations

from collections import Counter

from fma.generation import DiverseReflectionGenerator, ReflectionStyle, TEMPLATE_POOLS


def test_template_pools_have_minimum_coverage() -> None:
    for style in ReflectionStyle:
        assert len(TEMPLATE_POOLS[style]) >= 3


def test_generation_deterministic_for_fixed_seed() -> None:
    generator = DiverseReflectionGenerator()
    first = generator.generate(ReflectionStyle.PLANNING, seed=7, n=5)
    second = generator.generate(ReflectionStyle.PLANNING, seed=7, n=5)
    assert [trace.to_dict() for trace in first] == [trace.to_dict() for trace in second]


def test_explicit_category_sequence_preserved() -> None:
    generator = DiverseReflectionGenerator()
    traces = generator.generate_chain(
        [ReflectionStyle.PLANNING, ReflectionStyle.VERIFICATION, ReflectionStyle.BACKTRACKING],
        seed=11,
        n=2,
    )
    assert all(
        trace.categories() == ["PLANNING", "VERIFICATION", "BACKTRACKING"]
        for trace in traces
    )


def test_balanced_generation_represents_all_categories() -> None:
    generator = DiverseReflectionGenerator()
    traces = generator.generate_balanced(n_per_category=4, seed=42, chain_length=3)
    primary_counts = Counter(trace.categories()[0] for trace in traces)
    assert set(primary_counts) == {style.name for style in ReflectionStyle}
    assert all(count == 4 for count in primary_counts.values())
