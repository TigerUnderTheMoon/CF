from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot import openai_client
from fma.real_task_pilot.fresh_preflight import (
    PREFLIGHT_FAIL_DRIFT,
    PREFLIGHT_FAIL_SCHEMA_OR_TAGS,
)
from fma.real_task_pilot.fresh_preflight_v2_1 import (
    V2_1_API_PREFLIGHT_ONLY,
    V2_1PreflightError,
    build_v2_1_generation_config,
    build_v2_1_preflight_report,
    validate_v2_1_preflight_readiness,
)
from fma.real_task_pilot.metrics import normalized_token_f1
from fma.real_task_pilot.fresh_holdout_v2_1 import (
    V2_1_CONTRACT_CLEAN,
    build_v2_1_api_preflight_approval_request,
    build_v2_1_contract_audit,
    build_v2_1_fresh_holdout_manifest,
    score_v2_1_answer,
    sort_v2_1_eligible_items,
)
from fma.real_task_pilot.generation import normalize_trace_record
from fma.real_task_pilot.schema import validate_trace_record
from scripts import run_s_fma_v2_1_fresh_holdout_preflight as v2_1_preflight_runner
from scripts.generate_s_fma_v2_1_fresh_holdout_manifest import _assert_current_task_boundary


def _v2_1_config(sample_count: int = 1) -> dict:
    return {
        "experiment": {
            "name": "s_fma_v2_1_fresh_holdout",
            "status": "planned",
            "seed": 20260603,
            "no_api_execution_without_user_approval": True,
            "no_api_run_in_current_task": True,
            "no_full_api_generation_in_current_task": True,
            "no_v2_scoring_in_current_task": True,
            "no_replay_in_current_task": True,
            "user_approved_budget_usd": None,
            "current_task_scope": "evidence_target_revision_non_api",
        },
        "target_policy": {
            "target_name": "graded_delta_u_v2_1",
            "task_targets": {
                "hotpotqa": {
                    "primary_score_field": "normalized_token_f1",
                    "llm_judge_allowed": False,
                },
                "gsm8k": {
                    "primary_score_field": "exact_match_numeric",
                    "graded_numeric_judge_allowed": False,
                },
            },
        },
        "fresh_selection_policy": {
            "non_overlap_required": True,
            "required_non_overlap_keys": [
                "sample_id",
                "task_id",
                "dataset_config_split_source_index",
                "normalized_question_hash",
                "reference_answer_hash",
                "non_empty_alias_hash",
            ],
            "forbidden_selection_fields": [
                "correctness",
                "original_score",
                "intervened_score",
                "delta_u",
                "replay_outcome",
                "final_answer",
                "reference_answer_similarity_after_generation",
                "rank_signal",
                "target_outcome",
            ],
            "tasks": {
                "gsm8k": {
                    "dataset": "gsm8k",
                    "config": "main",
                    "split": "test",
                    "sample_count": sample_count,
                    "unsaturated_selection": {
                        "policy": "rank_fresh_candidates_by_question_difficulty_proxy_desc",
                        "proxy_helper": "fma.real_task_pilot.baselines.question_difficulty_proxy",
                        "tie_breakers": ["manifest_item_hash", "source_index"],
                        "target_outcomes_allowed_for_selection": False,
                    },
                },
                "hotpotqa": {
                    "dataset": "hotpot_qa",
                    "config": "distractor",
                    "split": "validation",
                    "sample_count": sample_count,
                    "selection_policy": "deterministic_non_overlapping_manifest_order",
                    "target_outcomes_allowed_for_selection": False,
                },
            },
        },
        "span_diversity_policy": {
            "prompt_file": "prompts/s_fma_v2_1_reflection_generation.txt",
            "prompt_snapshot_required": True,
            "prompt_version_lock_required": True,
            "future_prompt_requirements": {
                "visible_text_only": True,
                "hidden_reasoning_forbidden": True,
                "reflection_blocks_requested": 2,
                "required_blocks": [
                    {"operation_type": "verification"},
                    {
                        "operation_type_group": "non_verification",
                        "allowed_types": [
                            "error_diagnosis",
                            "plan_revision",
                            "self-evaluation",
                            "uncertainty_monitoring",
                        ],
                    },
                ],
            },
            "target_span_policy": {
                "max_target_spans_per_trace": 2,
                "include_first_verification_span": True,
                "include_first_non_verification_span": True,
                "eligible_non_verification_types": [
                    "error_diagnosis",
                    "plan_revision",
                    "self-evaluation",
                    "uncertainty_monitoring",
                ],
            },
            "reporting": {
                "report_operation_type_distribution": True,
                "report_non_verification_span_count_by_task": True,
                "keep_trajectory_controls_separate_from_span_attribution": True,
            },
        },
        "smoke_gate": {
            "api_authorized_by_this_config": False,
            "requires_explicit_budget_approval": True,
            "sample_count_by_task": {"gsm8k": 10, "hotpotqa": 10},
            "min_nonzero_delta_u_per_task": 1,
            "min_nonzero_delta_u_pooled": 3,
        },
        "claim_policy": {
            "current_status_must_remain": [
                "PILOT_BLOCKED",
                "v2_1_planned_only",
                "no_api_authorized",
                "no_v2_1_validation",
                "no_prm_claim",
            ],
        },
        "future_execution_boundary": {"api_calls_authorized": False},
    }


