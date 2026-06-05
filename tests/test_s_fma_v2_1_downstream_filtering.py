from __future__ import annotations

import importlib

import pytest

from fma.real_task_pilot.parsing import extract_reflection_spans


def _module():
    try:
        return importlib.import_module("fma.real_task_pilot.downstream_filtering_v2_1")
    except ModuleNotFoundError as exc:
        pytest.fail(f"downstream filtering module missing: {exc}")


def _record(sample_id: str, task_type: str = "gsm8k") -> dict:
    trace = (
        "Initial solution attempt: compute carefully.\n"
        '<reflection type="verification">Check the arithmetic.</reflection>\n'
        "Continue with the same answer.\n"
        '<reflection type="plan_revision">Revise only if a contradiction appears.</reflection>\n'
        "Final Answer: 5"
    )
    return {
        "sample_id": sample_id,
        "task_id": sample_id,
        "task_type": task_type,
        "question": "What is 2 + 3?" if task_type == "gsm8k" else "Who wrote Hamlet?",
        "reference_answer": "#### 5" if task_type == "gsm8k" else "William Shakespeare",
        "aliases": [] if task_type == "gsm8k" else ["Shakespeare"],
        "observable_trace": trace,
        "reflection_spans": extract_reflection_spans(trace),
        "final_answer": "5" if task_type == "gsm8k" else "Shakespeare",
        "correctness": True,
    }


def _candidate_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        rows.extend(
            [
                {
                    "sample_id": record["sample_id"],
                    "task_type": record["task_type"],
                    "span_index": 0,
                    "score_name": "structurally_calibrated_fma",
                    "candidate_score": 0.9,
                    "target_leakage_status": "clean",
                    "leakage_status": "clean",
                    "source_fields_used": ["observable_trace", "reflection_spans", "sample_id"],
                    "forbidden_fields_used": [],
                },
                {
                    "sample_id": record["sample_id"],
                    "task_type": record["task_type"],
                    "span_index": 1,
                    "score_name": "structurally_calibrated_fma",
                    "candidate_score": 0.1,
                    "target_leakage_status": "clean",
                    "leakage_status": "clean",
                    "source_fields_used": ["observable_trace", "reflection_spans", "sample_id"],
                    "forbidden_fields_used": [],
                },
            ]
        )
    return rows


def test_preregistration_locks_exact_scope_budget_and_claim_boundary() -> None:
    mod = _module()

    prereg = mod.build_downstream_filtering_preregistration()

    assert prereg["requested_scope"] == mod.V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY
    assert prereg["approval_status"] == "REQUEST_ONLY_NOT_APPROVED"
    assert prereg["sample_count"] == 20
    assert prereg["sample_count_by_task"] == {"gsm8k": 10, "hotpotqa": 10}
    assert prereg["planned_api_calls"] == 40
    assert prereg["max_api_requests"] == 60
    assert prereg["recommended_budget_ceiling_usd"] == 5.0
    assert prereg["current_status_remains"] == "PILOT_BLOCKED"
    assert "full validation claim" in prereg["forbidden_claim_scope"]
    assert "PRM/filtering superiority claim" in prereg["forbidden_claim_scope"]
    assert prereg["source_artifacts"]["original_traces"].endswith(
        "v2_1_pilot_stochastic_original_traces.jsonl"
    )
    assert "v2_1_full_stochastic_report.json" not in prereg["source_artifacts"].values()


def test_readiness_rejects_full_validation_source_and_budget_mismatch() -> None:
    mod = _module()
    prereg = mod.build_downstream_filtering_preregistration()
    prereg["source_artifacts"]["original_traces"] = (
        "outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_report.json"
    )

    with pytest.raises(mod.V2_1DownstreamFilteringError, match="full validation"):
        mod.validate_downstream_filtering_readiness(
            preregistration=prereg,
            pilot_report={"status": "V2_1_PILOT_STOCHASTIC_PASS", "GLOBAL_pass": True},
            abandonment_audit={"current_status_remains": "PILOT_BLOCKED"},
            current_status="PILOT_BLOCKED",
            allow_downstream_filtering_validation_only=True,
            approved_budget_usd=5.0,
        )

    prereg = mod.build_downstream_filtering_preregistration()
    with pytest.raises(mod.V2_1DownstreamFilteringError, match="approved budget"):
        mod.validate_downstream_filtering_readiness(
            preregistration=prereg,
            pilot_report={"status": "V2_1_PILOT_STOCHASTIC_PASS", "GLOBAL_pass": True},
            abandonment_audit={"current_status_remains": "PILOT_BLOCKED"},
            current_status="PILOT_BLOCKED",
            allow_downstream_filtering_validation_only=True,
            approved_budget_usd=4.99,
        )


