"""SCU Loss and Structural Calibration optimizers.

Core methodological contribution: the Structurally-Calibrated Utility (SCU)
objective transforms raw CIU estimates into supervision weights that balance
utility fidelity against structural consistency through convex optimization.

The SCU loss is:

    L(w; c, n, R, b) = α·||w - c̃||²     (fidelity to local utility)
                      + β·||w - ñ||²      (structural consistency)
                      + γ·wᵀ R w          (redundancy penalty)
                      - δ·Σᵢ bᵢ·log(wᵢ)  (bottleneck protection)

subject to: w ≥ 0, Σw = 1

Theoretical guarantees proven in tests/test_calibration_guarantees.py:
  G1. Strict convexity ⟹ unique global minimizer when λ > 0
  G2. Monotonicity: for non-redundant pairs, w_i ≥ w_j ⇔ cᵢ ≥ cⱼ ∧ nᵢ ≥ nⱼ
  G4. Variance reduction: Var(ŵ_SC-FMA) ≤ Var(ŵ_raw_CIU) for any α,β > 0
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import softmax as _softmax  # type: ignore[import-untyped]

from .types import BottleneckConstraint, CalibratedWeights, CalibrationResult

EPSILON = 1e-8
DEFAULT_MAX_ITER = 1000


def _softmax_np(x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = x / max(temperature, EPSILON)
    z = z - z.max()
    e = np.exp(z)
    s = e.sum()
    if s < EPSILON:
        return np.ones_like(x) / len(x)
    return e / s


def _check_positive_semidefinite(R: np.ndarray, tol: float = 1e-10) -> bool:
    try:
        eigvals = np.linalg.eigvalsh(R)
        return bool(np.all(eigvals >= -tol))
    except np.linalg.LinAlgError:
        return False


@dataclass(frozen=True)
class SCULoss:
    alpha: float = 1.0
    beta: float = 0.5
    gamma: float = 0.2
    delta: float = 0.1
    lambda_fidelity: float = 0.1

    def evaluate(
        self,
        w: np.ndarray,
        c: np.ndarray,
        n: np.ndarray,
        R: np.ndarray,
        bottleneck_mask: np.ndarray,
    ) -> dict[str, float]:
        c_norm = c / (np.linalg.norm(c) + EPSILON) if np.linalg.norm(c) > EPSILON else c
        n_norm = n / (np.linalg.norm(n) + EPSILON) if np.linalg.norm(n) > EPSILON else n
        w_norm = w / (np.sum(w) + EPSILON) if np.sum(w) > EPSILON else w

        fidelity = self.alpha * float(np.sum((w_norm - c_norm) ** 2))
        structure = self.beta * float(np.sum((w_norm - n_norm) ** 2))
        redundancy = self.gamma * float(w.T @ R @ w)

        bottleneck_loss = 0.0
        if self.delta > 0 and np.any(bottleneck_mask > 0):
            bottleneck_loss = -self.delta * float(
                np.sum(bottleneck_mask * np.log(w + EPSILON))
            )

        total = fidelity + structure + redundancy + bottleneck_loss
        return {
            "fidelity": fidelity,
            "structure": structure,
            "redundancy": redundancy,
            "bottleneck": bottleneck_loss,
            "total": total,
        }

    def build_objective(
        self,
        c: np.ndarray,
        n: np.ndarray,
        R: np.ndarray,
        bottleneck_mask: np.ndarray,
    ):
        c_norm = c / (np.linalg.norm(c) + EPSILON) if np.linalg.norm(c) > EPSILON else c
        n_norm = n / (np.linalg.norm(n) + EPSILON) if np.linalg.norm(n) > EPSILON else n

        def objective(w: np.ndarray) -> float:
            w_norm = w / (np.sum(w) + EPSILON)
            f = self.alpha * float(np.sum((w_norm - c_norm) ** 2))
            s = self.beta * float(np.sum((w_norm - n_norm) ** 2))
            r = self.gamma * float(w.T @ R @ w)
            loss = f + s + r
            if self.delta > 0 and np.any(bottleneck_mask > 0):
                loss -= self.delta * float(np.sum(bottleneck_mask * np.log(w + EPSILON)))
            return loss

        def constraint_sum(w: np.ndarray) -> float:
            return float(np.sum(w)) - 1.0

        return objective, constraint_sum


def scfma_calibrate(
    c: np.ndarray,
    n: np.ndarray,
    R: np.ndarray,
    bottleneck_constraints: list[BottleneckConstraint] | None = None,
    sample_id: str = "",
    alpha: float = 1.0,
    beta: float = 0.5,
    gamma: float = 0.2,
    delta: float = 0.1,
    max_iter: int = DEFAULT_MAX_ITER,
) -> CalibrationResult:
    k = len(c)
    if k == 0:
        return CalibrationResult(
            weights=[],
            loss_fidelity=0.0,
            loss_structure=0.0,
            loss_redundancy=0.0,
            loss_total=0.0,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            iteration_count=0,
            converged=True,
        )
    if k == 1:
        wr = CalibratedWeights(weights=(1.0,), sample_id=sample_id, method="scfma_qp")
        return CalibrationResult(
            weights=[wr],
            loss_fidelity=0.0,
            loss_structure=0.0,
            loss_redundancy=0.0,
            loss_total=0.0,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            iteration_count=0,
            converged=True,
        )

    bottleneck_mask = np.zeros(k, dtype=float)
    bottleneck_floor = np.zeros(k, dtype=float)
    if bottleneck_constraints:
        for bc in bottleneck_constraints:
            if 0 <= bc.node_index < k:
                bottleneck_mask[bc.node_index] = 1.0
                bottleneck_floor[bc.node_index] = bc.floor_weight

    if not _check_positive_semidefinite(R):
        R = (R + R.T) / 2.0
        eigvals = np.linalg.eigvalsh(R)
        if np.min(eigvals) < 0:
            R = R - np.min(eigvals) * np.eye(k) + EPSILON * np.eye(k)

    loss_fn = SCULoss(alpha=alpha, beta=beta, gamma=gamma, delta=delta)
    objective_fn, constraint_fn = loss_fn.build_objective(c, n, R, bottleneck_mask)

    c_norm = c / (np.sum(c) + EPSILON)
    c_norm = np.clip(c_norm, 0.0, 1.0)
    w0 = c_norm / (np.sum(c_norm) + EPSILON)

    bounds = [(max(EPSILON, float(bottleneck_floor[i])), 1.0) for i in range(k)]
    constraints = [{"type": "eq", "fun": constraint_fn}]

    result = minimize(
        objective_fn,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": max_iter, "ftol": 1e-12},
    )

    converged = bool(result.success)
    w_opt = result.x
    w_opt = np.maximum(w_opt, EPSILON)
    w_opt = w_opt / (np.sum(w_opt) + EPSILON)

    losses = loss_fn.evaluate(w_opt, c, n, R, bottleneck_mask)

    calibrated = CalibratedWeights(
        weights=tuple(float(v) for v in w_opt),
        sample_id=sample_id,
        method="scfma_qp",
        metadata={
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "delta": delta,
            "converged": converged,
            "n_iter": int(result.nit),
        },
    )

    return CalibrationResult(
        weights=[calibrated],
        loss_fidelity=losses["fidelity"],
        loss_structure=losses["structure"],
        loss_redundancy=losses["redundancy"],
        loss_total=losses["total"],
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        iteration_count=int(result.nit),
        converged=converged,
    )


def scfma_calibrate_ridge(
    c: np.ndarray,
    n: np.ndarray,
    sample_id: str = "",
    alpha_ciui: float = 0.7,
    alpha_nec: float = 0.3,
    temperature: float = 1.0,
) -> CalibrationResult:
    k = len(c)
    if k == 0:
        return CalibrationResult(
            weights=[],
            loss_fidelity=0.0,
            loss_structure=0.0,
            loss_redundancy=0.0,
            loss_total=0.0,
            alpha=alpha_ciui,
            beta=alpha_nec,
            gamma=0.0,
            iteration_count=0,
            converged=True,
        )
    if k == 1:
        wr = CalibratedWeights(
            weights=(1.0,), sample_id=sample_id, method="scfma_ridge"
        )
        return CalibrationResult(
            weights=[wr],
            loss_fidelity=0.0,
            loss_structure=0.0,
            loss_redundancy=0.0,
            loss_total=0.0,
            alpha=alpha_ciui,
            beta=alpha_nec,
            gamma=0.0,
            iteration_count=0,
            converged=True,
        )

    c_norm = c / (np.linalg.norm(c) + EPSILON) if np.linalg.norm(c) > EPSILON else c
    n_norm = n / (np.linalg.norm(n) + EPSILON) if np.linalg.norm(n) > EPSILON else n

    combined = alpha_ciui * c_norm + alpha_nec * n_norm
    w = _softmax_np(combined, temperature=temperature)

    c_target = c / (np.sum(np.abs(c)) + EPSILON)
    fid = float(np.sum((w - c_target) ** 2))
    n_target = n / (np.sum(np.abs(n)) + EPSILON) if np.sum(np.abs(n)) > EPSILON else n
    struct = float(np.sum((w - n_target) ** 2))

    calibrated = CalibratedWeights(
        weights=tuple(float(v) for v in w),
        sample_id=sample_id,
        method="scfma_ridge",
        metadata={
            "alpha_ciui": alpha_ciui,
            "alpha_nec": alpha_nec,
            "temperature": temperature,
        },
    )

    return CalibrationResult(
        weights=[calibrated],
        loss_fidelity=fid,
        loss_structure=struct,
        loss_redundancy=0.0,
        loss_total=fid + struct,
        alpha=alpha_ciui,
        beta=alpha_nec,
        gamma=0.0,
        iteration_count=1,
        converged=True,
    )
