from __future__ import annotations

import pytest

from fma.eval.diagnostics.correlation_metrics import (
    correlation_summary,
    kendall_tau,
    pearson,
    spearman,
    top_k_overlap,
)
from fma.eval.diagnostics.topology_statistics import (
    StructuralDiagnosticRecord,
    grouped_correlations,
    mode_diagnostics,
)
from fma.eval.diagnostics.zero_inflation import zero_inflation_stats


def test_correlation_metrics_are_deterministic_for_monotonic_scores() -> None:
    left = [0.1, 0.3, 0.6, 0.9]
    right = [0.0, 0.2, 0.5, 1.0]

    assert pearson(left, right) > 0.98
    assert spearman(left, right) == pytest.approx(1.0)
    assert kendall_tau(left, right) == pytest.approx(1.0)

    summary = correlation_summary(left, right, top_k_values=(2,))

    assert summary["num_samples"] == 4
    assert summary["top_k_overlap"]["2"] == pytest.approx(1.0)


def test_kendall_tau_handles_ties_without_nan() -> None:
    left = [1.0, 1.0, 2.0, 3.0]
    right = [0.0, 0.0, 4.0, 2.0]

    value = kendall_tau(left, right)

    assert value == pytest.approx(0.6)


def test_top_k_overlap_uses_stable_keys() -> None:
    left = [0.9, 0.8, 0.1]
    right = [0.2, 0.8, 0.7]
    keys = ["a", "b", "c"]

    assert top_k_overlap(left, right, 2, keys=keys) == pytest.approx(0.5)


def test_zero_inflation_reports_local_to_structural_mismatch() -> None:
    stats = zero_inflation_stats(
        attribution_scores=[0.9, 0.6, 0.0, 0.3],
        structural_necessity=[0.0, 0.5, 0.2, 0.0],
    )

    assert stats["zero_structural_necessity_fraction"] == pytest.approx(0.5)
    assert stats["positive_attribution_zero_necessity_count"] == 2
    assert stats["positive_attribution_zero_necessity_fraction"] == pytest.approx(0.5)
    assert stats["zero_attribution_positive_necessity_count"] == 1


def test_grouped_diagnostics_report_counts_and_rank_correlation() -> None:
    records = [
        StructuralDiagnosticRecord("t1", "a", 0, "VERIFY", 0.1, 0.0, "PRUNE", True),
        StructuralDiagnosticRecord("t1", "b", 1, "VERIFY", 0.7, 1.0, "PRUNE", False),
        StructuralDiagnosticRecord("t2", "c", 0, "PLAN", 0.8, 0.0, "PRUNE", True),
        StructuralDiagnosticRecord("t2", "d", 1, "PLAN", 0.2, 1.0, "PRUNE", False),
    ]

    taxonomy = grouped_correlations(records, lambda record: record.taxonomy_label)
    report = mode_diagnostics(records, top_k_values=(2,))

    assert taxonomy["VERIFY"]["num_samples"] == 2
    assert taxonomy["VERIFY"]["spearman"] == pytest.approx(1.0)
    assert taxonomy["PLAN"]["spearman"] == pytest.approx(-1.0)
    assert report["stratified"]["source_role"]["source_node"]["num_samples"] == 2
    assert report["correlation"]["top_k_overlap"]["2"] == pytest.approx(0.5)
