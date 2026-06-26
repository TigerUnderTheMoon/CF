"""Diagnostic separability analysis for WebQSP trace-audit outputs."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from fma.eval.prm800k_audit_prioritization import keep_count
from fma.trace_audit.schema import CLAIM, ROUTE_ID


IN_DISPENSABLE_STEP_TYPES = {
    "entity_linking",
    "relation_traversal",
    "answer_verification",
}


def build_separability_report(
    importance_rows: Sequence[Mapping[str, Any]],
    ranking_results: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in importance_rows]
    ranking = dict(ranking_results or {})
    by_step_type = _summarize_by_step_type(rows)
    traces = _group_by_trace(rows)
    keep_counts = sorted({keep_count(len(trace_rows), 0.25) for trace_rows in traces.values()})
    six_step_keep_count = keep_count(6, 0.25)
    binary_separable = _step_type_binary_separable(by_step_type)
    continuous_perfect = _step_type_continuous_value_perfect(by_step_type)
    position_profile = _position_profile(rows)
    method_diagnostics = _method_diagnostics(ranking)

    return {
        "route_id": ROUTE_ID,
        "claim": CLAIM,
        "analysis_scope": "diagnostic_fixed_schema_separability",
        "not_a_kgqa_benchmark": True,
        "validated_kbs_workflow": False,
        "trace_count": len(traces),
        "step_count": len(rows),
        "step_type_summary": by_step_type,
        "position_summary": position_profile,
        "step_type_binary_separable": binary_separable,
        "step_type_continuous_value_perfect": continuous_perfect,
        "metric_artifacts": {
            "review_budget_fraction": 0.25,
            "observed_keep_counts": keep_counts,
            "ndcg_at_25_keep_count_for_six_step_trace": six_step_keep_count,
            "top_budget_is_deterministic_indispensable_prefix": _top_budget_is_indispensable_prefix(
                traces,
                six_step_keep_count,
            ),
            "interpretation": (
                "NDCG@25 is weakly discriminative for fixed six-step traces because the "
                "top budget selects a deterministic prefix of indispensable steps."
            ),
        },
        "method_diagnostics": method_diagnostics,
        "linear_separability_interpretation": _interpretation(
            binary_separable,
            continuous_perfect,
            method_diagnostics,
        ),
        "recommended_positioning": "supplementary_diagnostic_evidence",
        "paper_safe_claim": (
            "WebQSP is diagnostic evidence that deterministic fixed-schema KG traces can "
            "make replay-derived importance largely separable by step role and position; "
            "it is not evidence of KGQA performance or deployed KBS validation."
        ),
        "forbidden_interpretations": [
            "SC-FMA improves KGQA accuracy on WebQSP",
            "WebQSP validates a deployed KBS workflow",
            "fixed-schema separability is universal across KG reasoning systems",
            "Ridge learns a new signal beyond raw replay delta under this schema",
        ],
    }


def render_separability_markdown(report: Mapping[str, Any]) -> str:
    methods = report.get("method_diagnostics", {})
    lines = [
        "# WebQSP Fixed-Schema Separability Diagnostic",
        "",
        "This is a fixed-schema separability diagnostic for replay-derived reasoning-step targets.",
        "",
        "This report analyzes replay-derived reasoning-step targets. It is not a KGQA benchmark result.",
        "",
        "## Summary",
        "",
        f"- Traces: {report.get('trace_count', 0)}",
        f"- Steps: {report.get('step_count', 0)}",
        f"- Step-type binary separable: `{str(report.get('step_type_binary_separable')).lower()}`",
        f"- Step-type exact continuous-value predictor: `{str(report.get('step_type_continuous_value_perfect')).lower()}`",
        f"- Recommended positioning: `{report.get('recommended_positioning')}`",
        "",
        "## Step-Type Target Profile",
        "",
        "| Step type | Count | Min | Max | Unique values |",
        "|---|---:|---:|---:|---:|",
    ]
    for step_type, values in report.get("step_type_summary", {}).items():
        if not isinstance(values, Mapping):
            continue
        lines.append(
            f"| {step_type} | {int(values.get('count', 0))} | "
            f"{float(values.get('min', 0.0)):.6f} | "
            f"{float(values.get('max', 0.0)):.6f} | "
            f"{int(values.get('unique_values', 0))} |"
        )

    lines.extend(
        [
            "",
            "## Metric Artifact",
            "",
            f"- NDCG@25 keep count for a six-step trace: `{report.get('metric_artifacts', {}).get('ndcg_at_25_keep_count_for_six_step_trace')}`",
            f"- Top budget selects deterministic indispensable prefix: `{str(report.get('metric_artifacts', {}).get('top_budget_is_deterministic_indispensable_prefix')).lower()}`",
            "",
            "## Method Diagnostics",
            "",
            f"- Ridge matches raw replay delta on pairwise accuracy: `{str(methods.get('scfma_ridge_matches_raw_delta_pairwise')).lower()}`",
            f"- Ridge NDCG@25: {float(methods.get('scfma_ridge', {}).get('ndcg_at_25', 0.0)):.6f}",
            f"- Raw replay delta NDCG@25: {float(methods.get('raw_rule_delta', {}).get('ndcg_at_25', 0.0)):.6f}",
            f"- Relative-position NDCG@25: {float(methods.get('relative_position', {}).get('ndcg_at_25', 0.0)):.6f}",
            "",
            "## Interpretation",
            "",
            str(report.get("linear_separability_interpretation", "")),
            "",
            "Paper-safe claim:",
            "",
            f"> {report.get('paper_safe_claim', '')}",
            "",
        ]
    )
    return "\n".join(lines)


def write_separability_report(
    importance_rows: Sequence[Mapping[str, Any]],
    ranking_results: Mapping[str, Any],
    *,
    output_json: str | Path,
    output_md: str | Path | None = None,
) -> dict[str, Any]:
    report = build_separability_report(importance_rows, ranking_results)
    json_path = Path(output_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if output_md is not None:
        md_path = Path(output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_separability_markdown(report), encoding="utf-8")
    return report


def _summarize_by_step_type(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("step_type"))].append(float(row.get("importance_target", 0.0)))
    summary = {}
    for step_type in sorted(grouped):
        values = grouped[step_type]
        summary[step_type] = {
            "count": len(values),
            "min": float(min(values)) if values else 0.0,
            "max": float(max(values)) if values else 0.0,
            "mean": float(np.mean(values)) if values else 0.0,
            "unique_values": len({round(value, 12) for value in values}),
            "is_deterministic": len({round(value, 12) for value in values}) == 1,
            "binary_class": "indispensable" if step_type in IN_DISPENSABLE_STEP_TYPES else "recoverable",
        }
    return summary


def _group_by_trace(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    traces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        traces[str(row.get("trace_id"))].append(dict(row))
    for trace_rows in traces.values():
        trace_rows.sort(key=lambda row: int(row.get("step_index", 0)))
    return traces


def _step_type_binary_separable(step_summary: Mapping[str, Mapping[str, Any]]) -> bool:
    indispensable_min = [
        float(values.get("min", 0.0))
        for step_type, values in step_summary.items()
        if step_type in IN_DISPENSABLE_STEP_TYPES
    ]
    recoverable_max = [
        float(values.get("max", 0.0))
        for step_type, values in step_summary.items()
        if step_type not in IN_DISPENSABLE_STEP_TYPES
    ]
    return bool(indispensable_min and recoverable_max and min(indispensable_min) > max(recoverable_max))


def _step_type_continuous_value_perfect(step_summary: Mapping[str, Mapping[str, Any]]) -> bool:
    return all(bool(values.get("is_deterministic")) for values in step_summary.values())


def _position_profile(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        grouped[int(row.get("step_index", 0))].append(float(row.get("importance_target", 0.0)))
    return {
        str(index): {
            "mean": float(np.mean(values)),
            "min": float(min(values)),
            "max": float(max(values)),
        }
        for index, values in sorted(grouped.items())
    }


def _top_budget_is_indispensable_prefix(
    traces: Mapping[str, Sequence[Mapping[str, Any]]],
    keep: int,
) -> bool:
    if keep <= 0 or not traces:
        return False
    for trace_rows in traces.values():
        prefix = list(trace_rows)[:keep]
        if len(prefix) < keep:
            return False
        if any(str(row.get("step_type")) not in IN_DISPENSABLE_STEP_TYPES for row in prefix):
            return False
    return True


def _method_diagnostics(ranking: Mapping[str, Any]) -> dict[str, Any]:
    methods = ranking.get("methods", {}) if isinstance(ranking, Mapping) else {}
    method_rows = {
        name: {
            "ndcg_at_25": _metric(methods, name, "ndcg_at_25"),
            "pairwise_accuracy": _metric(methods, name, "pairwise_accuracy"),
            "spearman": _metric(methods, name, "spearman"),
        }
        for name in ("relative_position", "raw_rule_delta", "scfma_ridge", "scfma_qp", "random", "graph_degree")
        if name in methods
    }
    ridge_pairwise = method_rows.get("scfma_ridge", {}).get("pairwise_accuracy", math.nan)
    raw_pairwise = method_rows.get("raw_rule_delta", {}).get("pairwise_accuracy", math.nan)
    ridge_ndcg = method_rows.get("scfma_ridge", {}).get("ndcg_at_25", math.nan)
    raw_ndcg = method_rows.get("raw_rule_delta", {}).get("ndcg_at_25", math.nan)
    position_ndcg = method_rows.get("relative_position", {}).get("ndcg_at_25", math.nan)
    method_rows.update(
        {
            "scfma_ridge_matches_raw_delta_pairwise": _close(ridge_pairwise, raw_pairwise),
            "scfma_ridge_matches_raw_delta_ndcg": _close(ridge_ndcg, raw_ndcg),
            "relative_position_ties_ridge_ndcg": _close(position_ndcg, ridge_ndcg),
        }
    )
    return method_rows


def _metric(methods: Mapping[str, Any], method: str, metric: str) -> float:
    values = methods.get(method, {})
    if not isinstance(values, Mapping):
        return 0.0
    return float(values.get(metric, 0.0))


def _close(left: float, right: float, *, tol: float = 1e-12) -> bool:
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= tol


def _interpretation(
    binary_separable: bool,
    continuous_perfect: bool,
    method_diagnostics: Mapping[str, Any],
) -> str:
    if binary_separable and not continuous_perfect:
        return (
            "The WebQSP trace route shows fixed-schema separability at the indispensable "
            "versus recoverable level, while continuous recoverable-step values still vary "
            "with candidate-set size. Under this schema, raw replay delta and SC-FMA Ridge "
            "provide the same pairwise ordering, so the route should be interpreted as a "
            "diagnostic transferability and evaluation-confound analysis."
        )
    if binary_separable:
        return (
            "The WebQSP trace route is separable by step role. This supports a diagnostic "
            "schema-saturation interpretation rather than a KGQA performance claim."
        )
    return (
        "The WebQSP trace route does not show clean step-role separability under the current "
        "replay targets; interpret any method comparison as exploratory diagnostics only."
    )


__all__ = [
    "build_separability_report",
    "render_separability_markdown",
    "write_separability_report",
]
