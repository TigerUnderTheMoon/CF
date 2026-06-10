from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_preflight import PREFLIGHT_FAIL_DRIFT
from fma.real_task_pilot.fresh_holdout_v2_2 import (
    S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT,
    V2_2_CONTRACT_CLEAN,
    build_v2_2_contract_audit,
    build_v2_2_fresh_holdout_manifest,
)
from fma.real_task_pilot.fresh_preflight_v2_2 import (
    V2_2_API_PREFLIGHT_ONLY,
    V2_2PreflightError,
    build_v2_2_generation_config,
    build_v2_2_preflight_report,
    validate_v2_2_preflight_readiness,
)
from scripts.generate_s_fma_v2_2_fresh_holdout_manifest import _assert_current_task_boundary
from scripts.run_s_fma_v2_2_single_transport_retry import merge_single_retry_attempt


V2_2_GENERATION_PROMPT_PATH = Path("prompts/s_fma_v2_2_reflection_generation.txt")
V2_2_REPLAY_PROMPT_PATH = Path("prompts/s_fma_v2_2_replay.txt")
V2_2_CONTRACT_AUDIT_PATH = Path("outputs/archive/s_fma_v2_2_fresh_holdout/v2_2_contract_audit.json")
V2_2_APPROVAL_REQUEST_PATH = Path(
    "outputs/archive/s_fma_v2_2_fresh_holdout/api_preflight_approval_request.json"
)


