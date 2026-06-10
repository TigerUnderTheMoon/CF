"""Tests for baseline families: gradient attribution, Shapley, surprisal, oracle."""

from __future__ import annotations

import numpy as np
import pytest

from fma.baselines.gradient_attribution import (
    GradientAttributionConfig,
    attention_rollout_scores,
    compute_ci_from_attribution,
    gradient_input_scores,
    integrated_gradients_scores,
)
from fma.baselines.oracle_baselines import (
    compute_oracle_step_scores,
    linear_oracle_ensemble,
    load_oracle_labels,
)
from fma.baselines.shapley import (
    ShapleyConfig,
    compute_shapley_step_scores,
    shapley_value_permutation,
)
from fma.baselines.surprisal_baselines import (
    conditional_entropy_scores,
    entropic_step_scores,
    surprisal_step_scores,
)


class TestGradientAttribution:
    def test_gradient_input_normalizes(self):
        n, d = 10, 4
        grad = np.random.randn(n, d)
        emb = np.random.randn(n, d)
        boundaries = [(0, 3), (3, 6), (6, 10)]
        scores = gradient_input_scores(grad, emb, boundaries)
        assert len(scores) == 3
        assert all(s >= 0 for s in scores)
        assert abs(max(scores) - 1.0) < 1e-6 or max(scores) == 0.0

    def test_integrated_gradients_empty(self):
        scores = integrated_gradients_scores([], np.zeros((5, 4)),
                                              step_boundaries=[(0, 2), (2, 5)])
        assert scores == []

    def test_integrated_gradients_normalizes(self):
        n, d = 6, 3
        grads = [np.random.randn(n, d) for _ in range(5)]
        emb = np.random.randn(n, d)
        boundaries = [(0, 3), (3, 6)]
        scores = integrated_gradients_scores(grads, emb, step_boundaries=boundaries)
        assert len(scores) == 2
        assert all(s >= 0 for s in scores)

    def test_attention_rollout_empty(self):
        scores = attention_rollout_scores([], [(0, 2)])
        assert len(scores) == 1

    def test_attention_rollout_normalizes(self):
        attn = [np.random.rand(2, 5, 5) for _ in range(3)]
        boundaries = [(0, 2), (2, 5)]
        scores = attention_rollout_scores(attn, boundaries)
        assert len(scores) == 2
        assert all(s >= 0 for s in scores)
        assert abs(max(scores) - 1.0) < 1e-6

    def test_ci_from_attribution(self):
        scores = [0.1, 0.2, 0.3, 0.4, 0.5]
        ci = compute_ci_from_attribution(scores, n_bootstrap=500)
        assert "mean" in ci
        assert "ci_lower" in ci
        assert "ci_upper" in ci
        assert ci["ci_lower"] <= ci["mean"] <= ci["ci_upper"]

    def test_ci_single_value(self):
        ci = compute_ci_from_attribution([0.5], n_bootstrap=100)
        assert ci["mean"] == 0.5


class TestShapley:
    def test_shapley_basic(self):
        step_ciu = [0.9, 0.7, 0.3, 0.1]
        config = ShapleyConfig(n_samples=100, seed=42)
        scores = compute_shapley_step_scores(step_ciu, config)
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6
        assert all(s >= 0 for s in scores)

    def test_shapley_single_step(self):
        scores = compute_shapley_step_scores([0.5])
        assert len(scores) == 1
        assert abs(scores[0] - 1.0) < 1e-6

    def test_shapley_empty(self):
        scores = compute_shapley_step_scores([])
        assert scores == []

    def test_shapley_permutation(self):
        step_scores = [0.8, 0.6, 0.4, 0.2]
        scores = shapley_value_permutation(step_scores, n_permutations=50, seed=42)
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6

    def test_shapley_antithetic(self):
        step_ciu = [0.9, 0.5, 0.1]
        config_anti = ShapleyConfig(n_samples=50, seed=42, use_antithetic=True)
        config_no = ShapleyConfig(n_samples=50, seed=42, use_antithetic=False)
        s_anti = compute_shapley_step_scores(step_ciu, config_anti)
        s_no = compute_shapley_step_scores(step_ciu, config_no)
        assert len(s_anti) == 3
        assert len(s_no) == 3


class TestSurprisal:
    def test_surprisal_basic(self):
        logprobs = [-0.1, -0.5, -1.0, -2.0,
                      -0.2, -0.3, -0.8,
                      -1.5, -2.5, -0.1]
        boundaries = [(0, 4), (4, 7), (7, 10)]
        scores = surprisal_step_scores(logprobs, boundaries)
        assert len(scores) == 3
        assert all(s >= 0 for s in scores)

    def test_entropic_basic(self):
        entropies = [0.1, 0.3, 0.5, 0.2, 0.1,
                      0.8, 1.0, 0.9,
                      2.0, 1.5, 0.5]
        boundaries = [(0, 5), (5, 8), (8, 11)]
        scores = entropic_step_scores(entropies, boundaries)
        assert len(scores) == 3

    def test_conditional_entropy(self):
        logprobs = [-0.2] * 10
        answer_lp = -3.0
        boundaries = [(0, 5), (5, 10)]
        scores = conditional_entropy_scores(logprobs, answer_lp, boundaries)
        assert len(scores) == 2


class TestOracle:
    def test_oracle_step_scores(self):
        correctness = [True, False, True, True, False]
        scores = compute_oracle_step_scores(correctness)
        assert len(scores) == 5
        assert abs(sum(scores) - 1.0) < 1e-6

    def test_oracle_all_false(self):
        correctness = [False, False, False]
        scores = compute_oracle_step_scores(correctness)
        assert len(scores) == 3
        assert abs(sum(scores) - 1.0) < 0.01

    def test_load_oracle_labels(self):
        records = [
            {"id": "1", "ground_truth_importance": 0.8},
            {"id": "2", "ground_truth_importance": 0.3},
        ]
        labels = load_oracle_labels(records)
        assert labels == [0.8, 0.3]

    def test_linear_ensemble(self):
        s1 = [0.5, 0.3, 0.2]
        s2 = [0.4, 0.4, 0.2]
        s3 = [0.6, 0.2, 0.2]
        ensemble = linear_oracle_ensemble([s1, s2, s3])
        assert len(ensemble) == 3
        assert abs(sum(ensemble) - 1.0) < 1e-6
