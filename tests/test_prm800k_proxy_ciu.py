from __future__ import annotations

import math

import pytest

from fma.ciu.estimator import compute_prm800k_proxy_ciu


def test_prm800k_proxy_ciu_keeps_span_indices_and_source_label() -> None:
    rows = compute_prm800k_proxy_ciu(
        [-1, 0, 1],
        step_indices=[3, 4, 5],
        trace_id="trace-prm",
        normalize=False,
    )

    assert rows == [
        {"step_index": 3, "ciu": 0.0, "source": "prm800k_proxy", "trace_id": "trace-prm"},
        {"step_index": 4, "ciu": 0.5, "source": "prm800k_proxy", "trace_id": "trace-prm"},
        {"step_index": 5, "ciu": 1.0, "source": "prm800k_proxy", "trace_id": "trace-prm"},
    ]


def test_prm800k_proxy_ciu_normalizes_and_rejects_invalid_ratings() -> None:
    rows = compute_prm800k_proxy_ciu([0, 1], normalize=True)

    assert rows[0]["ciu"] == round(0.5 / math.sqrt(1.25), 8)
    assert rows[1]["ciu"] == round(1.0 / math.sqrt(1.25), 8)

    with pytest.raises(ValueError, match=r"\{-1, 0, \+1\}"):
        compute_prm800k_proxy_ciu([2])
