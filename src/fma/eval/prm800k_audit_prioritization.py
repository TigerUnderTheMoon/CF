from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MethodAuditSummary:
    method: str
    mean_top1_hit: float
    mean_mass_at_25: float
    mean_mass_at_50: float
    mean_ndcg_at_25: float
    mean_ndcg_at_50: float


SIMPLE_BASELINE_METHODS = (
    "raw_local_utility",
    "relative_position",
    "span_length",
    "random",
)


def keep_count(n_steps: int, keep_fraction: float) -> int:
    if n_steps <= 0:
        return 0
    return max(1, min(n_steps, int(math.ceil(n_steps * keep_fraction))))


def selected_indices(scores: Sequence[float], keep_fraction: float) -> list[int]:
    scores_array = np.asarray(scores, dtype=float)
    k = keep_count(len(scores_array), keep_fraction)
    if k == 0:
        return []
    order = np.argsort(-scores_array, kind="mergesort")
    return [int(i) for i in order[:k]]


def max_label_hit_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    if labels_array.size == 0:
        return 0.0
    selected = selected_indices(scores, keep_fraction)
    max_label = float(np.max(labels_array))
    return 1.0 if any(float(labels_array[i]) == max_label for i in selected) else 0.0


def label_mass_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    total = float(np.sum(labels_array))
    if total <= 0.0:
        return 0.0
    selected = selected_indices(scores, keep_fraction)
    return float(np.sum(labels_array[selected]) / total)


def ndcg_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    selected = selected_indices(scores, keep_fraction)
    if not selected:
        return 0.0
    gains = np.power(2.0, labels_array[selected]) - 1.0
    discounts = 1.0 / np.log2(np.arange(2, len(selected) + 2))
    dcg = float(np.sum(gains * discounts))
    ideal = np.sort(labels_array)[::-1][: len(selected)]
    ideal_gains = np.power(2.0, ideal) - 1.0
    ideal_dcg = float(np.sum(ideal_gains * discounts))
    return 0.0 if ideal_dcg <= 0.0 else dcg / ideal_dcg


def label_entropy(labels: Sequence[float]) -> float:
    """Return normalized Shannon entropy over the observed label support."""
    values = np.asarray(labels, dtype=float)
    if values.size == 0:
        return 0.0
    unique, counts = np.unique(values, return_counts=True)
    if len(unique) <= 1:
        return 0.0
    probabilities = counts.astype(float) / float(np.sum(counts))
    entropy = -float(np.sum(probabilities * np.log(probabilities)))
    return entropy / float(np.log(len(unique)))


def tertile_cutpoints(values: Sequence[float]) -> tuple[float, float]:
    """Compute deterministic tertile cutpoints for stratum assignment."""
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return (0.0, 0.0)
    return (float(np.quantile(array, 1.0 / 3.0)), float(np.quantile(array, 2.0 / 3.0)))


def assign_trace_length_stratum(n_steps: int | float, cutpoints: tuple[float, float]) -> str:
    return _assign_tertile(float(n_steps), cutpoints, "trace_length")


def assign_label_entropy_stratum(entropy: float, cutpoints: tuple[float, float]) -> str:
    return _assign_tertile(float(entropy), cutpoints, "label_entropy")


def assign_error_uncertainty_stratum(feature_rows: Sequence[Mapping[str, Any]]) -> str:
    for row in feature_rows:
        if float(row.get("error_uncertainty_cue_count", 0.0)) > 0.0:
            return "error_uncertainty_present"
    return "error_uncertainty_absent"


def _assign_tertile(value: float, cutpoints: tuple[float, float], prefix: str) -> str:
    low, high = cutpoints
    if value <= low:
        return f"{prefix}_low"
    if value <= high:
        return f"{prefix}_mid"
    return f"{prefix}_high"


