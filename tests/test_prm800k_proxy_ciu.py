from __future__ import annotations

import math

from fma.ciu.estimator import compute_prm800k_proxy_ciu


def test_prm800k_proxy_ciu_basic():
    ratings = [1, 0, -1, 1, 0]
    result = compute_prm800k_proxy_ciu(ratings, normalize=False)
    assert len(result) == 5
    assert result[0]["ciu"] == 1.0
    assert result[1]["ciu"] == 0.5
    assert result[2]["ciu"] == 0.0
    assert result[3]["ciu"] == 1.0
    assert result[4]["ciu"] == 0.5
    assert result[0]["source"] == "prm800k_proxy"


def test_prm800k_proxy_ciu_normalized():
    ratings = [1, 0, -1]
    result = compute_prm800k_proxy_ciu(ratings, normalize=True)
    values = [r["ciu"] for r in result]
    l2 = math.sqrt(sum(v * v for v in values))
    assert abs(l2 - 1.0) < 1e-6


def test_prm800k_proxy_ciu_all_zero():
    ratings = [-1, -1, -1]
    result = compute_prm800k_proxy_ciu(ratings, normalize=True)
    values = [r["ciu"] for r in result]
    assert abs(sum(values) - 1.0) < 1e-6
    for v in values:
        assert abs(v - 1.0 / 3) < 1e-6


def test_prm800k_proxy_ciu_empty():
    result = compute_prm800k_proxy_ciu([])
    assert result == []


def test_prm800k_proxy_ciu_custom_indices():
    ratings = [1, 0, -1]
    result = compute_prm800k_proxy_ciu(
        ratings, step_indices=[10, 20, 30], trace_id="test_trace"
    )
    assert result[0]["step_index"] == 10
    assert result[1]["step_index"] == 20
    assert result[2]["step_index"] == 30
    assert result[0]["trace_id"] == "test_trace"


def test_prm800k_proxy_ciu_invalid_rating():
    import pytest

    with pytest.raises(ValueError, match="not in"):
        compute_prm800k_proxy_ciu([1, 0, 2])


def test_prm800k_proxy_ciu_index_mismatch():
    import pytest

    with pytest.raises(ValueError, match="same length"):
        compute_prm800k_proxy_ciu([1, 0], step_indices=[0])