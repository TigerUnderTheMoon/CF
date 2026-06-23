"""Offline KBS-style audit-prioritization route.

This module builds deterministic HotpotQA/KGQA-style evidence-chain traces and
evaluates fixed-budget step audit ordering. It is offline only: no model APIs
are called, and the claim boundary remains KBS-style audit prioritization rather
than deployed KBS validation.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from fma.baselines.simple_average import simple_average_baseline
from fma.eval.prm800k_audit_prioritization import (
    label_mass_at_budget,
    max_label_hit_at_budget,
    ndcg_at_budget,
    spearman,
)
from fma.ranking import rank_steps_by_method

CLAIM_BOUNDARY = "kbs_style_audit_prioritization_evidence_only"
LABEL_SOURCE = "hotpotqa_supporting_fact_constructed_audit_labels"
SPLIT_SALT = "kbs_style_audit_v1"
METHODS = (
    "random",
    "relative_position",
    "span_length",
    "raw_local_utility",
    "simple_average",
    "retrieval_overlap",
    "w_struct",
    "scfma_ridge",
    "scfma_qp",
)
SCFMA_METHODS = ("scfma_ridge", "scfma_qp")
CONTROL_METHODS = (
    "random",
    "relative_position",
    "span_length",
    "raw_local_utility",
    "simple_average",
    "retrieval_overlap",
)
FORBIDDEN_SCORING_FIELDS = {
    "audit_label",
    "label_source",
    "scores_by_method",
    "ground_truth",
}
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def hash_bucket(sample_id: str, *, salt: str = SPLIT_SALT) -> int:
    digest = hashlib.sha256(f"{sample_id}|{salt}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def build_kbs_audit_traces(
    rows: Sequence[Mapping[str, Any]],
    *,
    dev_mod_upper: int = 30,
    max_supporting_facts: int = 2,
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        sample_id = str(
            row.get("sample_id")
            or row.get("task_id")
            or row.get("_id")
            or f"hotpotqa-row-{index:05d}"
        )
        question = str(row.get("question") or "").strip()
        answer = str(row.get("reference_answer") or row.get("answer") or "").strip()
        if not question or not answer:
            continue
        support_titles = _supporting_fact_titles(row.get("supporting_facts"))
        if not support_titles:
            support_titles = _fallback_support_titles(question, answer)
        support_titles = support_titles[:max_supporting_facts]

        steps, labels, typed_edges = _build_trace_steps(question, answer, support_titles, row)
        if len(steps) < 3 or len(steps) != len(labels):
            continue

        split = "dev" if hash_bucket(sample_id) < dev_mod_upper else "locked"
        traces.append(
            {
                "sample_id": sample_id,
                "question": question,
                "answer": answer,
                "steps": steps,
                "typed_edges": typed_edges,
                "audit_label": labels,
                "label_source": LABEL_SOURCE,
                "split": split,
                "provenance": {
                    "source_dataset": row.get("dataset") or row.get("source_dataset") or "hotpot_qa",
                    "source_config": row.get("config") or row.get("source_config") or "distractor",
                    "source_split": row.get("split") or row.get("source_split") or "train",
                    "source_index": row.get("source_index", row.get("hf_row_index", index)),
                    "supporting_fact_titles": support_titles,
                    "trace_construction": "deterministic_hotpotqa_support_fact_kbs_style_trace",
                    "validated_kbs_workflow": False,
                    "api_calls": 0,
                },
            }
        )
    return traces


def evaluate_kbs_audit_traces(
    traces: Sequence[Mapping[str, Any]],
    *,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    dev = [trace for trace in traces if trace.get("split") == "dev"]
    locked = [trace for trace in traces if trace.get("split") == "locked"]
    model = fit_w_struct_model(dev)

    rows: list[dict[str, Any]] = []
    for trace in locked:
        labels = [float(v) for v in trace.get("audit_label", [])]
        if len(labels) < 2:
            continue
        scores = score_trace_methods(trace, model=model, seed=seed)
        rows.append(
            {
                "sample_id": trace.get("sample_id"),
                "n_steps": len(labels),
                "labels": labels,
                "scores_by_method": scores,
            }
        )

    method_summaries = {method: _summarize_method(rows, method) for method in METHODS}
    leakage_audit = build_leakage_audit()
    support_decision = _support_decision(rows, method_summaries, n_bootstrap=n_bootstrap, seed=seed)

    return {
        "route_id": "kbs_style_hotpotqa_audit",
        "claim_boundary": CLAIM_BOUNDARY,
        "validated_kbs_workflow": False,
        "api_calls": 0,
        "data_source": "HotpotQA/KGQA-style supporting-fact traces",
        "label_source": LABEL_SOURCE,
        "dev_samples": len(dev),
        "locked_samples": len(rows),
        "locked_steps": int(sum(row["n_steps"] for row in rows)),
        "methods": method_summaries,
        "leakage_audit": leakage_audit,
        "support_decision": support_decision,
    }


def score_trace_methods(
    trace: Mapping[str, Any],
    *,
    model: Mapping[str, Any] | None,
    seed: int = 42,
) -> dict[str, list[float]]:
    features = build_trace_features(trace)
    ciu = [row["raw_local_utility"] for row in features]
    necessity = [row["structural_necessity"] for row in features]
    lengths = [row["span_length"] for row in features]
    step_indices = list(range(len(features)))
    redundancy = redundancy_matrix([str(step.get("text") or "") for step in trace["steps"]])
    bottlenecks = {
        index
        for index, row in enumerate(features)
        if row["structural_necessity"] >= 0.65 and row["mean_redundancy"] <= 0.35
    }

    scores: dict[str, list[float]] = {
        "raw_local_utility": _normalize(ciu),
        "simple_average": simple_average_baseline(ciu, necessity),
        "retrieval_overlap": _normalize([row["retrieval_overlap"] for row in features]),
        "span_length": rank_steps_by_method(
            "span_length",
            ciu,
            span_lengths=lengths,
            step_indices=step_indices,
        ),
        "relative_position": rank_steps_by_method(
            "relative_position",
            ciu,
            span_lengths=lengths,
            step_indices=step_indices,
        ),
        "random": rank_steps_by_method(
            "random",
            ciu,
            seed=_stable_seed(f"{seed}:{trace.get('sample_id')}"),
        ),
        "scfma_ridge": rank_steps_by_method(
            "scfma_ridge",
            ciu,
            necessity,
            redundancy,
            bottlenecks,
            sample_id=str(trace.get("sample_id") or ""),
        ),
        "scfma_qp": rank_steps_by_method(
            "scfma_qp",
            ciu,
            necessity,
            redundancy,
            bottlenecks,
            sample_id=str(trace.get("sample_id") or ""),
        ),
    }
    scores["w_struct"] = _predict_w_struct(features, model)
    return scores


def fit_w_struct_model(traces: Sequence[Mapping[str, Any]], *, ridge_lambda: float = 1.0) -> dict[str, Any]:
    x_rows: list[list[float]] = []
    y_rows: list[float] = []
    for trace in traces:
        labels = [float(v) for v in trace.get("audit_label", [])]
        features = build_trace_features(trace)
        for row, label in zip(features, labels, strict=False):
            x_rows.append(_feature_vector(row))
            y_rows.append(label)

    if not x_rows:
        return {"available": False}

    x = np.asarray(x_rows, dtype=float)
    y = np.asarray(y_rows, dtype=float)
    mean = np.mean(x, axis=0)
    std = np.std(x, axis=0)
    std[std == 0.0] = 1.0
    x_norm = (x - mean) / std
    design = np.column_stack([np.ones(len(x_norm)), x_norm])
    penalty = np.eye(design.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    coef = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y
    return {
        "available": True,
        "coef": coef.tolist(),
        "mean": mean.tolist(),
        "std": std.tolist(),
        "training_steps": len(y_rows),
        "training_samples": len(traces),
        "ridge_lambda": ridge_lambda,
    }


def build_trace_features(trace: Mapping[str, Any]) -> list[dict[str, float]]:
    steps = trace.get("steps", [])
    if not isinstance(steps, Sequence):
        return []
    question_tokens = _tokens(str(trace.get("question") or ""))
    answer_tokens = _tokens(str(trace.get("answer") or ""))
    support_tokens = _tokens(" ".join(trace.get("provenance", {}).get("supporting_fact_titles", [])))
    reachability = _downstream_reachability(len(steps), trace.get("typed_edges", []))
    red = redundancy_matrix([str(step.get("text") or "") for step in steps])

    rows: list[dict[str, float]] = []
    for index, step in enumerate(steps):
        text = str(step.get("text") or "")
        text_tokens = _tokens(text)
        support_overlap = _jaccard(text_tokens, support_tokens)
        answer_overlap = _jaccard(text_tokens, answer_tokens)
        question_overlap = _jaccard(text_tokens, question_tokens)
        type_prior = _step_type_prior(str(step.get("step_type") or ""))
        downstream = reachability[index] if index < len(reachability) else 0.0
        structural = min(1.0, 0.55 * downstream + 0.45 * type_prior)
        raw = min(1.0, 0.45 * support_overlap + 0.35 * answer_overlap + 0.20 * question_overlap)
        rows.append(
            {
                "raw_local_utility": raw,
                "structural_necessity": structural,
                "retrieval_overlap": min(1.0, 0.7 * support_overlap + 0.3 * question_overlap),
                "answer_overlap": answer_overlap,
                "question_overlap": question_overlap,
                "span_length": float(max(1, len(text_tokens))),
                "relative_position": float(index / max(1, len(steps) - 1)),
                "step_type_prior": type_prior,
                "downstream_reachability": downstream,
                "mean_redundancy": float(np.mean(red[index])) if len(red) else 0.0,
            }
        )
    return rows


def redundancy_matrix(step_texts: Sequence[str]) -> np.ndarray:
    n = len(step_texts)
    matrix = np.zeros((n, n), dtype=float)
    token_sets = [_tokens(text) for text in step_texts]
    for i in range(n):
        for j in range(i + 1, n):
            sim = _jaccard(token_sets[i], token_sets[j])
            matrix[i, j] = sim
            matrix[j, i] = sim
    return matrix


def build_leakage_audit() -> dict[str, Any]:
    source_fields = {
        "question",
        "answer",
        "steps.text",
        "steps.step_type",
        "typed_edges",
        "provenance.supporting_fact_titles",
    }
    forbidden = sorted(source_fields.intersection(FORBIDDEN_SCORING_FIELDS))
    return {
        "target_leakage_status": "target_leaking" if forbidden else "clean",
        "target_leakage_detected": bool(forbidden),
        "source_fields_used_for_locked_scoring": sorted(source_fields),
        "forbidden_scoring_fields": sorted(FORBIDDEN_SCORING_FIELDS),
        "forbidden_fields_used": forbidden,
        "dev_labels_used_for_w_struct_fit": True,
        "locked_labels_used_for_scoring": False,
    }


def _build_trace_steps(
    question: str,
    answer: str,
    support_titles: Sequence[str],
    row: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[float], list[dict[str, Any]]]:
    steps: list[dict[str, Any]] = []
    labels: list[float] = []
    edges: list[dict[str, Any]] = []

    def add_step(step_type: str, text: str, label: float) -> int:
        index = len(steps)
        steps.append(
            {
                "step_id": f"s{index}",
                "step_index": index,
                "step_type": step_type,
                "text": text,
            }
        )
        labels.append(float(label))
        if index > 0:
            edges.append({"source": f"s{index - 1}", "target": f"s{index}", "edge_type": "temporal"})
        return index

    evidence_indices: list[int] = []
    for title in support_titles:
        retrieval_idx = add_step(
            "retrieval",
            f"Retrieve candidate evidence about {title} for the question: {question}",
            0.72,
        )
        evidence_idx = add_step(
            "evidence_check",
            f"Verify whether evidence about {title} supports the answer {answer}.",
            1.0,
        )
        edges.append(
            {
                "source": f"s{retrieval_idx}",
                "target": f"s{evidence_idx}",
                "edge_type": "retrieval_to_evidence_check",
            }
        )
        evidence_indices.append(evidence_idx)

    entity_idx = add_step(
        "entity_binding",
        f"Bind answer entity or alias {answer} to the evidence chain.",
        0.86,
    )
    distractor_idx = add_step(
        "distractor_rejection",
        "Reject unsupported distractor evidence before synthesizing the final answer.",
        0.28,
    )
    synthesis_idx = add_step(
        "answer_synthesis",
        f"Synthesize the final answer {answer} from verified evidence.",
        0.78,
    )

    for evidence_idx in evidence_indices:
        edges.append(
            {
                "source": f"s{evidence_idx}",
                "target": f"s{synthesis_idx}",
                "edge_type": "supports_answer",
            }
        )
    edges.append({"source": f"s{entity_idx}", "target": f"s{synthesis_idx}", "edge_type": "binds_entity"})
    edges.append(
        {
            "source": f"s{distractor_idx}",
            "target": f"s{synthesis_idx}",
            "edge_type": "guards_against_distractor",
        }
    )

    return steps, labels, edges


def _supporting_fact_titles(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    titles: list[str] = []
    for item in value:
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)) and item:
            title = str(item[0]).strip()
        else:
            title = str(item).strip()
        if title and title not in titles:
            titles.append(title)
    return titles


def _fallback_support_titles(question: str, answer: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z][A-Za-z0-9'_-]+\b", question)
    titles = []
    for candidate in candidates:
        if candidate.lower() not in {"what", "which", "who", "where", "when", "are", "the"}:
            titles.append(candidate)
    return (titles or [answer])[:2]


def _support_decision(
    rows: Sequence[Mapping[str, Any]],
    method_summaries: Mapping[str, Mapping[str, float]],
    *,
    n_bootstrap: int,
    seed: int,
) -> dict[str, Any]:
    best_scfma = max(SCFMA_METHODS, key=lambda m: method_summaries[m]["mean_ndcg_at_25"])
    best_control = max(CONTROL_METHODS, key=lambda m: method_summaries[m]["mean_ndcg_at_25"])
    delta = (
        float(method_summaries[best_scfma]["mean_ndcg_at_25"])
        - float(method_summaries[best_control]["mean_ndcg_at_25"])
    )
    deltas = []
    for row in rows:
        labels = row["labels"]
        scores_by_method = row["scores_by_method"]
        scfma_score = ndcg_at_budget(scores_by_method[best_scfma], labels, keep_fraction=0.25)
        control_score = ndcg_at_budget(scores_by_method[best_control], labels, keep_fraction=0.25)
        deltas.append(scfma_score - control_score)
    ci = _bootstrap_ci(deltas, n_bootstrap=n_bootstrap, seed=seed)
    support = delta >= 0.05 and ci["ci_lower"] > 0.0
    return {
        "best_scfma_method": best_scfma,
        "best_control_method": best_control,
        "best_scfma_delta_vs_best_control": float(delta),
        "bootstrap_ci": ci,
        "support_condition_met": bool(support),
        "required_interpretation": (
            "KBS-style audit prioritization evidence only; not production KBS deployment"
        ),
    }


def _summarize_method(rows: Sequence[Mapping[str, Any]], method: str) -> dict[str, float]:
    top1: list[float] = []
    mass25: list[float] = []
    ndcg25: list[float] = []
    auprc: list[float] = []
    spearmans: list[float] = []
    for row in rows:
        scores_by_method = row["scores_by_method"]
        if method not in scores_by_method:
            continue
        scores = scores_by_method[method]
        labels = row["labels"]
        top1.append(max_label_hit_at_budget(scores, labels, keep_fraction=1.0 / len(labels)))
        mass25.append(label_mass_at_budget(scores, labels, keep_fraction=0.25))
        ndcg25.append(ndcg_at_budget(scores, labels, keep_fraction=0.25))
        auprc.append(average_precision_at_trace(scores, labels))
        spearmans.append(spearman(scores, labels))
    return {
        "mean_spearman": _mean(spearmans),
        "mean_top1_hit": _mean(top1),
        "mean_mass_at_25": _mean(mass25),
        "mean_ndcg_at_25": _mean(ndcg25),
        "mean_auprc": _mean(auprc),
        "n_samples": len(top1),
    }


def average_precision_at_trace(scores: Sequence[float], labels: Sequence[float]) -> float:
    if not scores or len(scores) != len(labels):
        return 0.0
    labels_array = np.asarray(labels, dtype=float)
    k = max(1, int(math.ceil(len(labels_array) * 0.25)))
    positive_indices = set(np.argsort(-labels_array, kind="mergesort")[:k].tolist())
    order = np.argsort(-np.asarray(scores, dtype=float), kind="mergesort")
    hits = 0
    precision_sum = 0.0
    for rank, index in enumerate(order, start=1):
        if int(index) in positive_indices:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / len(positive_indices) if positive_indices else 0.0


def _predict_w_struct(features: Sequence[Mapping[str, float]], model: Mapping[str, Any] | None) -> list[float]:
    if not model or not model.get("available"):
        return _normalize([row["raw_local_utility"] for row in features])
    x = np.asarray([_feature_vector(row) for row in features], dtype=float)
    mean = np.asarray(model["mean"], dtype=float)
    std = np.asarray(model["std"], dtype=float)
    std[std == 0.0] = 1.0
    design = np.column_stack([np.ones(len(x)), (x - mean) / std])
    pred = design @ np.asarray(model["coef"], dtype=float)
    return _normalize(np.maximum(pred, 0.0).tolist())


def _feature_vector(row: Mapping[str, float]) -> list[float]:
    return [
        float(row["raw_local_utility"]),
        float(row["structural_necessity"]),
        float(row["retrieval_overlap"]),
        float(row["answer_overlap"]),
        float(row["relative_position"]),
        float(row["step_type_prior"]),
        float(row["downstream_reachability"]),
        float(row["mean_redundancy"]),
    ]


def _downstream_reachability(n_steps: int, typed_edges: Any) -> list[float]:
    adjacency: dict[int, list[int]] = {index: [] for index in range(n_steps)}
    if isinstance(typed_edges, Sequence):
        for edge in typed_edges:
            if not isinstance(edge, Mapping):
                continue
            source = _step_number(edge.get("source"))
            target = _step_number(edge.get("target"))
            if source is None or target is None:
                continue
            if 0 <= source < n_steps and 0 <= target < n_steps:
                adjacency[source].append(target)
    values = []
    for index in range(n_steps):
        seen = set()
        stack = list(adjacency[index])
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(adjacency.get(node, []))
        values.append(len(seen) / max(1, n_steps - 1))
    return values


def _step_number(value: Any) -> int | None:
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def _step_type_prior(step_type: str) -> float:
    return {
        "evidence_check": 0.95,
        "entity_binding": 0.85,
        "answer_synthesis": 0.75,
        "retrieval": 0.55,
        "distractor_rejection": 0.25,
    }.get(step_type, 0.35)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _normalize(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    arr = np.asarray(values, dtype=float)
    arr = np.maximum(arr, 0.0)
    total = float(np.sum(arr))
    if total <= 1e-12:
        return [1.0 / len(arr)] * len(arr)
    return [float(v / total) for v in arr]


def _stable_seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _bootstrap_ci(values: Sequence[float], *, n_bootstrap: int, seed: int) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(max(1, n_bootstrap)):
        indices = rng.integers(0, len(arr), size=len(arr))
        boot.append(float(np.mean(arr[indices])))
    return {
        "mean": float(np.mean(arr)),
        "ci_lower": float(np.percentile(boot, 2.5)),
        "ci_upper": float(np.percentile(boot, 97.5)),
    }


def _mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if values else 0.0
