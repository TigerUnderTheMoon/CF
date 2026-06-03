from __future__ import annotations

import hashlib
from datetime import date

import pytest

from fma.real_task_pilot.fresh_holdout import (
    BLOCKED_INSUFFICIENT_FRESH_ROWS,
    MANIFEST_OVERLAP_CLEAN,
    alias_hash,
    build_fresh_holdout_manifest,
    normalized_text_hash,
)
from scripts.generate_s_fma_v2_fresh_holdout_manifest import _assert_current_task_boundary

from fma.real_task_pilot.fresh_preflight import (
    API_PREFLIGHT_READY,
    PREFLIGHT_FAIL_COST,
    PREFLIGHT_FAIL_DRIFT,
    PREFLIGHT_FAIL_METADATA,
    PREFLIGHT_FAIL_SCHEMA_OR_TAGS,
    PREFLIGHT_METADATA_MISSING,
    FreshPreflightError,
    build_budget_blocked_report,
    select_preflight_records,
    summarize_fresh_preflight,
    validate_preflight_readiness,
)


def _config(sample_count: int = 1) -> dict:
    return {
        "experiment": {"seed": 20260601},
        "scorer": {"formula_hash": "sha256:test-formula"},
        "fresh_holdout": {
            "tasks": {
                "gsm8k": {
                    "dataset": "gsm8k",
                    "config": "main",
                    "split": "test",
                    "sample_count": sample_count,
                }
            }
        },
    }


def _fresh_preflight_config(*, budget: float | None = 5.0, sample_count: int = 2) -> dict:
    return {
        "experiment": {
            "seed": 20260601,
            "user_approved_budget_usd": budget,
            "plan_file": "paper/s_fma_v2_fresh_holdout_plan.md",
        },
        "fresh_holdout": {
            "manifest_path": "outputs/s_fma_v2_fresh_holdout/fresh_manifest.json",
            "tasks": {
                "gsm8k": {"sample_count": sample_count},
                "hotpotqa": {"sample_count": sample_count},
            },
        },
        "api_preflight": {
            "mode": "API_PREFLIGHT_ONLY",
            "samples_per_task": 1,
            "cost_ceiling_usd": 1.0,
        },
        "api_policy": {
            "api_logging": {
                "required_fields": [
                    "api_date",
                    "endpoint",
                    "model",
                    "fallback_model",
                    "service_tier",
                    "request_parameters",
                    "response_id",
                    "sdk_or_transport_version",
                ],
                "disclosure_fields": ["system_fingerprint"],
            }
        },
        "generation": {
            "minimum_schema_success_rate": 0.95,
            "minimum_tag_success_rate": 0.95,
        },
        "pricing": {"input_per_million_usd": 5, "output_per_million_usd": 30},
        "claim_policy": {"C_S_FMA_V2_FRESH_HOLDOUT": "planned"},
    }


def _manifest_rows(per_task: int = 2) -> list[dict]:
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


def _clean_overlap_audit() -> dict:
    return {
        "status": MANIFEST_OVERLAP_CLEAN,
        "api_preflight_only": True,
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


def _valid_preflight_attempt(sample_id: str = "gsm8k-00000") -> dict:
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
            "fallback_order": ["gpt-5.5", "gpt-5.4"],
            "temperature": 0,
            "max_output_tokens": 2048,
            "response_id": "resp_test",
            "api_request_metadata": {"seed_sent": True},
        },
        "system_fingerprint": "fp_test",
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
    }
    return {
        "preflight_attempt": True,
        "record": record,
        "raw_output": record,
        "usage": record["usage"],
        "model_name": "gpt-5.5",
        "system_fingerprint": "fp_test",
        "response_id": "resp_test",
        "validation_errors": [],
    }


def test_generation_boundary_rejects_api_scoring_replay_or_manifest_disallowance() -> None:
    config = {
        "experiment": {
            "no_api_execution_without_user_approval": True,
            "no_manifest_generation_in_current_task": True,
        },
        "claim_policy": {"C_S_FMA_V2_FRESH_HOLDOUT": "planned"},
    }

    with pytest.raises(RuntimeError, match="manifest generation"):
        _assert_current_task_boundary(config)