def _v2_2_prompt_bundle_hash() -> str:
    payload = {
        "generation_prompt_file": V2_2_GENERATION_PROMPT_PATH.as_posix(),
        "generation_prompt_text": V2_2_GENERATION_PROMPT_PATH.read_text(encoding="utf-8"),
        "replay_prompt_file": V2_2_REPLAY_PROMPT_PATH.as_posix(),
        "replay_prompt_text": V2_2_REPLAY_PROMPT_PATH.read_text(encoding="utf-8"),
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "prompt-sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _v2_2_config(sample_count: int = 1) -> dict:
    return {
        "experiment": {
            "name": "s_fma_v2_2_fresh_holdout",
            "status": "planned_preregistration_only",
            "seed": 20260605,
            "output_dir": "outputs/archive/s_fma_v2_2_fresh_holdout",
            "plan_file": "paper/s_fma_v2_2_preregistration_plan.md",
            "transition_audit_file": "paper/v2_1_to_v2_2_transition_audit.md",
            "current_task_scope": "S_FMA_V2_2_PREREGISTRATION_ONLY_AFTER_FULL_VALIDATION_FAILURE",
            "no_api_execution_without_user_approval": True,
            "no_api_run_in_current_task": True,
            "no_manifest_generation_in_current_task": True,
            "no_full_api_generation_in_current_task": True,
            "no_replay_in_current_task": True,
            "no_scoring_in_current_task": True,
            "no_prm_filtering_in_current_task": True,
            "user_approved_budget_usd": None,
        },
        "provenance_boundary": {
            "current_project_status": "PILOT_BLOCKED",
            "source_status": "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS",
            "source_artifacts": {
                "failure_audit_json": "outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json",
                "failure_audit_md": "outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.md",
            },
            "allowed_uses": ["failure_provenance", "route_motivation"],
            "forbidden_uses": [
                "tune_v2_2_thresholds_from_v2_1_full_artifacts",
                "fit_v2_2_weights_from_v2_1_full_artifacts",
                "select_v2_2_rows_from_v2_1_full_artifacts",
            ],
        },
        "fresh_split_policy": {
            "manifest_generation_authorized_by_this_config": False,
            "non_overlap_required_before_execution": True,
            "required_non_overlap_keys": [
                "sample_id",
                "task_id",
                "dataset_config_split_source_index",
                "normalized_question_hash",
                "reference_answer_hash",
                "non_empty_alias_hash",
            ],
            "overlap_policy": {
                "any_required_key_overlap": "hard_stop_before_api_replay_scoring_reporting",
                "empty_alias_set_policy": "non_informative_not_blocking",
                "non_empty_alias_hash_overlap": "hard_stop",
            },
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
                "v2_1_full_validation_result",
            ],
            "tasks": {
                "gsm8k": {
                    "dataset": "gsm8k",
                    "config": "main",
                    "split": "test_or_new_preregistered_split",
                    "planned_sample_count": sample_count,
                    "selection_policy": "locked_before_manifest_generation",
                },
                "hotpotqa": {
                    "dataset": "hotpot_qa",
                    "config": "distractor",
                    "split": "validation_or_new_preregistered_split",
                    "planned_sample_count": sample_count,
                    "selection_policy": "locked_before_manifest_generation",
                },
            },
        },
        "utility_target": {
            "target_name": "graded_stochastic_delta_u_v2_2",
            "tasks": {
                "gsm8k": {
                    "primary_score_field": "repeated_numeric_success_probability",
                },
                "hotpotqa": {
                    "primary_score_field": "normalized_token_f1",
                    "llm_judge_allowed": False,
                },
            },
        },
        "prompt_lock": {
            "generation_prompt_file": "prompts/s_fma_v2_2_reflection_generation.txt",
            "replay_prompt_file": "prompts/s_fma_v2_2_replay.txt",
            "prompt_version": _v2_2_prompt_bundle_hash(),
            "prompt_lock_status": "CURRENT_PACKAGE_PROMPT_LOCK",
            "prompt_hash_scope": "generation_and_replay_prompt_bundle",
            "allowed_reflection_types": [
                "self-reflection",
                "self-evaluation",
                "error_diagnosis",
                "plan_revision",
                "strategy_critique",
                "verification",
                "planning",
                "uncertainty_monitoring",
                "other",
            ],
            "model_must_not_invent_new_types": True,
            "utility_target_supported": "graded_stochastic_delta_u_v2_2",
        },
        "schema_transport_policy": {
            "bounded_repair_policy": {
                "allowed": True,
                "authorized_by_this_config": False,
                "preserve_all_failed_attempts": True,
                "answer_content_editing_allowed": False,
            }
        },
        "rank_signal_reporting": {
            "metrics": [
                "spearman",
                "kendall_tau_b",
                "ndcg_at_3",
                "top_10_percent_high_utility_auc",
            ],
            "uncertainty": {
                "bootstrap_ci_required": True,
                "bootstrap_standard_error_required": True,
                "bootstrap_variance_required": True,
                "bootstrap_unit": "sample_id",
            },
        },
        "claim_policy": {
            "current_status_must_remain": [
                "PILOT_BLOCKED",
                "v2_2_preregistered_only",
                "no_api_authorized",
                "no_manifest_generated",
                "no_replay_run",
                "no_scoring_run",
                "no_prm_filtering_claim",
            ],
        },
        "future_execution_boundary": {
            "api_calls_authorized": False,
            "manifest_generation_authorized": False,
            "replay_authorized": False,
            "scoring_authorized": False,
            "prm_filtering_authorized": False,
        },
    }


def test_v2_2_prompt_lock_files_use_schema_canonical_types_and_target_policy() -> None:
    config = load_pilot_config(Path("configs/s_fma_v2_2_fresh_holdout.yaml"))
    prompt_lock = config["prompt_lock"]
    generation_prompt = V2_2_GENERATION_PROMPT_PATH.read_text(encoding="utf-8")
    replay_prompt = V2_2_REPLAY_PROMPT_PATH.read_text(encoding="utf-8")
    allowed_types = [
        "self-reflection",
        "self-evaluation",
        "error_diagnosis",
        "plan_revision",
        "strategy_critique",
        "verification",
        "planning",
        "uncertainty_monitoring",
        "other",
    ]

    assert prompt_lock["generation_prompt_file"] == V2_2_GENERATION_PROMPT_PATH.as_posix()
    assert prompt_lock["replay_prompt_file"] == V2_2_REPLAY_PROMPT_PATH.as_posix()
    assert prompt_lock["allowed_reflection_types"] == allowed_types
    for operation_type in allowed_types:
        assert operation_type in generation_prompt
        assert operation_type in replay_prompt
    assert "Do not invent new reflection types" in generation_prompt
    assert "Do not invent new reflection types" in replay_prompt
    assert "self-evaluation" in generation_prompt
    assert "self-evaluation" in replay_prompt
    assert "self_evaluation" not in generation_prompt
    assert "self_evaluation" not in replay_prompt
    assert "graded_stochastic_delta_u_v2_2" in generation_prompt
    assert "graded_stochastic_delta_u_v2_2" in replay_prompt
    assert "repeated_numeric_success_probability" in generation_prompt
    assert "normalized_token_f1" in generation_prompt


