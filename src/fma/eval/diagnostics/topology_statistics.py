"""Grouped diagnostics for local-to-structural attribution comparisons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Hashable, Mapping, Sequence

from fma.eval.diagnostics.correlation_metrics import correlation_summary, scatter_summary
from fma.eval.diagnostics.zero_inflation import zero_inflation_stats


@dataclass(frozen=True)
class StructuralDiagnosticRecord:
    trace_id: str
    node_id: str
    step_idx: int
    taxonomy_label: str
    attribution_score: float
    structural_necessity: float
    removal_mode: str
    is_source_node: bool


def join_phase5_structural_records(
    node_rows: Sequence[Mapping[str, Any] | Any],
    phase5_scores: Sequence[Mapping[str, Any]],
    source_node_ids: set[str] | None = None,
    removal_mode: str | None = None,
) -> list[StructuralDiagnosticRecord]:
    """Join Phase 5 attribution scores with structural node necessity rows."""
    attribution_by_key = {
        (str(row.get("trace_id")), int(row.get("step_idx"))): float(
            row.get("attribution_score", 0.0)
        )
        for row in phase5_scores
        if "trace_id" in row and "step_idx" in row
    }
    sources = source_node_ids or set()
    records: list[StructuralDiagnosticRecord] = []
    for row in node_rows:
        trace_id = str(_field(row, "trace_id"))
        step_idx = int(_field(row, "step_idx"))
        key = (trace_id, step_idx)
        if key not in attribution_by_key:
            continue
        node_id = str(_field(row, "node_id"))
        records.append(
            StructuralDiagnosticRecord(
                trace_id=trace_id,
                node_id=node_id,
                step_idx=step_idx,
                taxonomy_label=str(_field(row, "taxonomy_label")),
                attribution_score=attribution_by_key[key],
                structural_necessity=float(_field(row, "necessity")),
                removal_mode=str(removal_mode or _field(row, "removal_mode", "")),
                is_source_node=node_id in sources,
            )
        )
    return records


def mode_diagnostics(
    records: Sequence[StructuralDiagnosticRecord],
    top_k_values: Sequence[int] = (3, 5, 10),
) -> dict[str, Any]:
    """Return all scalar and grouped diagnostics for one removal mode."""
    attribution = [record.attribution_score for record in records]
    necessity = [record.structural_necessity for record in records]
    keys = [(record.trace_id, record.step_idx) for record in records]
    return {
        "correlation": correlation_summary(
            attribution,
            necessity,
            keys=keys,
            top_k_values=top_k_values,
        ),
        "zero_inflation": zero_inflation_stats(attribution, necessity),
        "scatter": scatter_summary(attribution, necessity),
        "stratified": stratified_correlations(records),
    }


def stratified_correlations(
    records: Sequence[StructuralDiagnosticRecord],
) -> dict[str, dict[str, dict[str, float]]]:
    """Compute per-taxonomy, per-step, and source-role correlation summaries."""
    return {
        "taxonomy": grouped_correlations(records, lambda record: record.taxonomy_label),
        "step_idx": grouped_correlations(records, lambda record: str(record.step_idx)),
        "source_role": grouped_correlations(
            records,
            lambda record: "source_node" if record.is_source_node else "non_source_node",
        ),
    }


def grouped_correlations(
    records: Sequence[StructuralDiagnosticRecord],
    key_fn: Callable[[StructuralDiagnosticRecord], Hashable],
) -> dict[str, dict[str, float]]:
    """Compute sample count, Pearson, and Spearman for deterministic groups."""
    grouped: dict[str, list[StructuralDiagnosticRecord]] = {}
    for record in records:
        grouped.setdefault(str(key_fn(record)), []).append(record)

    summaries: dict[str, dict[str, float]] = {}
    for group_key in sorted(grouped):
        group = grouped[group_key]
        attribution = [record.attribution_score for record in group]
        necessity = [record.structural_necessity for record in group]
        summary = correlation_summary(attribution, necessity, top_k_values=())
        summaries[group_key] = {
            "num_samples": int(summary["num_samples"]),
            "pearson": float(summary["pearson"]),
            "spearman": float(summary["spearman"]),
        }
    return summaries


def records_to_dicts(records: Sequence[StructuralDiagnosticRecord]) -> list[dict[str, Any]]:
    """Serialize diagnostic records for optional inspection."""
    return [asdict(record) for record in records]


def _field(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


__all__ = [
    "StructuralDiagnosticRecord",
    "grouped_correlations",
    "join_phase5_structural_records",
    "mode_diagnostics",
    "records_to_dicts",
    "stratified_correlations",
]
