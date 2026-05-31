from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fma.real_task_pilot.baselines import (
    FORBIDDEN_BASELINE_SOURCE_FIELDS,
    build_baseline_leakage_audit,
    question_difficulty_proxy,
    score_independent_baselines,
)
from fma.real_task_pilot.hygiene import scan_hygiene
from fma.real_task_pilot.metrics import exact_match, normalized_token_f1, score_answer
from fma.real_task_pilot.generation import (
    build_generation_summary,
    generate_trace_with_fallback,
    normalize_trace_record,
)
from fma.real_task_pilot.openai_client import ApiCallResult
from fma.real_task_pilot.parsing import extract_reflection_spans
from fma.real_task_pilot.preflight import evaluate_preflight, token_diff_ratio
from fma.real_task_pilot.protocol import (
    BLOCKED_STATUS,
    REVISED_STATUS,
    build_api_determinism_blocker,
    build_nondeterministic_protocol,
    protocol_allows_generation,
)
from fma.real_task_pilot.readiness import build_readiness_audit
from fma.real_task_pilot.replay import build_replay_prefix, compute_delta_u
from fma.real_task_pilot.schema import structured_output_text_format, validate_trace_record
from fma.real_task_pilot.sampling import (
    build_sample_manifest,
    normalize_real_task_source_row,
    validate_manifest_for_live_api,
)


@dataclass
class FakeAdapter:
    outputs: list[Any]
    openai_version: str = "fake-openai-0"

    def create_trace(self, *, prompt, config, model_name, json_mode=False):
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return ApiCallResult(
            output_text=json.dumps(value),
            model_name=model_name,
            system_fingerprint="fp_fake",
            usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            raw_response=value,
            request_metadata={"seed_sent": True, "reasoning_sent": True},
        )


def valid_record(sample_id: str = "gsm8k-00001") -> dict:
    trace = (
        "We compute 2 + 3 = 5.\n"
        "<reflection type=\"verification\">Check the arithmetic before finalizing.</reflection>\n"
        "The sum is still 5.\n"
        "Final Answer: 5"
    )
    spans = extract_reflection_spans(trace)
    return {
        "sample_id": sample_id,
        "task_id": sample_id,
        "task_type": "gsm8k",
        "question": "What is 2 + 3?",
        "observable_trace": trace,
        "reflection_spans": spans,
        "final_answer": "5",
        "reference_answer": "#### 5",
        "correctness": True,
        "model_name": "gpt-5.5",
        "generation_config": {"endpoint": "/v1/responses", "seed": 20260530},
        "system_fingerprint": "fp_test",
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
    }


def test_schema_accepts_observable_trace_and_reflection_spans() -> None:
    record = valid_record()
    output_format = structured_output_text_format()

    assert validate_trace_record(record) == []
    assert output_format["type"] == "json_schema"
    assert output_format["schema"]["additionalProperties"] is False
    assert set(output_format["schema"]["required"]) == {"observable_trace", "final_answer"}
    assert record["reflection_spans"][0]["operation_type"] == "verification"


def test_generation_normalizes_api_payload_to_schema_record() -> None:
    sample = {
        "sample_id": "hotpotqa-00001",
        "task_id": "hp-1",
        "task_type": "hotpotqa",
        "question": "Who wrote Hamlet?",
        "reference_answer": "William Shakespeare",
        "aliases": ["Shakespeare"],
    }
    payload = {
        "observable_trace": (
            "The question asks for the author. "
            "<reflection type=\"verification\">Hamlet is a play by Shakespeare.</reflection> "
            "Final Answer: Shakespeare"
        )
    }

    record = normalize_trace_record(
        payload,
        sample=sample,
        model_name="gpt-5.5",
        generation_config={"structured_output_mode": "json_schema"},
        system_fingerprint="fp_fake",
        usage={"total_tokens": 3},
    )

    assert validate_trace_record(record) == []
    assert record["correctness"] is True
    assert record["reflection_spans"][0]["operation_type"] == "verification"


