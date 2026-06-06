"""Leakage-safe real-task candidate scores for structurally calibrated FMA."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .baselines import FORBIDDEN_BASELINE_SOURCE_FIELDS, TAXONOMY_PRIOR, question_difficulty_proxy
from .parsing import proxy_token_count


SCORE_NAME = "structurally_calibrated_fma"
SCORE_RULE_ID = "structurally_calibrated_fma_v1"
ANSWER_LABEL_FIELDS = {"final_answer", "reference_answer", "aliases"}
CANDIDATE_FORBIDDEN_SOURCE_FIELDS = FORBIDDEN_BASELINE_SOURCE_FIELDS | ANSWER_LABEL_FIELDS
SOURCE_FIELDS_USED = {
    "sample_id",
    "task_type",
    "question",
    "observable_trace",
    "reflection_spans",
    "question_length",
    "number_count",
    "entity_count",
    "supporting_fact_count",
}


def build_structurally_calibrated_fma_scores(
    records: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    structural_diagnostics: Mapping[str, Any],
    redundancy_analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build one leakage-safe candidate score row per expected reflection span."""

    max_spans = int(config.get("replay", {}).get("max_spans_per_trace", 3))
    rows: list[dict[str, Any]] = []
    for record in records:
        trace = str(record.get("observable_trace") or "")
        trajectory_tokens = max(1, proxy_token_count(trace))
        spans = list(record.get("reflection_spans") or [])
        difficulty = question_difficulty_proxy(record)
        for span_index, span in enumerate(spans[:max_spans]):
            operation_type = str(
                span.get("operation_type") or span.get("reflection_type") or "other"
            )
            taxonomy = _taxonomy_label(operation_type)
            span_length_ratio = _span_length_ratio(span, trajectory_tokens)
            relative_position = _relative_position(span, trajectory_tokens)
            taxonomy_prior = TAXONOMY_PRIOR.get(operation_type, TAXONOMY_PRIOR["other"])
            observable_local_proxy = _mean(
                [
                    taxonomy_prior,
                    span_length_ratio,
                    relative_position,
                    float(difficulty["score"]),
                ]
            )
            alignment_prior = _alignment_prior(structural_diagnostics, taxonomy)
            bottleneck_prior = _bottleneck_prior(
                structural_diagnostics,
                redundancy_analysis,
                taxonomy,
            )
            redundancy_penalty = _redundancy_penalty(redundancy_analysis)
            compensation_penalty = _compensation_penalty(redundancy_analysis, taxonomy)
            raw_score = (
                observable_local_proxy
                * (0.5 + 0.5 * alignment_prior)
                * (0.5 + bottleneck_prior)
                * redundancy_penalty
                * compensation_penalty
            )
            rows.append(
                {
                    "sample_id": record.get("sample_id"),
                    "task_type": record.get("task_type"),
                    "span_index": span_index,
                    "operation_type": operation_type,
                    "score_name": SCORE_NAME,
                    "candidate_name": SCORE_NAME,
                    "score_rule_id": SCORE_RULE_ID,
                    "score": 0.0,
                    "candidate_score": 0.0,
                    "raw_score": float(raw_score),
                    "components": {
                        "taxonomy_prior": float(taxonomy_prior),
                        "span_length_ratio": span_length_ratio,
                        "relative_position": relative_position,
                        "question_difficulty_proxy": float(difficulty["score"]),
                        "observable_local_proxy": observable_local_proxy,
                        "alignment_prior": alignment_prior,
                        "bottleneck_prior": bottleneck_prior,
                        "redundancy_penalty": redundancy_penalty,
                        "compensation_penalty": compensation_penalty,
                    },
                    "source_fields_used": sorted(SOURCE_FIELDS_USED),
                    "forbidden_fields_used": _forbidden_fields_used(SOURCE_FIELDS_USED),
                    "leakage_status": "clean",
                    "target_leakage_status": "clean",
                }
            )

    normalized = _min_max([row["raw_score"] for row in rows])
    for row, score in zip(rows, normalized):
        row["score"] = score
        row["candidate_score"] = score
    return rows


