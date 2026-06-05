from __future__ import annotations

import math
from pathlib import Path

from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.validation_v3 import (
    EXPECTED_V3_HARD_CAPS,
    REAL_TASK_V3_PREREGISTRATION_ONLY,
    V3_GLOBAL_PASS,
    V3_TASK_SPECIFIC_ONLY,
    audit_v3_config_contract,
    build_v3_split_manifest,
    build_dense_target_reliability_report,
    build_v3_decision_report,
    score_gsm8k_v3_utility,
    score_hotpotqa_v3_utility,
    validate_w_struct_feature_rows,
)
from scripts.generate_real_task_v3_manifest import _assert_current_task_boundary


def test_real_task_v3_config_locks_budget_scale_and_claim_boundary() -> None:
    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))

    audit = audit_v3_config_contract(config)

    assert audit["status"] == "REAL_TASK_V3_CONTRACT_CLEAN"
    assert audit["scope"] == REAL_TASK_V3_PREREGISTRATION_ONLY
    assert audit["current_status_remains"] == "PILOT_BLOCKED"
    assert audit["api_execution_allowed"] is False
    assert audit["validation_or_pass_claim_allowed"] is False
    assert audit["hard_caps"] == EXPECTED_V3_HARD_CAPS
    assert config["splits"]["locked_validation"]["sample_count_by_task"] == {
        "gsm8k": 1000,
        "hotpotqa": 1000,
    }


def test_v3_dense_utility_scoring_uses_locked_weights() -> None:
    gsm_score = score_gsm8k_v3_utility(
        predictions=["#### 100", "The answer is 80", "not parseable"],
        reference_answer="#### 100",
    )

    assert gsm_score["utility"] == (
        0.60 * (1 / 3)
        + 0.40 * ((1.0 + math.exp(-abs(math.log(81 / 101))) + 0.0) / 3)
    )
    assert gsm_score["repeated_numeric_exact"] == 1 / 3

    hotpot_score = score_hotpotqa_v3_utility(
        prediction="Shakespeare wrote Hamlet",
        reference_answer="William Shakespeare",
        aliases=["Shakespeare"],
        predicted_supports=["Hamlet"],
        reference_supports=["Hamlet", "Authorship"],
        semantic_equivalence=0.8,
    )

    assert hotpot_score["weights"] == {
        "alias_token_f1": 0.45,
        "reference_only_f1": 0.25,
        "support_overlap": 0.20,
        "semantic_equivalence": 0.10,
    }
    assert 0.0 < hotpot_score["utility"] <= 1.0
    assert hotpot_score["semantic_equivalence"] == 0.8


def test_v3_split_manifest_uses_six_key_non_overlap_and_locked_counts() -> None:
    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))
    source_rows = {
        "gsm8k": [
            {
                "dataset": "gsm8k",
                "config": "main",
                "split": "test",
                "source_index": index,
                "sample_id": f"gsm8k-{index:05d}",
                "task_id": f"gsm8k-task-{index}",
                "question": f"What is {index} + 1?",
                "reference_answer": f"#### {index + 1}",
                "aliases": [],
                "task_type": "gsm8k",
            }
            for index in range(3)
        ],
        "hotpotqa": [
            {
                "dataset": "hotpot_qa",
                "config": "distractor",
                "split": "validation",
                "source_index": index,
                "sample_id": f"hotpotqa-{index:05d}",
                "task_id": f"hotpotqa-task-{index}",
                "question": f"Who is entity {index}?",
                "reference_answer": f"Entity {index}",
                "aliases": [f"Alias {index}"],
                "task_type": "hotpotqa",
            }
            for index in range(3)
        ],
    }
    overlap_sources = {
        "old": [
            {
                "sample_id": "gsm8k-00000",
                "task_id": "old",
                "question": "What is 0 + 1?",
                "reference_answer": "#### 1",
                "aliases": [],
            }
        ]
    }

    manifest, audit = build_v3_split_manifest(
        source_rows,
        config=config,
        split_name="smoke",
        sample_count_by_task={"gsm8k": 2, "hotpotqa": 2},
        overlap_sources=overlap_sources,
    )

    assert audit["status"] == "MANIFEST_OVERLAP_CLEAN"
    assert audit["split_name"] == "smoke"
    assert audit["manifest_rows"] == 4
    assert audit["overlap_summary"]["selected_overlaps_by_key"]["sample_id"] == 0
    assert "gsm8k-00000" not in {row["sample_id"] for row in manifest}
    assert {row["split_role"] for row in manifest} == {"smoke"}


