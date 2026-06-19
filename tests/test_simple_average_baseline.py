"""Tests for the simple_average baseline."""

from __future__ import annotations

import numpy as np
import pytest

from fma.baselines.simple_average import simple_average_baseline


class TestSimpleAverageBaseline:
    def test_output_length_matches_input(self):
        """Output weight vector has same length as input CIU."""
        ciu = [0.1, 0.3, 0.5, 0.1]
        nec = [0.2, 0.4, 0.3, 0.1]
        result = simple_average_baseline(ciu, nec)
        assert len(result) == len(ciu)

    def test_output_is_probability_simplex(self):
        """Output weights are non-negative and sum to 1.0."""
        ciu = [0.1, 0.3, 0.5, 0.1]
        nec = [0.2, 0.4, 0.3, 0.1]
        result = simple_average_baseline(ciu, nec)
        assert all(w >= 0 for w in result)
        assert abs(sum(result) - 1.0) < 1e-9

    def test_preserves_ranking_when_inputs_agree(self):
        """When CIU and necessity rank steps identically, simple_average
        preserves that ranking."""
        rng = np.random.default_rng(42)
        base = [0.1, 0.9, 0.3, 0.6, 0.2]  # rank: 1 > 3 > 2 > 4 > 0
        # Both CIU and necessity use the same ordering
        ciu = [b + rng.normal(0, 0.01) for b in base]
        nec = [b + rng.normal(0, 0.01) for b in base]

        result = simple_average_baseline(ciu, nec)

        # Expected ranking: index 1 > 3 > 2 > 4 > 0
        gt_rank = np.argsort(np.argsort(-np.array(base)))
        pred_rank = np.argsort(np.argsort(-np.array(result)))
        assert np.array_equal(gt_rank, pred_rank), (
            f"Expected ranking {gt_rank}, got {pred_rank}"
        )

    def test_empty_input_returns_empty(self):
        """Empty CIU returns empty list."""
        result = simple_average_baseline([], [])
        assert result == []

    def test_length_mismatch_raises(self):
        """Mismatched CIU and necessity lengths raise ValueError."""
        with pytest.raises(ValueError, match="Length mismatch"):
            simple_average_baseline([0.1, 0.2], [0.1])