def test_generation_fallback_tries_next_model_then_selects_valid_output() -> None:
    adapter = FakeAdapter(
        outputs=[
            RuntimeError("model unavailable"),
            {"bad": "record"},
            valid_record("gsm8k-00002"),
        ]
    )
    sample = valid_record("gsm8k-00002")
    config = {
        "experiment": {"seed": 20260530},
        "api": {"endpoint": "/v1/responses", "api_date": "2026-05-30"},
        "model": {
            "primary": "gpt-5.5",
            "fallback_order": ["gpt-5.5", "gpt-5.1", "gpt-4o-2024-08-06"],
            "reasoning": {"effort": "none"},
        },
    }

    result = generate_trace_with_fallback(
        sample,
        adapter=adapter,
        config=config,
        prompt_template="Task type: {task_type}\nQuestion: {question}",
    )
    summary = build_generation_summary([result])

    assert result.record is not None
    assert result.model_name == "gpt-4o-2024-08-06"
    assert result.record["generation_config"]["api_request_metadata"]["seed_sent"] is True
    assert summary["valid_records"] == 1
    assert any(event["status"] == "api_error" for event in result.fallback_events)


def test_hotpotqa_exact_match_and_f1_are_non_llm_metrics() -> None:
    assert exact_match("The United States.", "United States", task_type="hotpotqa")
    assert score_answer("hotpotqa", "USA", "United States", aliases=["USA"])["score"] == 1.0
    assert normalized_token_f1("red blue", "red green") == 0.5


def test_preflight_schema_drift_and_budget_gates() -> None:
    config = {
        "experiment": {"user_approved_budget_usd": 5, "max_api_requests_pilot": 40},
        "generation": {
            "minimum_schema_success_rate": 0.95,
            "minimum_tag_success_rate": 0.95,
        },
    }
    outputs = [valid_record(f"gsm8k-{index:05d}") for index in range(20)]

    report = evaluate_preflight(outputs, drift_outputs=["a b c", "a b c"], config=config)

    assert report["api_preflight_report"]["status"] == "pass"
    assert report["schema_compliance_report"]["fallback_required"] is False
    assert report["determinism_drift_report"]["determinism_gate_pass"] is True
    assert token_diff_ratio("a b c", "a x c") == 1 / 3


def test_preflight_reports_tag_gate_separately_from_schema() -> None:
    config = {
        "experiment": {"user_approved_budget_usd": 5, "pilot_generation_requests": 40},
        "generation": {
            "minimum_schema_success_rate": 0.95,
            "minimum_tag_success_rate": 0.95,
        },
    }
    outputs = [valid_record(f"gsm8k-{index:05d}") for index in range(20)]
    for record in outputs[-2:]:
        record["observable_trace"] = "The answer is 5.\nFinal Answer: 5"

    report = evaluate_preflight(outputs, config=config)

    assert "PREFLIGHT_FAIL_TAG" in report["api_preflight_report"]["failure_codes"]
    assert "PREFLIGHT_FAIL_SCHEMA" not in report["api_preflight_report"]["failure_codes"]
    assert report["schema_compliance_report"]["schema_gate_pass"] is True
    assert report["schema_compliance_report"]["tag_gate_pass"] is False


