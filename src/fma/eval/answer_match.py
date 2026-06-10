"""Unified answer matching for numeric and free-text answers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def normalize_answer(text: str) -> str:
    """Normalize an answer string for comparison."""
    t = text.strip()
    if "####" in t:
        t = t.split("####")[-1].strip()
    return t.lower().rstrip(".")


def extract_numeric(text: str) -> str:
    """Extract the last numeric value from text, normalizing commas."""
    numbers = _NUMBER_RE.findall(text)
    if not numbers:
        return ""
    return numbers[-1].replace(",", "")


def extract_answer(raw_text: str, answer_type: str = "auto") -> str:
    """Extract final answer from reasoning text.

    Args:
        raw_text: Full reasoning trace.
        answer_type: "auto", "numeric", or "free_text".
    """
    if answer_type == "auto":
        candidates = _NUMBER_RE.findall(raw_text)
        if candidates:
            return candidates[-1].replace(",", "")
        return raw_text.strip().split("\n")[-1].strip().rstrip(".")

    if answer_type == "numeric":
        return extract_numeric(raw_text)

    return raw_text.strip().split("\n")[-1].strip().rstrip(".")


def match_answer(
    predicted: str,
    reference: str,
    aliases: Sequence[str] = (),
    answer_type: str = "auto",
) -> bool:
    """Check if predicted answer matches reference.

    Args:
        predicted: Extracted predicted answer.
        reference: Ground truth answer.
        aliases: Acceptable alternative answers (for HotpotQA).
        answer_type: "auto", "numeric", or "free_text".
    """
    pred = normalize_answer(predicted)
    ref = normalize_answer(reference)

    if pred == ref:
        return True

    for alias in aliases:
        if normalize_answer(alias) == pred:
            return True

    if answer_type in ("auto", "numeric"):
        pred_num = extract_numeric(predicted)
        ref_num = extract_numeric(reference)
        if pred_num and ref_num and pred_num == ref_num:
            return True

    if answer_type in ("auto", "free_text"):
        alias_tokens = set(pred.split())
        ref_tokens = set(ref.split())
        if alias_tokens and ref_tokens:
            overlap = alias_tokens & ref_tokens
            if len(overlap) / len(ref_tokens) >= 0.7:
                return True
        sim = SequenceMatcher(None, pred, ref).ratio()
        if sim > 0.85:
            return True

    return False


__all__ = [
    "extract_answer",
    "extract_numeric",
    "match_answer",
    "normalize_answer",
]
