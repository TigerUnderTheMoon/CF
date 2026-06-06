"""API replay request construction and Delta U scoring."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .metrics import score_answer
from .parsing import extract_reflection_spans, proxy_token_count


def build_replay_prefix(
    record: Mapping[str, Any],
    *,
    span_index: int,
    mask_token: str = "[REASONING_MASK]",
) -> dict[str, Any]:
    """Build a no-leakage replay prefix ending at the masked target span."""

    trace = str(record.get("observable_trace") or record.get("reasoning_trace") or "")
    spans = record.get("reflection_spans") or extract_reflection_spans(trace)
    if not isinstance(spans, list) or span_index >= len(spans):
        raise ValueError(f"span_index={span_index} is unavailable for sample_id={record.get('sample_id')!r}")
    span = spans[span_index]
    start = int(span["start_char"])
    end = int(span["end_char"])
    content_start = int(span["content_start_char"])
    content_end = int(span["content_end_char"])
    original_content = trace[content_start:content_end]
    original_tokens = proxy_token_count(original_content)
    mask_payload = " ".join([mask_token] * max(1, original_tokens))
    masked_span = trace[start:content_start] + mask_payload + trace[content_end:end]
    observable_prefix = trace[:start] + masked_span
    original_prefix = trace[:end]
    prefix_token_delta = proxy_token_count(observable_prefix) - proxy_token_count(original_prefix)
    return {
        "sample_id": record.get("sample_id"),
        "task_id": record.get("task_id"),
        "task_type": record.get("task_type"),
        "question": record.get("question"),
        "reference_answer": record.get("reference_answer"),
        "aliases": record.get("aliases", []),
        "span_index": span_index,
        "observable_prefix": observable_prefix,
        "target_span": span,
        "target_original_token_count": original_tokens,
        "target_mask_token_count": proxy_token_count(mask_payload),
        "prefix_token_delta": prefix_token_delta,
        "token_preservation_status": "proxy_exact" if prefix_token_delta == 0 else "approximate",
        "post_target_leakage_detected": False,
        "intervention_type": "api_length_preserving_masked_prefix",
    }


def compute_delta_u(
    original_record: Mapping[str, Any],
    intervened_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute Delta U from exact-match task scores."""

    task_type = str(original_record.get("task_type") or intervened_record.get("task_type") or "")
    reference = str(original_record.get("reference_answer") or intervened_record.get("reference_answer") or "")
    aliases = original_record.get("aliases") or intervened_record.get("aliases") or []
    original_answer = str(original_record.get("final_answer") or "")
    intervened_answer = str(intervened_record.get("final_answer") or "")
    original_score = float(score_answer(task_type, original_answer, reference, aliases)["score"])
    intervened_score = float(score_answer(task_type, intervened_answer, reference, aliases)["score"])
    return {
        "sample_id": original_record.get("sample_id"),
        "task_type": task_type,
        "original_score": original_score,
        "intervened_score": intervened_score,
        "delta_u": original_score - intervened_score,
        "metric": "exact_match",
    }


def aggregate_delta_u_by_span(
    original_records: Sequence[Mapping[str, Any]],
    intervened_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate repeated replay outcomes into one Delta U row per span."""

    original_by_id = {str(record.get("sample_id")): record for record in original_records}
    grouped: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for intervened in intervened_records:
        if intervened.get("status") not in {None, "success", "replayed"}:
            continue
        sample_id = str(intervened.get("sample_id") or "")
        if not sample_id or sample_id not in original_by_id or "span_index" not in intervened:
            continue
        grouped[(sample_id, int(intervened.get("span_index", 0) or 0))].append(intervened)

    rows = []
    for (sample_id, span_index), repeats in sorted(grouped.items()):
        original = original_by_id[sample_id]
        task_type = str(original.get("task_type") or "")
        reference = str(original.get("reference_answer") or "")
        aliases = original.get("aliases") or []
        original_score = float(
            score_answer(task_type, str(original.get("final_answer") or ""), reference, aliases)["score"]
        )
        intervened_scores = [
            float(
                score_answer(
                    task_type,
                    str(intervened.get("final_answer") or ""),
                    reference,
                    aliases,
                )["score"]
            )
            for intervened in repeats
        ]
        intervened_mean = sum(intervened_scores) / len(intervened_scores)
        rows.append(
            {
                "sample_id": sample_id,
                "task_type": task_type,
                "span_index": span_index,
                "repeat_count": len(repeats),
                "successful_repeats": len(intervened_scores),
                "original_score": original_score,
                "intervened_mean_score": intervened_mean,
                "delta_u": original_score - intervened_mean,
                "metric": "exact_match",
            }
        )
    return rows


def missing_replay_jobs(
    prefixes: Sequence[Mapping[str, Any]],
    existing_rows: Sequence[Mapping[str, Any]],
    *,
    repeats: int,
) -> list[dict[str, Any]]:
    """Return replay jobs not already completed by `(sample_id, span_index, repeat_index)`."""

    completed = {
        _replay_job_key(row)
        for row in existing_rows
        if row.get("status") in {"success", "replayed"}
    }
    jobs = []
    for prefix in prefixes:
        sample_id = str(prefix.get("sample_id") or "")
        span_index = int(prefix.get("span_index", 0) or 0)
        for repeat_index in range(repeats):
            key = (sample_id, span_index, repeat_index)
            if key in completed:
                continue
            jobs.append({**dict(prefix), "repeat_index": repeat_index})
    return jobs


def _replay_job_key(row: Mapping[str, Any]) -> tuple[str, int, int]:
    return (
        str(row.get("sample_id") or ""),
        int(row.get("span_index", 0) or 0),
        int(row.get("repeat_index", 0) or 0),
    )


__all__ = [
    "aggregate_delta_u_by_span",
    "build_replay_prefix",
    "compute_delta_u",
    "missing_replay_jobs",
]