def test_preflight_attempt_denominator_includes_invalid_outputs() -> None:
    config = {
        "experiment": {"user_approved_budget_usd": 5, "pilot_generation_requests": 40},
        "pricing": {"input_per_million_usd": 5, "output_per_million_usd": 30},
    }
    attempts = [
        {"preflight_attempt": True, "record": valid_record(f"gsm8k-{index:05d}"), "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}}
        for index in range(18)
    ]
    attempts.extend(
        [
            {"preflight_attempt": True, "record": None, "raw_output": "not json", "usage": {"input_tokens": 7, "output_tokens": 11, "total_tokens": 18}},
            {"preflight_attempt": True, "record": None, "raw_output": "", "usage": {"input_tokens": 8, "output_tokens": 12, "total_tokens": 20}},
        ]
    )

    report = evaluate_preflight(attempts, config=config)

    assert report["api_preflight_report"]["records_evaluated"] == 20
    assert report["api_preflight_report"]["json_parse_success_rate"] == 0.9
    assert report["cost_and_rate_limit_report"]["usage_totals"]["input_tokens"] == 195
    assert "PREFLIGHT_FAIL_SCHEMA" in report["api_preflight_report"]["failure_codes"]


def test_cost_projection_uses_pilot_generation_requests_and_budget() -> None:
    config = {
        "experiment": {
            "user_approved_budget_usd": 150,
            "pilot_generation_requests": 400,
            "max_api_requests_pilot": 3600,
        },
        "pricing": {"input_per_million_usd": 5, "output_per_million_usd": 30},
    }
    outputs = [valid_record(f"gsm8k-{index:05d}") for index in range(20)]

    report = evaluate_preflight(outputs, config=config)

    assert report["cost_and_rate_limit_report"]["projected_requests"] == 400
    assert report["cost_and_rate_limit_report"]["budget_gate_pass"] is True
    assert report["cost_and_rate_limit_report"]["projected_cost_usd"] == 0.26


def test_preflight_triggers_fallback_on_invalid_schema() -> None:
    config = {"experiment": {"user_approved_budget_usd": 5}}
    outputs = [valid_record(f"gsm8k-{index:05d}") for index in range(18)] + [
        {"bad": "record"},
        {"also_bad": "record"},
    ]

    report = evaluate_preflight(outputs, config=config)

    assert report["schema_compliance_report"]["fallback_required"] is True
    assert "PREFLIGHT_FAIL_SCHEMA" in report["api_preflight_report"]["failure_codes"]


def test_preflight_discloses_non_deterministic_drift() -> None:
    config = {"experiment": {"user_approved_budget_usd": 5}}
    outputs = [valid_record(f"gsm8k-{index:05d}") for index in range(20)]

    report = evaluate_preflight(
        outputs,
        drift_outputs=[
            "alpha beta gamma",
            "alpha totally different gamma",
            "unrelated output tokens",
        ],
        config=config,
    )

    assert "PREFLIGHT_FAIL_DRIFT" in report["api_preflight_report"]["failure_codes"]
    assert report["determinism_drift_report"]["paper_disclosure_required"] is True


def test_replay_prefix_masks_target_span_without_post_target_leakage() -> None:
    record = valid_record()
    prefix = build_replay_prefix(record, span_index=0)

    assert "[REASONING_MASK]" in prefix["observable_prefix"]
    assert prefix["question"] == record["question"]
    assert prefix["reference_answer"] == record["reference_answer"]
    assert prefix["prefix_token_delta"] == 0
    assert prefix["token_preservation_status"] == "proxy_exact"
    assert prefix["post_target_leakage_detected"] is False
    assert "The sum is still 5" not in prefix["observable_prefix"]


def test_delta_u_uses_task_exact_match() -> None:
    original = valid_record()
    intervened = {**original, "final_answer": "4"}

    delta = compute_delta_u(original, intervened)

    assert delta["original_score"] == 1.0
    assert delta["intervened_score"] == 0.0
    assert delta["delta_u"] == 1.0


def test_independent_baselines_use_no_target_like_fields() -> None:
    record = valid_record()
    rows = score_independent_baselines([record])
    audit = build_baseline_leakage_audit(rows)
    difficulty = question_difficulty_proxy(record)

    assert rows[0]["forbidden_fields_used"] == []
    assert audit["target_leakage_status"] == "clean"
    assert FORBIDDEN_BASELINE_SOURCE_FIELDS.isdisjoint(rows[0]["source_fields_used"])
    assert set(difficulty["features"]) == {
        "question_length",
        "number_count",
        "entity_count",
        "supporting_fact_count",
    }


def test_readiness_requires_clean_gates_and_positive_rank_signal() -> None:
    audit = build_readiness_audit(
        preflight_report={"status": "pass", "failure_codes": []},
        valid_trace_count=300,
        span_validity_rate=0.90,
        replay_success_rate=0.85,
        baseline_leakage_clean=True,
        cost_report_complete=True,
        tests_passed=True,
        hygiene_clean=True,
        signal_report={
            "per_task": {"gsm8k": {"spearman_ci_lower_gt_zero": True}},
            "pooled": {"spearman_ci_lower_gt_zero": True},
        },
    )

    assert audit["status"] == "PILOT_PASS"
    assert audit["gates"]["expand_to_top_tier_scale"] is True


def test_hygiene_scan_reports_forbidden_phrases(tmp_path) -> None:
    path = tmp_path / "paper.md"
    path.write_text("This is a true causal effect.\n", encoding="utf-8")

    report = scan_hygiene([path])

    assert report["hygiene_clean"] is False
    assert report["forbidden_findings"][0]["pattern"] == "true causal effect"


def test_sample_manifest_is_task_balanced_and_deterministic() -> None:
    gsm8k_rows = [
        {"question": "What is 2 + 3?", "answer": "#### 5"},
        {"question": "What is 4 + 6?", "answer": "#### 10"},
    ]
    hotpot_rows = [
        {"_id": "hp-1", "question": "Who wrote Hamlet?", "answer": "William Shakespeare"},
        {"_id": "hp-2", "question": "Where is the Eiffel Tower?", "answer": "France"},
    ]

    first = build_sample_manifest(gsm8k_rows, hotpot_rows, seed=7, max_per_task=1)
    second = build_sample_manifest(gsm8k_rows, hotpot_rows, seed=7, max_per_task=1)

    assert first == second
    assert [row["task_type"] for row in first] == ["gsm8k", "hotpotqa"]
    assert all("manifest_order_key" in row for row in first)
    assert len({row["manifest_hash"] for row in first}) == 1


def test_real_data_normalization_and_manifest_provenance() -> None:
    source = normalize_real_task_source_row(
        {"question": "What is 2 + 3?", "answer": "#### 5"},
        task_type="gsm8k",
        source_dataset="gsm8k",
        source_config="main",
        source_split="test",
        source_index=17,
    )

    manifest = build_sample_manifest([source], [], seed=7, max_per_task=1)

    assert manifest[0]["sample_id"] == "gsm8k-00017"
    assert manifest[0]["source_dataset"] == "gsm8k"
    assert manifest[0]["source_split"] == "test"
    assert validate_manifest_for_live_api(manifest, source_path="outputs/real_task_pilot/sample_manifest.json") == []


def test_live_manifest_rejects_fixture_or_missing_provenance() -> None:
    record = valid_record()

    fixture_errors = validate_manifest_for_live_api(
        [{**record, "manifest_hash": "abc"}],
        source_path="tests/fixtures/real_task_traces.jsonl",
    )
    missing_errors = validate_manifest_for_live_api(
        [{**record, "manifest_hash": "abc"}],
        source_path="outputs/real_task_pilot/sample_manifest.json",
    )

    assert any("fixtures" in error for error in fixture_errors)
    assert any("source_dataset" in error for error in missing_errors)


def test_api_determinism_blocker_and_revised_protocol() -> None:
    blocker = build_api_determinism_blocker(
        api_preflight_report={"status": "fail", "failure_codes": ["PREFLIGHT_FAIL_DRIFT"]},
        seed_transport_report={"seed_requested": True, "seed_sent_rate": 0.0},
        seed_model_probe={
            "passing_models": [],
            "models": [
                {
                    "model_name": "gpt-5.5",
                    "valid_records": 3,
                    "attempts": 3,
                    "seed_sent_rate": 0.0,
                    "max_token_diff_ratio": 0.5,
                    "drift_gate_pass": False,
                }
            ],
        },
    )
    protocol = build_nondeterministic_protocol(
        config={
            "experiment": {"user_approved_budget_usd": 150},
            "nondeterministic_protocol": {
                "allow_400_trace_generation": True,
                "repeats": {"replay_per_span": 3, "key_sample_replay_per_span": 5},
                "bootstrap": {"resamples": 10000, "confidence_level": 0.95},
                "gates": {"minimum_valid_traces": 300},
            },
        },
        blocker=blocker,
    )

    assert blocker["status"] == BLOCKED_STATUS
    assert blocker["decision"]["run_400_deterministic_pilot"] is False
    assert protocol["status"] == REVISED_STATUS
    assert protocol["repeats"]["replay_per_span"] == 3
    assert protocol["bootstrap"]["resamples"] == 10000
    assert protocol["gates"]["effect_gate"] == "bootstrap_ci_lower_gt_zero_by_task_or_pooled_with_task_pass"
    assert protocol_allows_generation(protocol) is True
    assert protocol_allows_generation({"status": BLOCKED_STATUS}) is False