def test_fresh_holdout_hash_policy_matches_preregistered_normalization() -> None:
    assert normalized_text_hash("  TeSt\nQuestion  ") == normalized_text_hash("test question")
    assert alias_hash([" Beta ", "alpha"]) == alias_hash(["alpha", "beta"])
    assert alias_hash([]) == hashlib.sha256(b"").hexdigest()


def test_fresh_holdout_manifest_records_required_lock_fields_when_clean() -> None:
    source_rows = {
        "gsm8k": [
            {
                "source_index": 7,
                "task_id": "gsm8k-test-00007",
                "task_type": "gsm8k",
                "question": "What is 2 + 3?",
                "reference_answer": "#### 5",
                "aliases": ["five"],
            }
        ]
    }

    manifest, audit = build_fresh_holdout_manifest(
        source_rows,
        config=_config(),
        current_pilot_sources={"pilot.json": []},
        prompt_version="prompt-sha256:test",
    )

    assert audit["status"] == MANIFEST_OVERLAP_CLEAN
    assert audit["overlap_clean"] is True
    assert audit["next_allowed_step"] == "API_PREFLIGHT_ONLY"
    assert audit["api_preflight_only"] is True
    assert len(manifest) == 1
    assert set(
        [
            "dataset",
            "config",
            "split",
            "source_index",
            "sample_id",
            "task_id",
            "question",
            "reference_answer",
            "aliases",
            "task_type",
            "selection_seed",
            "formula_hash",
            "prompt_version",
            "manifest_item_hash",
        ]
    ).issubset(manifest[0])
    assert manifest[0]["sample_id"] == "gsm8k-00007"
    assert manifest[0]["formula_hash"] == "sha256:test-formula"
    assert manifest[0]["prompt_version"] == "prompt-sha256:test"
    assert audit["overlap_summary"]["total_overlaps_by_key"] == {
        "sample_id": 0,
        "task_id": 0,
        "dataset_config_split_source_index": 0,
        "normalized_question_hash": 0,
        "reference_answer_hash": 0,
        "alias_hash": 0,
    }


def test_fresh_holdout_empty_alias_hash_is_non_informative_not_blocking() -> None:
    source_rows = {
        "gsm8k": [
            {
                "source_index": 7,
                "task_id": "gsm8k-test-00007",
                "task_type": "gsm8k",
                "question": "Fresh question",
                "reference_answer": "Fresh answer",
                "aliases": [],
            }
        ]
    }
    current_pilot_sources = {
        "outputs/real_task_pilot/sample_manifest.json": [
            {
                "sample_id": "gsm8k-00000",
                "task_id": "gsm8k-00000",
                "source_dataset": "gsm8k",
                "source_config": "main",
                "source_split": "test",
                "source_index": 0,
                "question": "Pilot question",
                "reference_answer": "Pilot answer",
                "aliases": [],
            }
        ]
    }

    manifest, audit = build_fresh_holdout_manifest(
        source_rows,
        config=_config(),
        current_pilot_sources=current_pilot_sources,
        prompt_version="prompt-sha256:test",
    )

    assert len(manifest) == 1
    assert audit["status"] == MANIFEST_OVERLAP_CLEAN
    assert audit["overlap_clean"] is True
    assert audit["hard_stop"] is False
    assert audit["next_allowed_step"] == "API_PREFLIGHT_ONLY"
    assert audit["api_preflight_only"] is True
    assert audit["tasks"]["gsm8k"]["eligible_count"] == 1
    assert audit["tasks"]["gsm8k"]["empty_alias_candidate_count"] == 1
    assert audit["tasks"]["gsm8k"]["non_empty_alias_candidate_count"] == 0
    assert audit["overlap_summary"]["total_overlaps_by_key"]["alias_hash"] == 0
    assert audit["alias_policy"]["empty_alias_set_blocking"] is False
    assert audit["alias_policy"]["non_empty_alias_hash_blocking"] is True


