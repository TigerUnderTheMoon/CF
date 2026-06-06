"""Diagnostics for interpreting structural reflection attribution outputs."""

from fma.eval.diagnostics.correlation_metrics import (
    correlation_summary,
    kendall_tau,
    pearson,
    scatter_summary,
    spearman,
    top_k_overlap,
)
from fma.eval.diagnostics.topology_statistics import (
    StructuralDiagnosticRecord,
    grouped_correlations,
    join_phase5_structural_records,
    mode_diagnostics,
    records_to_dicts,
    stratified_correlations,
)
from fma.eval.diagnostics.zero_inflation import zero_inflation_stats

__all__ = [
    "StructuralDiagnosticRecord",
    "correlation_summary",
    "grouped_correlations",
    "join_phase5_structural_records",
    "kendall_tau",
    "mode_diagnostics",
    "pearson",
    "records_to_dicts",
    "scatter_summary",
    "spearman",
    "stratified_correlations",
    "top_k_overlap",
    "zero_inflation_stats",
]
