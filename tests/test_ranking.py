"""Tests for step importance ranking module."""

from __future__ import annotations

import numpy as np
import pytest

from fma.ranking.comparison import (
    BaselineMethod,
    ImportanceRanker,
    compare_methods,
    list_methods,
)
from fma.ranking.metrics import (
    compute_ndcg,
    compute_ranking_metrics,
    compute_topk_overlap,
)
from fma.ranking.significance import (
    bootstrap_ci,
    friedman_test,
    wilcoxon_pairs,
)


class TestRankingMetrics:
    def test_spearman_perfect(self):
        pred = [0.9, 0.7, 0.5, 0.3, 0.1]
        gt = [0.9, 0.7, 0.5, 0.3, 0.1]
        metrics = compute_ranking_metrics(pred, gt, k_values=(3, 5))
        assert abs(metrics["spearman_rho"] - 1.0) < 1e-6
        assert abs(metrics["kendall_tau"] - 1.0) < 1e-6

    def test_spearman_reverse(self):
        pred = [0.1, 0.3, 0.5, 0.7, 0.9]
        gt = [0.9, 0.7, 0.5, 0.3, 0.1]
        metrics = compute_ranking_metrics(pred, gt, k_values=(3, 5))
        assert metrics["spearman_rho"] < -0.9

    def test_single_element(self):
        metrics = compute_ranking_metrics([0.5], [0.8])
        assert metrics["spearman_rho"] == 0.0
        assert metrics["kendall_tau"] == 0.0

    def test_ndcg_perfect(self):
        pred = np.array([0.9, 0.7, 0.5, 0.3, 0.1])
        gt = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
        ndcg = compute_ndcg(pred, gt, k=3)
        assert abs(ndcg - 1.0) < 1e-6

    def test_ndcg_zero_relevance(self):
        pred = np.array([0.9, 0.5, 0.1])
        gt = np.array([0.0, 0.0, 0.0])
        ndcg = compute_ndcg(pred, gt, k=2)
        assert ndcg == 0.0

    def test_topk_overlap_full(self):
        pred = [0.9, 0.7, 0.5, 0.3, 0.1]
        gt = [0.9, 0.7, 0.5, 0.3, 0.1]
        overlap = compute_topk_overlap(pred, gt, k=3)
        assert abs(overlap - 1.0) < 1e-6

    def test_topk_overlap_none(self):
        pred = [0.9, 0.7, 0.5, 0.3, 0.1, 0.05]
        gt = [0.05, 0.1, 0.3, 0.5, 0.7, 0.9]
        overlap = compute_topk_overlap(pred, gt, k=3)
        assert abs(overlap - 0.0) < 1e-6


class TestSignificance:
    def test_bootstrap_ci(self):
        data = np.array([0.1, 0.2, 0.15, 0.25, 0.18] * 10)
        ci = bootstrap_ci(data, n_bootstrap=1000, seed=42)
        assert ci["ci_lower"] <= ci["mean"] <= ci["ci_upper"]
        assert ci["std"] >= 0

    def test_bootstrap_empty(self):
        ci = bootstrap_ci(np.array([]), n_bootstrap=1000)
        assert ci["mean"] == 0.0

    def test_friedman_different(self):
        scores = {
            "A": [0.5, 0.6, 0.55, 0.7, 0.65] * 10,
            "B": [0.3, 0.35, 0.4, 0.45, 0.5] * 10,
            "C": [0.2, 0.25, 0.3, 0.35, 0.4] * 10,
        }
        result = friedman_test(scores)
        assert result["n_methods"] == 3
        assert result["p_value"] < 0.05

    def test_friedman_identical(self):
        scores = {
            "A": [0.5, 0.5, 0.5, 0.5],
            "B": [0.5, 0.5, 0.5, 0.5],
        }
        result = friedman_test(scores)
        assert result["p_value"] == 1.0

    def test_friedman_single_method(self):
        scores = {"A": [0.5, 0.6]}
        result = friedman_test(scores)
        assert result["p_value"] == 1.0

    def test_wilcoxon_pairs(self):
        scores = {
            "A": [0.5, 0.6, 0.55, 0.7, 0.65] * 5,
            "B": [0.3, 0.35, 0.4, 0.45, 0.5] * 5,
        }
        pairs = wilcoxon_pairs(scores)
        assert len(pairs) >= 1

    def test_wilcoxon_identical(self):
        scores = {"A": [0.5, 0.5, 0.5], "B": [0.5, 0.5, 0.5]}
        pairs = wilcoxon_pairs(scores)
        assert len(pairs) == 1
        assert pairs[0]["p_value"] == 1.0