def test_v2_2_prompt_hash_is_locked_across_config_contract_and_approval_request() -> None:
    prompt_version = _v2_2_prompt_bundle_hash()
    config = load_pilot_config(Path("configs/s_fma_v2_2_fresh_holdout.yaml"))
    contract_audit = json.loads(V2_2_CONTRACT_AUDIT_PATH.read_text(encoding="utf-8"))
    approval_request = json.loads(V2_2_APPROVAL_REQUEST_PATH.read_text(encoding="utf-8"))

    assert config["prompt_lock"]["prompt_version"] == prompt_version
    assert config["prompt_lock"]["prompt_hash_scope"] == "generation_and_replay_prompt_bundle"
    assert contract_audit["prompt_version"] == prompt_version
    assert contract_audit["prompt_lock_status"] == "CURRENT_PACKAGE_PROMPT_LOCK"
    assert contract_audit["checks"]["prompt_lock"]["status"] == "clean"
    assert contract_audit["checks"]["prompt_lock"]["details"]["prompt_version"] == prompt_version
    assert approval_request["prompt_version"] == prompt_version
    assert approval_request["prompt_lock_status"] == "CURRENT_PACKAGE_PROMPT_LOCK"
    assert approval_request["prompt_file"] == V2_2_GENERATION_PROMPT_PATH.as_posix()
    assert approval_request["replay_prompt_file"] == V2_2_REPLAY_PROMPT_PATH.as_posix()
    assert approval_request["requested_scope"] == "V2_2_API_PREFLIGHT_ONLY"
    assert approval_request["approval_status"] == "REQUEST_ONLY_NOT_APPROVED"
    assert approval_request["api_execution_authorized_by_this_request"] is False
    assert approval_request["preflight_performed_by_this_task"] is False
    assert approval_request["claim_boundary"]["no_v2_2_pass_claim"] is True
    assert approval_request["claim_boundary"]["no_submission_ready_claim"] is True

    prompt_checks = [
        check
        for check in approval_request["required_pre_run_checks"]
        if check["check"] == "v2.2 prompt hash lock"
    ]
    assert prompt_checks == [
        {
            "check": "v2.2 prompt hash lock",
            "evidence": [
                V2_2_GENERATION_PROMPT_PATH.as_posix(),
                V2_2_REPLAY_PROMPT_PATH.as_posix(),
            ],
            "required_value": prompt_version,
            "observed_value": prompt_version,
            "status": "clean",
        }
    ]