def summarize_audit_prioritization(
    rows: Sequence[Mapping[str, object]],
    *,
    methods: Sequence[str],
) -> list[MethodAuditSummary]:
    summaries: list[MethodAuditSummary] = []
    for method in methods:
        top1_hits: list[float] = []
        mass25: list[float] = []
        mass50: list[float] = []
        ndcg25: list[float] = []
        ndcg50: list[float] = []
        for row in rows:
            labels = row["labels"]
            scores_by_method = row["scores_by_method"]
            if not isinstance(labels, Sequence):
                continue
            if not isinstance(scores_by_method, Mapping) or method not in scores_by_method:
                continue
            scores = scores_by_method[method]
            if not isinstance(scores, Sequence):
                continue
            top1_hits.append(
                max_label_hit_at_budget(
                    scores,
                    labels,
                    keep_fraction=1.0 / len(labels),
                )
            )
            mass25.append(label_mass_at_budget(scores, labels, keep_fraction=0.25))
            mass50.append(label_mass_at_budget(scores, labels, keep_fraction=0.50))
            ndcg25.append(ndcg_at_budget(scores, labels, keep_fraction=0.25))
            ndcg50.append(ndcg_at_budget(scores, labels, keep_fraction=0.50))
        summaries.append(
            MethodAuditSummary(
                method=method,
                mean_top1_hit=float(np.mean(top1_hits)) if top1_hits else 0.0,
                mean_mass_at_25=float(np.mean(mass25)) if mass25 else 0.0,
                mean_mass_at_50=float(np.mean(mass50)) if mass50 else 0.0,
                mean_ndcg_at_25=float(np.mean(ndcg25)) if ndcg25 else 0.0,
                mean_ndcg_at_50=float(np.mean(ndcg50)) if ndcg50 else 0.0,
            )
        )
    return summaries


