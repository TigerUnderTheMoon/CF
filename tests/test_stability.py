from __future__ import annotations

import numpy as np
import pytest

from fma.eval.stability import StabilityAnalyzer, bounded_stability


def identity(scores: np.ndarray) -> np.ndarray:
    return scores


def mean_score(scores: np.ndarray) -> np.ndarray:
    return np.asarray([np.mean(scores)], dtype=float)


def test_stability_range() -> None:
    scores = np.asarray([0.2, 0.5, 0.8], dtype=float)
    stability = StabilityAnalyzer(noise_level=0.05, n_perturbations=10).compute_stability(scores, identity)
    assert 0.0 < stability <= 1.0


def test_bounded_stability_metric_range() -> None:
    stability = bounded_stability(np.asarray([0.0, 1.0, 2.0], dtype=float))
    assert 0.0 < stability <= 1.0


def test_zero_noise_perfect_stability() -> None:
    scores = np.asarray([0.2, 0.5, 0.8], dtype=float)
    stability = StabilityAnalyzer(noise_level=0.0, n_perturbations=10).compute_stability(scores, mean_score)
    assert stability == pytest.approx(1.0)


def test_high_noise_low_stability() -> None:
    scores = np.asarray([0.4, 0.6, 0.8], dtype=float)
    low_noise = StabilityAnalyzer(noise_level=0.01, n_perturbations=30).compute_stability(scores, mean_score)
    high_noise = StabilityAnalyzer(noise_level=1.0, n_perturbations=30).compute_stability(scores, mean_score)
    assert high_noise < low_noise


def test_n_perturbations_effect() -> None:
    scores = np.linspace(0.2, 1.0, 8)
    short_estimates = [
        StabilityAnalyzer(noise_level=0.4, n_perturbations=2, random_seed=seed).compute_stability(scores, mean_score)
        for seed in range(12)
    ]
    long_estimates = [
        StabilityAnalyzer(noise_level=0.4, n_perturbations=40, random_seed=seed).compute_stability(scores, mean_score)
        for seed in range(12)
    ]
    assert np.var(long_estimates) < np.var(short_estimates)