def test_v2_2_manifest_only_audit_selects_fresh_rows_and_never_unlocks_execution() -> None:
    source_rows = {
        "gsm8k": [
            {
                "source_index": 1,
                "task_id": "seen-gsm",
                "question": "Seen question?",
                "reference_answer": "#### 1",
                "aliases": ["one"],
            },
            {
                "source_index": 2,
                "task_id": "fresh-gsm",
                "question": "Fresh question?",
                "reference_answer": "#### 2",
                "aliases": [],
            },
        ],
        "hotpotqa": [
            {
                "source_index": 3,
                "task_id": "seen-hotpot",
                "question": "Alias overlap?",
                "reference_answer": "Mars",
                "aliases": ["red planet"],
            },
            {
                "source_index": 4,
                "task_id": "fresh-hotpot",
                "question": "Fresh hotpot?",
                "reference_answer": "Venus",
                "aliases": ["morning star"],
            },
        ],
    }
    overlap_sources = {
        "v2_1_full_failed_overlap_exclusion_only.jsonl": [
            {
                "sample_id": "gsm8k-00001",
                "task_id": "seen-gsm",
                "dataset": "gsm8k",
                "config": "main",
                "split": "test_or_new_preregistered_split",
                "source_index": 1,
                "question": "seen question?",
                "reference_answer": "#### 1",
                "aliases": ["one"],
            },
            {
                "sample_id": "hotpotqa-00003",
                "task_id": "other-hotpot",
                "dataset": "hotpot_qa",
                "config": "distractor",
                "split": "validation_or_new_preregistered_split",
                "source_index": 99,
                "question": "Different question",
                "reference_answer": "Different answer",
                "aliases": ["red planet"],
            },
        ]
    }

    manifest, audit = build_v2_2_fresh_holdout_manifest(
        source_rows,
        config=_v2_2_config(sample_count=1),
        overlap_sources=overlap_sources,
    )

    assert audit["status"] == "MANIFEST_OVERLAP_CLEAN"
    assert audit["current_status_remains"] == "PILOT_BLOCKED"
    assert audit["s_fma_v2_2_status"] == "manifest-only"
    assert audit["no_api_run"] is True
    assert audit["no_replay"] is True
    assert audit["no_scoring"] is True
    assert audit["no_prm_filtering_claim"] is True
    assert audit["validation_or_pass_claim_allowed"] is False
    assert audit["api_preflight_approval_request_generated"] is False
    assert audit["next_allowed_step"] == "V2_2_API_PREFLIGHT_APPROVAL_REQUEST_ONLY"
    assert audit["required_non_overlap_keys"] == [
        "sample_id",
        "task_id",
        "dataset_config_split_source_index",
        "normalized_question_hash",
        "reference_answer_hash",
        "alias_hash",
    ]
    assert audit["overlap_summary"]["selected_overlaps_by_key"] == {
        "sample_id": 0,
        "task_id": 0,
        "dataset_config_split_source_index": 0,
        "normalized_question_hash": 0,
        "reference_answer_hash": 0,
        "alias_hash": 0,
    }
    assert {row["sample_id"] for row in manifest} == {"gsm8k-00002", "hotpotqa-00004"}
    assert all(row["v2_1_full_validation_tuning_source"] is False for row in manifest)
    assert all(row["target_name"] == "graded_stochastic_delta_u_v2_2" for row in manifest)


def test_v2_2_contract_audit_keeps_failed_v2_1_artifacts_as_provenance_only() -> None:
    failure_audit = {
        "provenance_status": "failed_full_validation_provenance",
        "source_full_validation_status": "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS",
        "status_boundary": {
            "full_validation_task_specific_pass": False,
            "full_validation_global_pass": False,
            "current_status_remains": "PILOT_BLOCKED",
            "prm_filtering_validation_execution_allowed": False,
            "top_tier_ready_claim_allowed": False,
        },
    }

    contract = build_v2_2_contract_audit(
        config=_v2_2_config(sample_count=1),
        preregistration_plan_text=(
            "PILOT_BLOCKED repeated_numeric_success_probability normalized_token_f1 "
            "bootstrap confidence intervals no PRM/filtering"
        ),
        transition_audit_text=(
            "failed full-validation provenance must not be used to tune v2.2 thresholds "
            "or select v2.2 rows"
        ),
        failure_audit=failure_audit,
        manifest_audit={
            "status": "MANIFEST_OVERLAP_CLEAN",
            "overlap_clean": True,
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
        },
        task_scope=S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT,
        current_submission_ready=False,
    )

    assert contract["status"] == V2_2_CONTRACT_CLEAN
    assert contract["current_status_remains"] == "PILOT_BLOCKED"
    assert contract["manifest_generation_scope"] == S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT
    assert contract["api_execution_allowed"] is False
    assert contract["validation_or_pass_claim_allowed"] is False
    assert contract["v2_1_failed_full_artifacts_used_as_tuning_source"] is False
    assert contract["next_allowed_step"] == "V2_2_API_PREFLIGHT_APPROVAL_REQUEST_ONLY"
    assert contract["blockers"] == []