def build_candidate_score_leakage_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Audit candidate score rows for target-side source field leakage."""

    checks = []
    leaked = False
    for row in rows:
        used = set(row.get("source_fields_used") or [])
        declared = set(row.get("forbidden_fields_used") or [])
        forbidden = sorted(used.intersection(CANDIDATE_FORBIDDEN_SOURCE_FIELDS) | declared)
        declared_status = str(
            row.get("leakage_status") or row.get("target_leakage_status") or "clean"
        )
        row_leaked = bool(forbidden) or declared_status not in {"clean", ""}
        leaked = leaked or row_leaked
        checks.append(
            {
                "sample_id": row.get("sample_id"),
                "span_index": row.get("span_index"),
                "score_name": row.get("score_name") or row.get("candidate_name"),
                "score_rule_id": row.get("score_rule_id"),
                "source_fields_used": sorted(used),
                "forbidden_fields_used": forbidden,
                "leakage_status": "target_leaking" if row_leaked else "clean",
                "target_leakage_status": "target_leaking" if row_leaked else "clean",
            }
        )
    return {
        "candidate_family": SCORE_NAME,
        "score_rule_id": SCORE_RULE_ID,
        "target_leakage_detected": leaked,
        "target_leakage_status": "target_leaking" if leaked else "clean",
        "forbidden_source_fields": sorted(CANDIDATE_FORBIDDEN_SOURCE_FIELDS),
        "checks": checks,
    }


def _span_length_ratio(span: Mapping[str, Any], trajectory_tokens: int) -> float:
    start = int(span.get("start_token", 0) or 0)
    end = int(span.get("end_token", 0) or 0)
    return _clamp01(max(0, end - start) / trajectory_tokens)


def _relative_position(span: Mapping[str, Any], trajectory_tokens: int) -> float:
    return _clamp01(int(span.get("start_token", 0) or 0) / trajectory_tokens)


def _alignment_prior(structural_diagnostics: Mapping[str, Any], taxonomy: str) -> float:
    values = []
    modes = structural_diagnostics.get("modes", {})
    if not isinstance(modes, Mapping):
        return 0.0
    for mode_payload in modes.values():
        if not isinstance(mode_payload, Mapping):
            continue
        taxonomy_payload = _taxonomy_payload(mode_payload).get(taxonomy, {})
        if isinstance(taxonomy_payload, Mapping):
            values.append(max(0.0, float(taxonomy_payload.get("spearman", 0.0))))
    return _clamp01(_mean(values))


def _bottleneck_prior(
    structural_diagnostics: Mapping[str, Any],
    redundancy_analysis: Mapping[str, Any],
    taxonomy: str,
) -> float:
    taxonomy_count = _taxonomy_count(structural_diagnostics, taxonomy)
    if taxonomy_count <= 0:
        return 0.0
    bottleneck = redundancy_analysis.get("bottleneck", {})
    distribution = bottleneck.get("taxonomy_distribution", {}) if isinstance(bottleneck, Mapping) else {}
    if not isinstance(distribution, Mapping):
        return 0.0
    return _clamp01(float(distribution.get(taxonomy, 0.0)) / taxonomy_count)


def _redundancy_penalty(redundancy_analysis: Mapping[str, Any]) -> float:
    redundancy = redundancy_analysis.get("redundancy", {})
    density = float(redundancy.get("density", 0.0)) if isinstance(redundancy, Mapping) else 0.0
    return _clamp01(1.0 - density)


def _compensation_penalty(redundancy_analysis: Mapping[str, Any], taxonomy: str) -> float:
    compensation = redundancy_analysis.get("compensation", {})
    if not isinstance(compensation, Mapping):
        return 1.0
    values = []
    for mode in ("prune", "cascade", "bypass"):
        mode_payload = compensation.get(mode, {})
        if not isinstance(mode_payload, Mapping):
            continue
        by_taxonomy = mode_payload.get("stratified_by_taxonomy", {})
        if not isinstance(by_taxonomy, Mapping):
            continue
        taxonomy_payload = by_taxonomy.get(taxonomy, {})
        if isinstance(taxonomy_payload, Mapping):
            values.append(float(taxonomy_payload.get("mean_ratio", 0.0)))
    mean_ratio = max(0.0, _mean(values))
    return float(1.0 / (1.0 + mean_ratio))


def _taxonomy_count(structural_diagnostics: Mapping[str, Any], taxonomy: str) -> float:
    counts = []
    modes = structural_diagnostics.get("modes", {})
    if not isinstance(modes, Mapping):
        return 0.0
    for mode_payload in modes.values():
        if not isinstance(mode_payload, Mapping):
            continue
        taxonomy_payload = _taxonomy_payload(mode_payload).get(taxonomy, {})
        if isinstance(taxonomy_payload, Mapping):
            counts.append(float(taxonomy_payload.get("num_samples", 0.0)))
    return max(counts) if counts else 0.0


def _taxonomy_payload(mode_payload: Mapping[str, Any]) -> Mapping[str, Any]:
    stratified = mode_payload.get("stratified", {})
    if not isinstance(stratified, Mapping):
        return {}
    taxonomy_payload = stratified.get("taxonomy_label") or stratified.get("taxonomy") or {}
    return taxonomy_payload if isinstance(taxonomy_payload, Mapping) else {}


def _taxonomy_label(operation_type: str) -> str:
    return str(operation_type).strip().upper().replace("-", "_") or "OTHER"


def _forbidden_fields_used(source_fields: set[str]) -> list[str]:
    return sorted(source_fields.intersection(CANDIDATE_FORBIDDEN_SOURCE_FIELDS))


def _min_max(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    min_value = min(values)
    max_value = max(values)
    if max_value == min_value:
        fill = 1.0 if max_value > 0.0 else 0.0
        return [fill for _value in values]
    return [float((value - min_value) / (max_value - min_value)) for value in values]


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


__all__ = [
    "CANDIDATE_FORBIDDEN_SOURCE_FIELDS",
    "SCORE_NAME",
    "SCORE_RULE_ID",
    "build_candidate_score_leakage_audit",
    "build_structurally_calibrated_fma_scores",
]
