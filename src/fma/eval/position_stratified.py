"""Position-stratified evaluation for FMA vs baselines.

Breaks step evaluation into early/middle/late bins based on
relative step position, enabling disentanglement of position
confounding from actual intervention-based CIU.
"""

from __future__ import annotations

import json
from pathlib import Path

from fma.data.schema import OpenTraceRecord

POSITION_BINS = {
    "early": (0.0, 0.33),
    "middle": (0.33, 0.67),
    "late": (0.67, 1.0),
}


def compute_position_stratified_accuracy(
    records: list[OpenTraceRecord],
    fma_scores: dict[str, list[float]],
    keep_ratios: tuple[float, ...] = (0.25, 0.50, 0.75),
) -> dict[str, dict[str, dict[str, float]]]:
    """Compute FMA filtering accuracy stratified by step position.

    Returns:
        Dict of {position_bin: {keep_ratio: accuracy}}
    """
    bins: dict[str, dict[float, list[int]]] = {
        bin_name: {r: [] for r in keep_ratios}
        for bin_name in POSITION_BINS
    }

    for record in records:
        spans = record.step_annotations
        if not spans:
            continue
        sid = record.sample_id
        fma = fma_scores.get(sid, [])
        n = len(spans)
        if not fma or len(fma) != n:
            continue

        for keep_ratio in keep_ratios:
            n_keep = max(1, round(n * keep_ratio))
            indexed = list(enumerate(fma))
            indexed.sort(key=lambda x: x[1], reverse=True)
            kept = set(i for i, _ in indexed[:n_keep])

            for bin_name, (lo, hi) in POSITION_BINS.items():
                bin_kept = 0
                bin_total = 0
                for idx, _span in enumerate(spans):
                    pos = (idx / max(1, n - 1)) if n > 1 else 0.0
                    if lo <= pos < hi or (hi >= 1.0 and pos >= lo):
                        bin_total += 1
                        if idx in kept:
                            bin_kept += 1
                if bin_total > 0:
                    bins[bin_name][keep_ratio].append(
                        1 if bin_kept / bin_total >= 0.5 else 0
                    )

    result: dict[str, dict[str, dict[str, float]]] = {}
    for bin_name in POSITION_BINS:
        result[bin_name] = {}
        for ratio in keep_ratios:
            vals = bins[bin_name][ratio]
            result[bin_name][f"keep_{ratio:.2f}"] = (
                sum(vals) / len(vals) if vals else 0.0
            )

    return result


def compute_position_baseline_accuracy(
    records: list[OpenTraceRecord],
    keep_ratios: tuple[float, ...] = (0.25, 0.50, 0.75),
) -> dict[str, dict[str, float]]:
    """Compute accuracy when always keeping steps in a specific position bin.

    This is the "oracle" position-based baseline: if we knew
    which bin contains the answer, how well would we do?
    """
    bins: dict[str, dict[float, list[int]]] = {
        bin_name: {r: [] for r in keep_ratios}
        for bin_name in POSITION_BINS
    }

    for record in records:
        spans = record.step_annotations
        if not spans:
            continue
        n = len(spans)
        if n == 0:
            continue

        reference = record.reference_answer
        for bin_name, (lo, hi) in POSITION_BINS.items():
            bin_indices = []
            for idx in range(n):
                pos = idx / max(1, n - 1) if n > 1 else 0.0
                if lo <= pos < hi or (hi >= 1.0 and pos >= lo):
                    bin_indices.append(idx)

            if not bin_indices:
                continue

            from fma.eval.answer_match import extract_answer, match_answer

            for keep_ratio in keep_ratios:
                n_keep = max(1, round(len(bin_indices) * keep_ratio))
                kept = set(bin_indices[:n_keep])

                trace_text = record.full_reasoning_trace
                filtered_parts = []
                prev_end = 0
                for idx, span in enumerate(spans):
                    s = span.start_char
                    e = span.end_char
                    if s > prev_end:
                        filtered_parts.append(trace_text[prev_end:s])
                    if idx in kept:
                        filtered_parts.append(trace_text[s:e])
                    else:
                        span_len = max(0, e - s)
                        mask = "[REASONING_MASK]" + " " * max(0, span_len - len("[REASONING_MASK]"))
                        filtered_parts.append(mask)
                    prev_end = e
                if prev_end < len(trace_text):
                    filtered_parts.append(trace_text[prev_end:])
                filtered_text = "".join(filtered_parts)

                extracted = extract_answer(filtered_text)
                is_match = match_answer(extracted, reference, record.metadata.get("aliases", []))
                bins[bin_name][keep_ratio].append(1 if is_match else 0)

    result: dict[str, dict[str, float]] = {}
    for bin_name in POSITION_BINS:
        result[bin_name] = {}
        for ratio in keep_ratios:
            vals = bins[bin_name][ratio]
            result[bin_name][f"keep_{ratio:.2f}"] = (
                sum(vals) / len(vals) if vals else 0.0
            )

    return result


def write_position_report(
    fma_stratified: dict[str, dict[str, dict[str, float]]],
    baseline_stratified: dict[str, dict[str, float]],
    output_path: str | Path,
) -> Path:
    """Write position-stratified analysis report to JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fma_stratified": fma_stratified,
        "baseline_position": baseline_stratified,
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return output_path


__all__ = [
    "POSITION_BINS",
    "compute_position_baseline_accuracy",
    "compute_position_stratified_accuracy",
    "write_position_report",
]