def test_v2_2_generator_boundary_rejects_api_replay_scoring_or_prm_scope() -> None:
    config = _v2_2_config()
    config["experiment"]["no_scoring_in_current_task"] = False

    with pytest.raises(RuntimeError, match="no_scoring_in_current_task"):
        _assert_current_task_boundary(
            config,
            task_scope=S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT,
        )


def test_v2_2_api_preflight_readiness_requires_scope_budget_and_failed_v2_1_boundary() -> None:
    config = _v2_2_config(sample_count=200)
    manifest = _v2_2_manifest_rows(per_task=200)

    with pytest.raises(V2_2PreflightError, match="--allow-api-preflight-only"):
        validate_v2_2_preflight_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=_v2_2_clean_overlap_audit(),
            contract_audit=_v2_2_clean_contract_audit(),
            approval_request=_v2_2_approval_request(),
            failure_audit=_v2_2_failed_v2_1_audit(),
            current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
            allow_api_preflight_only=False,
            approved_budget_usd=2,
        )

    bad_failure = _v2_2_failed_v2_1_audit()
    bad_failure["status_boundary"]["full_validation_global_pass"] = True
    with pytest.raises(V2_2PreflightError, match="failure provenance"):
        validate_v2_2_preflight_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=_v2_2_clean_overlap_audit(),
            contract_audit=_v2_2_clean_contract_audit(),
            approval_request=_v2_2_approval_request(),
            failure_audit=bad_failure,
            current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
            allow_api_preflight_only=True,
            approved_budget_usd=2,
        )

    readiness = validate_v2_2_preflight_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=_v2_2_clean_overlap_audit(),
        contract_audit=_v2_2_clean_contract_audit(),
        approval_request=_v2_2_approval_request(),
        failure_audit=_v2_2_failed_v2_1_audit(),
        current_readiness={"status": "PILOT_BLOCKED", "pilot_pass": False},
        allow_api_preflight_only=True,
        approved_budget_usd=2,
        current_prompt_version=_v2_2_prompt_bundle_hash(),
    )

    assert readiness["scope"] == V2_2_API_PREFLIGHT_ONLY
    assert readiness["api_call_allowed"] is True
    assert readiness["approved_budget_usd"] == 2
    assert readiness["max_api_requests"] == 25
    assert readiness["selected_records"] == 20
    assert readiness["selected_counts_by_task"] == {"gsm8k": 10, "hotpotqa": 10}
    assert readiness["planned_api_requests"] == 23
    assert readiness["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_2_preflight_report_allows_only_stochastic_smoke_request_after_clean_schema_with_drift() -> (
    None
):
    readiness = {
        "approved_budget_usd": 2,
        "max_api_requests": 25,
        "selected_records": 20,
    }
    attempts = [
        _v2_2_valid_attempt(f"gsm8k-{index:05d}", include_disclosure_metadata=True)
        for index in range(20)
    ]
    drift_outputs = [
        'Trace one <reflection type="verification">check</reflection> Final Answer: 5',
        'Trace two <reflection type="verification">check differently</reflection> Final Answer: 5',
    ]

    report = build_v2_2_preflight_report(
        attempts,
        selected_records=_v2_2_manifest_rows(per_task=10),
        drift_outputs=drift_outputs,
        config=build_v2_2_generation_config(_v2_2_config(sample_count=200), readiness=readiness),
        readiness=readiness,
        cost_attempts=attempts,
    )

    assert report["scope"] == V2_2_API_PREFLIGHT_ONLY
    assert report["status"] == PREFLIGHT_FAIL_DRIFT
    assert report["json_parse_success_rate"] == 1.0
    assert report["schema_success_rate"] == 1.0
    assert report["tag_extraction_success_rate"] == 1.0
    assert report["final_answer_parse_success_rate"] == 1.0
    assert report["raw_output_nonempty_rate"] == 1.0
    assert report["v2_2_stochastic_smoke_approval_request_allowed"] is True
    assert report["smoke_execution_allowed"] is False
    assert report["deterministic_replay_claim_allowed"] is False
    assert report["global_pass_claim_allowed"] is False
    assert report["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_2_preflight_report_keeps_metadata_disclosure_missing_as_blocker() -> None:
    readiness = {
        "approved_budget_usd": 2,
        "max_api_requests": 25,
        "selected_records": 20,
    }
    attempts = [_v2_2_valid_attempt(f"gsm8k-{index:05d}") for index in range(20)]

    report = build_v2_2_preflight_report(
        attempts,
        selected_records=_v2_2_manifest_rows(per_task=10),
        drift_outputs=[
            'Trace one <reflection type="verification">check</reflection> Final Answer: 5',
            'Trace two <reflection type="verification">check differently</reflection> Final Answer: 5',
        ],
        config=build_v2_2_generation_config(_v2_2_config(sample_count=200), readiness=readiness),
        readiness=readiness,
        cost_attempts=attempts,
    )

    assert report["status"] == PREFLIGHT_FAIL_DRIFT
    assert "PREFLIGHT_FAIL_METADATA" in report["failure_codes"]
    assert report["metadata_disclosure_status"] == "PREFLIGHT_METADATA_MISSING"
    assert report["metadata_disclosure_missing_counts"] == {
        "fallback_model": 20,
        "system_fingerprint": 20,
    }
    assert report["v2_2_stochastic_smoke_approval_request_allowed"] is False
    assert report["current_status_remains"] == "PILOT_BLOCKED"


def test_v2_2_single_retry_merge_replaces_only_target_failed_attempt() -> None:
    attempts = [
        _v2_2_valid_attempt("gsm8k-00000", include_disclosure_metadata=True),
        _v2_2_failed_attempt("hotpotqa-00240"),
        _v2_2_valid_attempt("hotpotqa-00241", include_disclosure_metadata=True),
    ]
    retry = _v2_2_valid_attempt("hotpotqa-00240", include_disclosure_metadata=True)

    merged, replaced = merge_single_retry_attempt(
        attempts,
        retry,
        target_sample_id="hotpotqa-00240",
    )

    assert replaced == 1
    assert len(merged) == 3
    assert [attempt["sample_id"] for attempt in merged] == [
        "gsm8k-00000",
        "hotpotqa-00240",
        "hotpotqa-00241",
    ]
    assert merged[1]["record"] is not None
    assert merged[1]["validation_errors"] == []
    assert merged[0] == attempts[0]
    assert merged[2] == attempts[2]


def _v2_2_manifest_rows(per_task: int) -> list[dict]:
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
                    "target_name": "graded_stochastic_delta_u_v2_2",
                    "primary_score_field": (
                        "normalized_token_f1"
                        if task_type == "hotpotqa"
                        else "repeated_numeric_success_probability"
                    ),
                }
            )
    return rows


