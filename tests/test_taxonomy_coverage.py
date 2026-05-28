from __future__ import annotations

import pytest

from fma.eval.taxonomy_coverage import TaxonomyCoverageAnalyzer
from fma.generation import DiverseReflectionGenerator, ReflectionStyle


def test_balanced_taxonomy_entropy_high_and_all_represented() -> None:
    traces = DiverseReflectionGenerator().generate_balanced(
        n_per_category=20,
        seed=42,
        chain_length=1,
    )
    report = TaxonomyCoverageAnalyzer().analyze(traces)
    assert report.entropy > 2.5
    assert report.collapsed is False
    assert report.rare_categories == []
    assert all(report.taxonomy_distribution[style.name] > 0 for style in ReflectionStyle)


def test_taxonomy_collapse_warning() -> None:
    traces = DiverseReflectionGenerator().generate(ReflectionStyle.VERIFICATION, seed=1, n=20)
    with pytest.warns(RuntimeWarning, match="taxonomy collapse detected"):
        report = TaxonomyCoverageAnalyzer().analyze(traces)
    assert report.collapsed is True
    assert "taxonomy collapse detected" in report.warnings
