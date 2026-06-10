"""Gradient-based attribution baselines for step-level importance scoring.

Family A: Gradient Attribution
  - Gradient × Input (Saliency)
  - Integrated Gradients (approximation via Riemann sum)
  - Attention rollout (for transformer models)

Used as comparison baselines against SC-FMA in the step importance ranking task.

Note: These methods operate on token-level gradients and aggregate to step-level
scores, preserving the step-level evaluation framework compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GradientAttributionConfig:
    n_steps: int = 50
    baseline_value: float = 0.0
    normalize: bool = True


def gradient_input_scores(
    gradient_matrix: np.ndarray,
    input_embeddings: np.ndarray,
    step_boundaries: list[tuple[int, int]],
    normalize: bool = True,
) -> list[float]:
    n_tokens = gradient_matrix.shape[0]
    token_scores = np.abs(gradient_matrix * input_embeddings).sum(axis=1)

    step_scores: list[float] = []
    for start, end in step_boundaries:
        start = max(0, min(start, n_tokens - 1))
        end = max(start + 1, min(end, n_tokens))
        if start < end:
            step_scores.append(float(np.mean(token_scores[start:end])))
        else:
            step_scores.append(0.0)

    if normalize and len(step_scores) > 0:
        max_val = max(step_scores) if step_scores else 1.0
        if max_val > 0:
            step_scores = [s / max_val for s in step_scores]
    return step_scores


def integrated_gradients_scores(
    gradient_sequence: list[np.ndarray],
    input_embeddings: np.ndarray,
    baseline_embeddings: np.ndarray | None = None,
    step_boundaries: list[tuple[int, int]] | None = None,
    normalize: bool = True,
) -> list[float]:
    n_tokens = input_embeddings.shape[0]
    if baseline_embeddings is None:
        baseline_embeddings = np.zeros_like(input_embeddings)

    if not gradient_sequence:
        return []

    avg_grad = np.mean(np.stack(gradient_sequence), axis=0)
    diff = input_embeddings - baseline_embeddings
    token_scores = np.abs(avg_grad * diff).sum(axis=1)

    if step_boundaries is None:
        return [float(s) / max(float(token_scores.max()), 1e-10) if normalize else float(s)
                for s in token_scores]

    step_scores: list[float] = []
    for start, end in step_boundaries:
        start = max(0, min(start, n_tokens - 1))
        end = max(start + 1, min(end, n_tokens))
        step_scores.append(float(np.mean(token_scores[start:end])))

    if normalize and step_scores:
        max_val = max(step_scores) if step_scores and max(step_scores) > 0 else 1.0
        step_scores = [s / max_val for s in step_scores]
    return step_scores


def attention_rollout_scores(
    attention_weights: list[np.ndarray],
    step_boundaries: list[tuple[int, int]],
    normalize: bool = True,
) -> list[float]:
    if not attention_weights:
        return [1.0 / len(step_boundaries)] * len(step_boundaries) if step_boundaries else []

    rollout = np.eye(attention_weights[0].shape[-1])
    for layer_attn in attention_weights:
        attn = layer_attn.mean(axis=0) if layer_attn.ndim > 2 else layer_attn
        rollout = rollout @ attn

    n_tokens = rollout.shape[0]
    token_importance = rollout.sum(axis=0)
    token_importance = token_importance / (np.sum(token_importance) + 1e-10)

    step_scores: list[float] = []
    for start, end in step_boundaries:
        start = max(0, min(start, n_tokens - 1))
        end = max(start + 1, min(end, n_tokens))
        step_scores.append(float(np.mean(token_importance[start:end])))

    if normalize and step_scores:
        m = max(step_scores) if step_scores and max(step_scores) > 0 else 1.0
        step_scores = [s / m for s in step_scores]
    return step_scores


def compute_ci_from_attribution(
    scores: list[float],
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
) -> dict[str, float]:
    if len(scores) < 2:
        return {"mean": float(np.mean(scores)) if scores else 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    arr = np.array(scores)
    n = len(arr)
    boot_means = np.array([
        float(np.mean(arr[np.random.randint(0, n, n)]))
        for _ in range(n_bootstrap)
    ])
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "mean": float(np.mean(arr)),
        "ci_lower": float(np.percentile(boot_means, 100 * alpha)),
        "ci_upper": float(np.percentile(boot_means, 100 * (1 - alpha))),
    }