def test_v2_1_hotpotqa_primary_score_uses_normalized_token_f1_not_exact_match() -> None:
    result = score_v2_1_answer(
        "hotpotqa",
        "The United States of America",
        "United States",
        aliases=[],
    )

    assert result["primary_score_field"] == "normalized_token_f1"
    assert result["exact_match"] is False
    assert result["primary_score"] == pytest.approx(
        normalized_token_f1("The United States of America", "United States")
    )
    assert 0.0 < result["primary_score"] < 1.0


def test_v2_1_hotpotqa_normalization_ignores_articles_and_punctuation() -> None:
    result = score_v2_1_answer("hotpotqa", "The Red, Planet!", "red planet")

    assert result["primary_score"] == 1.0
    assert result["normalized_token_f1"] == 1.0


def test_v2_1_gsm8k_selection_ranks_by_pre_outcome_difficulty_proxy() -> None:
    source_rows = {
        "gsm8k": [
            {
                "source_index": 1,
                "task_id": "gsm8k-test-00001",
                "question": "What is 2 + 2?",
                "reference_answer": "#### 4",
                "aliases": [],
            },
            {
                "source_index": 2,
                "task_id": "gsm8k-test-00002",
                "question": "Alice has 10 Blue boxes, Bob has 20 Red boxes, and Carl has 30 Green boxes. How many boxes are there after 5 more arrive?",
                "reference_answer": "#### 65",
                "aliases": [],
            },
            {
                "source_index": 3,
                "task_id": "gsm8k-test-00003",
                "question": "Mira has one apple.",
                "reference_answer": "#### 1",
                "aliases": [],
            },
        ],
        "hotpotqa": [
            {
                "source_index": 10,
                "task_id": "hotpot-test-00010",
                "question": "Who wrote Hamlet?",
                "reference_answer": "William Shakespeare",
                "aliases": ["Shakespeare"],
            }
        ],
    }

    manifest, audit = build_v2_1_fresh_holdout_manifest(
        source_rows,
        config=_v2_1_config(sample_count=1),
        overlap_sources={"pilot.json": []},
        prompt_version="prompt-sha256:test",
    )

    gsm8k = [row for row in manifest if row["task_type"] == "gsm8k"]
    assert audit["status"] == "MANIFEST_OVERLAP_CLEAN"
    assert len(gsm8k) == 1
    assert gsm8k[0]["source_index"] == 2
    assert gsm8k[0]["selection_policy"] == "rank_fresh_candidates_by_question_difficulty_proxy_desc"
    assert set(gsm8k[0]["question_difficulty_proxy"]["features"]) == {
        "question_length",
        "number_count",
        "entity_count",
        "supporting_fact_count",
    }
    assert gsm8k[0]["forbidden_selection_fields_used"] == []
    assert "correctness" not in gsm8k[0]["selection_source_fields_used"]


def test_v2_1_gsm8k_ties_sort_by_manifest_hash_then_source_index() -> None:
    rows = [
        {"task_type": "gsm8k", "question_difficulty_proxy": {"score": 0.5}, "manifest_item_hash": "sha256:b", "source_index": 1},
        {"task_type": "gsm8k", "question_difficulty_proxy": {"score": 0.7}, "manifest_item_hash": "sha256:z", "source_index": 2},
        {"task_type": "gsm8k", "question_difficulty_proxy": {"score": 0.5}, "manifest_item_hash": "sha256:a", "source_index": 9},
        {"task_type": "gsm8k", "question_difficulty_proxy": {"score": 0.5}, "manifest_item_hash": "sha256:a", "source_index": 3},
    ]

    ordered = sort_v2_1_eligible_items("gsm8k", rows)

    assert [row["source_index"] for row in ordered] == [2, 3, 9, 1]


def test_v2_1_manifest_audit_checks_all_six_required_overlap_keys() -> None:
    source_rows = {
        "gsm8k": [
            {
                "source_index": 7,
                "task_id": "same-task",
                "question": "Same question?",
                "reference_answer": "#### 5",
                "aliases": ["same alias"],
            }
        ],
        "hotpotqa": [
            {
                "source_index": 8,
                "task_id": "fresh-hotpot",
                "question": "Fresh hotpot?",
                "reference_answer": "fresh",
                "aliases": [],
            }
        ],
    }
    overlap_sources = {
        "pilot.json": [
            {
                "sample_id": "gsm8k-00007",
                "task_id": "same-task",
                "source_dataset": "gsm8k",
                "source_config": "main",
                "source_split": "test",
                "source_index": 7,
                "question": "same question?",
                "reference_answer": "#### 5",
                "aliases": ["same alias"],
            }
        ]
    }

    manifest, audit = build_v2_1_fresh_holdout_manifest(
        source_rows,
        config=_v2_1_config(sample_count=1),
        overlap_sources=overlap_sources,
        prompt_version="prompt-sha256:test",
    )

    assert manifest == []
    assert audit["status"] == "BLOCKED_INSUFFICIENT_FRESH_ROWS"
    assert audit["hard_stop"] is True
    assert audit["required_non_overlap_keys"] == [
        "sample_id",
        "task_id",
        "dataset_config_split_source_index",
        "normalized_question_hash",
        "reference_answer_hash",
        "alias_hash",
    ]
    assert audit["overlap_summary"]["candidate_pool_overlaps_by_key"] == {
        "sample_id": 1,
        "task_id": 1,
        "dataset_config_split_source_index": 1,
        "normalized_question_hash": 1,
        "reference_answer_hash": 1,
        "alias_hash": 1,
    }


