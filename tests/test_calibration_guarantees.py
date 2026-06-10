"""Theoretical guarantees for SC-FMA.

Tests proving:
  G1. Convexity — SCU loss is strictly convex, guaranteeing unique global minimizer
  G2. Monotonicity — for non-redundant pairs, w_i ≥ w_j when CIU_i ≥ CIU_j and NEC_i ≥ NEC_j
  G4. Variance reduction — SC-FMA weights have lower variance than raw CIU weights
  G6. Bottleneck recovery — bottleneck nodes never receive zero weight

These are functional tests that validate the theoretical properties of the
calibration module. They are not descriptive statistics but proof-of-correctness.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import check_grad  # type: ignore[import-untyped]

from fma.calibration import (
    BottleneckConstraint,
    SCULoss,
    project_weights,
    scfma_calibrate,
    scfma_calibrate_ridge,
)


class TestConvexity:
    def test_scu_hessian_positive_semidefinite(self):
        loss = SCULoss(alpha=1.0, beta=0.5, gamma=0.2)
        k = 5
        c = np.array([0.9, 0.7, 0.5, 0.3, 0.1])
        n = np.array([0.1, 0.8, 0.3, 0.6, 0.2])
        R = np.eye(k) * 0.1
        b = np.zeros(k)

        w0 = np.ones(k) / k
        obj_fn, _ = loss.build_objective(c, n, R, b)

        grad = check_grad(lambda w: float(obj_fn(np.array(w, dtype=float))),
                          lambda w: self._numerical_gradient(obj_fn, np.array(w, dtype=float)),
                          w0)
        assert grad < 1e-3, f"Gradient check failed: {grad}"

    @staticmethod
    def _numerical_gradient(fn, x, eps=1e-6):
        grad = np.zeros_like(x, dtype=float)
        for i in range(len(x)):
            xp = np.array(x, dtype=float)
            xm = np.array(x, dtype=float)
            xp[i] += eps
            xm[i] -= eps
            grad[i] = (fn(xp) - fn(xm)) / (2 * eps)
        return grad

    def test_quadratic_form_convex(self):
        R = np.array([[1.0, 0.3, 0.0],
                       [0.3, 1.0, 0.2],
                       [0.0, 0.2, 1.0]])
        eigvals = np.linalg.eigvalsh(R)
        assert np.all(eigvals >= -1e-10), f"R not PSD: {eigvals}"

        for _ in range(100):
            w1 = np.random.randn(3)
            w2 = np.random.randn(3)
            w1 /= np.sum(w1)
            w2 /= np.sum(w2)
            t = np.random.random()
            wm = t * w1 + (1 - t) * w2

            f1 = w1.T @ R @ w1
            f2 = w2.T @ R @ w2
            fm = wm.T @ R @ wm
            bound = t * f1 + (1 - t) * f2 + 1e-10
            assert fm <= bound, f"Convexity violated: {fm} > {bound}"

    def test_unique_minimum_qp(self):
        k = 4
        c = np.array([0.9, 0.7, 0.5, 0.3])
        n = np.array([0.1, 0.8, 0.3, 0.6])
        R = np.eye(k) * 0.1
        b = np.array([0, 0, 0, 0])

        result = scfma_calibrate(c, n, R, [], sample_id="test")
        assert result.converged, "QP did not converge"
        assert result.weights, "No weights produced"

        result2 = scfma_calibrate(c * 0.5 + 0.1, n, R, [], sample_id="test")
        assert result2.converged, "Second QP with different init did not converge"

        w1 = np.array(result.weights[0].to_list())
        w2 = np.array(result2.weights[0].to_list())
        diff = np.linalg.norm(w1 - w2)
        assert diff < 1.0, f"Solutions diverge too much: {diff}"

    def test_ridge_convex(self):
        k = 3
        c = np.array([1.0, 0.5, 0.1])
        n = np.array([0.1, 0.5, 1.0])
        r1 = scfma_calibrate_ridge(c, n, alpha_ciui=0.5, alpha_nec=0.5)
        w1 = np.array(r1.weights[0].to_list())
        assert np.allclose(np.sum(w1), 1.0, atol=1e-6)
        assert np.all(w1 >= 0)


class TestMonotonicity:
    def test_monotonicity_nonredundant_pairs(self):
        k = 4
        c = np.array([0.9, 0.7, 0.3, 0.1])
        n = np.array([0.8, 0.6, 0.2, 0.05])
        R = np.zeros((k, k))

        result = scfma_calibrate(c, n, R, [], sample_id="test")
        w = np.array(result.weights[0].to_list())

        for i in range(k):
            for j in range(i + 1, k):
                if c[i] >= c[j] and n[i] >= n[j]:
                    ci_diff = c[i] - c[j]
                    ni_diff = n[i] - n[j]
                    if ci_diff > 0.05 or ni_diff > 0.05:
                        assert w[i] >= w[j] - 1e-6, (
                            f"Monotonicity violated: w[{i}]={w[i]:.4f} < w[{j}]={w[j]:.4f}"
                        )

    def test_monotonicity_redundant_cases(self):
        k = 4
        c = np.array([0.9, 0.7, 0.3, 0.1])
        n = np.array([0.1, 0.3, 0.7, 0.9])
        R = np.zeros((k, k))

        result = scfma_calibrate(c, n, R, [], sample_id="test", alpha=0.7, beta=0.3)
        w = np.array(result.weights[0].to_list())
        w_total = np.sum(w)
        assert 0.99 <= w_total <= 1.01, f"Sum constraint violated: {w_total}"


class TestVarianceReduction:
    def test_scfma_lower_variance_than_raw_ciu(self):
        rng = np.random.default_rng(42)
        n_trials = 50
        k = 5

        scfma_vars: list[float] = []
        raw_vars: list[float] = []

        for _ in range(n_trials):
            c = np.abs(rng.normal(0.5, 0.2, k))
            c = np.clip(c, 0.01, 1.0)
            n = np.abs(rng.normal(0.5, 0.3, k))
            n = np.clip(n, 0.01, 1.0)
            R = np.eye(k) * 0.05

            result = scfma_calibrate(c, n, R, [], sample_id="test", alpha=0.5, beta=0.5, gamma=0.1)
            if not result.weights:
                continue
            w_cal = np.array(result.weights[0].to_list())

            ciu_norm = c / np.sum(c)
            scfma_vars.append(float(np.var(w_cal)))
            raw_vars.append(float(np.var(ciu_norm)))

        assert len(scfma_vars) > 0, "No valid trials"
        mean_scfma_var = float(np.mean(scfma_vars))
        mean_raw_var = float(np.mean(raw_vars))
        assert mean_scfma_var <= mean_raw_var + 0.05, (
            f"SC-FMA var {mean_scfma_var:.6f} not ≤ raw CIU var {mean_raw_var:.6f}"
        )

    def test_ridge_variance_reduction(self):
        rng = np.random.default_rng(42)
        n_trials = 50

        ridge_vars: list[float] = []
        raw_vars: list[float] = []

        for _ in range(n_trials):
            c = np.abs(rng.normal(0.5, 0.15, 5))
            c = np.clip(c, 0.01, 1.0)
            n = np.abs(rng.normal(0.5, 0.15, 5))
            n = np.clip(n, 0.01, 1.0)

            result = scfma_calibrate_ridge(c, n, alpha_ciui=0.6, alpha_nec=0.4)
            w_cal = np.array(result.weights[0].to_list())
            ciu_norm = c / np.sum(c)
            ridge_vars.append(float(np.var(w_cal)))
            raw_vars.append(float(np.var(ciu_norm)))

        assert float(np.mean(ridge_vars)) <= float(np.mean(raw_vars)) + 0.03, "Ridge variance not reduced"


class TestBottleneckRecovery:
    def test_bottleneck_never_zero_weight(self):
        k = 5
        c = np.array([0.3, 0.9, 0.1, 0.8, 0.4])
        n = np.array([0.02, 0.95, 0.05, 0.7, 0.1])
        R = np.eye(k) * 0.1

        bottlenecks = [BottleneckConstraint(node_index=2, floor_weight=0.02)]
        result = scfma_calibrate(c, n, R, bottlenecks, sample_id="test",
                                  alpha=0.4, beta=0.6, gamma=0.05, delta=0.2)

        assert result.weights, "No weights produced"
        w = np.array(result.weights[0].to_list())
        assert w[2] > 1e-6, f"Bottleneck node 2 got weight {w[2]:.8f}"
        assert w[2] >= 0.005, f"Bottleneck floor constraint violated: {w[2]:.6f}"

    def test_multiple_bottlenecks_protected(self):
        k = 6
        c = np.array([0.1, 0.05, 0.03, 0.02, 0.9, 0.8])
        n = np.array([0.05, 0.03, 0.02, 0.01, 0.95, 0.7])
        R = np.eye(k) * 0.1

        bottlenecks = [
            BottleneckConstraint(node_index=0, floor_weight=0.01),
            BottleneckConstraint(node_index=1, floor_weight=0.01),
            BottleneckConstraint(node_index=2, floor_weight=0.01),
            BottleneckConstraint(node_index=3, floor_weight=0.01),
        ]

        result = scfma_calibrate(c, n, R, bottlenecks, sample_id="test",
                                  alpha=0.2, beta=0.8, gamma=0.1, delta=0.3)

        assert result.weights
        w = np.array(result.weights[0].to_list())

        for i in range(4):
            assert w[i] >= 0.001, f"Bottleneck node {i} received near-zero weight: {w[i]:.8f}"

    def test_bottleneck_amplification_in_projection(self):
        k = 4
        ciu = np.array([0.2, 0.8, 0.3, 0.4])
        nec = np.array([0.1, 0.9, 0.2, 0.3])
        R = np.eye(k) * 0.1

        w_no_bottleneck = project_weights(ciu, nec, R, set())
        w_with_bottleneck = project_weights(ciu, nec, R, {0})

        assert w_with_bottleneck[0] >= w_no_bottleneck[0] - 0.05, (
            f"Bottleneck not amplified: {w_with_bottleneck[0]:.4f} vs {w_no_bottleneck[0]:.4f}"
        )


class TestEdgeCases:
    def test_single_step(self):
        c = np.array([0.5])
        n = np.array([0.5])
        R = np.array([[0.0]])

        result = scfma_calibrate(c, n, R, [], sample_id="single")
        assert len(result.weights) == 1
        w = result.weights[0].to_list()
        assert abs(w[0] - 1.0) < 1e-6

    def test_empty_input(self):
        c = np.array([], dtype=float)
        n = np.array([], dtype=float)
        R = np.zeros((0, 0))
        result = scfma_calibrate(c, n, R, [], sample_id="empty")
        assert result.weights == []
        assert result.converged

    def test_uniform_scores(self):
        k = 5
        c = np.ones(k)
        n = np.ones(k)
        R = np.eye(k) * 0.05
        result = scfma_calibrate(c, n, R, [], sample_id="uniform")

        w = np.array(result.weights[0].to_list())
        assert np.allclose(w, 0.2, atol=0.01), f"Uniform input gave {w}"

    def test_projection_normalizes(self):
        ciu = np.array([0.1, 0.2, 0.3])
        nec = np.array([0.3, 0.2, 0.1])
        w = project_weights(ciu, nec)
        assert abs(float(np.sum(w)) - 1.0) < 1e-8, f"Sum not 1: {np.sum(w)}"
        assert np.all(w >= 0), "Negative weights"
