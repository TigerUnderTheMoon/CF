"""Compute masking-based intervention CIU for open-source reasoning traces.

This is the core of FMA: for each reasoning step, we mask it with
[REASONING_MASK], extract the final answer from the remaining text, and
compare with the reference answer.

CIU(m_k | x_<k) = correctness(original) - correctness(do(mask_k))
"""

from __future__ import annotations

import re

from fma.data.schema import OpenTraceRecord
from fma.eval.answer_match import extract_answer, match_answer

_MASK_TOKEN = "[REASONING_MASK]"


def compute_masking_ciu(
    records: list[OpenTraceRecord],
    mask_token: str = _MASK_TOKEN,
) -> dict[str, list[float]]:
    """Compute CIU via structure-preserving masking intervention.

    For each step in each trace:
    1. Replace step text with ``mask_token`` repeated to match length
    2. Extract final answer from the masked trace
    3. CIU = correct(original) - correct(masked)

    Returns:
        Dict mapping sample_id to list of CIU values in [-1, 0, 1].
    """
    ciu_scores: dict[str, list[float]] = {}

    for record in records:
        spans = record.step_annotations
        if not spans:
            ciu_scores[record.sample_id] = []
            continue

        original_correct = 1.0 if record.is_correct else 0.0
        trace_text = record.full_reasoning_trace
        reference = record.reference_answer
        aliases = record.metadata.get("aliases", [])

        if not trace_text:
            ciu_scores[record.sample_id] = [0.0] * len(spans)
            continue

        scores: list[float] = []
        for ann in spans:
            masked_text = _mask_span(trace_text, ann.start_char, ann.end_char, mask_token)
            masked_answer = extract_answer(masked_text, answer_type=_detect_type(reference))
            masked_correct = 1.0 if match_answer(
                masked_answer, reference,
                aliases=aliases,
                answer_type=_detect_type(reference),
            ) else 0.0
            ciu = original_correct - masked_correct
            scores.append(ciu)

        ciu_scores[record.sample_id] = scores

    return ciu_scores


def compute_masking_ciu_normalized(
    records: list[OpenTraceRecord],
    mask_token: str = _MASK_TOKEN,
) -> dict[str, list[float]]:
    """Like ``compute_masking_ciu`` but normalizes scores to [-1, 1].

    Normalization: divide by max absolute CIU within each trace.
    If all CIU are zero, returns original scores (all zeros).
    """
    raw = compute_masking_ciu(records, mask_token)
    normalized: dict[str, list[float]] = {}
    for sid, scores in raw.items():
        abs_max = max((abs(s) for s in scores), default=1.0)
        if abs_max > 0:
            normalized[sid] = [s / abs_max for s in scores]
        else:
            normalized[sid] = scores
    return normalized


def _mask_span(
    text: str,
    start_char: int,
    end_char: int,
    mask_token: str,
) -> str:
    """Replace a character range in text with length-preserving mask tokens."""
    if start_char < 0 or end_char <= start_char:
        return text
    span_len = end_char - start_char
    mask_len = len(mask_token)
    if mask_len >= span_len:
        masked_part = mask_token[:span_len]
    else:
        repeats = span_len // mask_len
        remainder = span_len % mask_len
        masked_part = mask_token * repeats + mask_token[:remainder]
    return text[:start_char] + masked_part + text[end_char:]


def _detect_type(reference: str) -> str:
    """Detect answer type from reference: numeric vs free_text."""
    if re.search(r"^-?\d[\d,.]*\s*$", reference.strip()):
        return "numeric"
    return "free_text"


__all__ = [
    "compute_masking_ciu",
    "compute_masking_ciu_normalized",
]
