"""Convert open-source reasoning traces to FMA attribution pipeline format.

Bridges ``fma.data.schema.OpenTraceRecord`` with ``fma.eval.utility_annotation.UtilityAnnotation``
so that open-source CoT traces can be consumed by the existing
``compute_necessity_scores`` / ``compute_trace_utility`` / ``run_single_step_ablations``
pipeline without requiring pre-computed intervention outcomes.
"""

from __future__ import annotations

from typing import Any

from fma.data.schema import OpenTraceRecord
from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
)


def open_traces_to_utility_annotations(
    records: list[OpenTraceRecord],
) -> list[UtilityAnnotation]:
    """Convert open-source traces to UtilityAnnotation objects.

    For each step/spans in each record, creates one ``UtilityAnnotation``.
    Utility labels are derived from:
    - PRM800K: ``ground_truth_importance`` (1.0→HELPFUL, 0.0→HARMFUL)
    - Other sources: operation_type + answer correctness heuristic
    """
    annotations: list[UtilityAnnotation] = []
    for record in records:
        if not record.step_annotations:
            continue
        for ann in record.step_annotations:
            utility = _derive_utility(ann.step_text, ann.ground_truth_importance, record.is_correct)
            attribution_type = _derive_attribution_type(ann.operation_type)

            annotations.append(
                UtilityAnnotation(
                    trace_id=record.sample_id,
                    reflection_idx=ann.step_index,
                    utility=utility,
                    outcome_delta=OutcomeDelta.INCONCLUSIVE,
                    degradation_score=_degradation_from_importance(ann.ground_truth_importance),
                    annotation_confidence=_confidence_from_importance(ann.ground_truth_importance),
                    attribution_type=attribution_type,
                    attribution_alignment=AttributionAlignment.PARTIAL,
                    intervention_type=None,
                    reflection_category=ann.operation_type.upper().replace("-", "_"),
                    correctness_preserved=record.is_correct,
                )
            )
    return annotations


def open_traces_to_internal_format(
    records: list[OpenTraceRecord],
) -> list[dict[str, Any]]:
    """Convert to dict format compatible with ``ablate_step`` and trace mapping."""
    traces: list[dict[str, Any]] = []
    for record in records:
        spans: list[dict[str, Any]] = []
        for ann in record.step_annotations:
            spans.append(
                {
                    "step_index": ann.step_index,
                    "start_char": ann.start_char,
                    "end_char": ann.end_char,
                    "start_token": ann.start_token,
                    "end_token": ann.end_token,
                    "content": ann.step_text,
                    "operation_type": ann.operation_type,
                    "reflection_type": ann.operation_type,
                    "text": ann.step_text,
                }
            )
        traces.append(
            {
                "trace_id": record.sample_id,
                "sample_id": record.sample_id,
                "task_type": record.dataset,
                "reflection_spans": spans,
                "reasoning_trace": record.full_reasoning_trace,
                "final_answer": record.answer,
                "reference_answer": record.reference_answer,
                "correctness": record.is_correct,
            }
        )
    return traces


def _derive_utility(
    step_text: str,
    importance: float | None,
    is_correct: bool,
) -> UtilityLabel:
    if importance is not None:
        if importance >= 0.8:
            return UtilityLabel.HELPFUL
        if importance <= 0.2:
            return UtilityLabel.HARMFUL
        return UtilityLabel.NEUTRAL

    text = step_text.strip().lower()
    error_cues = ("mistake", "error", "incorrect", "wrong", "that's not right", "miscalc")
    verify_cues = ("verify", "check", "confirm", "double-check", "let me verify")
    plan_cues = ("plan", "next step", "strategy", "approach", "let me think")
    compute_cues = (
        "calculate", "compute", "multiply", "divide", "add", "subtract",
        "total", "sum", "difference", "product",
    )
    transition_cues = ("therefore", "thus", "hence", "so ", "then ")

    error_count = sum(1 for cue in error_cues if cue in text)
    verify_count = sum(1 for cue in verify_cues if cue in text)
    plan_count = sum(1 for cue in plan_cues if cue in text)
    compute_count = sum(1 for cue in compute_cues if cue in text)
    transition_count = sum(1 for cue in transition_cues if cue in text)

    if error_count > 0:
        return UtilityLabel.HARMFUL
    if verify_count > 0:
        return UtilityLabel.NEUTRAL
    if plan_count > 0 and compute_count == 0:
        return UtilityLabel.HELPFUL
    if compute_count > 0:
        return UtilityLabel.HELPFUL if is_correct else UtilityLabel.NEUTRAL
    if transition_count > 0:
        return UtilityLabel.NEUTRAL

    return UtilityLabel.NEUTRAL


def _derive_attribution_type(operation_type: str) -> str | None:
    mapping: dict[str, str] = {
        "verification": "metacognitive",
        "error_correction": "factual_error",
        "backtracking": "reasoning_gap",
        "decomposition": "reasoning_gap",
        "planning": "metacognitive",
        "uncertainty_monitoring": "metacognitive",
        "constraint_tracking": "reasoning_gap",
        "retrieval": "reasoning_gap",
        "self-evaluation": "metacognitive",
        "strategy_critique": "vague",
    }
    return mapping.get(operation_type, None)


def _degradation_from_importance(importance: float | None) -> float:
    if importance is None:
        return 0.0
    return max(0.0, 1.0 - importance)


def _confidence_from_importance(importance: float | None) -> float:
    if importance is None:
        return 0.5
    return 0.3 + 0.4 * abs(importance - 0.5) * 2.0


__all__ = [
    "open_traces_to_internal_format",
    "open_traces_to_utility_annotations",
]
