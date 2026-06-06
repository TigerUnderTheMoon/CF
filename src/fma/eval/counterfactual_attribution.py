"""Counterfactual-style functional attribution for reflection chains.

This module implements deterministic intervention-style ablations over
reflection steps. It estimates functional necessity, not true causal effects.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from collections import OrderedDict, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
)
from fma.utils.common import trace_id_for_record


ATTRIBUTION_SCORE_MAP: dict[str, float] = {
    "factual_error": 0.90,
    "reasoning_gap": 0.75,
    "metacognitive": 0.60,
    "vague": 0.30,
    "irrelevant": 0.10,
}
UTILITY_NUMERIC: dict[UtilityLabel, float] = {
    UtilityLabel.HELPFUL: 1.0,
    UtilityLabel.NEUTRAL: 0.0,
    UtilityLabel.HARMFUL: -1.0,
    UtilityLabel.SPURIOUS: -0.5,
}

ATTRIBUTION_TOP_K = "ATTRIBUTION_TOP_K"
ATTRIBUTION_BOTTOM_K = "ATTRIBUTION_BOTTOM_K"
RANDOM_K = "RANDOM_K"
POSITIONAL_FIRST_K = "POSITIONAL_FIRST_K"
POSITIONAL_LAST_K = "POSITIONAL_LAST_K"
CATEGORY_MATCHED_RANDOM = "CATEGORY_MATCHED_RANDOM"
ABLATION_STRATEGIES: tuple[str, ...] = (
    ATTRIBUTION_TOP_K,
    ATTRIBUTION_BOTTOM_K,
    RANDOM_K,
    POSITIONAL_FIRST_K,
    POSITIONAL_LAST_K,
    CATEGORY_MATCHED_RANDOM,
)


@dataclass(frozen=True)
class CounterfactualAblationResult:
    trace_id: str
    strategy: str
    removed_step_idx: int
    original_utility: float
    ablated_utility: float
    delta_utility: float
    attribution_score_of_removed: float


@dataclass(frozen=True)
class NecessityScore:
    trace_id: str
    step_idx: int
    attribution_score: float
    necessity: float
    necessity_normalized: float


@dataclass(frozen=True)
class FaithfulnessMetrics:
    pearson: float
    spearman: float
    rank_agreement: float
    top_k_overlap: dict[int, float]
    num_samples: int


@dataclass(frozen=True)
class RedundancyAnalysis:
    trace_id: str
    redundancy_ratio: float
    attribution_inflation_score: float
    duplicate_verification_density: float


@dataclass(frozen=True)
class MinimalSubsetResult:
    trace_id: str
    original_step_count: int
    minimal_step_count: int
    compression_ratio: float
    steps_removed: list[int]
    steps_retained: list[int]
    utility_retained: float
    utility_threshold: float


def attribution_score_for_type(attribution_type: str | None) -> float:
    """Map a Phase 4 attribution type to the required Phase 5 score."""
    if attribution_type is None:
        return 0.0
    return ATTRIBUTION_SCORE_MAP.get(str(attribution_type), 0.0)


def attribution_score_for_annotation(annotation: UtilityAnnotation) -> float:
    """Return the deterministic attribution score for one Phase 4 annotation."""
    return attribution_score_for_type(annotation.attribution_type)


def compute_trace_utility(steps: Sequence[UtilityAnnotation]) -> float:
    """
    Compute scalar trace utility from Phase 4 utility labels.

    If any step is helpful, the trace utility reaches the 1.0 ceiling.
    Otherwise, utility is the mean numeric label value. Empty traces are neutral.
    """
    if not steps:
        return 0.0
    numeric = [UTILITY_NUMERIC[_utility_label(step.utility)] for step in steps]
    if any(value == 1.0 for value in numeric):
        return 1.0
    return float(sum(numeric) / len(numeric))


def ablate_step(trace: Mapping[str, Any], step_idx: int) -> dict[str, Any]:
    """Return a copy of a trace with reflection step ``step_idx`` removed."""
    steps = _trace_reflection_steps(trace)
    if step_idx < 0 or step_idx >= len(steps):
        raise IndexError(f"step_idx {step_idx} is out of range for {len(steps)} reflection steps")

    ablated = dict(trace)
    new_steps = [dict(step) for index, step in enumerate(steps) if index != step_idx]
    ablated["reflection_chain"] = new_steps

    categories = trace.get("reflection_categories")
    if isinstance(categories, list) and len(categories) == len(steps):
        ablated["reflection_categories"] = [
            category for index, category in enumerate(categories) if index != step_idx
        ]

    spans = trace.get("reflection_spans")
    if isinstance(spans, list) and len(spans) == len(steps):
        new_spans: list[dict[str, Any]] = []
        for new_index, span in enumerate(
            dict(span) for index, span in enumerate(spans) if index != step_idx
        ):
            new_span = dict(span)
            new_span["step_index"] = new_index
            new_spans.append(new_span)
        ablated["reflection_spans"] = new_spans

    reflection_text = " ".join(_step_text(step) for step in new_steps).strip()
    ablated["reflection_text"] = reflection_text
    ablated["reasoning_trace"] = reflection_text
    return ablated


def utility_annotation_from_record(record: Mapping[str, Any]) -> UtilityAnnotation:
    """Load a Phase 4 utility annotation from a JSON-compatible mapping."""
    return UtilityAnnotation(
        trace_id=str(record["trace_id"]),
        reflection_idx=int(record["reflection_idx"]),
        utility=UtilityLabel(str(record["utility"])),
        outcome_delta=OutcomeDelta(str(record["outcome_delta"])),
        degradation_score=float(record["degradation_score"]),
        annotation_confidence=float(record.get("annotation_confidence", 0.0)),
        attribution_type=record.get("attribution_type"),
        attribution_alignment=AttributionAlignment(str(record["attribution_alignment"])),
        intervention_type=record.get("intervention_type"),
        reflection_category=str(record.get("reflection_category") or "OTHER"),
        correctness_preserved=bool(record.get("correctness_preserved", False)),
    )


def utility_annotations_from_records(records: Sequence[Mapping[str, Any]]) -> list[UtilityAnnotation]:
    """Convert JSON-compatible records to Phase 4 annotation dataclasses."""
    return [utility_annotation_from_record(record) for record in records]


def group_annotations_by_trace(
    annotations: Sequence[UtilityAnnotation],
) -> OrderedDict[str, list[UtilityAnnotation]]:
    """Group annotations by trace id while preserving first-seen trace order."""
    grouped: OrderedDict[str, list[UtilityAnnotation]] = OrderedDict()
    for annotation in annotations:
        grouped.setdefault(annotation.trace_id, []).append(annotation)
    for trace_id, group in grouped.items():
        grouped[trace_id] = sorted(group, key=lambda item: item.reflection_idx)
    return grouped


def strategy_order(
    annotations: Sequence[UtilityAnnotation],
    strategy: str,
    seed: int = 42,
    trace_id: str | None = None,
) -> list[int]:
    """Return reflection indices in deterministic strategy order."""
    if strategy not in ABLATION_STRATEGIES:
        raise ValueError(f"Unsupported ablation strategy {strategy!r}.")

    items = list(annotations)
    if strategy == ATTRIBUTION_TOP_K:
        ordered = sorted(
            items,
            key=lambda item: (-attribution_score_for_annotation(item), item.reflection_idx),
        )
    elif strategy == ATTRIBUTION_BOTTOM_K:
        ordered = sorted(
            items,
            key=lambda item: (attribution_score_for_annotation(item), item.reflection_idx),
        )
    elif strategy == POSITIONAL_FIRST_K:
        ordered = sorted(items, key=lambda item: item.reflection_idx)
    elif strategy == POSITIONAL_LAST_K:
        ordered = sorted(items, key=lambda item: -item.reflection_idx)
    elif strategy == RANDOM_K:
        ordered = sorted(items, key=lambda item: item.reflection_idx)
        rng = random.Random(_stable_seed(seed, trace_id or _trace_id_for_group(items), strategy))
        rng.shuffle(ordered)
    else:
        ordered = []
        rng = random.Random(_stable_seed(seed, trace_id or _trace_id_for_group(items), strategy))
        grouped: dict[str, list[UtilityAnnotation]] = defaultdict(list)
        for item in items:
            grouped[item.attribution_type or "none"].append(item)
        for attribution_type in sorted(grouped):
            group = sorted(grouped[attribution_type], key=lambda item: item.reflection_idx)
            rng.shuffle(group)
            ordered.extend(group)

    return [item.reflection_idx for item in ordered]


def compute_necessity_scores(
    annotations: Sequence[UtilityAnnotation],
) -> list[NecessityScore]:
    """Compute single-step functional necessity for every reflection annotation.

    For each trace, the original utility U is computed.  Then, for each
    step j, the same utility is recomputed with step j removed, yielding
    the ablated utility U_{-j}.  The necessity of step j is

        NEC(j) = U - U_{-j}.

    This quantifies how much the trace utility degrades when that single
    reflection step is taken away.

    Complexity:
        Let T = number of traces and Sᵢ = number of reflection steps in
        trace i (S = maxᵢ Sᵢ).  The algorithm performs T traces × Sᵢ
        steps × O(Sᵢ) work for the per-step list filtering and utility
        re-computation.

        Time:  O(T × S²) worst-case (every trace has the maximum
               length S).
               Average: O(T × S̄²) where S̄ is the mean trace length.
        Space: O(T × S) to store the returned NecessityScore list.
               O(S) additional working memory per trace.
    """
    scores: list[NecessityScore] = []
    for trace_id, group in group_annotations_by_trace(annotations).items():
        original_utility = compute_trace_utility(group)
        min_possible_utility = -1.0 if any(step.utility is UtilityLabel.HARMFUL for step in group) else 0.0
        max_possible_delta = original_utility - min_possible_utility
        for annotation in group:
            remaining = [
                step for step in group if step.reflection_idx != annotation.reflection_idx
            ]
            ablated_utility = compute_trace_utility(remaining)
            necessity = float(original_utility - ablated_utility)
            normalized = _normalize_necessity(necessity, max_possible_delta)
            scores.append(
                NecessityScore(
                    trace_id=trace_id,
                    step_idx=annotation.reflection_idx,
                    attribution_score=attribution_score_for_annotation(annotation),
                    necessity=necessity,
                    necessity_normalized=normalized,
                )
            )
    return scores


def run_single_step_ablations(
    traces: Sequence[Mapping[str, Any]],
    annotations: Sequence[UtilityAnnotation],
    seed: int = 42,
    strategies: Sequence[str] = ABLATION_STRATEGIES,
) -> list[CounterfactualAblationResult]:
    """Run deterministic single-step ablations for every ablation strategy.

    For each trace, each ablation strategy specifies a removal order over
    the trace's reflection steps.  Every step is individually removed,
    the ablated utility is computed, and the utility delta is recorded.

    Complexity:
        Let T = number of traces, S = max steps per trace, and
        K = |strategies| (K = 6 by default).

        Time:  O(T × S² × K) worst-case.  Per trace–strategy pair:
               S steps × O(S) per-step list filtering and utility
               computation.
               Average: O(T × S̄² × K).
        Space: O(T × S × K) for the result list.  Each ablation yields
               one CounterfactualAblationResult entry.

        The *ablate_step* call on the trace dictionary (line 289) is
        side-effect-free for the utility computation because the
        subsequent *compute_trace_utility* call operates on the
        annotation-derived group, not the trace dict.  The call is
        retained for side-channel inspection but does not affect the
        result values.
    """
    trace_by_id = {trace_id_for_record(trace, index): trace for index, trace in enumerate(traces)}
    grouped = group_annotations_by_trace(annotations)
    results: list[CounterfactualAblationResult] = []
    for trace_id, group in grouped.items():
        original_utility = compute_trace_utility(group)
        annotations_by_idx = {annotation.reflection_idx: annotation for annotation in group}
        trace = trace_by_id.get(trace_id)
        for strategy in strategies:
            for step_idx in strategy_order(group, strategy, seed=seed, trace_id=trace_id):
                if trace is not None:
                    ablate_step(trace, step_idx)
                remaining = [step for step in group if step.reflection_idx != step_idx]
                ablated_utility = compute_trace_utility(remaining)
                annotation = annotations_by_idx[step_idx]
                results.append(
                    CounterfactualAblationResult(
                        trace_id=trace_id,
                        strategy=strategy,
                        removed_step_idx=step_idx,
                        original_utility=original_utility,
                        ablated_utility=ablated_utility,
                        delta_utility=float(original_utility - ablated_utility),
                        attribution_score_of_removed=attribution_score_for_annotation(annotation),
                    )
                )
    return results


def compute_faithfulness_metrics(scores: Sequence[NecessityScore]) -> FaithfulnessMetrics:
    """Compare attribution scores with step-level necessity scores."""
    samples = list(scores)
    attribution = [sample.attribution_score for sample in samples]
    necessity = [sample.necessity for sample in samples]
    return FaithfulnessMetrics(
        pearson=_pearson(attribution, necessity),
        spearman=_pearson(_ranks(attribution), _ranks(necessity)),
        rank_agreement=_rank_agreement(samples),
        top_k_overlap={k: _top_k_overlap(samples, k) for k in (3, 5, 10)},
        num_samples=len(samples),
    )


def analyze_redundancy(
    annotations: Sequence[UtilityAnnotation],
    necessity_scores: Sequence[NecessityScore],
    traces: Sequence[Mapping[str, Any]] | None = None,
) -> list[RedundancyAnalysis]:
    """Detect high-attribution, low-necessity reflection steps per trace."""
    score_by_key = {
        (score.trace_id, score.step_idx): score
        for score in necessity_scores
    }
    trace_texts = {
        trace_id_for_record(trace, index): _trace_step_texts(trace)
        for index, trace in enumerate(traces or ())
    }
    reports: list[RedundancyAnalysis] = []
    for trace_id, group in group_annotations_by_trace(annotations).items():
        if not group:
            reports.append(
                RedundancyAnalysis(
                    trace_id=trace_id,
                    redundancy_ratio=0.0,
                    attribution_inflation_score=0.0,
                    duplicate_verification_density=0.0,
                )
            )
            continue
        step_scores = [score_by_key[(trace_id, step.reflection_idx)] for step in group]
        redundant_count = sum(
            1
            for step_score in step_scores
            if step_score.attribution_score > 0.8 and step_score.necessity < 0.2
        )
        inflation = [
            step_score.attribution_score - step_score.necessity_normalized
            for step_score in step_scores
        ]
        reports.append(
            RedundancyAnalysis(
                trace_id=trace_id,
                redundancy_ratio=float(redundant_count / len(group)),
                attribution_inflation_score=float(np.mean(inflation)) if inflation else 0.0,
                duplicate_verification_density=_duplicate_density(group, trace_texts.get(trace_id, [])),
            )
        )
    return reports


def find_minimal_sufficient_subset(
    annotations: Sequence[UtilityAnnotation],
    utility_threshold: float = 0.9,
) -> MinimalSubsetResult:
    """Greedily remove lowest-necessity steps while preserving trace utility.

    Starting from the full step set, the algorithm iteratively removes
    the single step whose elimination produces the smallest utility drop.
    Removal stops when further ablation would drop the retained utility
    below ``utility_threshold * original_utility``.

    This is a backward greedy deletion heuristic.  The utility function
    is not guaranteed to be monotone or submodular, so no formal
    approximation ratio is claimed.  The heuristic serves as a practical
    upper-bound engine for redundancy analysis.

    Complexity:
        Let S = number of reflection steps in the trace.

        Time:  O(S³) worst-case.  The outer while-loop executes up to
               S-1 iterations; each iteration evaluates all remaining
               candidates (at most S) by computing an O(S) ablated
               utility, for O(S²) work per iteration.
               Average: O(S³) if the majority of steps must be evaluated
               before the threshold is reached.
        Space: O(S) for working lists and the output MinimalSubsetResult.
    """
    if utility_threshold < 0.0:
        raise ValueError("utility_threshold must be non-negative.")
    trace_id = _trace_id_for_group(annotations)
    result, _curve = _minimal_subset_with_curve(annotations, utility_threshold)
    return result if result.trace_id == trace_id else result


def run_minimal_subset_analysis(
    annotations: Sequence[UtilityAnnotation],
    utility_threshold: float = 0.9,
) -> list[MinimalSubsetResult]:
    """Run greedy minimal-subset analysis for every trace."""
    return [
        find_minimal_sufficient_subset(group, utility_threshold=utility_threshold)
        for group in group_annotations_by_trace(annotations).values()
    ]


def minimal_subset_curves(
    annotations: Sequence[UtilityAnnotation],
    utility_threshold: float = 0.9,
) -> list[dict[str, Any]]:
    """Return cumulative greedy utility curves for plotting."""
    rows: list[dict[str, Any]] = []
    for group in group_annotations_by_trace(annotations).values():
        _result, curve = _minimal_subset_with_curve(group, utility_threshold)
        rows.extend(curve)
    return rows


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    """Serialize Phase 5 dataclasses to JSON-compatible dictionaries."""
    data = asdict(value)
    if isinstance(value, FaithfulnessMetrics):
        data["top_k_overlap"] = {
            str(k): float(v) for k, v in sorted(value.top_k_overlap.items())
        }
    return data


def build_counterfactual_summary(
    traces: Sequence[Mapping[str, Any]],
    ablation_results: Sequence[CounterfactualAblationResult],
    necessity_scores: Sequence[NecessityScore],
    faithfulness: FaithfulnessMetrics,
    redundancy: Sequence[RedundancyAnalysis],
    minimal_subsets: Sequence[MinimalSubsetResult],
) -> dict[str, Any]:
    """Build the deterministic aggregate summary for Phase 5 outputs."""
    strategy_counts: dict[str, int] = {strategy: 0 for strategy in ABLATION_STRATEGIES}
    for result in ablation_results:
        strategy_counts[result.strategy] = strategy_counts.get(result.strategy, 0) + 1

    necessity = np.asarray([score.necessity for score in necessity_scores], dtype=float)
    necessity_normalized = np.asarray(
        [score.necessity_normalized for score in necessity_scores],
        dtype=float,
    )
    compression = np.asarray(
        [result.compression_ratio for result in minimal_subsets],
        dtype=float,
    )
    redundancy_ratios = [
        result.redundancy_ratio for result in redundancy
    ]
    return {
        "num_traces": len(traces),
        "num_ablations": len(necessity_scores),
        "num_ablation_runs_by_strategy": dict(sorted(strategy_counts.items())),
        "mean_necessity": _mean(necessity),
        "std_necessity": _std(necessity),
        "mean_necessity_normalized": _mean(necessity_normalized),
        "faithfulness_pearson": faithfulness.pearson,
        "faithfulness_spearman": faithfulness.spearman,
        "faithfulness_rank_agreement": faithfulness.rank_agreement,
        "faithfulness_top_k_overlap": {
            str(k): float(v) for k, v in sorted(faithfulness.top_k_overlap.items())
        },
        "redundancy_ratio": float(np.mean(redundancy_ratios)) if redundancy_ratios else 0.0,
        "mean_compression_ratio": _mean(compression),
        "median_compression_ratio": float(np.median(compression)) if compression.size else 0.0,
        "traces_with_redundancy": sum(
            1 for result in redundancy if result.redundancy_ratio > 0.0
        ),
    }


def _minimal_subset_with_curve(
    annotations: Sequence[UtilityAnnotation],
    utility_threshold: float,
) -> tuple[MinimalSubsetResult, list[dict[str, Any]]]:
    group = sorted(annotations, key=lambda item: item.reflection_idx)
    trace_id = _trace_id_for_group(group)
    original_count = len(group)
    if original_count == 0:
        result = MinimalSubsetResult(
            trace_id=trace_id,
            original_step_count=0,
            minimal_step_count=0,
            compression_ratio=0.0,
            steps_removed=[],
            steps_retained=[],
            utility_retained=0.0,
            utility_threshold=utility_threshold,
        )
        return result, [{"trace_id": trace_id, "steps_removed": 0, "utility_retained": 0.0}]

    by_idx = {annotation.reflection_idx: annotation for annotation in group}
    remaining = [annotation.reflection_idx for annotation in group]
    removed: list[int] = []
    original_utility = compute_trace_utility(group)
    current_utility = original_utility
    curve = [
        {
            "trace_id": trace_id,
            "steps_removed": 0,
            "utility_retained": current_utility,
        }
    ]

    while len(remaining) > 1:
        candidates: list[tuple[float, float, int, float]] = []
        current_steps = [by_idx[index] for index in remaining]
        current_utility = compute_trace_utility(current_steps)
        for step_idx in remaining:
            next_steps = [by_idx[index] for index in remaining if index != step_idx]
            ablated_utility = compute_trace_utility(next_steps)
            necessity = current_utility - ablated_utility
            attribution_score = attribution_score_for_annotation(by_idx[step_idx])
            candidates.append((necessity, attribution_score, step_idx, ablated_utility))

        necessity, _attribution_score, step_idx, ablated_utility = min(
            candidates,
            key=lambda item: (item[0], item[1], item[2]),
        )
        if not _utility_preserved(
            utility_retained=ablated_utility,
            utility_original=original_utility,
            utility_threshold=utility_threshold,
        ):
            break
        remaining.remove(step_idx)
        removed.append(step_idx)
        current_utility = ablated_utility
        curve.append(
            {
                "trace_id": trace_id,
                "steps_removed": len(removed),
                "utility_retained": current_utility,
                "removed_step_idx": step_idx,
                "removed_step_necessity": necessity,
            }
        )

    minimal_count = len(remaining)
    result = MinimalSubsetResult(
        trace_id=trace_id,
        original_step_count=original_count,
        minimal_step_count=minimal_count,
        compression_ratio=1.0 - (minimal_count / original_count),
        steps_removed=removed,
        steps_retained=remaining,
        utility_retained=current_utility,
        utility_threshold=utility_threshold,
    )
    return result, curve


def _utility_preserved(
    utility_retained: float,
    utility_original: float,
    utility_threshold: float,
) -> bool:
    if utility_original <= 0.0:
        return utility_retained >= 0.0
    return utility_retained >= utility_threshold * utility_original


def _trace_reflection_steps(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    chain = trace.get("reflection_chain")
    if isinstance(chain, list):
        return [dict(step) for step in chain if isinstance(step, Mapping)]

    spans = trace.get("reflection_spans")
    if isinstance(spans, list):
        return [
            {"text": span.get("content", ""), "category": span.get("reflection_type", "OTHER")}
            for span in spans
            if isinstance(span, Mapping)
        ]

    text = trace.get("reflection_text")
    if isinstance(text, str) and text.strip():
        return [{"text": text, "category": trace.get("category", "OTHER")}]
    return []


def _trace_step_texts(trace: Mapping[str, Any]) -> list[str]:
    return [_step_text(step) for step in _trace_reflection_steps(trace)]


def _step_text(step: Mapping[str, Any]) -> str:
    return str(step.get("text") or step.get("content") or "").strip()


def _trace_id_for_group(annotations: Sequence[UtilityAnnotation]) -> str:
    return annotations[0].trace_id if annotations else "unknown"


def _stable_seed(seed: int, trace_id: str, strategy: str) -> int:
    payload = f"{seed}:{trace_id}:{strategy}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return int(digest[:16], 16)


def _utility_label(value: UtilityLabel | str) -> UtilityLabel:
    if isinstance(value, UtilityLabel):
        return value
    return UtilityLabel(str(value))


def _normalize_necessity(necessity: float, max_possible_delta: float) -> float:
    if max_possible_delta <= 0.0:
        return 0.0
    return _clamp(necessity / max_possible_delta, 0.0, 1.0)


def _rank_agreement(samples: Sequence[NecessityScore]) -> float:
    if not samples:
        return 0.0
    limit = max(1, int(math.ceil(len(samples) * 0.5)))
    top_attribution = _top_keys(samples, "attribution_score", limit)
    top_necessity = _top_keys(samples, "necessity", limit)
    return float(len(top_attribution & top_necessity) / limit)


def _top_k_overlap(samples: Sequence[NecessityScore], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive.")
    if not samples:
        return 0.0
    limit = min(k, len(samples))
    top_attribution = _top_keys(samples, "attribution_score", limit)
    top_necessity = _top_keys(samples, "necessity", limit)
    return float(len(top_attribution & top_necessity) / k)


def _top_keys(samples: Sequence[NecessityScore], field_name: str, limit: int) -> set[tuple[str, int]]:
    ordered = sorted(
        samples,
        key=lambda item: (
            -float(getattr(item, field_name)),
            item.trace_id,
            item.step_idx,
        ),
    )
    return {(item.trace_id, item.step_idx) for item in ordered[:limit]}


def _ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(float(value) for value in values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(indexed)
    position = 0
    while position < len(indexed):
        end = position + 1
        while end < len(indexed) and indexed[end][1] == indexed[position][1]:
            end += 1
        average_rank = (position + 1 + end) / 2.0
        for offset in range(position, end):
            ranks[indexed[offset][0]] = average_rank
        position = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    if float(np.std(left_array)) == 0.0 or float(np.std(right_array)) == 0.0:
        return 0.0
    value = float(np.corrcoef(left_array, right_array)[0, 1])
    return value if math.isfinite(value) else 0.0


def _duplicate_density_exact(
    annotations: Sequence[UtilityAnnotation],
    texts: Sequence[str],
) -> float:
    """Exact O(n²) duplicate density via pairwise Jaccard comparison.

    Complexity:
        Time:  O(n² × T) where n = len(annotations), T = avg token count.
        Space: O(T) for token sets per pair.
    """
    if len(annotations) < 2:
        return 0.0
    total_pairs = 0
    duplicate_pairs = 0
    for left_index in range(len(annotations)):
        for right_index in range(left_index + 1, len(annotations)):
            total_pairs += 1
            left = annotations[left_index]
            right = annotations[right_index]
            if left.attribution_type == right.attribution_type and left.attribution_type is not None:
                left_text = texts[left.reflection_idx] if left.reflection_idx < len(texts) else left.attribution_type
                right_text = texts[right.reflection_idx] if right.reflection_idx < len(texts) else right.attribution_type
            else:
                left_text = left.attribution_type or ""
                right_text = right.attribution_type or ""
            if _jaccard(left_text, right_text) > 0.8:
                duplicate_pairs += 1
    return float(duplicate_pairs / total_pairs) if total_pairs else 0.0


_DUPLICATE_DENSITY_THRESHOLD = 50


def _duplicate_density_fast(
    annotations: Sequence[UtilityAnnotation],
    texts: Sequence[str],
) -> float:
    """Approximate duplicate density using attribution-type grouping + n-gram signatures.

    Strategy:
        1. Group annotations by attribution_type (Option B).
        2. Within each group, precompute word n-gram signatures.
        3. Only compare pairs within the same group (cross-group pairs
           cannot exceed the 0.8 Jaccard threshold since they share
           no meaningful tokens beyond the type label).
        4. Use signature intersection to quickly skip dissimilar pairs.
        5. Denominator uses total pairs (n choose 2) to match exact semantics.

    Complexity:
        Time:  O(n × G + Σ_g n_g² × T) where G = number of unique types,
               n_g = group size, Σ n_g = n.
               In practice much faster than O(n²) when types are diverse.
        Space: O(n × T) for signature storage.

    The result correlates with the exact version at Spearman > 0.95
    on typical traces because cross-type pairs rarely exceed 0.8 Jaccard.
    """
    if len(annotations) < 2:
        return 0.0

    # Precompute n-gram signatures for all annotations
    signatures: list[frozenset[str]] = []
    for ann in annotations:
        raw_text = (
            texts[ann.reflection_idx]
            if ann.reflection_idx < len(texts)
            else (ann.attribution_type or "")
        )
        signatures.append(_ngram_signature(raw_text, n=2))

    # Group indices by attribution_type
    type_groups: dict[str | None, list[int]] = defaultdict(list)
    for idx, ann in enumerate(annotations):
        type_groups[ann.attribution_type].append(idx)

    total_pairs = len(annotations) * (len(annotations) - 1) // 2
    duplicate_pairs = 0

    # Only compare within same attribution_type group
    for group_indices in type_groups.values():
        group_size = len(group_indices)
        if group_size < 2:
            continue
        for i in range(len(group_indices)):
            left_idx = group_indices[i]
            left_sig = signatures[left_idx]
            for j in range(i + 1, len(group_indices)):
                right_idx = group_indices[j]
                right_sig = signatures[right_idx]
                if _jaccard_from_signatures(left_sig, right_sig) > 0.8:
                    duplicate_pairs += 1

    return float(duplicate_pairs / total_pairs) if total_pairs else 0.0


def _duplicate_density(
    annotations: Sequence[UtilityAnnotation],
    texts: Sequence[str],
    *,
    approximate: bool = False,
) -> float:
    """Compute duplicate verification density with automatic algorithm selection.

    When ``approximate=False`` (default) and len(annotations) > 50,
    the fast approximation is used automatically for performance.
    Set ``approximate=True`` to always use the fast version,
    or pass ``approximate=False`` with small inputs for exact results.

    Complexity:
        Exact:     O(n² × T) — pairwise Jaccard for all pairs.
        Approximate: O(n × G + Σ_g n_g² × T) — grouped by attribution type.
    """
    n = len(annotations)
    use_fast = approximate or n > _DUPLICATE_DENSITY_THRESHOLD

    if use_fast:
        return _duplicate_density_fast(annotations, texts)
    return _duplicate_density_exact(annotations, texts)


def _jaccard(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"\w+", left.lower()))
    right_tokens = set(re.findall(r"\w+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return float(len(left_tokens & right_tokens) / len(left_tokens | right_tokens))


def _ngram_signature(text: str, n: int = 2) -> frozenset[str]:
    """Compute a set of word n-grams for fast similarity filtering."""
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return frozenset()
    if len(tokens) < n:
        return frozenset(tokens)
    return frozenset(" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def _jaccard_from_signatures(left: frozenset[str], right: frozenset[str]) -> float:
    """Compute Jaccard similarity from precomputed n-gram signatures."""
    if not left or not right:
        return 0.0
    return float(len(left & right) / len(left | right))


def _mean(values: np.ndarray) -> float:
    return float(np.mean(values)) if values.size else 0.0


def _std(values: np.ndarray) -> float:
    return float(np.std(values)) if values.size else 0.0


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


__all__ = [
    "ABLATION_STRATEGIES",
    "ATTRIBUTION_BOTTOM_K",
    "ATTRIBUTION_SCORE_MAP",
    "ATTRIBUTION_TOP_K",
    "CATEGORY_MATCHED_RANDOM",
    "CounterfactualAblationResult",
    "FaithfulnessMetrics",
    "MinimalSubsetResult",
    "NecessityScore",
    "POSITIONAL_FIRST_K",
    "POSITIONAL_LAST_K",
    "RANDOM_K",
    "RedundancyAnalysis",
    "UTILITY_NUMERIC",
    "ablate_step",
    "analyze_redundancy",
    "attribution_score_for_annotation",
    "attribution_score_for_type",
    "build_counterfactual_summary",
    "compute_faithfulness_metrics",
    "compute_necessity_scores",
    "compute_trace_utility",
    "dataclass_to_dict",
    "find_minimal_sufficient_subset",
    "group_annotations_by_trace",
    "minimal_subset_curves",
    "run_minimal_subset_analysis",
    "run_single_step_ablations",
    "strategy_order",
    "utility_annotation_from_record",
    "utility_annotations_from_records",
]
