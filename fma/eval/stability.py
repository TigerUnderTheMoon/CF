"""Stability under perturbation metrics for attribution scores."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


class StabilityAnalyzer:
    """Measure score consistency after small controlled perturbations."""

    def __init__(
        self,
        noise_level: float = 0.05,
        n_perturbations: int = 10,
        random_seed: int = 42,
    ):
        """
        noise_level: relative Gaussian noise std (0.05 = 5%)
        n_perturbations: number of perturbed copies to generate
        """
        if noise_level < 0.0:
            raise ValueError("noise_level must be non-negative.")
        if n_perturbations <= 0:
            raise ValueError("n_perturbations must be positive.")
        self.noise_level = float(noise_level)
        self.n_perturbations = int(n_perturbations)
        self.rng = np.random.default_rng(random_seed)

    def compute_stability(
        self,
        base_scores: np.ndarray,
        evaluator: Callable[[np.ndarray], np.ndarray],
    ) -> float:
        """
        Bounded stability of evaluator outputs under small perturbations.

        The metric is 1 / (1 + CV^2), where CV^2 is variance divided by
        mean^2 + epsilon across seeded perturbation outputs. It is bounded in
        (0, 1] for non-empty finite inputs.
        """
        scores = np.asarray(base_scores, dtype=float)
        if scores.size == 0:
            return float("nan")

        base_result = np.asarray(evaluator(scores), dtype=float)
        perturbation_results: list[np.ndarray] = [base_result]
        for _ in range(self.n_perturbations):
            noise = self.rng.normal(loc=0.0, scale=self.noise_level, size=scores.shape)
            perturbed_scores = scores * (1.0 + noise)
            perturbed_result = np.asarray(evaluator(perturbed_scores), dtype=float)
            perturbation_results.append(perturbed_result)

        stacked = np.asarray(perturbation_results, dtype=float)
        if not np.all(np.isfinite(stacked)):
            return float("nan")
        mean = np.mean(stacked, axis=0)
        variance = np.var(stacked, axis=0)
        normalized_variance = variance / (np.square(mean) + 1e-6)
        stability = 1.0 / (1.0 + normalized_variance)
        return float(np.mean(stability))


def bounded_stability(values: np.ndarray, epsilon: float = 1e-6) -> float:
    """Return 1 / (1 + CV^2) for a vector of scores."""
    scores = np.asarray(values, dtype=float)
    if scores.size == 0 or not np.all(np.isfinite(scores)):
        return float("nan")
    mean = float(np.mean(scores))
    variance = float(np.var(scores))
    normalized_variance = variance / (mean * mean + epsilon)
    return float(1.0 / (1.0 + normalized_variance))