def test_v2_1_contract_audit_enforces_prompt_span_smoke_and_no_api_policy() -> None:
    prompt_text = """
Return visible text only.
<reflection type="verification">...</reflection>
<reflection type="error_diagnosis">...</reflection>
Do not include hidden reasoning.
"""

    audit = build_v2_1_contract_audit(
        config=_v2_1_config(sample_count=1),
        plan_text="PILOT_BLOCKED normalized_token_f1 question_difficulty_proxy",
        prompt_text=prompt_text,
        prompt_version="prompt-sha256:test",
        manifest_audit={"status": "MANIFEST_OVERLAP_CLEAN", "overlap_clean": True},
    )

    assert audit["status"] == V2_1_CONTRACT_CLEAN
    assert audit["current_status_remains"] == "PILOT_BLOCKED"
    assert audit["no_api_run"] is True
    assert audit["no_v2_1_scoring"] is True
    assert audit["checks"]["hotpotqa_primary_target"]["status"] == "clean"
    assert audit["checks"]["gsm8k_selection_policy"]["status"] == "clean"
    assert audit["checks"]["prompt_policy"]["status"] == "clean"
    assert audit["checks"]["span_diversity_policy"]["status"] == "clean"
    assert audit["checks"]["smoke_gate"]["details"]["min_nonzero_delta_u_per_task"] == 1
    assert audit["checks"]["smoke_gate"]["details"]["min_nonzero_delta_u_pooled"] == 3
    assert audit["claim_upgrade_allowed"] is False


def test_v2_1_generator_boundary_rejects_api_replay_or_scoring_scope() -> None:
    config = _v2_1_config()
    config["experiment"]["no_replay_in_current_task"] = False

    with pytest.raises(RuntimeError, match="no_replay_in_current_task"):
        _assert_current_task_boundary(config)


def test_v2_1_api_preflight_readiness_requires_scope_guard_budget_and_clean_contract() -> None:
    config = _v2_1_config(sample_count=200)
    manifest = _v2_1_manifest_rows(per_task=200)

    with pytest.raises(V2_1PreflightError, match="--allow-api-preflight-only"):
        validate_v2_1_preflight_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=_v2_1_clean_overlap_audit(),
            contract_audit=_v2_1_clean_contract_audit(),
            approval_request=_v2_1_approval_request(),
            current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
            allow_api_preflight_only=False,
            approved_budget_usd=2,
        )

    bad_approval = _v2_1_approval_request()
    bad_approval["requested_scope"] = "SMOKE_ONLY"
    with pytest.raises(V2_1PreflightError, match=V2_1_API_PREFLIGHT_ONLY):
        validate_v2_1_preflight_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=_v2_1_clean_overlap_audit(),
            contract_audit=_v2_1_clean_contract_audit(),
            approval_request=bad_approval,
            current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
            allow_api_preflight_only=True,
            approved_budget_usd=2,
        )

    readiness = validate_v2_1_preflight_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=_v2_1_clean_overlap_audit(),
        contract_audit=_v2_1_clean_contract_audit(),
        approval_request=_v2_1_approval_request(),
        current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
        allow_api_preflight_only=True,
        approved_budget_usd=2,
    )

    assert readiness["api_call_allowed"] is True
    assert readiness["scope"] == V2_1_API_PREFLIGHT_ONLY
    assert readiness["approved_budget_usd"] == 2
    assert readiness["max_api_requests"] == 25
    assert readiness["selected_records"] == 20
    assert readiness["selected_counts_by_task"] == {"gsm8k": 10, "hotpotqa": 10}
    assert readiness["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_1_preflight_rejects_stale_prompt_locked_artifacts() -> None:
    config = _v2_1_config(sample_count=200)
    manifest = [
        {**row, "prompt_version": "prompt-sha256:old"}
        for row in _v2_1_manifest_rows(per_task=200)
    ]
    contract_audit = {
        **_v2_1_clean_contract_audit(),
        "prompt_version": "prompt-sha256:old",
    }

    with pytest.raises(V2_1PreflightError, match="prompt version lock mismatch"):
        validate_v2_1_preflight_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=_v2_1_clean_overlap_audit(),
            contract_audit=contract_audit,
            approval_request=_v2_1_approval_request(),
            current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
            allow_api_preflight_only=True,
            approved_budget_usd=2,
            current_prompt_version="prompt-sha256:new",
        )


def test_v2_1_prompt_and_config_use_schema_canonical_self_evaluation() -> None:
    config = load_pilot_config(Path("configs/s_fma_v2_1_fresh_holdout.yaml"))
    prompt = Path("prompts/s_fma_v2_1_reflection_generation.txt").read_text(encoding="utf-8")
    allowed_types = config["span_diversity_policy"]["future_prompt_requirements"][
        "required_blocks"
    ][1]["allowed_types"]
    eligible_types = config["span_diversity_policy"]["target_span_policy"][
        "eligible_non_verification_types"
    ]

    assert "self-evaluation" in prompt
    assert "self_evaluation" not in prompt
    assert "self-evaluation" in allowed_types
    assert "self_evaluation" not in allowed_types
    assert "self-evaluation" in eligible_types
    assert "self_evaluation" not in eligible_types