def test_selection_is_task_balanced_and_ignores_target_like_fields() -> None:
    mod = _module()
    records = [_record(f"gsm8k-{i:05d}", "gsm8k") for i in range(4)] + [
        _record(f"hotpotqa-{i:05d}", "hotpotqa") for i in range(4)
    ]
    candidate_rows = _candidate_rows(records)

    selected = mod.select_filtering_samples(
        records,
        candidate_rows,
        records_per_task={"gsm8k": 2, "hotpotqa": 2},
        seed=123,
    )
    changed = [
        {
            **record,
            "correctness": not bool(record["correctness"]),
            "final_answer": "target-field-mutated",
            "delta_u": 999,
        }
        for record in records
    ]
    selected_after_target_mutation = mod.select_filtering_samples(
        changed,
        candidate_rows,
        records_per_task={"gsm8k": 2, "hotpotqa": 2},
        seed=123,
    )

    assert [row["sample_id"] for row in selected] == [
        row["sample_id"] for row in selected_after_target_mutation
    ]
    assert {row["task_type"] for row in selected} == {"gsm8k", "hotpotqa"}
    assert sum(row["task_type"] == "gsm8k" for row in selected) == 2
    assert sum(row["task_type"] == "hotpotqa" for row in selected) == 2


def test_filtering_jobs_mask_low_and_high_candidate_spans() -> None:
    mod = _module()
    records = [_record("gsm8k-00001", "gsm8k")]
    selected = mod.select_filtering_samples(
        records,
        _candidate_rows(records),
        records_per_task={"gsm8k": 1},
        seed=7,
    )

    jobs = mod.build_filtering_replay_jobs(selected, _candidate_rows(records))

    assert [job["condition"] for job in jobs] == [
        "mask_low_retain_high",
        "mask_high_anti_filter",
    ]
    assert [job["span_index"] for job in jobs] == [1, 0]
    assert all("[REASONING_MASK]" in job["observable_prefix"] for job in jobs)
    assert jobs[0]["retained_span_index"] == 0
    assert jobs[1]["retained_span_index"] == 1
    assert all(job["post_target_leakage_detected"] is False for job in jobs)


def test_report_passes_only_for_positive_pooled_and_nonnegative_task_advantage() -> None:
    mod = _module()
    originals = [_record("gsm8k-00001", "gsm8k"), _record("hotpotqa-00001", "hotpotqa")]
    jobs = mod.build_filtering_replay_jobs(originals, _candidate_rows(originals))
    replay_records = [
        {"sample_id": "gsm8k-00001", "condition": "mask_low_retain_high", "final_answer": "5", "status": "success"},
        {"sample_id": "gsm8k-00001", "condition": "mask_high_anti_filter", "final_answer": "4", "status": "success"},
        {
            "sample_id": "hotpotqa-00001",
            "condition": "mask_low_retain_high",
            "final_answer": "Shakespeare",
            "status": "success",
        },
        {"sample_id": "hotpotqa-00001", "condition": "mask_high_anti_filter", "final_answer": "Marlowe", "status": "success"},
    ]

    report = mod.build_downstream_filtering_report(
        jobs=jobs,
        original_records=originals,
        replay_records=replay_records,
        api_attempts=4,
        cost_used_usd=1.25,
        approved_budget_usd=5.0,
        request_cap=60,
        min_valid_pairs=2,
        min_valid_pairs_per_task=1,
    )

    assert report["status"] == mod.V2_1_DOWNSTREAM_FILTERING_MINI_PASS
    assert report["GLOBAL_pass"] is True
    assert report["paired_metrics"]["pooled"]["mean_advantage"] > 0
    assert report["current_status_remains"] == "PILOT_BLOCKED"
    assert report["claim_upgrade_allowed"] is False

    replay_records[-1]["final_answer"] = "William Shakespeare"
    replay_records[2]["final_answer"] = "Marlowe"
    failed = mod.build_downstream_filtering_report(
        jobs=jobs,
        original_records=originals,
        replay_records=replay_records,
        api_attempts=4,
        cost_used_usd=1.25,
        approved_budget_usd=5.0,
        request_cap=60,
        min_valid_pairs=2,
        min_valid_pairs_per_task=1,
    )

    assert failed["status"] == mod.V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_FILTERING_SIGNAL
    assert failed["GLOBAL_pass"] is False
