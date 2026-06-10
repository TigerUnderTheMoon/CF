"""Step/token-level PRM score extraction and aggregation."""

from __future__ import annotations

import re
from typing import Any

from .registry import PRMModelSpec

_TOKEN_RE = re.compile(r"\S+")


def aggregate_step_scores(
    token_scores: list[float],
    step_boundaries: list[tuple[int, int]],
    method: str = "mean",
) -> list[float]:
    """Aggregate token-level PRM scores into step-level scores.

    Args:
        token_scores: One score per token in the trace.
        step_boundaries: List of (start_token, end_token) for each step.
        method: Aggregation method: ``"mean"``, ``"min"``, ``"last"``.

    Returns:
        List of aggregated scores, one per step.
    """
    step_scores: list[float] = []
    for start, end in step_boundaries:
        if start >= len(token_scores):
            step_scores.append(0.0)
            continue
        end = min(end, len(token_scores))
        segment = token_scores[start:end]
        if not segment:
            step_scores.append(0.0)
            continue

        if method == "mean":
            step_scores.append(sum(segment) / len(segment))
        elif method == "min":
            step_scores.append(min(segment))
        elif method == "last":
            step_scores.append(segment[-1])
        else:
            raise ValueError(f"Unknown aggregation method: {method!r}")

    return step_scores


def extract_step_boundaries_from_spans(
    spans: list[dict[str, Any]],
) -> list[tuple[int, int]]:
    """Extract (start_token, end_token) boundaries from span dicts."""
    boundaries: list[tuple[int, int]] = []
    for span in spans:
        start = int(span.get("start_token", 0))
        end = int(span.get("end_token", start + 1))
        boundaries.append((start, end))
    return boundaries


def format_prm_input(
    question: str,
    steps: list[str],
    spec: PRMModelSpec,
) -> str:
    """Format a question + steps into the input string expected by a PRM model.

    Each PRM model has its own expected input format (step separator tokens,
    special prefix/suffix, etc.).
    """
    sep = spec.step_separator
    if spec.model_name.startswith("Qwen2.5-Math-PRM"):
        joined = sep.join(steps)
        return f"{question} {sep} {joined}"
    if spec.model_name == "Math-Shepherd":
        joined = sep.join(steps)
        return f"{question} {joined}"
    return f"{question}\n" + "\n".join(steps)


def normalize_prm_scores(
    raw_scores: list[float],
    method: str = "sigmoid",
) -> list[float]:
    """Normalize raw PRM output scores to [0, 1].

    Args:
        raw_scores: Raw model output scores (can be any range).
        method: Normalization method:
            - ``"sigmoid"``: 1 / (1 + exp(-x))
            - ``"minmax"``: Scale to [0, 1] using observed min/max
            - ``"clip"``: Clip to [0, 1] (assumes already calibrated)
    """
    if not raw_scores:
        return []

    if method == "sigmoid":
        import math

        return [1.0 / (1.0 + math.exp(-s)) for s in raw_scores]

    if method == "minmax":
        min_s = min(raw_scores)
        max_s = max(raw_scores)
        if max_s == min_s:
            return [0.5] * len(raw_scores)
        return [(s - min_s) / (max_s - min_s) for s in raw_scores]

    if method == "clip":
        return [max(0.0, min(1.0, s)) for s in raw_scores]

    raise ValueError(f"Unknown normalization method: {method!r}")


def length_calibrate_scores(
    scores: list[float],
    step_token_counts: list[int],
    alpha: float = 0.1,
) -> list[float]:
    """Apply length-based calibration to PRM scores.

    Longer steps tend to receive higher cumulative scores.  This divides
    each step's score by its token count raised to ``alpha``.
    """
    if len(scores) != len(step_token_counts):
        raise ValueError("scores and step_token_counts must have equal length")

    calibrated: list[float] = []
    for score, count in zip(scores, step_token_counts, strict=False):
        if count <= 0:
            calibrated.append(score)
        else:
            calibrated.append(score / (count ** alpha))
    return calibrated


__all__ = [
    "aggregate_step_scores",
    "extract_step_boundaries_from_spans",
    "format_prm_input",
    "length_calibrate_scores",
    "normalize_prm_scores",
]