def summarize_audit_prioritization_by_stratum(
    rows: Sequence[Mapping[str, object]],
    *,
    methods: Sequence[str],
    strata: Sequence[str],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for stratum_type in strata:
        stratum_names = sorted(
            {
                str(row.get("strata", {}).get(stratum_type))
                for row in rows
                if isinstance(row.get("strata"), Mapping)
                and row.get("strata", {}).get(stratum_type) is not None
            }
        )
        for stratum_name in stratum_names:
            stratum_rows = [
                row
                for row in rows
                if isinstance(row.get("strata"), Mapping)
                and row.get("strata", {}).get(stratum_type) == stratum_name
            ]
            for method in methods:
                values = _method_metric_values(stratum_rows, method)
                if not values["top1_max_label_hit"]:
                    continue
                summaries.append(
                    {
                        "stratum_type": stratum_type,
                        "stratum": stratum_name,
                        "method": method,
                        "n_samples": len(values["top1_max_label_hit"]),
                        "n_steps": sum(int(row.get("n_steps", 0)) for row in stratum_rows),
                        "mean_spearman": _mean(values["spearman"]),
                        "mean_top1_hit": _mean(values["top1_max_label_hit"]),
                        "mean_mass_at_25": _mean(values["label_mass_at_25"]),
                        "mean_mass_at_50": _mean(values["label_mass_at_50"]),
                        "mean_ndcg_at_25": _mean(values["ndcg_at_25"]),
                        "mean_ndcg_at_50": _mean(values["ndcg_at_50"]),
                    }
                )
    return summaries


def classify_stratified_decision(
    summaries: Sequence[Mapping[str, Any]],
    *,
    primary_method: str = "w_struct",
    simple_baselines: Sequence[str] = SIMPLE_BASELINE_METHODS,
    hard_drop_tolerance: float = 0.05,
) -> dict[str, str]:
    """Map stratified PRM800K results to the manuscript action table."""
    if not summaries:
        return _decision(
            "blocked",
            "Update paper/submission_lock_audit.md to blocked_for_submission; "
            "update paper/claim_registry.md active empirical claims to "
            "stratum_dependent or failed_validation; do not mark final package "
            "submission-ready.",
        )

    by_key = {
        (str(row["stratum_type"]), str(row["stratum"]), str(row["method"])): row
        for row in summaries
    }
    hard_rows = [
        row
        for row in summaries
        if row.get("method") == primary_method
        and (
            str(row.get("stratum", "")).endswith("_high")
            or str(row.get("stratum", "")) == "error_uncertainty_present"
        )
    ]
    if not hard_rows:
        return _decision(
            "blocked",
            "Update paper/submission_lock_audit.md to blocked_for_submission; "
            "update paper/claim_registry.md active empirical claims to "
            "stratum_dependent or failed_validation; do not mark final package "
            "submission-ready.",
        )

    for hard_row in hard_rows:
        stratum_type = str(hard_row["stratum_type"])
        stratum_name = str(hard_row["stratum"])
        hard_score = float(hard_row.get("mean_spearman", 0.0))
        baseline_scores = [
            float(by_key[(stratum_type, stratum_name, baseline)].get("mean_spearman", 0.0))
            for baseline in simple_baselines
            if (stratum_type, stratum_name, baseline) in by_key
        ]
        if baseline_scores and hard_score <= max(baseline_scores):
            return _decision(
                "diagnostic",
                "Retitle as Diagnostic Framework; downgrade abstract, conclusion, "
                "cover letter, and final submission manifest.",
            )

    for hard_row in hard_rows:
        stratum_type = str(hard_row["stratum_type"])
        stratum_name = str(hard_row["stratum"])
        easy_name = _paired_easy_stratum(stratum_name)
        if not easy_name:
            continue
        easy_row = by_key.get((stratum_type, easy_name, primary_method))
        if easy_row is None:
            continue
        if float(hard_row.get("mean_spearman", 0.0)) < (
            float(easy_row.get("mean_spearman", 0.0)) - hard_drop_tolerance
        ):
            return _decision(
                "moderate",
                "Soften title and abstract to moderate or preliminary real-data support; "
                "keep PRM800K-like audit-prioritization boundary.",
            )

    return _decision(
        "strong",
        "Retain methodology wording while limiting the claim to PRM800K-like "
        "audit prioritization.",
    )


def _method_metric_values(
    rows: Sequence[Mapping[str, object]],
    method: str,
) -> dict[str, list[float]]:
    values = {
        "spearman": [],
        "top1_max_label_hit": [],
        "label_mass_at_25": [],
        "label_mass_at_50": [],
        "ndcg_at_25": [],
        "ndcg_at_50": [],
    }
    for row in rows:
        scores_by_method = row.get("scores_by_method")
        labels = row.get("labels")
        if not isinstance(scores_by_method, Mapping) or method not in scores_by_method:
            continue
        if not isinstance(labels, Sequence):
            continue
        scores = scores_by_method[method]
        if not isinstance(scores, Sequence):
            continue
        values["spearman"].append(spearman(scores, labels))
        values["top1_max_label_hit"].append(
            max_label_hit_at_budget(scores, labels, keep_fraction=1.0 / len(labels))
        )
        values["label_mass_at_25"].append(
            label_mass_at_budget(scores, labels, keep_fraction=0.25)
        )
        values["label_mass_at_50"].append(
            label_mass_at_budget(scores, labels, keep_fraction=0.50)
        )
        values["ndcg_at_25"].append(ndcg_at_budget(scores, labels, keep_fraction=0.25))
        values["ndcg_at_50"].append(ndcg_at_budget(scores, labels, keep_fraction=0.50))
    return values


def spearman(left: Sequence[float], right: Sequence[float]) -> float:
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    if left_array.size != right_array.size or left_array.size < 2:
        return 0.0
    left_rank = _rankdata(left_array)
    right_rank = _rankdata(right_array)
    if float(np.std(left_rank)) == 0.0 or float(np.std(right_rank)) == 0.0:
        return 0.0
    return float(np.corrcoef(left_rank, right_rank)[0, 1])


def _rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    index = 0
    while index < len(values):
        end = index + 1
        while end < len(values) and values[order[end]] == values[order[index]]:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        ranks[order[index:end]] = average_rank
        index = end
    return ranks


def _mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _decision(decision: str, required_action: str) -> dict[str, str]:
    return {"decision": decision, "required_action": required_action}


def _paired_easy_stratum(stratum_name: str) -> str | None:
    if stratum_name.endswith("_high"):
        return stratum_name.removesuffix("_high") + "_low"
    if stratum_name == "error_uncertainty_present":
        return "error_uncertainty_absent"
    return None
