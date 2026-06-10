"""Downstream task evaluation for filtering experiments."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any

from fma.data.schema import OpenTraceRecord


@dataclass(frozen=True)
class FilteringResult:
    method_name: str
    keep_ratio: float
    kept_indices: tuple[int, ...]
    filtered_trace: str
    filtered_answer: str
    original_answer: str
    reference_answer: str
    is_correct_after: bool
    is_correct_before: bool
    sample_id: str


@dataclass
class FilteringConfig:
    keep_ratios: tuple[float, ...] = (0.25, 0.5, 0.75)
    n_trials: int = 1
    seed: int = 42
    answer_extraction: str = "last_number"


def filter_spans_by_scores(
    spans: list[dict[str, Any]],
    scores: list[float],
    keep_ratio: float,
    trace_text: str,
) -> tuple[tuple[int, ...], str]:
    """Keep top-scoring spans and reconstruct trace.

    Spans not in the top-K are replaced with ``[REASONING_MASK]``
    tokens of matching length, preserving positional structure.
    """
    if not spans or not scores:
        return tuple(), trace_text

    n_keep = max(1, round(len(spans) * keep_ratio))
    indexed_scores = list(enumerate(scores))
    indexed_scores.sort(key=lambda x: x[1], reverse=True)
    kept_indices = tuple(sorted(i for i, _ in indexed_scores[:n_keep]))

    return kept_indices, _reconstruct_trace(spans, kept_indices, trace_text)


def filter_spans_random(
    spans: list[dict[str, Any]],
    keep_ratio: float,
    trace_text: str,
    rng: random.Random,
) -> tuple[tuple[int, ...], str]:
    """Randomly keep spans at the given ratio."""
    if not spans:
        return tuple(), trace_text

    n_keep = max(1, round(len(spans) * keep_ratio))
    indices = list(range(len(spans)))
    rng.shuffle(indices)
    kept_indices = tuple(sorted(indices[:n_keep]))

    return kept_indices, _reconstruct_trace(spans, kept_indices, trace_text)


def _reconstruct_trace(
    spans: list[dict[str, Any]],
    kept_indices: tuple[int, ...],
    trace_text: str,
) -> str:
    """Reconstruct trace text, replacing non-kept spans with masks."""
    kept_set = set(kept_indices)
    parts: list[str] = []
    prev_end = 0

    sorted_spans = sorted(
        enumerate(spans),
        key=lambda x: int(x[1].get("start_char", 0)),
    )

    for span_idx, span in sorted_spans:
        start = int(span.get("start_char", 0))
        end = int(span.get("end_char", start + len(str(span.get("content", "")))))

        if start > prev_end:
            parts.append(trace_text[prev_end:start])

        if span_idx in kept_set:
            parts.append(trace_text[start:end])
        else:
            content_len = end - start
            parts.append("[REASONING_MASK]" + " " * max(0, content_len - len("[REASONING_MASK]")))

        prev_end = end

    if prev_end < len(trace_text):
        parts.append(trace_text[prev_end:])

    return "".join(parts)


def extract_answer(text: str, method: str = "last_number") -> str:
    """Extract a final answer from trace text."""
    import re

    if method == "last_number":
        numbers = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
        if numbers:
            return numbers[-1].replace(",", "")
        return ""

    if method == "final_answer_tag":
        match = re.search(r"[Ff]inal\s+[Aa]nswer\s*:\s*(.+?)(?:\n|$)", text)
        if match:
            return match.group(1).strip()
        return extract_answer(text, "last_number")

    return text.strip()[-50:]


def check_correctness(predicted: str, reference: str) -> bool:
    """Check if predicted answer matches reference."""
    import re

    pred_clean = predicted.strip().replace(",", "").replace(" ", "")
    ref_clean = reference.strip().replace(",", "").replace(" ", "")

    if pred_clean == ref_clean:
        return True

    pred_nums = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", predicted)
    ref_nums = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", reference)
    if pred_nums and ref_nums:
        return pred_nums[-1].replace(",", "") == ref_nums[-1].replace(",", "")

    return pred_clean.lower() == ref_clean.lower()


def evaluate_filtering(
    record: OpenTraceRecord,
    spans: list[dict[str, Any]],
    scores: list[float],
    method_name: str,
    config: FilteringConfig,
) -> list[FilteringResult]:
    """Evaluate one trace under all keep ratios for one scoring method."""
    results: list[FilteringResult] = []
    original_answer = extract_answer(record.full_reasoning_trace, config.answer_extraction)
    correct_before = check_correctness(original_answer, record.reference_answer)

    for keep_ratio in config.keep_ratios:
        if method_name == "random":
            for trial in range(config.n_trials):
                hash_input = (
                    f"{config.seed}:{record.sample_id}:{trial}"
                ).encode()
                hash_int = int(
                    hashlib.sha256(hash_input).hexdigest()[:8], 16
                )
                trial_rng = random.Random(hash_int)
                kept_indices, filtered_trace = filter_spans_random(
                    spans, keep_ratio, record.full_reasoning_trace, trial_rng
                )
                filtered_answer = extract_answer(filtered_trace, config.answer_extraction)
                correct_after = check_correctness(filtered_answer, record.reference_answer)
                results.append(
                    FilteringResult(
                        method_name=f"random_trial{trial}",
                        keep_ratio=keep_ratio,
                        kept_indices=kept_indices,
                        filtered_trace=filtered_trace,
                        filtered_answer=filtered_answer,
                        original_answer=original_answer,
                        reference_answer=record.reference_answer,
                        is_correct_after=correct_after,
                        is_correct_before=correct_before,
                        sample_id=record.sample_id,
                    )
                )
        else:
            kept_indices, filtered_trace = filter_spans_by_scores(
                spans, scores, keep_ratio, record.full_reasoning_trace
            )
            filtered_answer = extract_answer(filtered_trace, config.answer_extraction)
            correct_after = check_correctness(filtered_answer, record.reference_answer)
            results.append(
                FilteringResult(
                    method_name=method_name,
                    keep_ratio=keep_ratio,
                    kept_indices=kept_indices,
                    filtered_trace=filtered_trace,
                    filtered_answer=filtered_answer,
                    original_answer=original_answer,
                    reference_answer=record.reference_answer,
                    is_correct_after=correct_after,
                    is_correct_before=correct_before,
                    sample_id=record.sample_id,
                )
            )

    return results


__all__ = [
    "FilteringConfig",
    "FilteringResult",
    "check_correctness",
    "evaluate_filtering",
    "extract_answer",
    "filter_spans_by_scores",
    "filter_spans_random",
]