def test_fresh_holdout_hard_stops_when_non_empty_alias_hash_overlaps_current_pilot() -> None:
    source_rows = {
        "gsm8k": [
            {
                "source_index": 7,
                "task_id": "gsm8k-test-00007",
                "task_type": "gsm8k",
                "question": "Fresh question",
                "reference_answer": "Fresh answer",
                "aliases": ["same alias"],
            }
        ]
    }
    current_pilot_sources = {
        "outputs/real_task_pilot/sample_manifest.json": [
            {
                "sample_id": "gsm8k-00000",
                "task_id": "gsm8k-00000",
                "source_dataset": "gsm8k",
                "source_config": "main",
                "source_split": "test",
                "source_index": 0,
                "question": "Pilot question",
                "reference_answer": "Pilot answer",
                "aliases": ["same alias"],
            }
        ]
    }

    manifest, audit = build_fresh_holdout_manifest(
        source_rows,
        config=_config(),
        current_pilot_sources=current_pilot_sources,
        prompt_version="prompt-sha256:test",
    )

    assert manifest == []
    assert audit["status"] == BLOCKED_INSUFFICIENT_FRESH_ROWS
    assert audit["overlap_clean"] is False
    assert audit["hard_stop"] is True
    assert audit["next_allowed_step"] == "PREREGISTER_ALTERNATE_SPLIT_DATASET_OR_SOURCE"
    assert audit["api_preflight_only"] is False
    assert audit["tasks"]["gsm8k"]["eligible_count"] == 0
    assert audit["overlap_summary"]["total_overlaps_by_key"]["alias_hash"] == 1
    assert audit["overlap_examples"]["alias_hash"][0]["candidate_sample_id"] == "gsm8k-00007"


def test_fresh_preflight_selects_fixed_per_task_sample() -> None:
    selected = select_preflight_records(_manifest_rows(per_task=12), samples_per_task=10)

    assert len(selected) == 20
    assert sum(1 for row in selected if row["task_type"] == "gsm8k") == 10
    assert sum(1 for row in selected if row["task_type"] == "hotpotqa") == 10
    assert selected[0]["sample_id"] == "gsm8k-00000"
    assert selected[10]["sample_id"] == "hotpotqa-00000"


def test_fresh_preflight_gate_requires_explicit_flag_and_clean_manifest() -> None:
    config = _fresh_preflight_config(sample_count=2)
    manifest = _manifest_rows(per_task=2)

    with pytest.raises(FreshPreflightError, match="--allow-api-preflight-only"):
        validate_preflight_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=_clean_overlap_audit(),
            plan_text="API preflight",
            allow_api_preflight_only=False,
        )

    dirty_audit = _clean_overlap_audit()
    dirty_audit["status"] = "OVERLAP_AUDIT_FAIL"
    with pytest.raises(FreshPreflightError, match="MANIFEST_OVERLAP_CLEAN"):
        validate_preflight_readiness(
            config=config,
            manifest=manifest,
            overlap_audit=dirty_audit,
            plan_text="API preflight",
            allow_api_preflight_only=True,
        )


def test_fresh_preflight_budget_gate_blocks_before_api_when_budget_missing() -> None:
    config = _fresh_preflight_config(budget=None, sample_count=2)
    selected = select_preflight_records(_manifest_rows(per_task=2), samples_per_task=1)
    readiness = validate_preflight_readiness(
        config=config,
        manifest=_manifest_rows(per_task=2),
        overlap_audit=_clean_overlap_audit(),
        plan_text="API preflight",
        allow_api_preflight_only=True,
    )

    report = build_budget_blocked_report(
        config=config,
        selected_records=selected,
        readiness=readiness,
    )

    assert readiness["api_call_allowed"] is False
    assert report["status"] == PREFLIGHT_FAIL_COST
    assert report["records_evaluated"] == 0
    assert report["selected_records"] == 2
    assert report["no_full_generation"] is True
    assert report["current_status_remains"] == "PILOT_BLOCKED"


def test_fresh_preflight_budget_blocked_report_is_json_serializable_with_yaml_date() -> None:
    config = _fresh_preflight_config(budget=None, sample_count=2)
    config["api"] = {
        "api_date": date(2026, 6, 3),
        "endpoint": "/v1/responses",
        "service_tier": "default",
    }
    config["model"] = {
        "primary": "gpt-5.5",
        "fallback_order": ["gpt-5.5", "gpt-5.4"],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": 2048,
    }
    readiness = validate_preflight_readiness(
        config=config,
        manifest=_manifest_rows(per_task=2),
        overlap_audit=_clean_overlap_audit(),
        plan_text="API preflight",
        allow_api_preflight_only=True,
    )

    report = build_budget_blocked_report(
        config=config,
        selected_records=select_preflight_records(_manifest_rows(per_task=2), samples_per_task=1),
        readiness=readiness,
    )

    assert report["api_metadata"]["api_date"] == "2026-06-03"