def test_v2_1_approval_request_is_request_only_and_prompt_locked() -> None:
    prompt_version = "prompt-sha256:test"
    request = build_v2_1_api_preflight_approval_request(
        config=_v2_1_config(sample_count=200),
        manifest_audit=_v2_1_clean_overlap_audit(),
        contract_audit={
            **_v2_1_clean_contract_audit(),
            "prompt_version": prompt_version,
        },
        prompt_version=prompt_version,
        output_root=Path("outputs") / "s_fma_v2_1_fresh_holdout",
    )

    assert request["requested_scope"] == V2_1_API_PREFLIGHT_ONLY
    assert request["approval_status"] == "REQUEST_ONLY_NOT_APPROVED"
    assert request["request_valid_for_review"] is True
    assert request["api_execution_authorized_by_this_request"] is False
    assert request["api_execution_performed_by_package_regeneration"] is False
    assert request["prompt_version"] == prompt_version
    assert request["recommended_budget_ceiling_usd"] == 2
    assert request["max_api_requests"] == 25
    assert "smoke" in request["forbidden_in_this_approval_request"]
    assert request["claim_boundary"]["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_1_api_preflight_report_keeps_smoke_as_request_only_after_clean_schema_with_drift() -> None:
    readiness = {
        "approved_budget_usd": 2,
        "max_api_requests": 25,
        "selected_records": 20,
        "scope": V2_1_API_PREFLIGHT_ONLY,
    }
    report = build_v2_1_preflight_report(
        [_v2_1_valid_attempt(f"gsm8k-{index:05d}") for index in range(20)],
        selected_records=_v2_1_manifest_rows(per_task=10),
        drift_outputs=["alpha beta gamma", "alpha totally different gamma"],
        config=build_v2_1_generation_config(_v2_1_config(sample_count=200), readiness=readiness),
        readiness=readiness,
    )

    assert report["status"] == PREFLIGHT_FAIL_DRIFT
    assert report["scope"] == V2_1_API_PREFLIGHT_ONLY
    assert report["json_parse_success_rate"] == 1.0
    assert report["schema_success_rate"] == 1.0
    assert report["tag_extraction_success_rate"] == 1.0
    assert report["final_answer_parse_success_rate"] == 1.0
    assert report["v2_1_smoke_approval_request_allowed"] is False
    assert report["v2_1_smoke_approval_request_scope"] == "not_allowed"
    assert report["no_smoke"] is True
    assert report["no_replay"] is True
    assert report["no_v2_1_scoring"] is True
    assert report["task_specific_pass_claim_allowed"] is False
    assert report["global_pass_claim_allowed"] is False
    assert report["claim_upgrade_allowed"] is False


def test_v2_1_normalizes_self_evaluation_alias_before_schema_validation() -> None:
    trace = (
        "Initial answer. "
        '<reflection type="verification">Check the arithmetic.</reflection> '
        '<reflection type="self_evaluation">The setup is direct.</reflection> '
        "Final Answer: 5"
    )

    record = normalize_trace_record(
        {"observable_trace": trace, "final_answer": "5"},
        sample={
            "sample_id": "gsm8k-00001",
            "task_id": "gsm8k-00001",
            "task_type": "gsm8k",
            "question": "What is 2 + 3?",
            "reference_answer": "#### 5",
            "aliases": [],
        },
        model_name="gpt-5.5",
        generation_config={"structured_output_mode": "json_schema"},
        system_fingerprint=None,
        usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
    )

    self_eval_span = record["reflection_spans"][1]
    assert validate_trace_record(record) == []
    assert self_eval_span["operation_type"] == "self-evaluation"
    assert self_eval_span["content"] == "The setup is direct."
    assert trace[self_eval_span["content_start_char"]:self_eval_span["content_end_char"]] == (
        "The setup is direct."
    )
    assert trace[self_eval_span["start_char"]:self_eval_span["end_char"]] == (
        '<reflection type="self_evaluation">The setup is direct.</reflection>'
    )
    assert record["generation_config"]["reflection_type_normalization"] == [
        {
            "span_index": 1,
            "raw_operation_type": "self_evaluation",
            "canonical_operation_type": "self-evaluation",
        }
    ]


def test_v2_1_invalid_reflection_type_still_fails_schema_validation() -> None:
    record = normalize_trace_record(
        {
            "observable_trace": (
                "Initial answer. "
                '<reflection type="not_a_valid_type">Bad enum.</reflection> '
                "Final Answer: 5"
            ),
            "final_answer": "5",
        },
        sample={
            "sample_id": "gsm8k-00001",
            "task_id": "gsm8k-00001",
            "task_type": "gsm8k",
            "question": "What is 2 + 3?",
            "reference_answer": "#### 5",
            "aliases": [],
        },
        model_name="gpt-5.5",
        generation_config={"structured_output_mode": "json_schema"},
        system_fingerprint=None,
        usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
    )

    assert record["reflection_spans"][0]["operation_type"] == "not_a_valid_type"
    assert any("operation_type" in error for error in validate_trace_record(record))


def test_v2_1_schema_failure_status_takes_precedence_over_drift_and_metadata() -> None:
    readiness = {
        "approved_budget_usd": 2,
        "max_api_requests": 25,
        "selected_records": 20,
        "scope": V2_1_API_PREFLIGHT_ONLY,
    }
    attempts = [_v2_1_valid_attempt(f"gsm8k-{index:05d}") for index in range(19)]
    invalid = _v2_1_valid_attempt("gsm8k-00019")
    invalid["record"]["reflection_spans"][0]["operation_type"] = "not_a_valid_type"
    invalid["record"]["generation_config"].pop("sdk_version")
    attempts.append(invalid)

    report = build_v2_1_preflight_report(
        attempts,
        selected_records=_v2_1_manifest_rows(per_task=10),
        drift_outputs=["alpha beta gamma", "alpha totally different gamma"],
        config=build_v2_1_generation_config(_v2_1_config(sample_count=200), readiness=readiness),
        readiness=readiness,
    )

    assert report["status"] == PREFLIGHT_FAIL_SCHEMA_OR_TAGS
    assert "PREFLIGHT_FAIL_SCHEMA" in report["failure_codes"]
    assert "PREFLIGHT_FAIL_DRIFT" in report["failure_codes"]
    assert "PREFLIGHT_FAIL_METADATA" in report["failure_codes"]
    assert report["drift_status"] == PREFLIGHT_FAIL_DRIFT
    assert report["metadata_missing_counts"]["sdk_or_transport_version"] == 1
    assert report["v2_1_smoke_approval_request_allowed"] is False
    assert report["next_allowed_step"] == "STOP_AND_FIX_PREFLIGHT"


def test_v2_1_api_preflight_schema_failure_blocks_smoke_approval_request() -> None:
    readiness = {
        "approved_budget_usd": 2,
        "max_api_requests": 25,
        "selected_records": 20,
        "scope": V2_1_API_PREFLIGHT_ONLY,
    }
    attempts = [_v2_1_valid_attempt(f"gsm8k-{index:05d}") for index in range(19)]
    invalid = _v2_1_valid_attempt("gsm8k-00019")
    invalid["record"]["final_answer"] = ""
    invalid["record"]["observable_trace"] = (
        "Compute 2 + 3. "
        '<reflection type="verification">Check arithmetic.</reflection>'
    )
    attempts.append(invalid)

    report = build_v2_1_preflight_report(
        attempts,
        selected_records=_v2_1_manifest_rows(per_task=10),
        drift_outputs=["same trace", "same trace"],
        config=build_v2_1_generation_config(_v2_1_config(sample_count=200), readiness=readiness),
        readiness=readiness,
    )

    assert report["status"] == PREFLIGHT_FAIL_SCHEMA_OR_TAGS
    assert "PREFLIGHT_FAIL_FINAL_ANSWER" in report["failure_codes"]
    assert report["v2_1_smoke_approval_request_allowed"] is False
    assert report["next_allowed_step"] == "STOP_AND_FIX_PREFLIGHT"


def test_responses_adapter_extracts_model_dump_output_text_with_diagnostics() -> None:
    response = _FakeResponsesObject(
        output_text="",
        response_id="resp_text",
        usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        output=[{"content": [{"text": '{"observable_trace":"ok"}'}]}],
    )

    result = openai_client._result_from_response(  # noqa: SLF001
        response,
        request_metadata={"retry_label": "full"},
    )

    assert result.output_text == '{"observable_trace":"ok"}'
    diagnostics = result.output_extraction_diagnostics
    assert diagnostics["fallback_used"] is True
    assert diagnostics["output_text_present"] is False
    assert diagnostics["extracted_text_empty"] is False
    assert diagnostics["response_id_present"] is True
    assert diagnostics["usage_present"] is True
    assert diagnostics["text_segment_count"] == 1


def test_v2_1_runner_extracts_typed_response_content_objects() -> None:
    response = _FakeResponsesObject(
        output_text="",
        response_id="resp_typed",
        usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        output=[_FakeOutput([_FakeContent('{"observable_trace":"typed"}')])],
    )

    result = v2_1_preflight_runner._api_result_from_response(  # noqa: SLF001
        response,
        request_metadata={"single_request_preflight": True},
    )

    assert result.output_text == '{"observable_trace":"typed"}'
    diagnostics = result.output_extraction_diagnostics
    assert diagnostics["fallback_used"] is True
    assert diagnostics["content_item_kinds"] == ["_FakeContent"]
    assert diagnostics["text_segment_count"] == 1


def test_responses_adapter_records_empty_output_extraction_diagnostics() -> None:
    response = _FakeResponsesObject(
        output_text="",
        response_id="resp_empty",
        usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        output=[{"content": [{"type": "output_text"}]}],
    )

    result = openai_client._result_from_response(  # noqa: SLF001
        response,
        request_metadata={"retry_label": "full"},
    )

    assert result.output_text == ""
    assert result.response_id == "resp_empty"
    assert result.usage["total_tokens"] == 30
    diagnostics = result.output_extraction_diagnostics
    assert diagnostics["extracted_text_empty"] is True
    assert diagnostics["response_id_present"] is True
    assert diagnostics["usage_present"] is True
    assert diagnostics["output_item_count"] == 1
    assert diagnostics["content_item_count"] == 1
    assert diagnostics["text_segment_count"] == 0


def test_v2_1_preflight_report_classifies_all_empty_raw_output_as_transport_failure() -> None:
    readiness = {
        "approved_budget_usd": 2,
        "max_api_requests": 25,
        "selected_records": 20,
        "scope": V2_1_API_PREFLIGHT_ONLY,
    }
    attempts = [
        {
            "preflight_attempt": True,
            "attempt_role": "preflight_record",
            "record": None,
            "raw_output": "",
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            "model_name": "gpt-5.5",
            "structured_output_mode": "json_schema",
            "response_id": f"resp_empty_{index}",
            "validation_errors": ["<root>: response is not a JSON object"],
            "fallback_events": [
                {
                    "model_name": "gpt-5.5",
                    "structured_output_mode": "json_schema",
                    "status": "invalid_output",
                    "validation_errors": ["<root>: response is not a JSON object"],
                }
            ],
        }
        for index in range(20)
    ]

    report = build_v2_1_preflight_report(
        attempts,
        selected_records=_v2_1_manifest_rows(per_task=10),
        drift_outputs=["", ""],
        config=build_v2_1_generation_config(_v2_1_config(sample_count=200), readiness=readiness),
        readiness=readiness,
    )

    assert report["status"] == "PREFLIGHT_FAIL_EMPTY_OUTPUT"
    assert "PREFLIGHT_FAIL_EMPTY_OUTPUT" in report["failure_codes"]
    assert "PREFLIGHT_FAIL_OUTPUT_EXTRACTION" in report["failure_codes"]
    assert report["empty_output_summary"]["raw_output_empty_count"] == 20
    assert report["empty_output_summary"]["any_nonempty_raw_output"] is False
    assert report["root_cause_classification"] == "transport_or_output_extraction_failure_suspected"
    assert report["v2_1_smoke_approval_request_allowed"] is False
    assert report["next_allowed_step"] == "STOP_AND_FIX_OUTPUT_EXTRACTION"


def test_current_v2_1_preflight_report_remains_drift_failed_not_ready() -> None:
    report = json.loads(
        Path("outputs/s_fma_v2_1_fresh_holdout/api_preflight_report.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["status"] == PREFLIGHT_FAIL_DRIFT
    assert report["json_parse_success_rate"] == 1.0
    assert report["schema_success_rate"] == 1.0
    assert report["tag_extraction_success_rate"] == 1.0
    assert report["final_answer_parse_success_rate"] == 1.0
    assert report["empty_output_summary"]["raw_output_nonempty_count"] == 20
    assert report["root_cause_classification"] == "not_empty_output_failure"
    assert report["v2_1_smoke_approval_request_allowed"] is False
    assert report["deterministic_replay_claim_allowed"] is False
    assert report["next_allowed_step"] == "STOP_AND_FIX_PREFLIGHT"
    assert report["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_1_preflight_cli_requires_approved_budget_before_adapter(monkeypatch) -> None:
    def fail_if_instantiated() -> None:
        raise AssertionError("adapter must not be instantiated before required budget is parsed")

    monkeypatch.setattr(v2_1_preflight_runner, "SingleRequestOpenAITraceAdapter", fail_if_instantiated)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_s_fma_v2_1_fresh_holdout_preflight.py",
            "--config",
            "configs/s_fma_v2_1_fresh_holdout.yaml",
            "--allow-api-preflight-only",
        ],
    )

    with pytest.raises(SystemExit):
        v2_1_preflight_runner.main()


def test_v2_1_transport_canary_runner_contract_exists_and_uses_independent_paths() -> None:
    runner = _transport_canary_runner()

    paths = runner.transport_canary_paths(Path("outputs") / "s_fma_v2_1_fresh_holdout")

    assert paths["report"] == Path("outputs/s_fma_v2_1_fresh_holdout/transport_canary_report.json")
    assert paths["attempts"] == Path("outputs/s_fma_v2_1_fresh_holdout/transport_canary_attempts.jsonl")
    assert paths["traces"] == Path("outputs/s_fma_v2_1_fresh_holdout/transport_canary_traces.jsonl")
    assert paths["cost"] == Path("outputs/s_fma_v2_1_fresh_holdout/logs/transport_canary_cost_report.json")


def test_v2_1_transport_canary_readiness_requires_guard_budget_and_clean_package() -> None:
    runner = _transport_canary_runner()
    config = _v2_1_config(sample_count=200)
    manifest = [
        {**row, "prompt_version": "prompt-sha256:test"}
        for row in _v2_1_manifest_rows(per_task=200)
    ]
    contract_audit = {
        **_v2_1_clean_contract_audit(),
        "prompt_version": "prompt-sha256:test",
    }

    with pytest.raises(runner.TransportCanaryError, match="--allow-transport-canary-only"):
        runner.validate_transport_canary_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=_v2_1_clean_overlap_audit(),
            contract_audit=contract_audit,
            approval_request=_v2_1_approval_request(),
            empty_output_failure_audit=_v2_1_empty_output_failure_audit(),
            current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
            allow_transport_canary_only=False,
            approved_budget_usd=0.5,
            current_prompt_version="prompt-sha256:test",
        )

    with pytest.raises(runner.TransportCanaryError, match="0.5"):
        runner.validate_transport_canary_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=_v2_1_clean_overlap_audit(),
            contract_audit=contract_audit,
            approval_request=_v2_1_approval_request(),
            empty_output_failure_audit=_v2_1_empty_output_failure_audit(),
            current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
            allow_transport_canary_only=True,
            approved_budget_usd=2.0,
            current_prompt_version="prompt-sha256:test",
        )

    readiness = runner.validate_transport_canary_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=_v2_1_clean_overlap_audit(),
        contract_audit=contract_audit,
        approval_request=_v2_1_approval_request(),
        empty_output_failure_audit=_v2_1_empty_output_failure_audit(),
        current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
        allow_transport_canary_only=True,
        approved_budget_usd=0.5,
        current_prompt_version="prompt-sha256:test",
    )

    assert readiness["scope"] == "TRANSPORT_CANARY_ONLY"
    assert readiness["api_call_allowed"] is True
    assert readiness["approved_budget_usd"] == 0.5
    assert readiness["max_api_requests"] == 3
    assert readiness["selected_records"] == 2
    assert readiness["selected_counts_by_task"] == {"gsm8k": 1, "hotpotqa": 1}
    assert readiness["historical_preflight_report_used_as_ready_evidence"] is False
    assert readiness["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_1_transport_canary_report_passes_transport_only_with_partial_parse_success() -> None:
    runner = _transport_canary_runner()
    readiness = _transport_canary_readiness()
    selected = _v2_1_manifest_rows(per_task=1)
    valid = _v2_1_valid_attempt("gsm8k-00000")
    valid["output_extraction_diagnostics"] = {
        "fallback_used": True,
        "extracted_text_empty": False,
    }
    empty = _v2_1_empty_attempt("hotpotqa-00000")

    report = runner.build_transport_canary_report(
        [valid, empty],
        selected_records=selected,
        config=runner.build_transport_canary_generation_config(
            _v2_1_config(sample_count=200),
            readiness=readiness,
        ),
        readiness=readiness,
    )

    assert report["status"] == "TRANSPORT_CANARY_PASS"
    assert report["api_attempts"] == 2
    assert report["raw_output_nonempty_count"] == 1
    assert report["raw_output_nonempty_rate"] == 0.5
    assert report["output_extraction_diagnostics_complete"] is True
    assert report["json_parse_success_count"] == 1
    assert report["json_parse_success_rate"] == 0.5
    assert report["schema_success_rate"] == 0.5
    assert report["tag_extraction_success_rate"] == 0.5
    assert report["final_answer_parse_success_rate"] == 0.5
    assert report["api_preflight_rerun_approval_request_allowed"] is True
    assert report["api_preflight_rerun_allowed_without_approval"] is False
    assert report["transport_canary_only"] is True
    assert report["cost_report"]["transport_canary_only"] is True
    assert report["cost_report"]["preflight_only"] is False
    assert report["claim_upgrade_allowed"] is False
    assert report["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_1_transport_canary_report_fails_when_diagnostics_are_missing() -> None:
    runner = _transport_canary_runner()
    readiness = _transport_canary_readiness()
    attempt = _v2_1_valid_attempt("gsm8k-00000")
    attempt["output_extraction_diagnostics"] = {}

    report = runner.build_transport_canary_report(
        [attempt],
        selected_records=_v2_1_manifest_rows(per_task=1),
        config=runner.build_transport_canary_generation_config(
            _v2_1_config(sample_count=200),
            readiness=readiness,
        ),
        readiness=readiness,
    )

    assert report["status"] == "TRANSPORT_CANARY_FAIL_MISSING_DIAGNOSTICS"
    assert report["output_extraction_diagnostics_complete"] is False
    assert report["api_preflight_rerun_approval_request_allowed"] is False
    assert report["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_1_transport_canary_cli_requires_budget_before_adapter(monkeypatch) -> None:
    runner = _transport_canary_runner()

    def fail_if_instantiated() -> None:
        raise AssertionError("adapter must not be instantiated before required budget is parsed")

    monkeypatch.setattr(runner, "SingleRequestOpenAITraceAdapter", fail_if_instantiated)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_s_fma_v2_1_transport_canary.py",
            "--config",
            "configs/s_fma_v2_1_fresh_holdout.yaml",
            "--allow-transport-canary-only",
        ],
    )

    with pytest.raises(SystemExit):
        runner.main()


def _v2_1_manifest_rows(per_task: int) -> list[dict]:
    rows = []
    for task_type in ("gsm8k", "hotpotqa"):
        for index in range(per_task):
            rows.append(
                {
                    "sample_id": f"{task_type}-{index:05d}",
                    "task_id": f"{task_type}-task-{index}",
                    "task_type": task_type,
                    "question": "What is 2 + 3?",
                    "reference_answer": "#### 5",
                    "aliases": ["5"] if task_type == "hotpotqa" else [],
                }
            )
    return rows


def _v2_1_clean_overlap_audit() -> dict:
    return {
        "status": "MANIFEST_OVERLAP_CLEAN",
        "overlap_clean": True,
        "api_preflight_approval_request_only": True,
        "claim_upgrade_allowed": False,
        "current_status_remains": "PILOT_BLOCKED",
        "overlap_summary": {
            "selected_overlaps_by_key": {
                "sample_id": 0,
                "task_id": 0,
                "dataset_config_split_source_index": 0,
                "normalized_question_hash": 0,
                "reference_answer_hash": 0,
                "alias_hash": 0,
            }
        },
    }


def _v2_1_clean_contract_audit() -> dict:
    return {
        "status": V2_1_CONTRACT_CLEAN,
        "current_status_remains": "PILOT_BLOCKED",
        "claim_upgrade_allowed": False,
        "no_api_run": True,
        "no_replay": True,
        "no_v2_1_scoring": True,
        "no_prm_claim_yet": True,
        "blockers": [],
    }


def _v2_1_approval_request() -> dict:
    return {
        "requested_scope": V2_1_API_PREFLIGHT_ONLY,
        "current_status_remains": "PILOT_BLOCKED",
        "request_valid_for_review": True,
        "api_execution_authorized_by_this_request": False,
        "requested_records": 20,
        "records_per_task": {"gsm8k": 10, "hotpotqa": 10},
        "recommended_budget_ceiling_usd": 2,
        "max_api_requests": 25,
    }


def _v2_1_empty_output_failure_audit() -> dict:
    return {
        "audit_name": "s_FMA_v2.1 EMPTY_OUTPUT_TRANSPORT_FAILURE_AUDIT",
        "raw_output_audit": {
            "any_nonempty_raw_output": False,
            "raw_output_empty_count": 23,
            "raw_output_nonempty_count": 0,
        },
        "claim_boundary": {
            "current_status_remains": "PILOT_BLOCKED",
            "v2_1_evidence_signal_available": False,
        },
    }


def _transport_canary_readiness() -> dict:
    return {
        "scope": "TRANSPORT_CANARY_ONLY",
        "approved_budget_usd": 0.5,
        "max_api_requests": 3,
        "selected_records": 2,
        "selected_counts_by_task": {"gsm8k": 1, "hotpotqa": 1},
        "current_status_remains": "PILOT_BLOCKED",
    }


def _transport_canary_runner():
    module_name = "scripts.run_s_fma_v2_1_transport_canary"
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, "TRANSPORT_CANARY_ONLY runner module is missing"
    return importlib.import_module(module_name)


class _FakeUsage:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def model_dump(self) -> dict:
        return dict(self.payload)


class _FakeContent:
    def __init__(self, text: str | None = None) -> None:
        self.text = text


class _FakeOutput:
    def __init__(self, content: list) -> None:
        self.content = content


class _FakeResponsesObject:
    model = "gpt-5.5"
    system_fingerprint = None

    def __init__(
        self,
        *,
        output_text: str,
        response_id: str,
        usage: dict,
        output: list,
    ) -> None:
        self.output_text = output_text
        self.id = response_id
        self.usage = _FakeUsage(usage)
        self.output = output

    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "model": self.model,
            "output": self.output,
        }


