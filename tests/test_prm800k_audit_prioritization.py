from __future__ import annotations

from fma.eval.prm800k_audit_prioritization import (
    label_mass_at_budget,
    max_label_hit_at_budget,
    ndcg_at_budget,
    summarize_audit_prioritization,
)


def test_max_label_hit_at_budget_selects_highest_label():
    scores = [0.1, 0.9, 0.2]
    labels = [0.0, 1.0, 0.5]
    assert max_label_hit_at_budget(scores, labels, keep_fraction=1 / 3) == 1.0


def test_max_label_hit_at_budget_detects_miss():
    scores = [0.9, 0.1, 0.2]
    labels = [0.0, 1.0, 0.5]
    assert max_label_hit_at_budget(scores, labels, keep_fraction=1 / 3) == 0.0


def test_label_mass_at_budget_is_normalized():
    scores = [0.9, 0.2, 0.1]
    labels = [0.5, 1.0, 0.5]
    assert label_mass_at_budget(scores, labels, keep_fraction=1 / 3) == 0.25


def test_ndcg_at_budget_is_one_for_perfect_order():
    scores = [0.9, 0.7, 0.1]
    labels = [1.0, 0.5, 0.0]
    assert ndcg_at_budget(scores, labels, keep_fraction=2 / 3) == 1.0


def test_summary_contains_all_methods():
    rows = [
        {
            "labels": [0.0, 1.0, 0.5],
            "scores_by_method": {
                "w_struct": [0.1, 0.9, 0.2],
                "raw_local_utility": [0.9, 0.1, 0.2],
            },
        }
    ]
    summaries = summarize_audit_prioritization(
        rows,
        methods=["w_struct", "raw_local_utility"],
    )
    assert [summary.method for summary in summaries] == [
        "w_struct",
        "raw_local_utility",
    ]
    assert summaries[0].mean_top1_hit == 1.0
    assert summaries[1].mean_top1_hit == 0.0