class TestImportanceRanker:
    def test_raw_ciu_ranking(self):
        ranker = ImportanceRanker()
        ciu = [0.9, 0.7, 0.3, 0.1]
        scores = ranker.rank_steps("raw_ciu", ciu)
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6
        assert scores[0] > scores[-1]

    def test_ridge_calibration(self):
        ranker = ImportanceRanker()
        ciu = [0.9, 0.7, 0.3, 0.1]
        nec = [0.3, 0.8, 0.5, 0.2]
        scores = ranker.rank_steps("scfma_ridge", ciu, nec)
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6

    def test_qp_calibration(self):
        ranker = ImportanceRanker()
        ciu = [0.9, 0.7, 0.3, 0.1]
        nec = [0.3, 0.8, 0.5, 0.2]
        R = np.eye(4) * 0.1
        scores = ranker.rank_steps("scfma_qp", ciu, nec, R, {1})
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6

    def test_projection_ranking(self):
        ranker = ImportanceRanker()
        ciu = [0.9, 0.7, 0.3, 0.1]
        nec = [0.3, 0.8, 0.5, 0.2]
        R = np.eye(4) * 0.1
        scores = ranker.rank_steps("scfma_projection", ciu, nec, R, {1})
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6

    def test_random_baseline(self):
        ranker = ImportanceRanker()
        ciu = [0.9, 0.7, 0.3, 0.1]
        scores = ranker.rank_steps("random", ciu)
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6

    def test_span_length_baseline(self):
        ranker = ImportanceRanker()
        ciu = [0.9, 0.7, 0.3, 0.1]
        scores = ranker.rank_steps("span_length", ciu, span_lengths=[20, 30, 10, 5])
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6
        assert scores[1] > scores[3]

    def test_position_baseline(self):
        ranker = ImportanceRanker()
        ciu = [0.9, 0.7, 0.3, 0.1]
        scores = ranker.rank_steps("relative_position", ciu, step_indices=[0, 1, 2, 3])
        assert len(scores) == 4
        assert abs(sum(scores) - 1.0) < 1e-6
        assert scores[0] > scores[-1]

    def test_unknown_method_falls_back(self):
        ranker = ImportanceRanker()
        ciu = [0.9, 0.7, 0.3]
        scores = ranker.rank_steps("nonexistent_method", ciu)
        assert len(scores) == 3
        assert abs(sum(scores) - 1.0) < 1e-6

    def test_compare_methods(self):
        samples = [
            {
                "sample_id": "s1",
                "ground_truth_scores": [0.9, 0.7, 0.3],
                "ciu_scores": [0.85, 0.65, 0.35],
                "necessity_scores": [0.8, 0.6, 0.4],
                "span_lengths": [15, 10, 8],
                "step_indices": [0, 1, 2],
            },
            {
                "sample_id": "s2",
                "ground_truth_scores": [0.9, 0.5, 0.1, 0.8],
                "ciu_scores": [0.88, 0.48, 0.12, 0.78],
                "necessity_scores": [0.85, 0.45, 0.15, 0.75],
                "span_lengths": [20, 12, 6, 18],
                "step_indices": [0, 1, 2, 3],
            },
        ]
        methods = ["raw_ciu", "scfma_ridge", "random", "span_length"]
        report = compare_methods(samples, methods=methods)
        assert report.n_samples > 0
        assert len(report.methods) >= 4
        assert "raw_ciu" in report.aggregate_metrics

    def test_list_methods(self):
        methods = list_methods()
        assert len(methods) >= 10
        names = {m.name for m in methods}
        assert "scfma_qp" in names
        assert "raw_ciu" in names
        assert "random" in names
        assert "oracle" in names