def test_fresh_preflight_schema_tag_or_final_answer_failure_uses_single_blocking_status() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(19)]
    invalid = _valid_preflight_attempt("gsm8k-00019")
    invalid["record"]["final_answer"] = ""
    invalid["record"]["observable_trace"] = (
        "Compute 2 + 3 = 5. "
        '<reflection type="verification">Check the arithmetic.</reflection>'
    )
    attempts.append(invalid)

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["same trace", "same trace"],
        config=_fresh_preflight_config(sample_count=10),
    )

    assert report["status"] == PREFLIGHT_FAIL_SCHEMA_OR_TAGS
    assert report["records_evaluated"] == 20
    assert report["final_answer_parse_success_rate"] == 0.95
    assert "PREFLIGHT_FAIL_FINAL_ANSWER" in report["failure_codes"]
    assert report["fresh_generation_approval_request_allowed"] is False


def test_fresh_preflight_drift_failure_forbids_deterministic_replay_claim() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["alpha beta gamma", "alpha totally different gamma"],
        config=_fresh_preflight_config(sample_count=10),
    )

    assert report["status"] == PREFLIGHT_FAIL_DRIFT
    assert report["drift_status"] == PREFLIGHT_FAIL_DRIFT
    assert report["deterministic_replay_claim_allowed"] is False
    assert report["stochastic_repeated_replay_estimand_candidate"] is True


def test_fresh_preflight_drift_failure_blocks_deterministic_full_generation() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["alpha beta gamma", "alpha totally different gamma"],
        config=_fresh_preflight_config(sample_count=10),
    )

    deterministic_route = report["route_policy"]["DETERMINISTIC_REPLAY_ROUTE"]
    assert report["status"] == PREFLIGHT_FAIL_DRIFT
    assert report["fresh_generation_approval_request_allowed"] is False
    assert report["no_full_generation"] is True
    assert deterministic_route["route_status"] == "blocked_preflight_drift"
    assert deterministic_route["full_generation_allowed"] is False
    assert deterministic_route["deterministic_replay_language_allowed"] is False


def test_fresh_preflight_drift_failure_only_allows_stochastic_planning_or_stronger_preflight() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["alpha beta gamma", "alpha totally different gamma"],
        config=_fresh_preflight_config(sample_count=10),
    )

    assert report["status"] == PREFLIGHT_FAIL_DRIFT
    assert report["next_allowed_step"] == "STOP_AND_FIX_PREFLIGHT"
    assert report["allowed_remediation_steps"] == [
        "PREREGISTER_STOCHASTIC_ROUTE",
        "RERUN_PREFLIGHT_WITH_STRONGER_DETERMINISM_SETTINGS",
    ]
    assert report["route_policy"]["allowed_routes_after_drift"] == [
        "STOCHASTIC_REPEATED_REPLAY_ROUTE"
    ]


def test_fresh_preflight_stochastic_route_still_requires_explicit_budget_before_api() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["alpha beta gamma", "alpha totally different gamma"],
        config=_fresh_preflight_config(sample_count=10),
    )

    stochastic_route = report["route_policy"]["STOCHASTIC_REPEATED_REPLAY_ROUTE"]
    assert stochastic_route["planning_allowed"] is True
    assert stochastic_route["api_execution_allowed"] is False
    assert stochastic_route["requires_explicit_budget_approval"] is True
    assert stochastic_route["cost_ceiling_required"] is True
    assert stochastic_route["claim_scope"] == "stochastic_repeated_replay_evidence_only"


def test_fresh_preflight_deterministic_replay_claim_forbidden_when_drift_persists() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["alpha beta gamma", "alpha totally different gamma"],
        config=_fresh_preflight_config(sample_count=10),
    )

    assert report["deterministic_replay_claim_allowed"] is False
    assert "deterministic replay" not in " ".join(report["allowed_claim_wording"]).lower()
    assert "deterministic causal" in report["forbidden_claim_wording"]
    assert "deterministic replay" in report["forbidden_claim_wording"]


