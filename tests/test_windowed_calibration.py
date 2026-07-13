"""Guarantee tests for the windowed SC-FMA QP calibration variant.

Mirrors the invariants in tests/test_calibration_guarantees.py for the plain QP
and adds the windowing-specific properties: exact reduction to the plain QP for
short traces, and recovery of fidelity-aligned ranking on long dense-redundancy
traces where the plain QP over-redistributes.
"""
from __future__ import annotations

import numpy as np

from fma.calibration import (
    BottleneckConstraint,
    scfma_calibrate,
    scfma_calibrate_windowed,
)
from fma.calibration.optimizer import _apply_floors, _window_bounds


def _weights(result) -> np.ndarray:
    return np.asarray(result.weights[0].weights, dtype=float)


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    if np.std(ra) == 0 or np.std(rb) == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def _dense_trace(k: int = 24, block=(8, 18), seed: int = 0):
    """Long trace with an increasing fidelity field and a dense redundancy block."""
    rng = np.random.default_rng(seed)
    c = np.linspace(0.1, 0.9, k)
    n = 0.5 + 0.05 * rng.standard_normal(k)
    R = np.zeros((k, k))
    lo, hi = block
    idx = np.arange(lo, hi)
    for a in idx:
        for b in idx:
            if a != b:
                R[a, b] = 0.9
    return c, n, (R + R.T) / 2.0


def test_simplex_and_nonnegativity():
    for seed in range(4):
        c, n, R = _dense_trace(seed=seed)
        w = _weights(scfma_calibrate_windowed(c, n, R, window_size=4))
        assert abs(float(w.sum()) - 1.0) < 1e-6
        assert (w >= -1e-12).all()


def test_bottleneck_floors_respected():
    c, n, R = _dense_trace()
    floors = [BottleneckConstraint(3, 0.05), BottleneckConstraint(20, 0.07)]
    for stitch in ("mass", "ridge"):
        w = _weights(
            scfma_calibrate_windowed(
                c, n, R, bottleneck_constraints=floors, window_size=4, stitch=stitch
            )
        )
        assert abs(float(w.sum()) - 1.0) < 1e-6
        assert w[3] >= 0.05 - 1e-9
        assert w[20] >= 0.07 - 1e-9


def test_reduces_to_plain_qp_for_short_traces():
    """For k <= window_size the windowed variant must equal the plain QP."""
    rng = np.random.default_rng(1)
    for k in (2, 3, 5, 8):
        c = rng.random(k)
        n = rng.random(k)
        R = np.zeros((k, k))
        base = _weights(scfma_calibrate(c, n, R))
        win = _weights(scfma_calibrate_windowed(c, n, R, window_size=8))
        assert np.allclose(base, win, atol=1e-9)


def test_windowed_method_label():
    c, n, R = _dense_trace()
    res = scfma_calibrate_windowed(c, n, R, window_size=4)
    assert res.weights[0].method == "scfma_qp_windowed"
    assert res.weights[0].metadata["n_windows"] >= 2


def test_recovers_fidelity_ranking_on_dense_long_trace():
    """Windowing must track the fidelity field at least as well as the plain QP,
    which over-redistributes across the dense redundancy block."""
    c, n, R = _dense_trace(k=24, block=(6, 20))
    bcs = None
    w_qp = _weights(scfma_calibrate(c, n, R, bottleneck_constraints=bcs))
    w_win = _weights(
        scfma_calibrate_windowed(c, n, R, bottleneck_constraints=bcs, window_size=4)
    )
    rho_qp = _spearman(w_qp, c)
    rho_win = _spearman(w_win, c)
    assert rho_win >= rho_qp - 1e-9
    assert rho_win > 0.5  # windowing recovers a strong fidelity-aligned ordering


def test_window_bounds_merge_small_tail():
    assert _window_bounds(9, 8) == [(0, 9)]  # tiny tail merged
    assert _window_bounds(12, 8) == [(0, 8), (8, 12)]
    assert _window_bounds(24, 8) == [(0, 8), (8, 16), (16, 24)]
    # every window is non-trivial (size >= 2)
    for k in range(4, 60):
        for ws in (2, 3, 4, 8):
            bounds = _window_bounds(k, ws)
            assert bounds[0][0] == 0 and bounds[-1][1] == k
            assert all(j - i >= 2 for i, j in bounds)
            # contiguous, non-overlapping cover
            for (a, b), (c2, _) in zip(bounds, bounds[1:]):
                assert b == c2


def test_apply_floors_projects_onto_constrained_simplex():
    rng = np.random.default_rng(2)
    w = rng.random(10)
    w = w / w.sum()
    floors = {2: 0.2, 7: 0.15}
    out = _apply_floors(w, floors)
    assert abs(float(out.sum()) - 1.0) < 1e-9
    assert out[2] >= 0.2 - 1e-9
    assert out[7] >= 0.15 - 1e-9
    assert (out >= -1e-12).all()
