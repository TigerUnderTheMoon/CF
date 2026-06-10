"""Surprisal and entropy-based baseline method for step importance.

Family E: Information-Theoretic
  - Token surprisal: -log p(token)
  - Step-level entropy: average token surprisal within step boundaries
  - Conditional entropy with answer: mutual information proxy
"""

from __future__ import annotations

import math

import numpy as np


def surprisal_step_scores(
    token_logprobs: list[float],
    step_boundaries: list[tuple[int, int]],
    normalize: bool = True,
) -> list[float]:
    n_tokens = len(token_logprobs)
    token_surprisal = [-float(lp) for lp in token_logprobs]

    step_scores: list[float] = []
    for start, end in step_boundaries:
        start = max(0, min(start, n_tokens - 1))
        end = max(start + 1, min(end, n_tokens))
        if start < end:
            step_scores.append(float(np.mean(token_surprisal[start:end])))
        else:
            step_scores.append(0.0)

    if normalize and step_scores:
        max_val = max(step_scores) if step_scores and max(step_scores) > 0 else 1.0
        if max_val > 1e-10:
            step_scores = [s / max_val for s in step_scores]
    return step_scores


def entropic_step_scores(
    token_entropies: list[float],
    step_boundaries: list[tuple[int, int]],
    normalize: bool = True,
) -> list[float]:
    n_tokens = len(token_entropies)

    step_scores: list[float] = []
    for start, end in step_boundaries:
        start = max(0, min(start, n_tokens - 1))
        end = max(start + 1, min(end, n_tokens))
        if start < end:
            step_scores.append(float(np.mean(token_entropies[start:end])))
        else:
            step_scores.append(0.0)

    if normalize and step_scores:
        max_val = max(step_scores) if step_scores and max(step_scores) > 0 else 1.0
        if max_val > 1e-10:
            step_scores = [s / max_val for s in step_scores]
    return step_scores


def conditional_entropy_scores(
    token_logprobs: list[float],
    answer_logprob: float,
    step_boundaries: list[tuple[int, int]],
    normalize: bool = True,
) -> list[float]:
    base_scores = surprisal_step_scores(token_logprobs, step_boundaries, normalize=False)
    joint = [-float(lp) for lp in token_logprobs]
    cond_info = float(np.mean(joint)) + float(answer_logprob) if answer_logprob < 0 else float(np.mean(joint))

    step_scores = [s * abs(cond_info) for s in base_scores]

    if normalize and step_scores:
        max_val = max(step_scores) if step_scores and max(step_scores) > 0 else 1.0
        if max_val > 1e-10:
            step_scores = [s / max_val for s in step_scores]
    return step_scores
