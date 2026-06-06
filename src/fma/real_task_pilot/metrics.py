"""Exact, non-LLM scoring helpers for GSM8K and HotpotQA."""

from __future__ import annotations

import re
import string
from collections import Counter
from typing import Iterable


NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def normalize_gsm8k_answer(text: str) -> str:
    if "####" in text:
        text = text.split("####")[-1]
    numbers = NUMBER_RE.findall(text)
    if numbers:
        return numbers[-1].replace(",", "")
    return normalize_text(text)


def normalize_text(text: str) -> str:
    lowered = text.lower()
    no_punct = "".join(" " if char in string.punctuation else char for char in lowered)
    tokens = [token for token in no_punct.split() if token not in {"a", "an", "the"}]
    return " ".join(tokens)


def exact_match(prediction: str, reference: str, *, task_type: str = "hotpotqa") -> bool:
    if task_type == "gsm8k":
        return normalize_gsm8k_answer(prediction) == normalize_gsm8k_answer(reference)
    return normalize_text(prediction) == normalize_text(reference)


def alias_match(prediction: str, aliases: Iterable[str] | None) -> bool:
    normalized_prediction = normalize_text(prediction)
    return any(normalized_prediction == normalize_text(alias) for alias in aliases or [])


def normalized_token_f1(prediction: str, reference: str) -> float:
    pred_tokens = normalize_text(prediction).split()
    ref_tokens = normalize_text(reference).split()
    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0
    overlap = Counter(pred_tokens) & Counter(ref_tokens)
    common = sum(overlap.values())
    if common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall = common / len(ref_tokens)
    return float(2 * precision * recall / (precision + recall))


def score_answer(
    task_type: str,
    prediction: str,
    reference: str,
    aliases: Iterable[str] | None = None,
) -> dict[str, float | bool]:
    em = exact_match(prediction, reference, task_type=task_type)
    if task_type == "hotpotqa" and not em:
        em = alias_match(prediction, aliases)
    return {
        "exact_match": bool(em),
        "score": 1.0 if em else 0.0,
        "normalized_token_f1": normalized_token_f1(prediction, reference)
        if task_type == "hotpotqa"
        else (1.0 if em else 0.0),
    }
