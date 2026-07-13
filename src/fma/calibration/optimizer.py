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


def _window_bounds(k: int, window_size: int) -> list[tuple[int, int]]:
    """Contiguous ``[i, j)`` window boundaries over ``k`` steps.

    A too-small trailing window (shorter than ``max(2, window_size // 2)``) is
    merged into the preceding window so every window supports a non-trivial QP.
    """
    if window_size < 1:
        window_size = 1
    bounds: list[tuple[int, int]] = []
    i = 0
    while i < k:
        j = min(i + window_size, k)
        bounds.append((i, j))
        i = j
    if len(bounds) >= 2:
        last_i, last_j = bounds[-1]
        if (last_j - last_i) < max(2, window_size // 2):
            prev_i, _ = bounds[-2]
            bounds[-2] = (prev_i, last_j)
            bounds.pop()
    return bounds


def _window_masses(
    c: np.ndarray,
    solutions: list[tuple[int, int, np.ndarray]],
    *,
    stitch: str,
    n: np.ndarray,
) -> list[float]:
    """Global mass allocated to each window, summing to one.

    ``"mass"`` (default) allocates proportional to each window's non-negative
    fidelity mass ``sum(max(c, 0))`` — a soft, Ridge-like averaging. ``"ridge"``
    derives inter-window masses from a softmax blend of per-window mean fidelity
    and mean necessity via :func:`scfma_calibrate_ridge`.
    """
    n_windows = len(solutions)
    if n_windows == 0:
        return []
    if n_windows == 1:
        return [1.0]

    if stitch == "ridge":
        cw = np.array([float(np.mean(c[i:j])) for (i, j, _) in solutions])
        nw = np.array([float(np.mean(n[i:j])) for (i, j, _) in solutions])
        res = scfma_calibrate_ridge(cw, nw, alpha_ciui=0.7, alpha_nec=0.3)
        if res.weights:
            return [float(v) for v in res.weights[0].weights]
        return [1.0 / n_windows] * n_windows

    raw = np.array([float(np.sum(np.maximum(c[i:j], 0.0))) for (i, j, _) in solutions])
    if np.sum(raw) < EPSILON:
        raw = np.array([float(np.sum(np.abs(c[i:j]))) for (i, j, _) in solutions])
    if np.sum(raw) < EPSILON:
        return [1.0 / n_windows] * n_windows
    return [float(v) for v in raw / np.sum(raw)]


def _apply_floors(w: np.ndarray, floor_by_index: dict[int, float]) -> np.ndarray:
    """Project ``w`` onto the simplex subject to per-node lower bounds.

    Deficient bottleneck nodes are raised to their floors; the remaining budget
    ``1 - sum(floors)`` is distributed over the surplus above each floor,
    preserving the solver's relative preference. Guarantees ``w_i >= floor_i``
    and ``sum(w) == 1`` in a single pass.
    """
    w = np.maximum(np.asarray(w, dtype=float), 0.0)
    s = float(np.sum(w))
    w = w / s if s > EPSILON else np.ones_like(w) / max(1, len(w))
    k = len(w)
    floor_vec = np.zeros(k)
    for idx, floor in floor_by_index.items():
        if 0 <= idx < k:
            floor_vec[idx] = max(0.0, float(floor))
    total_floor = float(np.sum(floor_vec))
    if total_floor <= EPSILON:
        return w
    if total_floor >= 1.0:
        return floor_vec / (total_floor + EPSILON)
    excess = np.maximum(w - floor_vec, 0.0)
    excess_total = float(np.sum(excess))
    if excess_total > EPSILON:
        return floor_vec + excess / excess_total * (1.0 - total_floor)
    return floor_vec + (1.0 - total_floor) / k


def _relabel_result(
    result: CalibrationResult,
    method_label: str,
    extra_metadata: dict[str, Any] | None = None,
) -> CalibrationResult:
    """Return a copy of ``result`` with a new method label on its weights."""
    new_weights = []
    for cw in result.weights:
        metadata = dict(cw.metadata or {})
        if extra_metadata:
            metadata.update(extra_metadata)
        new_weights.append(
            CalibratedWeights(
                weights=cw.weights,
                sample_id=cw.sample_id,
                method=method_label,
                metadata=metadata,
            )
        )
    return CalibrationResult(
        weights=new_weights,
        loss_fidelity=result.loss_fidelity,
        loss_structure=result.loss_structure,
        loss_redundancy=result.loss_redundancy,
        loss_total=result.loss_total,
        alpha=result.alpha,
        beta=result.beta,
        gamma=result.gamma,
        iteration_count=result.iteration_count,
        converged=result.converged,
        metadata=result.metadata,
    )


def scfma_calibrate_windowed(
    c: np.ndarray,
    n: np.ndarray,
    R: np.ndarray,
    bottleneck_constraints: list[BottleneckConstraint] | None = None,
    sample_id: str = "",
    window_size: int = 8,
    stitch: str = "mass",
    alpha: float = 1.0,
    beta: float = 0.5,
    gamma: float = 0.2,
    delta: float = 0.1,
    max_iter: int = DEFAULT_MAX_ITER,
) -> CalibrationResult:
    """Windowed SC-FMA QP calibration for long reasoning traces.

    Long traces induce dense redundancy blocks, and the global ``γ·wᵀRw`` term
    then over-equalizes priorities across the whole trace (the observed QP
    degradation on the long-trace stratum). This variant partitions the trace
    into contiguous windows of at most ``window_size`` steps, solves the SCU QP
    independently within each window on the *block-diagonal* redundancy
    sub-matrix ``R[i:j, i:j]`` (reducing the effective problem size so the
    redundancy penalty acts only within a window), and stitches the per-window
    simplex solutions into one global simplex weight vector.

    For ``k <= window_size`` it reduces exactly to :func:`scfma_calibrate`
    (only the method label differs), preserving the standard guarantees. The
    returned weights always satisfy ``w >= 0``, ``sum(w) == 1``, and the
    bottleneck floors.
    """
    method_label = "scfma_qp_windowed"
    k = len(c)

    if k <= window_size:
        base = scfma_calibrate(
            c,
            n,
            R,
            bottleneck_constraints=bottleneck_constraints,
            sample_id=sample_id,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            delta=delta,
            max_iter=max_iter,
        )
        return _relabel_result(
            base,
            method_label,
            extra_metadata={
                "window_size": int(window_size),
                "n_windows": 1 if k > 0 else 0,
                "stitch": stitch,
            },
        )

    c = np.asarray(c, dtype=float)
    n = np.asarray(n, dtype=float)
    R = np.asarray(R, dtype=float)

    floor_by_index: dict[int, float] = {}
    if bottleneck_constraints:
        for bc in bottleneck_constraints:
            if 0 <= bc.node_index < k:
                floor_by_index[bc.node_index] = bc.floor_weight

    bounds_list = _window_bounds(k, window_size)
    solutions: list[tuple[int, int, np.ndarray]] = []
    total_iters = 0
    all_converged = True

    for (i, j) in bounds_list:
        local_constraints = [
            BottleneckConstraint(idx - i, floor_by_index[idx])
            for idx in range(i, j)
            if idx in floor_by_index
        ]
        res = scfma_calibrate(
            c[i:j],
            n[i:j],
            R[i:j, i:j],
            bottleneck_constraints=local_constraints or None,
            sample_id=f"{sample_id}:w{i}",
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            delta=delta,
            max_iter=max_iter,
        )
        w_local = (
            np.asarray(res.weights[0].weights, dtype=float)
            if res.weights
            else np.ones(j - i) / (j - i)
        )
        solutions.append((i, j, w_local))
        total_iters += int(res.iteration_count)
        all_converged = all_converged and bool(res.converged)

    masses = _window_masses(c, solutions, stitch=stitch, n=n)

    global_w = np.zeros(k, dtype=float)
    for (i, j, w_local), mass in zip(solutions, masses):
        global_w[i:j] = mass * w_local

    global_w = np.maximum(global_w, EPSILON)
    global_w = global_w / (np.sum(global_w) + EPSILON)
    if floor_by_index:
        global_w = _apply_floors(global_w, floor_by_index)

    R_eval = R
    if not _check_positive_semidefinite(R_eval):
        R_eval = (R_eval + R_eval.T) / 2.0
        eigvals = np.linalg.eigvalsh(R_eval)
        if np.min(eigvals) < 0:
            R_eval = R_eval - np.min(eigvals) * np.eye(k) + EPSILON * np.eye(k)

    bottleneck_mask = np.zeros(k, dtype=float)
    for idx in floor_by_index:
        bottleneck_mask[idx] = 1.0
    losses = SCULoss(alpha=alpha, beta=beta, gamma=gamma, delta=delta).evaluate(
        global_w, c, n, R_eval, bottleneck_mask
    )

    calibrated = CalibratedWeights(
        weights=tuple(float(v) for v in global_w),
        sample_id=sample_id,
        method=method_label,
        metadata={
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "delta": delta,
            "window_size": int(window_size),
            "n_windows": len(bounds_list),
            "stitch": stitch,
            "converged": all_converged,
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
        iteration_count=total_iters,
        converged=all_converged,
    )
