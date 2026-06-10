"""Span filtering A/B experiment: FMA vs PRM vs heuristic baselines."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from fma.data.schema import OpenTraceRecord
from fma.real_task_pilot.baselines import score_independent_baselines

from .downstream_eval import FilteringConfig, FilteringResult, evaluate_filtering


@dataclass
class SpanScores:
    sample_id: str
    task_type: str
    n_spans: int
    fma_scores: list[float] = field(default_factory=list)
    prm_scores: list[float] = field(default_factory=list)
    baseline_scores: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class ComparisonReport:
    experiment_name: str
    total_traces: int
    total_spans: int
    methods: tuple[str, ...]
    keep_ratios: tuple[float, ...]
    accuracy_by_method_and_ratio: dict[str, dict[str, float]]
    rank_correlations: dict[str, dict[str, float]]
    agreement_kappa: dict[str, float]
    filtering_results: list[dict[str, Any]]
    claims_allowed: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_name": self.experiment_name,
            "total_traces": self.total_traces,
            "total_spans": self.total_spans,
            "methods": list(self.methods),
            "keep_ratios": list(self.keep_ratios),
            "accuracy_by_method_and_ratio": self.accuracy_by_method_and_ratio,
            "rank_correlations": self.rank_correlations,
            "agreement_kappa": self.agreement_kappa,
            "filtering_results": self.filtering_results,
            "claims_allowed": self.claims_allowed,
        }


def compute_span_scores(
    records: list[OpenTraceRecord],
    fma_score_map: dict[str, list[float]] | None = None,
    prm_score_map: dict[str, list[float]] | None = None,
    baseline_methods: tuple[str, ...] = (
        "random",
        "span_length",
        "taxonomy_prior",
        "relative_position",
    ),
    seed: int = 42,
) -> list[SpanScores]:
    """Compute span-level scores from all methods for each record."""
    all_scores: list[SpanScores] = []

    baseline_records = _records_to_baseline_format(records)
    baseline_rows = score_independent_baselines(baseline_records, seed=seed)

    baseline_by_sample: dict[str, list[dict[str, Any]]] = {}
    for row in baseline_rows:
        sid = str(row.get("sample_id", ""))
        baseline_by_sample.setdefault(sid, []).append(row)

    for record in records:
        spans = _record_to_spans(record)
        n_spans = len(spans)

        fma = fma_score_map.get(record.sample_id, []) if fma_score_map else []
        prm = prm_score_map.get(record.sample_id, []) if prm_score_map else []

        baselines: dict[str, list[float]] = {}
        sample_baselines = baseline_by_sample.get(record.sample_id, [])
        for method in baseline_methods:
            method_scores: list[float] = []
            for span_row in sample_baselines:
                scores_dict = span_row.get("scores", {})
                if method in scores_dict:
                    method_scores.append(float(scores_dict[method]))
            if len(method_scores) != n_spans:
                rng = random.Random(hash(record.sample_id) % (2**31))
                method_scores = [rng.random() for _ in range(n_spans)]
            baselines[method] = method_scores

        all_scores.append(
            SpanScores(
                sample_id=record.sample_id,
                task_type=record.dataset,
                n_spans=n_spans,
                fma_scores=fma,
                prm_scores=prm,
                baseline_scores=baselines,
            )
        )

    return all_scores


def run_filtering_ablation(
    records: list[OpenTraceRecord],
    span_scores: list[SpanScores],
    config: FilteringConfig,
    experiment_name: str = "fma_vs_prm_downstream_v1",
    claims_allowed: dict[str, bool] | None = None,
) -> ComparisonReport:
    """Run the full filtering A/B experiment across all methods and keep ratios."""
    if claims_allowed is None:
        claims_allowed = {
            "prm_superiority": False,
            "fma_superiority": False,
            "correlation_report": True,
            "ranking_agreement": True,
        }

    all_results: list[FilteringResult] = []
    methods_seen: set[str] = set()

    for record, scores in zip(records, span_scores, strict=False):
        spans = _record_to_spans(record)

        methods_to_run: list[tuple[str, list[float]]] = []
        if scores.fma_scores and len(scores.fma_scores) == scores.n_spans:
            methods_to_run.append(("fma_ciu", scores.fma_scores))
        if scores.prm_scores and len(scores.prm_scores) == scores.n_spans:
            methods_to_run.append(("perplexity_heuristic", scores.prm_scores))
        if scores.prm_scores and len(scores.prm_scores) == scores.n_spans:
            from fma.prm.scoring import length_calibrate_scores

            step_lengths = [
                int(s.get("end_token", 0)) - int(s.get("start_token", 0))
                for s in spans
            ]
            step_lengths = [max(1, step_len) for step_len in step_lengths]
            calibrated = length_calibrate_scores(scores.prm_scores, step_lengths)
            methods_to_run.append(("perplexity_length_calibrated", calibrated))

        for method_name, method_scores in scores.baseline_scores.items():
            if len(method_scores) == scores.n_spans:
                methods_to_run.append((method_name, method_scores))

        for method_name, method_scores in methods_to_run:
            methods_seen.add(method_name)
            results = evaluate_filtering(record, spans, method_scores, method_name, config)
            all_results.extend(results)

    accuracy_by_method = _compute_accuracy_by_method(all_results)
    rank_correlations = _compute_rank_correlations(span_scores)
    agreement_kappa = _compute_agreement_kappa(span_scores)

    total_spans = sum(s.n_spans for s in span_scores)

    report = ComparisonReport(
        experiment_name=experiment_name,
        total_traces=len(records),
        total_spans=total_spans,
        methods=tuple(sorted(methods_seen)),
        keep_ratios=config.keep_ratios,
        accuracy_by_method_and_ratio=accuracy_by_method,
        rank_correlations=rank_correlations,
        agreement_kappa=agreement_kappa,
        filtering_results=[_result_to_dict(r) for r in all_results],
        claims_allowed=claims_allowed,
    )

    return report


def _record_to_spans(record: OpenTraceRecord) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for ann in record.step_annotations:
        spans.append(
            {
                "span_index": ann.step_index,
                "start_char": ann.start_char,
                "end_char": ann.end_char,
                "start_token": ann.start_token,
                "end_token": ann.end_token,
                "operation_type": ann.operation_type,
                "content": ann.step_text,
            }
        )
    return spans


def _records_to_baseline_format(records: list[OpenTraceRecord]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        spans = _record_to_spans(record)
        result.append(
            {
                "sample_id": record.sample_id,
                "task_type": record.dataset,
                "question": record.question,
                "observable_trace": record.full_reasoning_trace,
                "reflection_spans": spans,
            }
        )
    return result


def _compute_accuracy_by_method(
    results: list[FilteringResult],
) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, list[bool]]] = {}
    for r in results:
        ratio_key = f"keep_{r.keep_ratio:.2f}"
        grouped.setdefault(r.method_name, {}).setdefault(ratio_key, [])
        grouped[r.method_name][ratio_key].append(r.is_correct_after)

    accuracy: dict[str, dict[str, float]] = {}
    for method, ratio_dict in grouped.items():
        accuracy[method] = {}
        for ratio_key, correct_list in ratio_dict.items():
            if correct_list:
                accuracy[method][ratio_key] = sum(correct_list) / len(correct_list)
    return accuracy


def _compute_rank_correlations(
    span_scores: list[SpanScores],
) -> dict[str, dict[str, float]]:
    import numpy as np

    correlations: dict[str, dict[str, float]] = {}

    fma_all: list[float] = []
    prm_all: list[float] = []
    for scores in span_scores:
        if scores.fma_scores and scores.prm_scores:
            min_len = min(len(scores.fma_scores), len(scores.prm_scores))
            fma_all.extend(scores.fma_scores[:min_len])
            prm_all.extend(scores.prm_scores[:min_len])

    if len(fma_all) >= 3:
        fma_arr = np.array(fma_all)
        prm_arr = np.array(prm_all)
        if np.std(fma_arr) > 0 and np.std(prm_arr) > 0:
            pearson = float(np.corrcoef(fma_arr, prm_arr)[0, 1])
            from scipy.stats import spearmanr
            spearman, _ = spearmanr(fma_arr, prm_arr)
            correlations["fma_vs_prm"] = {
                "pearson": pearson,
                "spearman": float(spearman),
                "n_pairs": len(fma_all),
            }

    return correlations


def _compute_agreement_kappa(
    span_scores: list[SpanScores],
) -> dict[str, float]:
    fma_binary: list[int] = []
    prm_binary: list[int] = []

    for scores in span_scores:
        if scores.fma_scores and scores.prm_scores:
            min_len = min(len(scores.fma_scores), len(scores.prm_scores))
            for i in range(min_len):
                fma_binary.append(1 if scores.fma_scores[i] > 0.5 else 0)
                prm_binary.append(1 if scores.prm_scores[i] > 0.5 else 0)

    if len(fma_binary) < 2:
        return {}

    n = len(fma_binary)
    agree = sum(1 for f, p in zip(fma_binary, prm_binary, strict=False) if f == p)
    p_observed = agree / n

    p_fma_1 = sum(fma_binary) / n
    p_prm_1 = sum(prm_binary) / n
    p_expected = p_fma_1 * p_prm_1 + (1 - p_fma_1) * (1 - p_prm_1)

    if p_expected >= 1.0:
        return {"fma_vs_prm_kappa": 0.0}

    kappa = (p_observed - p_expected) / (1.0 - p_expected)
    return {"fma_vs_prm_kappa": kappa}


def _result_to_dict(result: FilteringResult) -> dict[str, Any]:
    return {
        "sample_id": result.sample_id,
        "method_name": result.method_name,
        "keep_ratio": result.keep_ratio,
        "n_kept": len(result.kept_indices),
        "is_correct_after": result.is_correct_after,
        "is_correct_before": result.is_correct_before,
        "filtered_answer": result.filtered_answer,
        "original_answer": result.original_answer,
        "reference_answer": result.reference_answer,
    }


__all__ = [
    "ComparisonReport",
    "SpanScores",
    "compute_span_scores",
    "run_filtering_ablation",
]
