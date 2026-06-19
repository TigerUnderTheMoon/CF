from __future__ import annotations

from fma.eval.prm800k_audit_prioritization import (
    assign_error_uncertainty_stratum,
    assign_label_entropy_stratum,
    assign_trace_length_stratum,
    classify_stratified_decision,
    label_entropy,
    label_mass_at_budget,
    max_label_hit_at_budget,
    ndcg_at_budget,
    summarize_audit_prioritization,
    summarize_audit_prioritization_by_stratum,
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


def test_label_entropy_is_normalized_by_observed_label_support():
    assert label_entropy([1.0, 1.0, 1.0]) == 0.0
    assert label_entropy([0.0, 1.0]) == 1.0


def test_prm800k_stratum_assignment_uses_tertiles_and_error_cues():
    assert assign_trace_length_stratum(4, (5.0, 8.0)) == "trace_length_low"
    assert assign_trace_length_stratum(7, (5.0, 8.0)) == "trace_length_mid"
    assert assign_trace_length_stratum(9, (5.0, 8.0)) == "trace_length_high"

    assert assign_label_entropy_stratum(0.2, (0.3, 0.7)) == "label_entropy_low"
    assert assign_label_entropy_stratum(0.5, (0.3, 0.7)) == "label_entropy_mid"
    assert assign_label_entropy_stratum(0.8, (0.3, 0.7)) == "label_entropy_high"

    assert assign_error_uncertainty_stratum([{"error_uncertainty_cue_count": 0.0}]) == (
        "error_uncertainty_absent"
    )
    assert assign_error_uncertainty_stratum([{"error_uncertainty_cue_count": 1.0}]) == (
        "error_uncertainty_present"
    )


def test_stratified_summary_reports_spearman_and_budget_metrics():
    rows = [
        {
            "n_steps": 3,
            "labels": [0.0, 0.5, 1.0],
            "scores_by_method": {
                "w_struct": [0.1, 0.4, 0.9],
                "span_length": [0.9, 0.4, 0.1],
            },
            "strata": {
                "trace_length": "trace_length_high",
                "label_entropy": "label_entropy_high",
            },
        },
        {
            "n_steps": 3,
            "labels": [0.0, 0.5, 1.0],
            "scores_by_method": {
                "w_struct": [0.2, 0.5, 0.8],
                "span_length": [0.8, 0.5, 0.2],
            },
            "strata": {
                "trace_length": "trace_length_low",
                "label_entropy": "label_entropy_low",
            },
        },
    ]

    summaries = summarize_audit_prioritization_by_stratum(
        rows,
        methods=["w_struct", "span_length"],
        strata=["trace_length", "label_entropy"],
    )

    high_w_struct = next(
        item
        for item in summaries
        if item["stratum_type"] == "trace_length"
        and item["stratum"] == "trace_length_high"
        and item["method"] == "w_struct"
    )
    assert high_w_struct["n_samples"] == 1
    assert high_w_struct["n_steps"] == 3
    assert high_w_struct["mean_spearman"] == 1.0
    assert high_w_struct["mean_top1_hit"] == 1.0


def test_stratified_decision_table_has_explicit_blocked_action():
    summaries = [
        {
            "stratum_type": "trace_length",
            "stratum": "trace_length_high",
            "method": "w_struct",
            "mean_spearman": 0.2,
            "mean_ndcg_at_25": 0.5,
        },
        {
            "stratum_type": "trace_length",
            "stratum": "trace_length_high",
            "method": "span_length",
            "mean_spearman": 0.3,
            "mean_ndcg_at_25": 0.6,
        },
        {
            "stratum_type": "trace_length",
            "stratum": "trace_length_low",
            "method": "w_struct",
            "mean_spearman": 0.7,
            "mean_ndcg_at_25": 0.9,
        },
    ]

    decision = classify_stratified_decision(summaries)

    assert decision["decision"] == "diagnostic"
    assert "Diagnostic Framework" in decision["required_action"]
    assert "claim_registry.md" in classify_stratified_decision([])["required_action"]
