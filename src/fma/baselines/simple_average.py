"""Simple average baseline: element-wise mean of normalized CIU and necessity.

This baseline computes a straightforward unweighted combination of
intervention-based local utility (CIU) and structural necessity, then
normalizes to a probability simplex for step-importance ranking.

It is an independent baseline, not an SC-FMA input.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

EPSILON = 1e-10


def simple_average_baseline(
    ciu: Sequence[float],
    necessity: Sequence[float],
) -> list[float]:
    """Compute simplex-normalized weights from unweighted CIU + necessity mean.

    Args:
        ciu: Conditional interventional utility scores per step.
        necessity: Structural necessity scores per step.

    Returns:
        Probability-simplex weights (non-negative, sum to 1.0).
    """
    n = len(ciu)
    if n == 0:
        return []
    if n != len(necessity):
        raise ValueError(
            f"Length mismatch: ciu has {n} elements, necessity has "
            f"{len(necessity)} elements."
        )

    ciu_arr = np.asarray(ciu, dtype=float)
    nec_arr = np.asarray(necessity, dtype=float)

    # Normalize each vector independently to sum to 1
    ciu_total = np.sum(ciu_arr)
    nec_total = np.sum(nec_arr)

    ciu_norm = ciu_arr / max(ciu_total, EPSILON) if ciu_total > EPSILON else np.ones(n) / n
    nec_norm = nec_arr / max(nec_total, EPSILON) if nec_total > EPSILON else np.ones(n) / n

    # Element-wise mean
    mean_arr = (ciu_norm + nec_norm) / 2.0

    # Normalize to probability simplex
    total = np.sum(mean_arr)
    if total > EPSILON:
        weights = mean_arr / total
    else:
        weights = np.ones(n) / n

    return [float(w) for w in weights]
