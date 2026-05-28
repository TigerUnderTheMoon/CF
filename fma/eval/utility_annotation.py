"""Outcome-grounded utility annotations for functional validity."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from fma.io import write_records


class UtilityLabel(Enum):
    HELPFUL = "helpful"
    HARMFUL = "harmful"
    NEUTRAL = "neutral"
    SPURIOUS = "spurious"


class OutcomeDelta(Enum):
    IMPROVED = "improved"
    DEGRADED = "degraded"
    UNCHANGED = "unchanged"
    INCONCLUSIVE = "inconclusive"


class AttributionAlignment(Enum):
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


@dataclass(frozen=True)
class UtilityAnnotation:
    trace_id: str
    reflection_idx: int
    utility: UtilityLabel
    outcome_delta: OutcomeDelta
    degradation_score: float
    annotation_confidence: float
    attribution_type: str | None
    attribution_alignment: AttributionAlignment
    intervention_type: str | None
    reflection_category: str
    correctness_preserved: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "trace_id": self.trace_id,
            "reflection_idx": self.reflection_idx,
            "utility": self.utility.value,
            "outcome_delta": self.outcome_delta.value,
            "degradation_score": self.degradation_score,
            "annotation_confidence": self.annotation_confidence,
            "attribution_type": self.attribution_type,
            "attribution_alignment": self.attribution_alignment.value,
            "intervention_type": self.intervention_type,
            "reflection_category": self.reflection_category,
            "correctness_preserved": self.correctness_preserved,
        }


@dataclass(frozen=True)
class AttributionSignal:
    attribution_type: str | None
    confidence: float
    matched_cues: tuple[str, ...]


SUPPORTED_INTERVENTIONS = frozenset({"delete", "shuffle", "replace", "truncate", "contradict"})
SUPPORTED_ATTRIBUTION_TYPES = frozenset(
    {"factual_error", "reasoning_gap", "metacognitive", "vague", "irrelevant"}
)
EXPECTED_SOURCE_BY_INTERVENTION: dict[str, str] = {
    "contradict": "contradiction",
    "delete": "missing_information",
    "shuffle": "ordering_error",
    "replace": "wrong_substitution",
    "truncate": "incomplete_reasoning",
}

_ATTRIBUTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "factual_error",
        (
            r"\bmiscalculat\w*\b",
            r"\bcalculation error\b",
            r"\barithmetic\b",
            r"\bwrong variable\b",
            r"\bwrong substitution\b",
            r"\bsubstitut\w+\b",
            r"\bmistake\b",
            r"\berror\b",
            r"\binconsistent\b",
            r"\bconflict\w*\b",
            r"\bcontradict\w*\b",
            r"\binvalid\b",
        ),
    ),
    (
        "reasoning_gap",
        (
            r"\bmissing\b",
            r"\bdropped\b",
            r"\bincomplete\b",
            r"\bgap\b",
            r"\breconsider\b",
            r"\bapproach\b",
            r"\bassumption\b",
            r"\balternative\b",
            r"\bbacktrack\b",
            r"\bsubproblem\b",
            r"\bcontinue\b",
            r"\bcontinuation\b",
            r"\bdefinition\b",
            r"\bknown relation\b",
            r"\brelevant rule\b",
            r"\bpreviously established\b",
        ),
    ),
    (
        "metacognitive",
        (
            r"\bthink more carefully\b",
            r"\bcarefully\b",
            r"\bcheck\b",
            r"\bverify\b",
            r"\bplan\b",
            r"\bstrategy\b",
            r"\buncertain\b",
            r"\bnot sure\b",
            r"\bmonitor\b",
            r"\bmark\b",
        ),
    ),
    (
        "vague",
        (
            r"\bwrong\b",
            r"\bflawed\b",
            r"\bsuspect\b",
            r"\bissue\b",
            r"\bproblem\b",
            r"\bwas wrong\b",
        ),
    ),
    (
        "irrelevant",
        (
            r"\birrelevant\b",
            r"\bunrelated\b",
            r"\boff[- ]topic\b",
            r"\bdoes not matter\b",
        ),
    ),
)

_SOURCE_PATTERNS: dict[str, tuple[str, ...]] = {
    "contradict": (
        r"\bcontradict\w*\b",
        r"\bconflict\w*\b",
        r"\binconsistent\b",
        r"\binvalid\b",
        r"\bsuspect\b",
    ),
    "delete": (
        r"\bmissing\b",
        r"\bdropped\b",
        r"\blost\b",
        r"\bincomplete\b",
        r"\bretrieve\b",
        r"\brecall\b",
        r"\bgiven information\b",
    ),
    "shuffle": (
        r"\border\b",
        r"\bsequence\b",
        r"\bscrambl\w*\b",
        r"\breorder\b",
        r"\bin order\b",
        r"\bprevious step\b",
        r"\bbacktrack\b",
    ),
    "replace": (
        r"\bwrong substitution\b",
        r"\bsubstitut\w+\b",
        r"\bwrong variable\b",
        r"\bdefinition\b",
        r"\bknown relation\b",
        r"\binconsistent\b",
    ),
    "truncate": (
        r"\bincomplete\b",
        r"\bcontinue\b",
        r"\bcontinuation\b",
        r"\bpartial\b",
        r"\bfinish\b",
        r"\bstop\w* too early\b",
    ),
}

_BROAD_ATTRIBUTION_BY_INTERVENTION: dict[str, tuple[str, ...]] = {
    "contradict": ("vague",),
    "delete": ("reasoning_gap", "metacognitive", "vague"),
    "shuffle": ("reasoning_gap", "metacognitive", "vague"),
    "replace": ("factual_error", "reasoning_gap", "vague"),
    "truncate": ("reasoning_gap", "metacognitive", "vague"),
}

_BOOL_FIELDS = (
    "correctness",
    "original_correctness",
    "counterfactual_correctness",
    "intervened_correctness",
)
_ORIGINAL_OUTCOME_FIELDS = ("original_outcome", "utility_before")
_INTERVENED_OUTCOME_FIELDS = ("intervened_outcome", "utility_after", "counterfactual_outcome")


def extract_attribution(text: str) -> AttributionSignal:
    """Extract attribution type with deterministic regex cues."""
    stripped = text.strip()
    if not stripped:
        return AttributionSignal(attribution_type=None, confidence=0.0, matched_cues=())

    scored: list[tuple[int, int, str, tuple[str, ...]]] = []
    for order, (attribution_type, patterns) in enumerate(_ATTRIBUTION_PATTERNS):
        cues = tuple(
            pattern
            for pattern in patterns
            if re.search(pattern, stripped, flags=re.IGNORECASE)
        )
        if cues:
            scored.append((len(cues), -order, attribution_type, cues))

    if not scored:
        return AttributionSignal(attribution_type=None, confidence=0.0, matched_cues=())

    scored.sort(reverse=True)
    cue_count, _order, attribution_type, cues = scored[0]
    confidence = min(1.0, 0.35 + 0.2 * cue_count)
    if attribution_type == "vague":
        confidence = min(confidence, 0.45)
    elif attribution_type == "irrelevant":
        confidence = min(confidence, 0.25)
    return AttributionSignal(
        attribution_type=attribution_type,
        confidence=float(confidence),
        matched_cues=cues,
    )


def expected_source_for_intervention(intervention_type: str | None) -> str | None:
    """Return the expected failure source label for an intervention."""
    normalized = normalize_intervention(intervention_type)
    if normalized is None:
        return None
    return EXPECTED_SOURCE_BY_INTERVENTION[normalized]


def normalize_intervention(value: Any) -> str | None:
    """Normalize supported Phase 3 intervention names."""
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("_", "-")
    normalized = normalized.replace("-", "_")
    if normalized in SUPPORTED_INTERVENTIONS:
        return normalized
    return None


def evaluate_attribution_alignment(
    reflection_text: str,
    intervention_type: str | None,
    attribution_type: str | None,
) -> AttributionAlignment:
    """Compare extracted attribution cues against the intervention source."""
    intervention = normalize_intervention(intervention_type)
    if intervention is None:
        return AttributionAlignment.PARTIAL if attribution_type else AttributionAlignment.INCORRECT
    if attribution_type is None or attribution_type == "irrelevant":
        return AttributionAlignment.INCORRECT

    text = reflection_text.strip()
    source_patterns = _SOURCE_PATTERNS[intervention]
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in source_patterns):
        return AttributionAlignment.CORRECT

    broad_types = _BROAD_ATTRIBUTION_BY_INTERVENTION[intervention]
    if attribution_type in broad_types:
        return AttributionAlignment.PARTIAL
    return AttributionAlignment.INCORRECT


def annotate_utility_records(
    trace_records: Sequence[Mapping[str, Any]],
    outcome_records: Sequence[Mapping[str, Any]] | None = None,
) -> list[UtilityAnnotation]:
    """Annotate each reflection step with outcome-grounded utility labels."""
    if trace_records is None:
        raise ValueError("trace_records must not be None.")

    outcome_by_trace = {
        _trace_id_for_record(record, index): record
        for index, record in enumerate(outcome_records or ())
    }
    annotations: list[UtilityAnnotation] = []
    for trace_index, trace_record in enumerate(trace_records):
        trace_id = _trace_id_for_record(trace_record, trace_index)
        outcome_record = outcome_by_trace.get(trace_id, {})
        merged = {**dict(trace_record), **dict(outcome_record)}
        reflection_steps = _reflection_steps(trace_record)
        if not reflection_steps:
            continue

        outcome_delta = infer_outcome_delta(trace_record, outcome_record)
        degradation_score = infer_degradation_score(trace_record, outcome_record)
        correctness_preserved = infer_correctness_preserved(trace_record, outcome_record, outcome_delta)
        intervention = normalize_intervention(
            outcome_record.get("intervention_type") or trace_record.get("intervention_type")
        )

        for reflection_idx, step in enumerate(reflection_steps):
            text = str(step.get("text") or step.get("content") or "")
            category = str(
                step.get("category")
                or step.get("reflection_type")
                or step.get("operation_type")
                or merged.get("category")
                or "OTHER"
            ).strip()
            signal = extract_attribution(text)
            alignment = evaluate_attribution_alignment(text, intervention, signal.attribution_type)
            utility = assign_utility_label(
                outcome_delta=outcome_delta,
                degradation_score=degradation_score,
                attribution_type=signal.attribution_type,
                attribution_alignment=alignment,
                correctness_preserved=correctness_preserved,
            )
            confidence = annotation_confidence(
                signal_confidence=signal.confidence,
                attribution_alignment=alignment,
                outcome_delta=outcome_delta,
                correctness_preserved=correctness_preserved,
            )
            annotations.append(
                UtilityAnnotation(
                    trace_id=trace_id,
                    reflection_idx=reflection_idx,
                    utility=utility,
                    outcome_delta=outcome_delta,
                    degradation_score=degradation_score,
                    annotation_confidence=confidence,
                    attribution_type=signal.attribution_type,
                    attribution_alignment=alignment,
                    intervention_type=intervention,
                    reflection_category=category.upper().replace("-", "_"),
                    correctness_preserved=correctness_preserved,
                )
            )
    return annotations


def infer_outcome_delta(
    trace_record: Mapping[str, Any],
    outcome_record: Mapping[str, Any] | None = None,
) -> OutcomeDelta:
    """Infer whether measurable downstream outcome improved, degraded, or stayed fixed."""
    original = _original_outcome(trace_record, outcome_record or {})
    intervened = _intervened_outcome(trace_record, outcome_record or {}, original)
    if original is None or intervened is None:
        return OutcomeDelta.INCONCLUSIVE

    tolerance = 1e-9
    if intervened > original + tolerance:
        return OutcomeDelta.IMPROVED
    if intervened < original - tolerance:
        return OutcomeDelta.DEGRADED
    return OutcomeDelta.UNCHANGED


def infer_degradation_score(
    trace_record: Mapping[str, Any],
    outcome_record: Mapping[str, Any] | None = None,
) -> float:
    """Compute correctness-aware degradation with text similarity fallback."""
    outcome_record = outcome_record or {}
    original = _original_outcome(trace_record, outcome_record)
    intervened = _intervened_outcome(trace_record, outcome_record, original)
    if original is not None and intervened is not None:
        return _bounded(max(0.0, original - intervened))

    for field_name in ("utility_delta", "utility_shift", "ciu", "reflection_ciu"):
        if field_name in outcome_record:
            value = _coerce_float(outcome_record.get(field_name))
            if value is not None:
                return _bounded(max(0.0, value))

    before_text = str(trace_record.get("reasoning_trace") or trace_record.get("reflection_text") or "")
    after_text = str(
        outcome_record.get("counterfactual_trace")
        or outcome_record.get("intervened_trace")
        or outcome_record.get("reasoning_trace")
        or ""
    )
    if before_text and after_text:
        return _bounded(1.0 - SequenceMatcher(None, before_text, after_text).ratio())
    return 0.0


def infer_correctness_preserved(
    trace_record: Mapping[str, Any],
    outcome_record: Mapping[str, Any] | None,
    outcome_delta: OutcomeDelta,
) -> bool:
    """Return whether downstream correctness or outcome was preserved."""
    original = _original_outcome(trace_record, outcome_record or {})
    intervened = _intervened_outcome(trace_record, outcome_record or {}, original)
    if original is None or intervened is None:
        return outcome_delta is not OutcomeDelta.DEGRADED
    return intervened >= original - 1e-9


def assign_utility_label(
    outcome_delta: OutcomeDelta,
    degradation_score: float,
    attribution_type: str | None,
    attribution_alignment: AttributionAlignment,
    correctness_preserved: bool,
) -> UtilityLabel:
    """Assign final utility from outcome effect first, then attribution quality."""
    has_attribution = attribution_type is not None and attribution_type != "irrelevant"
    materially_degraded = outcome_delta is OutcomeDelta.DEGRADED or degradation_score > 0.05

    if outcome_delta is OutcomeDelta.INCONCLUSIVE:
        return UtilityLabel.NEUTRAL if not has_attribution else UtilityLabel.SPURIOUS

    if materially_degraded:
        if has_attribution and attribution_alignment in {
            AttributionAlignment.CORRECT,
            AttributionAlignment.PARTIAL,
        }:
            return UtilityLabel.SPURIOUS
        return UtilityLabel.HARMFUL

    if correctness_preserved:
        if attribution_alignment is AttributionAlignment.CORRECT:
            return UtilityLabel.HELPFUL
        if attribution_alignment is AttributionAlignment.PARTIAL and has_attribution:
            return UtilityLabel.HELPFUL
        if has_attribution:
            return UtilityLabel.SPURIOUS
        return UtilityLabel.NEUTRAL

    return UtilityLabel.HARMFUL


def annotation_confidence(
    signal_confidence: float,
    attribution_alignment: AttributionAlignment,
    outcome_delta: OutcomeDelta,
    correctness_preserved: bool,
) -> float:
    """Estimate deterministic annotation confidence in [0, 1]."""
    confidence = _bounded(signal_confidence)
    if correctness_preserved and outcome_delta in {OutcomeDelta.IMPROVED, OutcomeDelta.UNCHANGED}:
        confidence += 0.2
    if outcome_delta is OutcomeDelta.DEGRADED:
        confidence += 0.1
    if attribution_alignment is AttributionAlignment.CORRECT:
        confidence += 0.2
    elif attribution_alignment is AttributionAlignment.PARTIAL:
        confidence += 0.05
    else:
        confidence -= 0.1
    if outcome_delta is OutcomeDelta.INCONCLUSIVE:
        confidence -= 0.25
    return _bounded(confidence)


def write_utility_annotations(annotations: Sequence[UtilityAnnotation], output_path: Path) -> None:
    """Write utility annotations as JSONL."""
    write_records([annotation.to_dict() for annotation in annotations], output_path)


def _reflection_steps(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    chain = record.get("reflection_chain")
    if isinstance(chain, list):
        steps = [dict(step) for step in chain if isinstance(step, Mapping)]
        if steps:
            return steps

    spans = record.get("reflection_spans") or record.get("metacognitive_spans")
    if isinstance(spans, list):
        steps = [dict(span) for span in spans if isinstance(span, Mapping)]
        if steps:
            return steps

    text = record.get("reflection_text")
    if isinstance(text, str) and text.strip():
        return [{"text": text, "category": record.get("category", "OTHER")}]
    return []


def _trace_id_for_record(record: Mapping[str, Any], index: int) -> str:
    return str(record.get("trace_id") or record.get("sample_id") or record.get("task_id") or f"trace_{index:03d}")


def _original_outcome(
    trace_record: Mapping[str, Any],
    outcome_record: Mapping[str, Any],
) -> float | None:
    for field_name in _ORIGINAL_OUTCOME_FIELDS:
        value = _coerce_float(outcome_record.get(field_name))
        if value is not None:
            return value
    value = _coerce_bool_or_float(trace_record.get("correctness"))
    if value is not None:
        return value
    return _answer_correctness(trace_record)


def _intervened_outcome(
    trace_record: Mapping[str, Any],
    outcome_record: Mapping[str, Any],
    original_outcome: float | None,
) -> float | None:
    for field_name in ("counterfactual_correctness", "intervened_correctness"):
        value = _coerce_bool_or_float(outcome_record.get(field_name))
        if value is not None:
            return value
    for field_name in _INTERVENED_OUTCOME_FIELDS:
        value = _coerce_float(outcome_record.get(field_name))
        if value is not None:
            return value
    if original_outcome is not None:
        for field_name in ("utility_delta", "utility_shift", "ciu", "reflection_ciu"):
            value = _coerce_float(outcome_record.get(field_name))
            if value is not None:
                return original_outcome - value
    return _answer_correctness(outcome_record)


def _answer_correctness(record: Mapping[str, Any]) -> float | None:
    final_answer = record.get("final_answer") or record.get("counterfactual_answer")
    reference = record.get("reference_answer")
    if final_answer is None or reference is None:
        return None
    return 1.0 if _normalize_answer(str(final_answer)) == _normalize_answer(str(reference)) else 0.0


def _normalize_answer(text: str) -> str:
    normalized = text.strip().lower()
    if "####" in normalized:
        normalized = normalized.split("####")[-1].strip()
    numbers = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", normalized)
    if numbers:
        return numbers[-1].replace(",", "")
    return re.sub(r"\s+", " ", normalized)


def _coerce_bool_or_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return _coerce_float(value)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _bounded(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


__all__ = [
    "AttributionAlignment",
    "AttributionSignal",
    "OutcomeDelta",
    "UtilityAnnotation",
    "UtilityLabel",
    "annotate_utility_records",
    "annotation_confidence",
    "assign_utility_label",
    "evaluate_attribution_alignment",
    "expected_source_for_intervention",
    "extract_attribution",
    "infer_correctness_preserved",
    "infer_degradation_score",
    "infer_outcome_delta",
    "normalize_intervention",
    "write_utility_annotations",
]