def _v2_2_clean_overlap_audit() -> dict:
    return {
        "status": "MANIFEST_OVERLAP_CLEAN",
        "overlap_clean": True,
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


def _v2_2_clean_contract_audit() -> dict:
    return {
        "status": V2_2_CONTRACT_CLEAN,
        "current_status_remains": "PILOT_BLOCKED",
        "claim_upgrade_allowed": False,
        "validation_or_pass_claim_allowed": False,
        "api_execution_allowed": False,
        "replay_allowed": False,
        "scoring_allowed": False,
        "prm_filtering_allowed": False,
        "v2_1_failed_full_artifacts_used_as_tuning_source": False,
        "prompt_version": _v2_2_prompt_bundle_hash(),
        "checks": {
            "prompt_lock": {
                "status": "clean",
                "details": {"prompt_version": _v2_2_prompt_bundle_hash()},
            }
        },
        "blockers": [],
    }


def _v2_2_approval_request() -> dict:
    return {
        "requested_scope": V2_2_API_PREFLIGHT_ONLY,
        "approval_status": "REQUEST_ONLY_NOT_APPROVED",
        "current_status_remains": "PILOT_BLOCKED",
        "request_valid_for_review": True,
        "api_execution_authorized_by_this_request": False,
        "requested_records": 20,
        "records_per_task": {"gsm8k": 10, "hotpotqa": 10},
        "recommended_budget_ceiling_usd": 2,
        "max_api_requests": 25,
        "prompt_version": _v2_2_prompt_bundle_hash(),
    }


def _v2_2_failed_v2_1_audit() -> dict:
    return {
        "provenance_status": "failed_full_validation_provenance",
        "source_full_validation_status": "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS",
        "status_boundary": {
            "full_validation_task_specific_pass": False,
            "full_validation_global_pass": False,
            "current_status_remains": "PILOT_BLOCKED",
        },
    }


def _v2_2_valid_attempt(sample_id: str, *, include_disclosure_metadata: bool = False) -> dict:
    fallback_order = ["gpt-5.5", "gpt-5.5-fallback"] if include_disclosure_metadata else ["gpt-5.5"]
    system_fingerprint = "fp_test" if include_disclosure_metadata else None
    record = {
        "sample_id": sample_id,
        "task_id": sample_id,
        "task_type": "gsm8k",
        "question": "What is 2 + 3?",
        "observable_trace": (
            "Compute 2 + 3 = 5. "
            '<reflection type="verification">Check the arithmetic.</reflection> '
            "Final Answer: 5"
        ),
        "reflection_spans": [
            {
                "span_index": 0,
                "start_char": 19,
                "end_char": 78,
                "content_start_char": 51,
                "content_end_char": 72,
                "start_token": 5,
                "end_token": 8,
                "operation_type": "verification",
                "content": "Check the arithmetic.",
            }
        ],
        "final_answer": "5",
        "reference_answer": "#### 5",
        "correctness": True,
        "model_name": "gpt-5.5",
        "generation_config": {
            "endpoint": "/v1/responses",
            "api_date": "2026-06-05",
            "sdk_version": "fake-openai-1.0",
            "service_tier": "default",
            "primary_model": "gpt-5.5",
            "fallback_order": fallback_order,
            "temperature": 0,
            "max_output_tokens": 2048,
            "response_id": "resp_test",
            "api_request_metadata": {"seed_sent": False},
        },
        "system_fingerprint": system_fingerprint,
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
    }
    return {
        "preflight_attempt": True,
        "attempt_role": "preflight_record",
        "sample_id": sample_id,
        "task_id": sample_id,
        "task_type": "gsm8k",
        "record": record,
        "raw_output": record,
        "usage": record["usage"],
        "model_name": "gpt-5.5",
        "structured_output_mode": "json_schema",
        "system_fingerprint": system_fingerprint,
        "response_id": "resp_test",
        "validation_errors": [],
    }


def _v2_2_failed_attempt(sample_id: str) -> dict:
    return {
        "preflight_attempt": True,
        "attempt_role": "preflight_record",
        "sample_id": sample_id,
        "task_id": "5a85cead5542991dd0999ea9",
        "task_type": "hotpotqa",
        "question_hash": "test_hash",
        "question_preview": "Failed hotpot question",
        "record": None,
        "raw_output": "",
        "usage": {},
        "model_name": "gpt-5.5",
        "structured_output_mode": "json_schema",
        "system_fingerprint": None,
        "response_id": None,
        "validation_errors": ["api_error:APIConnectionError:Connection error."],
        "fallback_events": [
            {
                "model_name": "gpt-5.5",
                "structured_output_mode": "json_schema",
                "status": "api_error",
                "error_type": "APIConnectionError",
                "error": "Connection error.",
            }
        ],
    }
