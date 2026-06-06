"""Zero-inflation summaries for structural necessity diagnostics."""

from __future__ import annotations

import math
from typing import Any, Sequence


def zero_inflation_stats(
    attribution_scores: Sequence[float],
    structural_necessity: Sequence[float],
    zero_tolerance: float = 0.0,
) -> dict[str, Any]:
    """Summarize zero necessity and local-to-structural mismatch rates."""
    if len(attribution_scores) != len(structural_necessity):
        raise ValueError("score vectors must have the same length.")
    if zero_tolerance < 0.0:
        raise ValueError("zero_tolerance must be non-negative.")

    pairs = [
        (float(attribution), float(necessity))
        for attribution, necessity in zip(attribution_scores, structural_necessity)
        if math.isfinite(float(attribution)) and math.isfinite(float(necessity))
    ]
    sample_count = len(pairs)
    zero_count = sum(1 for _attribution, necessity in pairs if abs(necessity) <= zero_tolerance)
    positive_attribution_count = sum(1 for attribution, _necessity in pairs if attribution > 0.0)
    positive_necessity_count = sum(1 for _attribution, necessity in pairs if necessity > zero_tolerance)
    positive_attribution_zero_necessity_count = sum(
        1
        for attribution, necessity in pairs
        if attribution > 0.0 and abs(necessity) <= zero_tolerance
    )
    zero_attribution_positive_necessity_count = sum(
        1
        for attribution, necessity in pairs
        if attribution == 0.0 and necessity > zero_tolerance
    )
    both_positive_count = sum(
        1 for attribution, necessity in pairs if attribution > 0.0 and necessity > zero_tolerance
    )
    both_zero_count = sum(
        1 for attribution, necessity in pairs if attribution == 0.0 and abs(necessity) <= zero_tolerance
    )

    return {
        "num_samples": sample_count,
        "zero_tolerance": zero_tolerance,
        "zero_structural_necessity_count": zero_count,
        "zero_structural_necessity_fraction": _fraction(zero_count, sample_count),
        "positive_attribution_count": positive_attribution_count,
        "positive_attribution_fraction": _fraction(positive_attribution_count, sample_count),
        "positive_structural_necessity_count": positive_necessity_count,
        "positive_structural_necessity_fraction": _fraction(positive_necessity_count, sample_count),
        "positive_attribution_zero_necessity_count": positive_attribution_zero_necessity_count,
        "positive_attribution_zero_necessity_fraction": _fraction(
            positive_attribution_zero_necessity_count,
            sample_count,
        ),
        "zero_attribution_positive_necessity_count": zero_attribution_positive_necessity_count,
        "zero_attribution_positive_necessity_fraction": _fraction(
            zero_attribution_positive_necessity_count,
            sample_count,
        ),
        "both_positive_count": both_positive_count,
        "both_positive_fraction": _fraction(both_positive_count, sample_count),
        "both_zero_count": both_zero_count,
        "both_zero_fraction": _fraction(both_zero_count, sample_count),
    }


def _fraction(count: int, total: int) -> float:
    return float(count / total) if total else 0.0


__all__ = ["zero_inflation_stats"]
