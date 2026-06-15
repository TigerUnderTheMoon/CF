"""Oracle and ground-truth baselines for step importance ranking.

Family F: Oracle / Upper Bound
  - Load ground-truth step labels from annotated datasets (PRM800K, ProcessBench)
  - Compute oracle step scores from correctness deltas
  - Provides ceiling performance for method comparison
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def load_oracle_labels(
    records: list[dict[str, Any]],
    label_key: str = "ground_truth_importance",
    step_scores_key: str = "step_scores",
) -> list[float]:
    all_scores: list[float] = []
    for record in records:
        if label_key in record and record[label_key] is not None:
            all_scores.append(float(record[label_key]))
        elif step_scores_key in record:
            scores = record[step_scores_key]
            if isinstance(scores, list):
                all_scores.extend([float(s) for s in scores])
    return all_scores


def compute_oracle_step_scores(
    step_correctness: list[bool],
    normalize: bool = True,
) -> list[float]:
    n = len(step_correctness)
    if n == 0:
        return []

    scores = [1.0 if c else 0.0 for c in step_correctness]
    if normalize and sum(scores) > 0:
        total = sum(scores)
        scores = [s / total for s in scores]
    elif normalize:
        scores = [1.0 / n] * n if n > 0 else []

    return scores


def linear_oracle_ensemble(
    step_scores_list: list[list[float]],
    weights: list[float] | None = None,
    normalize: bool = True,
) -> list[float]:
    if not step_scores_list:
        return []

    n = len(step_scores_list[0])
    if weights is None:
        weights = [1.0 / len(step_scores_list)] * len(step_scores_list)

    result = np.zeros(n)
    for scores, w in zip(step_scores_list, weights):
        arr = np.array(scores)
        result += w * arr

    if normalize:
        total = np.sum(np.abs(result))
        if total > 1e-10:
            result = result / total
        else:
            result = np.ones(n) / n

    return [float(v) for v in result]


def _count_reasoning_keywords(text: str) -> int:
    reasoning_keywords = {
        "therefore", "hence", "thus", "since", "because", "so",
        "implies", "conclude", "deduce", "infer", "assume",
        "suppose", "given", "let", "consider", "observe",
        "note", "recall", "follows", "equivalent", "respect",
    }
    lowered = text.lower()
    return sum(1 for kw in reasoning_keywords if kw in lowered)


def _count_complexity(text: str) -> int:
    import re
    numeric_count = len(re.findall(r"\b\d+(?:\.\d+)?\b", text))
    equation_count = len(re.findall(r"[=<>+\-*/^]{2,}", text))
    equation_count += len(re.findall(r"\\(?:frac|sqrt|sum|prod|int)", text))
    return numeric_count + equation_count


def _type_token_ratio(text: str) -> float:
    tokens = text.lower().split()
    if len(tokens) == 0:
        return 0.0
    return len(set(tokens)) / len(tokens)


def compute_independent_oracle(
    step_texts: list[str] | None = None,
    num_steps: int | None = None,
    *,
    seed: int | None = None,
    normalize: bool = True,
) -> np.ndarray:
    """Compute oracle step scores using features independent of SCU inputs.

    This oracle is deliberately constructed to avoid isomorphism with the
    SCU objective.  SCU operates on CIU (c), necessity (n), and the
    redundancy matrix (R) / bottleneck indicators.  The independent oracle
    uses NONE of those inputs:

    - **step_correctness** is sampled from a logistic model over *depth*
      (reasoning keyword count) and *complexity* (numeric + equation
      tokens), which are unrelated to CIU or necessity.
    - **lexical_diversity** is the type-token ratio of step text, a
      surface-level statistic that has no overlap with the redundancy
      matrix R.
    - **position_value** is a smooth sinusoidal curve peaking at
      mid-trace, independent of necessity measurements.

    Formula::

        y_i = 0.5 * step_correctness_i
            + 0.3 * lexical_diversity_i
            + 0.2 * position_value_i

    where::

        step_correctness_i ~ Bernoulli(logistic(0.3 * depth_i
                                         + 0.2 * complexity_i))

    If *step_texts* is ``None`` (texts unavailable), the function falls
    back to uniform scores and emits a warning — it does NOT fall back to
    the SCU-isomorphic formula.

    Args:
        step_texts: List of step text strings.  Required for the
            independent oracle; if ``None``, a uniform fallback is used.
        num_steps: Number of steps (used only when *step_texts* is
            ``None`` to determine output length).  Ignored when
            *step_texts* is provided.
        seed: Optional RNG seed for reproducibility of the Bernoulli
            sampling.
        normalize: If ``True``, normalize scores to sum to 1.

    Returns:
        1-D numpy array of oracle scores, length equal to the number of
        steps.  Normalized to sum to 1 when *normalize* is ``True``.
    """
    import logging
    import warnings

    logger = logging.getLogger(__name__)

    if step_texts is None:
        n = num_steps if num_steps is not None else 0
        if n == 0:
            return np.array([], dtype=float)
        warnings.warn(
            "step_texts unavailable for independent oracle; "
            "falling back to uniform scores. This is NOT the "
            "SCU-isomorphic formula.",
            stacklevel=2,
        )
        logger.warning(
            "compute_independent_oracle: step_texts is None, "
            "returning uniform scores (not SCU-isomorphic fallback)"
        )
        uniform = np.ones(n, dtype=float)
        if normalize:
            uniform /= uniform.sum()
        return uniform

    k = len(step_texts)
    if k == 0:
        return np.array([], dtype=float)

    rng = np.random.default_rng(seed)

    correctness = np.zeros(k, dtype=float)
    for i, text in enumerate(step_texts):
        depth_i = _count_reasoning_keywords(text)
        complexity_i = _count_complexity(text)
        logit = 0.3 * depth_i + 0.2 * complexity_i
        prob = 1.0 / (1.0 + math.exp(-logit))
        correctness[i] = float(rng.binomial(1, prob))

    lexical_diversity = np.array(
        [_type_token_ratio(text) for text in step_texts], dtype=float
    )

    position_value = np.array(
        [math.sin(math.pi * (i + 1) / k) for i in range(k)], dtype=float
    )

    raw = 0.5 * correctness + 0.3 * lexical_diversity + 0.2 * position_value

    if normalize:
        total = raw.sum()
        if total > 1e-10:
            raw = raw / total
        else:
            raw = np.ones(k, dtype=float) / k

    return raw
