from __future__ import annotations

from pathlib import Path

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
from fma.graph.diagnostics import (
    MODE_ORDER,
    _cross_mode_summary,
    _project_path,
    _uses_hydra_config,
    write_markdown,
    write_plots,
)


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


def test_structural_diagnostics_artifact_writers_capture_claim_safe_boundary(
    tmp_path: Path,
) -> None:
    report = _diagnostic_report()
    records_by_mode = {
        mode: [
            StructuralDiagnosticRecord(
                trace_id=f"trace-{mode.lower()}",
                node_id=f"node-{mode.lower()}-source",
                step_idx=0,
                taxonomy_label="VERIFY",
                attribution_score=0.7,
                structural_necessity=0.2,
                removal_mode=mode,
                is_source_node=True,
            ),
            StructuralDiagnosticRecord(
                trace_id=f"trace-{mode.lower()}",
                node_id=f"node-{mode.lower()}-non-source",
                step_idx=1,
                taxonomy_label="PLAN",
                attribution_score=0.3,
                structural_necessity=0.6,
                removal_mode=mode,
                is_source_node=False,
            ),
        ]
        for mode in MODE_ORDER
    }

    markdown_path = tmp_path / "structural_diagnostics.md"
    figures_dir = tmp_path / "figures"

    write_markdown(markdown_path, report)
    write_plots(records_by_mode, report, figures_dir)

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "does not claim true causal identification" in markdown
    assert "| PRUNE |" in markdown
    assert "weak structural alignment" in markdown
    assert (
        figures_dir / "structural_diagnostics_attribution_vs_necessity.png"
    ).stat().st_size > 0
    assert (
        figures_dir / "structural_diagnostics_mode_comparison.png"
    ).stat().st_size > 0


def test_structural_diagnostics_helpers_detect_hydra_and_paths() -> None:
    assert _uses_hydra_config(["--config-name=phase6/graph"])
    assert _uses_hydra_config(["+intervention_mode=BYPASS"])
    assert _uses_hydra_config(["paths.output_root=outputs/tmp"])
    assert not _uses_hydra_config(["--traces", "data/traces/synthetic_100x8.json"])

    relative_path = _project_path("data/traces/synthetic_100x8.json")
    absolute_path = Path("D:/CF/data/traces/synthetic_100x8.json")

    assert relative_path.is_absolute()
    assert _project_path(absolute_path) == absolute_path

    summary = _cross_mode_summary(_diagnostic_report()["modes"])

    assert summary["lowest_pearson_mode"] == MODE_ORDER[0]
    assert summary["highest_pearson_mode"] == MODE_ORDER[-1]
    assert summary["mean_zero_structural_necessity_fraction"] == pytest.approx(0.2)


def _diagnostic_report() -> dict:
    modes = {}
    for index, mode in enumerate(MODE_ORDER):
        modes[mode] = {
            "correlation": {
                "pearson": 0.1 + index,
                "spearman": 0.2 + index,
                "kendall_tau": 0.05 + index,
                "top_k_overlap": {"10": 0.5},
            },
            "zero_inflation": {
                "zero_structural_necessity_fraction": 0.2,
                "positive_attribution_zero_necessity_fraction": 0.1,
                "positive_structural_necessity_fraction": 0.8,
            },
            "scatter": {
                "num_samples": 2,
                "attribution_score": {"mean": 0.5},
                "structural_necessity": {"mean": 0.4, "median": 0.3},
            },
            "stratified": {
                "taxonomy": {
                    "VERIFY": {"num_samples": 1, "pearson": 1.0, "spearman": 1.0},
                    "PLAN": {"num_samples": 1, "pearson": -1.0, "spearman": -1.0},
                },
                "step_idx": {
                    "0": {"num_samples": 1, "pearson": 1.0, "spearman": 1.0},
                    "1": {"num_samples": 1, "pearson": -1.0, "spearman": -1.0},
                },
                "source_role": {
                    "source_node": {"num_samples": 1, "pearson": 1.0, "spearman": 1.0},
                    "non_source_node": {
                        "num_samples": 1,
                        "pearson": -1.0,
                        "spearman": -1.0,
                    },
                },
            },
        }
    return {"modes": modes}
