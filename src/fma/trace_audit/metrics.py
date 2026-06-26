"""Experiment reporting metrics for WebQSP trace audit."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from fma.calibration import BottleneckConstraint, scfma_calibrate, scfma_calibrate_ridge
from fma.eval.diagnostics.correlation_metrics import spearman
from fma.eval.prm800k_audit_prioritization import ndcg_at_budget, selected_indices
from fma.trace_audit.schema import CLAIM, FORBIDDEN_CLAIMS, ROUTE_ID


METHOD_ORDER = (
    "scfma_ridge",
    "scfma_qp",
    "random",
    "relative_position",
    "span_length",
    "candidate_count",
    "graph_degree",
    "raw_rule_delta",
)

SCFMA_STEP_PRIORS = {
    "entity_linking": 0.85,
    "relation_traversal": 0.90,
    "candidate_generation": 0.30,
    "candidate_verification": 0.68,
    "ambiguity_resolution": 0.55,
    "answer_verification": 0.95,
}


def build_experiment_report(
    traces: Sequence[Mapping[str, Any]],
    scored_by_trace: Sequence[Sequence[Mapping[str, Any]]],
    graphs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ranking = build_ranking_report(traces, scored_by_trace, graphs)
    methods = ranking["methods"]
    ridge = methods.get("scfma_ridge", {})

    return {
        "route_id": ROUTE_ID,
        "claim": CLAIM,
        "dataset": "WebQSP",
        "not_a_kgqa_benchmark": True,
        "kgqa_model_comparison": False,
        "semantic_parser_optimization": False,
        "validated_kbs_workflow": False,
        "trace_count": len(traces),
        "step_count": sum(len(trace.get("steps", [])) for trace in traces),
        "graph_count": len(graphs),
        "metrics": {
            "mean_ndcg_at_25": float(ridge.get("ndcg_at_25", 0.0)),
            "mean_spearman": float(ridge.get("spearman", 0.0)),
        },
        "methods": _legacy_method_summary(methods),
        "ranking": ranking,
        "experiment_review": experiment_review(ranking),
        "support_decision": _support_decision(methods),
        "forbidden_claims": list(FORBIDDEN_CLAIMS),
    }


def build_ranking_report(
    traces: Sequence[Mapping[str, Any]],
    scored_by_trace: Sequence[Sequence[Mapping[str, Any]]],
    graphs: Sequence[Mapping[str, Any]],
    *,
    bootstrap_samples: int = 200,
    bootstrap_seed: int = 17,
) -> dict[str, Any]:
    rows = score_traces(traces, scored_by_trace, graphs)
    methods: dict[str, dict[str, Any]] = {}
    for method in METHOD_ORDER:
        metric_rows = _method_metric_rows(rows, method)
        methods[method] = {
            "spearman": _mean([row["spearman"] for row in metric_rows]),
            "ndcg_at_25": _mean([row["ndcg_at_25"] for row in metric_rows]),
            "topk_recall": _mean([row["topk_recall"] for row in metric_rows]),
            "pairwise_accuracy": _mean([row["pairwise_accuracy"] for row in metric_rows]),
            "bootstrap_ci": _bootstrap_ci(
                [row["ndcg_at_25"] for row in metric_rows],
                n_bootstrap=bootstrap_samples,
                seed=bootstrap_seed,
            ),
            "n_traces": len(metric_rows),
        }

    return {
        "route_id": ROUTE_ID,
        "claim": CLAIM,
        "evaluation_scope": "reasoning_trace_step_ranking_only",
        "not_a_kgqa_benchmark": True,
        "methods": methods,
        "per_trace": rows,
        "method_order": list(METHOD_ORDER),
        "review_budget": "top_25_percent_steps",
        "bootstrap_unit": "trace",
        "bootstrap_samples": bootstrap_samples,
    }


def score_traces(
    traces: Sequence[Mapping[str, Any]],
    scored_by_trace: Sequence[Sequence[Mapping[str, Any]]],
    graphs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    graph_by_trace = {str(graph.get("trace_id")): graph for graph in graphs}
    rows = []
    for trace, scored in zip(traces, scored_by_trace):
        scored_rows = [dict(row) for row in scored]
        if not scored_rows:
            continue
        graph = graph_by_trace.get(str(trace.get("trace_id")), {})
        scores_by_method = _scores_for_trace(trace, scored_rows, graph)
        rows.append(
            {
                "trace_id": trace.get("trace_id"),
                "sample_id": trace.get("sample_id"),
                "source_split": trace.get("source_sample", {}).get("source_split"),
                "labels": [
                    float(row.get("importance_target", 0.0))
                    for row in scored_rows
                ],
                "step_ids": [str(row.get("step_id")) for row in scored_rows],
                "step_types": [str(row.get("step_type")) for row in scored_rows],
                "scores_by_method": scores_by_method,
            }
        )
    return rows


def experiment_review(ranking: Mapping[str, Any]) -> dict[str, Any]:
    methods = ranking.get("methods", {})
    best_scfma_method = _best_method(methods, ("scfma_qp", "scfma_ridge"))
    best_baseline_method = _best_method(
        methods,
        tuple(method for method in METHOD_ORDER if not method.startswith("scfma_")),
    )
    best_scfma = _method_score(methods, best_scfma_method)
    best_baseline = _method_score(methods, best_baseline_method)
    delta = best_scfma - best_baseline
    trace_count = len(ranking.get("per_trace", []))

    if trace_count == 0:
        positioning = "future_work_only"
    elif delta > 0.0 and best_scfma > 0.0:
        positioning = "kbs_main_experiment_candidate"
    elif any(float(values.get("ndcg_at_25", 0.0)) > 0.0 for values in methods.values()):
        positioning = "supplementary_diagnostic_evidence"
    else:
        positioning = "future_work_only"

    return {
        "positioning": positioning,
        "best_scfma_method": best_scfma_method,
        "best_baseline_method": best_baseline_method,
        "delta_vs_best_baseline_ndcg_at_25": float(delta),
        "claim_boundary": (
            "reasoning-trace audit evidence only; no KGQA performance claim"
        ),
        "review_label": "Experiment Review",
    }


def build_case_studies(
    traces: Sequence[Mapping[str, Any]],
    scored_by_trace: Sequence[Sequence[Mapping[str, Any]]],
    replay_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    replay_by_step = {
        (str(row.get("trace_id")), str(row.get("masked_step_id"))): dict(row)
        for row in replay_rows
    }
    rows = []
    for trace, scored in zip(traces, scored_by_trace):
        for row in scored:
            replay = replay_by_step.get(
                (str(row.get("trace_id")), str(row.get("step_id"))),
                {},
            )
            rows.append(
                {
                    "trace_id": trace.get("trace_id"),
                    "sample_id": trace.get("sample_id"),
                    "question": trace.get("leakage_safe_question", trace.get("question", "")),
                    "step_id": row.get("step_id"),
                    "step_type": row.get("step_type"),
                    "importance_target": float(row.get("importance_target", 0.0)),
                    "rule_delta": float(row.get("rule_delta", 0.0)),
                    "agreement_score": float(row.get("agreement_score", 0.0)),
                    "replay_status": replay.get("status", ""),
                    "failure_reason": replay.get("failure_reason", ""),
                }
            )

    high = max(rows, key=lambda row: row["importance_target"], default=None)
    recoverable = min(
        rows,
        key=lambda row: (row["importance_target"], -row["agreement_score"]),
        default=None,
    )
    disagreement = min(rows, key=lambda row: row["agreement_score"], default=None)
    failure = next(
        (
            row
            for row in rows
            if row["replay_status"] and row["replay_status"] not in {"success", "cached"}
        ),
        None,
    )
    if failure is None:
        failure = {
            "case_type": "failure",
            "status": "no_replay_failure_observed",
            "interpretation": "Rule replay completed without failed rows in this run.",
        }

    cases = {
        "high_importance": _with_case_type(high, "high_importance"),
        "recoverable": _with_case_type(recoverable, "recoverable"),
        "disagreement": _with_case_type(disagreement, "disagreement"),
        "failure": _with_case_type(failure, "failure"),
    }
    return {
        "route_id": ROUTE_ID,
        "case_studies": cases,
        "claim_boundary": "audit case studies only; not KGQA error analysis",
    }


def render_case_studies(case_report: Mapping[str, Any]) -> str:
    lines = [
        "# WebQSP Trace-Audit Case Studies",
        "",
        "These cases inspect replay-derived reasoning-step importance targets. They are not KGQA benchmark examples.",
        "",
    ]
    for name, case in case_report.get("case_studies", {}).items():
        if not isinstance(case, Mapping):
            continue
        lines.extend(
            [
                f"## {name.replace('_', ' ').title()}",
                "",
                f"- Trace: `{case.get('trace_id', '')}`",
                f"- Step: `{case.get('step_id', '')}` / `{case.get('step_type', '')}`",
                f"- Importance target: {float(case.get('importance_target', 0.0)):.4f}",
                f"- Rule delta: {float(case.get('rule_delta', 0.0)):.4f}",
                f"- Agreement score: {float(case.get('agreement_score', 0.0)):.4f}",
                f"- Replay status: `{case.get('replay_status', case.get('status', ''))}`",
                "",
            ]
        )
    return "\n".join(lines)


def _scores_for_trace(
    trace: Mapping[str, Any],
    scored: Sequence[Mapping[str, Any]],
    graph: Mapping[str, Any],
) -> dict[str, list[float]]:
    raw = np.asarray([float(row.get("rule_delta", 0.0)) for row in scored], dtype=float)
    priors = np.asarray(
        [SCFMA_STEP_PRIORS.get(str(row.get("step_type")), 0.0) for row in scored],
        dtype=float,
    )
    candidate_count = np.asarray(_candidate_counts(scored, graph), dtype=float)
    graph_degree = np.asarray(_graph_degrees(scored, graph), dtype=float)
    relative_position = np.asarray(
        [1.0 - (idx / max(1, len(scored) - 1)) for idx in range(len(scored))],
        dtype=float,
    )
    span_length = np.asarray(
        [len(str(row.get("step_type", "")).replace("_", " ").split()) for row in scored],
        dtype=float,
    )
    necessity = _simplex(0.50 * priors + 0.25 * graph_degree + 0.25 * relative_position)
    structural = _simplex(0.55 * raw + 0.30 * priors + 0.15 * graph_degree)
    redundancy = _redundancy_matrix(scored)
    bottlenecks = _bottleneck_constraints(necessity, graph_degree)

    scores = {
        "random": _deterministic_random(str(trace.get("trace_id")), len(scored)),
        "relative_position": relative_position,
        "span_length": span_length,
        "candidate_count": candidate_count,
        "graph_degree": graph_degree,
        "raw_rule_delta": raw,
    }

    try:
        ridge = scfma_calibrate_ridge(
            structural,
            necessity,
            sample_id=str(trace.get("sample_id", "")),
            alpha_ciui=0.65,
            alpha_nec=0.35,
            temperature=0.8,
        )
        scores["scfma_ridge"] = (
            np.asarray(ridge.weights[0].weights, dtype=float)
            if ridge.weights
            else structural
        )
    except Exception:
        scores["scfma_ridge"] = structural

    try:
        qp = scfma_calibrate(
            structural,
            necessity,
            redundancy,
            bottleneck_constraints=bottlenecks,
            sample_id=str(trace.get("sample_id", "")),
            alpha=1.0,
            beta=0.45,
            gamma=0.05,
            delta=0.08,
        )
        scores["scfma_qp"] = (
            np.asarray(qp.weights[0].weights, dtype=float)
            if qp.weights and qp.converged
            else structural
        )
    except Exception:
        scores["scfma_qp"] = structural

    return {
        method: _finite_list(scores[method])
        for method in METHOD_ORDER
    }


def _legacy_method_summary(
    methods: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    return {
        method: {
            "mean_ndcg_at_25": float(values.get("ndcg_at_25", 0.0)),
            "mean_spearman": float(values.get("spearman", 0.0)),
        }
        for method, values in methods.items()
    }


def _support_decision(methods: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    review = experiment_review({"methods": methods, "per_trace": [1]})
    return {
        "primary_method": review["best_scfma_method"],
        "best_control_method": review["best_baseline_method"],
        "best_control_ndcg_at_25": _method_score(
            methods,
            str(review["best_baseline_method"]),
        ),
        "delta_vs_best_control": review["delta_vs_best_baseline_ndcg_at_25"],
        "interpretation": (
            "reasoning-trace audit evidence only; not KGQA benchmark performance"
        ),
    }


def _method_metric_rows(
    rows: Sequence[Mapping[str, Any]],
    method: str,
) -> list[dict[str, float]]:
    values = []
    for row in rows:
        scores = row.get("scores_by_method", {}).get(method)
        labels = row.get("labels")
        if not isinstance(scores, Sequence) or not isinstance(labels, Sequence):
            continue
        scores_float = [float(value) for value in scores]
        labels_float = [float(value) for value in labels]
        values.append(
            {
                "spearman": spearman(scores_float, labels_float),
                "ndcg_at_25": ndcg_at_budget(
                    scores_float,
                    labels_float,
                    keep_fraction=0.25,
                ),
                "topk_recall": _topk_recall(scores_float, labels_float, keep_fraction=0.25),
                "pairwise_accuracy": _pairwise_accuracy(scores_float, labels_float),
            }
        )
    return values


def _topk_recall(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    if labels_array.size == 0:
        return 0.0
    selected = set(selected_indices(scores, keep_fraction))
    k = max(1, len(selected))
    ideal = set(np.argsort(-labels_array, kind="mergesort")[:k].tolist())
    if not ideal:
        return 0.0
    return float(len(selected & ideal) / len(ideal))


def _pairwise_accuracy(scores: Sequence[float], labels: Sequence[float]) -> float:
    score_values = [float(value) for value in scores]
    label_values = [float(value) for value in labels]
    correct = 0.0
    total = 0.0
    for left in range(len(score_values)):
        for right in range(left + 1, len(score_values)):
            label_cmp = _compare(label_values[left], label_values[right])
            if label_cmp == 0:
                continue
            score_cmp = _compare(score_values[left], score_values[right])
            total += 1.0
            if score_cmp == label_cmp:
                correct += 1.0
            elif score_cmp == 0:
                correct += 0.5
    return float(correct / total) if total else 0.0


def _candidate_counts(
    scored: Sequence[Mapping[str, Any]],
    graph: Mapping[str, Any],
) -> list[float]:
    node_by_id = {
        str(node.get("node_id")): node
        for node in graph.get("nodes", [])
        if isinstance(node, Mapping)
    }
    counts = []
    for row in scored:
        node = node_by_id.get(str(row.get("step_id")), {})
        counts.append(float(node.get("candidate_count", 0.0)))
    return counts


def _graph_degrees(
    scored: Sequence[Mapping[str, Any]],
    graph: Mapping[str, Any],
) -> list[float]:
    degree = {str(row.get("step_id")): 0.0 for row in scored}
    for edge in graph.get("edges", []):
        if not isinstance(edge, Mapping):
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source in degree:
            degree[source] += 1.0
        if target in degree:
            degree[target] += 1.0
    max_degree = max(degree.values(), default=0.0)
    if max_degree <= 0.0:
        return [0.0 for _ in scored]
    return [float(degree[str(row.get("step_id"))] / max_degree) for row in scored]


def _redundancy_matrix(scored: Sequence[Mapping[str, Any]]) -> np.ndarray:
    n = len(scored)
    matrix = np.zeros((n, n), dtype=float)
    step_types = [str(row.get("step_type")) for row in scored]
    for left in range(n):
        for right in range(left + 1, n):
            same_family = step_types[left].split("_")[-1] == step_types[right].split("_")[-1]
            value = 0.2 if same_family else 0.0
            matrix[left, right] = value
            matrix[right, left] = value
    return matrix


def _bottleneck_constraints(
    necessity: Sequence[float],
    graph_degree: Sequence[float],
) -> list[BottleneckConstraint]:
    if len(necessity) == 0:
        return []
    nec = np.asarray(necessity, dtype=float)
    degree = np.asarray(graph_degree, dtype=float)
    threshold = float(np.percentile(degree, 70)) if degree.size else 0.0
    return [
        BottleneckConstraint(index, 0.02)
        for index, value in enumerate(degree)
        if value >= threshold and nec[index] > 0.0
    ]


def _bootstrap_ci(
    values: Sequence[float],
    *,
    n_bootstrap: int,
    seed: int,
) -> dict[str, float]:
    arr = np.asarray([float(value) for value in values], dtype=float)
    if arr.size == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    if n_bootstrap <= 0:
        mean = float(np.mean(arr))
        return {"mean": mean, "ci_lower": mean, "ci_upper": mean}
    rng = np.random.default_rng(seed)
    samples = np.empty(n_bootstrap, dtype=float)
    for index in range(n_bootstrap):
        samples[index] = float(np.mean(rng.choice(arr, size=len(arr), replace=True)))
    return {
        "mean": float(np.mean(arr)),
        "ci_lower": float(np.percentile(samples, 2.5)),
        "ci_upper": float(np.percentile(samples, 97.5)),
    }


def _deterministic_random(key: str, n: int) -> np.ndarray:
    digest = hashlib.sha256(f"webqsp-random:{key}".encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    return np.random.default_rng(seed).random(n)


def _best_method(methods: Mapping[str, Any], candidates: Sequence[str]) -> str:
    available = [method for method in candidates if method in methods]
    if not available:
        return candidates[0] if candidates else ""
    return max(available, key=lambda method: _method_score(methods, method))


def _method_score(methods: Mapping[str, Any], method: str) -> float:
    values = methods.get(method, {})
    return float(values.get("ndcg_at_25", values.get("mean_ndcg_at_25", 0.0)))


def _simplex(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    arr = np.maximum(arr, 0.0)
    total = float(np.sum(arr))
    if total <= 1e-10:
        return np.ones(len(arr), dtype=float) / len(arr)
    return arr / total


def _finite_list(values: Sequence[float]) -> list[float]:
    return [
        float(value) if math.isfinite(float(value)) else 0.0
        for value in values
    ]


def _mean(values: Sequence[float]) -> float:
    return float(np.mean(np.asarray(values, dtype=float))) if values else 0.0


def _compare(left: float, right: float) -> int:
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _with_case_type(case: Mapping[str, Any] | None, case_type: str) -> dict[str, Any]:
    if case is None:
        return {"case_type": case_type, "status": "not_available"}
    return {"case_type": case_type, **dict(case)}


__all__ = [
    "METHOD_ORDER",
    "build_case_studies",
    "build_experiment_report",
    "build_ranking_report",
    "experiment_review",
    "render_case_studies",
    "score_traces",
]