def _v2_1_valid_attempt(sample_id: str) -> dict:
    record = {
        "sample_id": sample_id,
        "task_id": sample_id,
        "task_type": "gsm8k",
        "question": "What is 2 + 3?",
        "observable_trace": (
            "Compute 2 + 3 = 5. "
            '<reflection type="verification">Check the arithmetic before finalizing.</reflection> '
            "Final Answer: 5"
        ),
        "reflection_spans": [
            {
                "span_index": 0,
                "start_char": 19,
                "end_char": 99,
                "content_start_char": 51,
                "content_end_char": 92,
                "start_token": 5,
                "end_token": 11,
                "operation_type": "verification",
                "content": "Check the arithmetic before finalizing.",
            }
        ],
        "final_answer": "5",
        "reference_answer": "#### 5",
        "correctness": True,
        "model_name": "gpt-5.5",
        "generation_config": {
            "endpoint": "/v1/responses",
            "api_date": "2026-06-03",
            "sdk_version": "fake-openai-1.0",
            "service_tier": "default",
            "primary_model": "gpt-5.5",
            "fallback_order": ["gpt-5.5"],
            "temperature": 0,
            "max_output_tokens": 2048,
            "response_id": "resp_test",
            "api_request_metadata": {"seed_sent": False},
        },
        "system_fingerprint": None,
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
    }
    return {
        "preflight_attempt": True,
        "record": record,
        "raw_output": record,
        "usage": record["usage"],
        "model_name": "gpt-5.5",
        "system_fingerprint": None,
        "response_id": "resp_test",
        "validation_errors": [],
    }


def _v2_1_empty_attempt(sample_id: str) -> dict:
    return {
        "preflight_attempt": True,
        "attempt_role": "transport_canary_record",
        "sample_id": sample_id,
        "task_id": sample_id,
        "task_type": "hotpotqa",
        "record": None,
        "raw_output": "",
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        "model_name": "gpt-5.5",
        "structured_output_mode": "json_schema",
        "response_id": f"resp_{sample_id}",
        "output_extraction_diagnostics": {
            "fallback_used": True,
            "extracted_text_empty": True,
        },
        "validation_errors": ["<root>: response is not a JSON object"],
        "fallback_events": [],
    }