def test_dense_target_reliability_gate_requires_variance_beyond_binary() -> None:
    rows = []
    for index in range(40):
        rows.append(
            {
                "sample_id": f"gsm8k-{index:05d}",
                "task_type": "gsm8k",
                "utility": (index % 20) / 20,
                "binary_correct": index % 2 == 0,
                "delta_u": 0.1 if index < 12 else 0.0,
            }
        )
        rows.append(
            {
                "sample_id": f"hotpotqa-{index:05d}",
                "task_type": "hotpotqa",
                "utility": (index % 25) / 25,
                "binary_correct": index % 3 == 0,
                "delta_u": 0.2 if index < 16 else 0.0,
            }
        )

    report = build_dense_target_reliability_report(rows)

    assert report["status"] == "V3_DENSE_TARGET_RELIABILITY_PASS"
    assert report["per_task"]["gsm8k"]["gate_pass"] is True
    assert report["per_task"]["hotpotqa"]["gate_pass"] is True
    assert report["per_task"]["gsm8k"]["nonzero_delta_fraction"] >= 0.25
    assert report["per_task"]["hotpotqa"]["nonzero_delta_fraction"] >= 0.35


def test_w_struct_feature_rows_reject_target_side_leakage() -> None:
    clean = [
        {
            "sample_id": "gsm8k-00001",
            "span_index": 0,
            "features": {
                "raw_local_utility": 0.4,
                "structural_necessity": 0.3,
                "raw_structural_interaction": 0.12,
                "redundancy": 0.2,
                "compensation": 0.1,
                "bottleneck_flag": 1,
                "span_type": "verification",
                "relative_position": 0.5,
                "span_length": 12,
                "task_type": "gsm8k",
                "question_difficulty_proxy": 0.4,
            },
            "source_fields_used": [
                "observable_trace",
                "reflection_spans",
                "structural_diagnostics",
                "redundancy_analysis",
            ],
        }
    ]
    leaked = [
        {
            **clean[0],
            "source_fields_used": [*clean[0]["source_fields_used"], "delta_u"],
        }
    ]

    assert validate_w_struct_feature_rows(clean)["status"] == "clean"
    assert validate_w_struct_feature_rows(leaked)["status"] == "target_leaking"


def test_v3_decision_tree_separates_global_task_specific_and_downstream_claims() -> None:
    global_report = build_v3_decision_report(
        task_gate_pass={"gsm8k": True, "hotpotqa": True},
        pooled_gate_pass=True,
        paired_improvement_ci95=[0.01, 0.08],
        blockers=[],
        downstream_gate_pass=False,
    )
    task_specific = build_v3_decision_report(
        task_gate_pass={"gsm8k": True, "hotpotqa": False},
        pooled_gate_pass=True,
        paired_improvement_ci95=[0.01, 0.08],
        blockers=[],
        downstream_gate_pass=False,
    )
    blocked = build_v3_decision_report(
        task_gate_pass={"gsm8k": True, "hotpotqa": True},
        pooled_gate_pass=True,
        paired_improvement_ci95=[0.01, 0.08],
        blockers=["leakage"],
        downstream_gate_pass=True,
    )

    assert global_report["status"] == V3_GLOBAL_PASS
    assert global_report["diagnostic_validation_claim_allowed"] is True
    assert global_report["prm_filtering_improvement_claim_allowed"] is False
    assert task_specific["status"] == V3_TASK_SPECIFIC_ONLY
    assert task_specific["global_claim_allowed"] is False
    assert blocked["status"] == "REAL_TASK_V3_VALIDATION_FAIL"
    assert blocked["diagnostic_validation_claim_allowed"] is False


def test_real_task_v3_manifest_script_rejects_execution_scope_drift() -> None:
    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))

    assert _assert_current_task_boundary(config, task_scope=REAL_TASK_V3_PREREGISTRATION_ONLY) is None

    bad = dict(config)
    bad["execution_boundary"] = {
        **config["execution_boundary"],
        "api_execution_allowed": True,
    }

    try:
        _assert_current_task_boundary(bad, task_scope=REAL_TASK_V3_PREREGISTRATION_ONLY)
    except RuntimeError as exc:
        assert "api_execution_allowed" in str(exc)
    else:
        raise AssertionError("expected execution boundary drift to be rejected")