def test_fresh_preflight_drift_status_takes_precedence_over_fingerprint_disclosure_missing() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]
    for attempt in attempts:
        attempt["system_fingerprint"] = None
        attempt["record"]["system_fingerprint"] = None

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["alpha beta gamma", "alpha totally different gamma"],
        config=_fresh_preflight_config(sample_count=10),
    )

    assert report["json_parse_success_rate"] == 1.0
    assert report["schema_success_rate"] == 1.0
    assert report["tag_extraction_success_rate"] == 1.0
    assert report["final_answer_parse_success_rate"] == 1.0
    assert PREFLIGHT_FAIL_METADATA not in report["failure_codes"]
    assert "PREFLIGHT_FAIL_SCHEMA" not in report["failure_codes"]
    assert "PREFLIGHT_FAIL_TAG" not in report["failure_codes"]
    assert report["status"] == PREFLIGHT_FAIL_DRIFT
    assert report["drift_status"] == PREFLIGHT_FAIL_DRIFT
    assert report["metadata_disclosure_status"] == PREFLIGHT_METADATA_MISSING
    assert report["metadata_disclosure_missing_counts"]["system_fingerprint"] == 20
    assert "all 20 evaluated records" in report["metadata_disclosure_explanation"]
    assert report["fresh_generation_approval_request_allowed"] is False
    assert report["next_allowed_step"] == "STOP_AND_FIX_PREFLIGHT"


def test_fresh_preflight_required_metadata_failure_is_separate_from_schema_tag_status() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]
    for attempt in attempts:
        attempt["response_id"] = None
        attempt["record"]["generation_config"]["response_id"] = None

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["same trace", "same trace"],
        config=_fresh_preflight_config(sample_count=10),
    )

    assert report["status"] == PREFLIGHT_FAIL_METADATA
    assert report["json_parse_success_rate"] == 1.0
    assert report["schema_success_rate"] == 1.0
    assert report["tag_extraction_success_rate"] == 1.0
    assert report["final_answer_parse_success_rate"] == 1.0
    assert report["metadata_missing_counts"]["response_id"] == 20
    assert PREFLIGHT_FAIL_METADATA in report["failure_codes"]
    assert "PREFLIGHT_FAIL_SCHEMA" not in report["failure_codes"]
    assert "PREFLIGHT_FAIL_TAG" not in report["failure_codes"]
    assert report["fresh_generation_approval_request_allowed"] is False
    assert report["next_allowed_step"] == "STOP_AND_FIX_PREFLIGHT"


def test_fresh_preflight_fingerprint_null_across_all_records_is_disclosure_only() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]
    for attempt in attempts:
        attempt["system_fingerprint"] = None
        attempt["record"]["system_fingerprint"] = None

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["same trace", "same trace"],
        config=_fresh_preflight_config(sample_count=10),
    )

    assert report["status"] == API_PREFLIGHT_READY
    assert report["required_metadata_success_rate"] == 1.0
    assert "system_fingerprint" not in report["metadata_missing_counts"]
    assert report["metadata_disclosure_status"] == PREFLIGHT_METADATA_MISSING
    assert report["metadata_disclosure_missing_counts"] == {"system_fingerprint": 20}
    assert "disclosure-only" in report["metadata_disclosure_explanation"]


def test_fresh_preflight_clean_report_only_allows_generation_approval_request() -> None:
    attempts = [_valid_preflight_attempt(f"gsm8k-{index:05d}") for index in range(20)]

    report = summarize_fresh_preflight(
        attempts,
        selected_records=_manifest_rows(per_task=10),
        drift_outputs=["same trace", "same trace"],
        config=_fresh_preflight_config(sample_count=10),
    )

    assert report["status"] == API_PREFLIGHT_READY
    assert report["json_parse_success_rate"] == 1.0
    assert report["schema_success_rate"] == 1.0
    assert report["tag_extraction_success_rate"] == 1.0
    assert report["final_answer_parse_success_rate"] == 1.0
    assert report["required_metadata_success_rate"] == 1.0
    assert report["fresh_generation_approval_request_allowed"] is True
    assert report["next_allowed_step"] == "REQUEST_FRESH_GENERATION_APPROVAL"
    assert report["no_v2_scoring"] is True
    assert report["no_replay"] is True
    assert report["no_prm_claim"] is True
