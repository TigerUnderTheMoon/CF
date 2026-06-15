"""Guarded API preflight-only gates for the s_FMA_v2.2 fresh holdout."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .fresh_holdout import MANIFEST_OVERLAP_CLEAN
from .fresh_holdout_v2_2 import V2_2_CONTRACT_CLEAN
from .fresh_preflight import (
    API_PREFLIGHT_READY,
    PREFLIGHT_FAIL_COST,
    PREFLIGHT_FAIL_DRIFT,
    PREFLIGHT_FAIL_METADATA,
    PREFLIGHT_FAIL_SCHEMA_OR_TAGS,
    FreshPreflightError,
    select_preflight_records,
    summarize_fresh_preflight,
)
from .fresh_preflight_v2_1 import estimate_attempt_cost_usd


V2_2_API_PREFLIGHT_ONLY = "V2_2_API_PREFLIGHT_ONLY"
PREFLIGHT_FAIL_EMPTY_OUTPUT = "PREFLIGHT_FAIL_EMPTY_OUTPUT"
PREFLIGHT_FAIL_OUTPUT_EXTRACTION = "PREFLIGHT_FAIL_OUTPUT_EXTRACTION"
PREFLIGHT_FAIL_INCOMPLETE_RECORDS = "PREFLIGHT_FAIL_INCOMPLETE_RECORDS"
PREFLIGHT_FAIL_REQUEST_LIMIT = "PREFLIGHT_FAIL_REQUEST_LIMIT"
V2_2_STOCHASTIC_SMOKE_APPROVAL_REQUEST_ONLY = (
    "V2_2_STOCHASTIC_SMOKE_APPROVAL_REQUEST_ONLY"
)


class V2_2PreflightError(FreshPreflightError):
    """Raised when a hard v2.2 preflight boundary is violated."""


def prompt_bundle_hash_from_config(config: Mapping[str, Any]) -> str:
    """Return the v2.2 prompt bundle hash used by the prompt lock."""

    prompt_lock = config.get("prompt_lock", {})
    generation_prompt_file = Path(prompt_lock.get("generation_prompt_file", ""))
    replay_prompt_file = Path(prompt_lock.get("replay_prompt_file", ""))
    payload = {
        "generation_prompt_file": generation_prompt_file.as_posix(),
        "generation_prompt_text": generation_prompt_file.read_text(encoding="utf-8"),
        "replay_prompt_file": replay_prompt_file.as_posix(),
        "replay_prompt_text": replay_prompt_file.read_text(encoding="utf-8"),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "prompt-sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_v2_2_preflight_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    failure_audit: Mapping[str, Any],
    current_readiness: Mapping[str, Any],
    allow_api_preflight_only: bool,
    approved_budget_usd: float,
    current_prompt_version: str | None = None,
) -> dict[str, Any]:
    """Validate all user-approved v2.2 gates before any live API call."""

    if not allow_api_preflight_only:
        raise V2_2PreflightError(
            "v2.2 API preflight requires explicit --allow-api-preflight-only."
        )
    if approval_request.get("requested_scope") != V2_2_API_PREFLIGHT_ONLY:
        raise V2_2PreflightError(
            f"api_preflight_approval_request.json must request {V2_2_API_PREFLIGHT_ONLY}."
        )
    if approval_request.get("approval_status") != "REQUEST_ONLY_NOT_APPROVED":
        raise V2_2PreflightError(
            "api_preflight_approval_request.json must remain REQUEST_ONLY_NOT_APPROVED."
        )
    if approval_request.get("api_execution_authorized_by_this_request") is not False:
        raise V2_2PreflightError("approval request must remain request-only, not self-authorizing.")
    if current_readiness.get("status") != "PILOT_BLOCKED":
        raise V2_2PreflightError("current readiness status must remain PILOT_BLOCKED.")
    if current_readiness.get("pilot_pass") is True:
        raise V2_2PreflightError("current readiness must not report pilot_pass=true.")
    if contract_audit.get("status") != V2_2_CONTRACT_CLEAN:
        raise V2_2PreflightError("v2_2_contract_audit.json must be V2_2_CONTRACT_CLEAN.")
    if contract_audit.get("claim_upgrade_allowed") is not False:
        raise V2_2PreflightError("v2.2 contract audit must not allow claim upgrade.")
    if contract_audit.get("validation_or_pass_claim_allowed") is not False:
        raise V2_2PreflightError("v2.2 contract audit must not allow validation or pass claims.")
    if contract_audit.get("v2_1_failed_full_artifacts_used_as_tuning_source") is not False:
        raise V2_2PreflightError("v2.1 failed artifacts must not be v2.2 tuning sources.")
    _validate_failed_v2_1_provenance(failure_audit)

    if current_prompt_version:
        _validate_prompt_version_lock(
            config=config,
            contract_audit=contract_audit,
            approval_request=approval_request,
            current_prompt_version=current_prompt_version,
        )

    expected_total, expected_by_task = _configured_manifest_counts(config)
    if len(manifest) != expected_total:
        raise V2_2PreflightError(
            f"v2.2 fresh manifest row count is {len(manifest)}, expected {expected_total}."
        )
    observed_by_task = Counter(str(row.get("task_type") or "") for row in manifest)
    for task_type, expected_count in expected_by_task.items():
        observed_count = observed_by_task.get(task_type, 0)
        if observed_count != expected_count:
            raise V2_2PreflightError(
                f"v2.2 manifest has {observed_count} {task_type} rows, expected {expected_count}."
            )

    if overlap_audit.get("status") != MANIFEST_OVERLAP_CLEAN:
        raise V2_2PreflightError("manifest_overlap_audit.json must be MANIFEST_OVERLAP_CLEAN.")
    selected_overlaps = dict(
        overlap_audit.get("overlap_summary", {}).get("selected_overlaps_by_key", {})
    )
    required_overlap_keys = [
        "sample_id",
        "task_id",
        "dataset_config_split_source_index",
        "normalized_question_hash",
        "reference_answer_hash",
        "alias_hash",
    ]
    missing_keys = [key for key in required_overlap_keys if key not in selected_overlaps]
    nonzero = {
        key: selected_overlaps.get(key)
        for key in required_overlap_keys
        if int(selected_overlaps.get(key) or 0) != 0
    }
    if missing_keys or nonzero:
        raise V2_2PreflightError(
            "all six selected overlap keys must be present and zero before v2.2 API preflight."
        )

    requested_records = int(approval_request.get("requested_records") or 0)
    records_per_task = dict(approval_request.get("records_per_task") or {})
    if requested_records != 20 or records_per_task != {"gsm8k": 10, "hotpotqa": 10}:
        raise V2_2PreflightError("v2.2 API preflight approval must be exactly 20 records, 10 per task.")
    recommended_budget = float(approval_request.get("recommended_budget_ceiling_usd") or 0)
    if float(approved_budget_usd) != recommended_budget:
        raise V2_2PreflightError(
            "approved budget must match api_preflight_approval_request.json recommended_budget_ceiling_usd."
        )
    max_api_requests = int(approval_request.get("max_api_requests") or 0)
    if max_api_requests != 25:
        raise V2_2PreflightError("v2.2 API preflight max_api_requests must be exactly 25.")

    selected = select_preflight_records(
        manifest,
        samples_per_task=10,
        task_order=["gsm8k", "hotpotqa"],
    )
    determinism_repeats = int(
        config.get("api_preflight", {}).get("determinism_probe_repeats", 3)
        if isinstance(config.get("api_preflight", {}), Mapping)
        else 3
    )
    planned_requests = len(selected) + max(0, determinism_repeats)
    if planned_requests > max_api_requests:
        raise V2_2PreflightError(
            f"v2.2 API preflight plans {planned_requests} API requests, above max {max_api_requests}."
        )

    selected_counts = Counter(str(row.get("task_type") or "") for row in selected)
    return {
        "scope": V2_2_API_PREFLIGHT_ONLY,
        "api_call_allowed": True,
        "manifest_rows": len(manifest),
        "manifest_counts_by_task": dict(observed_by_task),
        "selected_records": len(selected),
        "selected_counts_by_task": dict(selected_counts),
        "selected_overlaps_by_key": selected_overlaps,
        "approved_budget_usd": float(approved_budget_usd),
        "max_api_requests": max_api_requests,
        "determinism_probe_repeats": determinism_repeats,
        "planned_api_requests": planned_requests,
        "prompt_version": current_prompt_version,
        "yaml_parse_status": "YAML_PARSE_OK",
        "current_status_remains": "PILOT_BLOCKED",
    }


def build_v2_2_generation_config(
    config: Mapping[str, Any],
    *,
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a live preflight config without mutating the request-only YAML."""

    cloned = deepcopy(dict(config))
    experiment = dict(cloned.get("experiment", {}))
    planned_requests = int(readiness.get("planned_api_requests") or readiness.get("max_api_requests") or 25)
    experiment["user_approved_budget_usd"] = float(readiness["approved_budget_usd"])
    experiment["max_api_requests_pilot"] = planned_requests
    experiment["pilot_generation_requests"] = planned_requests
    cloned["experiment"] = experiment

    api_preflight = dict(cloned.get("api_preflight", {}))
    api_preflight.setdefault("mode", V2_2_API_PREFLIGHT_ONLY)
    api_preflight.setdefault("samples_per_task", 10)
    api_preflight.setdefault("total_records", 20)
    api_preflight.setdefault("determinism_probe_repeats", int(readiness.get("determinism_probe_repeats", 3)))
    api_preflight.setdefault("cost_ceiling_usd", float(readiness["approved_budget_usd"]))
    api_preflight.setdefault("max_api_requests", int(readiness["max_api_requests"]))
    cloned["api_preflight"] = api_preflight

    api = dict(cloned.get("api", {}))
    api.setdefault("endpoint", "/v1/responses")
    api.setdefault("api_date", "2026-06-05")
    api.setdefault("service_tier", "default")
    api.setdefault("store", False)
    api.setdefault("request_timeout_seconds", 45)
    cloned["api"] = api

    model = dict(cloned.get("model", {}))
    model.setdefault("primary", "gpt-5.5")
    model.setdefault("fallback_order", [model["primary"]])
    model.setdefault("temperature", 0.0)
    model.setdefault("top_p", 1.0)
    model.setdefault("max_output_tokens", 2048)
    cloned["model"] = model

    pricing = dict(cloned.get("pricing", {}))
    pricing.setdefault("input_per_million_usd", 5.0)
    pricing.setdefault("output_per_million_usd", 30.0)
    pricing.setdefault("basis", "s_FMA_v2.2 API preflight-only ceiling")
    cloned["pricing"] = pricing

    prompt_lock = cloned.get("prompt_lock", {})
    generation = dict(cloned.get("generation", {}))
    generation.setdefault(
        "prompt_file",
        prompt_lock.get("generation_prompt_file", "prompts/s_fma_v2_2_reflection_generation.txt"),
    )
    generation.setdefault("required_tag", "reflection")
    generation.setdefault("trace_field", "observable_trace")
    generation.setdefault("minimum_schema_success_rate", 1.0)
    generation.setdefault("minimum_tag_success_rate", 1.0)
    cloned["generation"] = generation

    reflection_type_policy = dict(cloned.get("reflection_type_policy", {}))
    reflection_type_policy.setdefault("policy_name", "v2_2_generation_schema_lock")
    reflection_type_policy.setdefault("allowed_types", list(prompt_lock.get("allowed_reflection_types") or []))
    reflection_type_policy.setdefault("alias_canonicalization", {})
    reflection_type_policy.setdefault("unknown_type_policy", "reject")
    cloned["reflection_type_policy"] = reflection_type_policy

    api_policy = dict(cloned.get("api_policy", {}))
    logging = dict(api_policy.get("api_logging", {}))
    logging.setdefault(
        "required_fields",
        [
            "api_date",
            "endpoint",
            "model",
            "service_tier",
            "request_parameters",
            "response_id",
            "sdk_or_transport_version",
        ],
    )
    logging.setdefault("disclosure_fields", ["system_fingerprint", "fallback_model"])
    api_policy["api_logging"] = logging
    cloned["api_policy"] = api_policy
    return cloned


def build_v2_2_preflight_report(
    attempts: Sequence[Mapping[str, Any]],
    *,
    selected_records: Sequence[Mapping[str, Any]],
    drift_outputs: Sequence[str],
    config: Mapping[str, Any],
    readiness: Mapping[str, Any],
    cost_attempts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize v2.2 preflight attempts without unlocking execution claims."""

    report = summarize_fresh_preflight(
        attempts,
        selected_records=selected_records,
        drift_outputs=drift_outputs,
        config=config,
        cost_attempts=cost_attempts,
    )
    expected_records = int(readiness.get("selected_records") or len(selected_records))
    max_requests = int(readiness.get("max_api_requests") or report.get("api_attempts") or 0)
    approved_budget = float(readiness.get("approved_budget_usd") or 0)
    actual_requests = int(report.get("api_attempts") or 0)
    cost_used = report.get("cost_used_usd")
    cost_over_budget = cost_used is not None and float(cost_used) > approved_budget
    request_over_limit = max_requests > 0 and actual_requests > max_requests
    incomplete_records = int(report.get("records_evaluated") or 0) != expected_records
    empty_output_summary = _empty_output_summary(attempts)
    raw_output_nonempty_rate = (
        empty_output_summary["raw_output_nonempty_count"] / empty_output_summary["attempt_count"]
        if empty_output_summary["attempt_count"]
        else 0.0
    )
    all_raw_output_empty = (
        empty_output_summary["attempt_count"] > 0
        and empty_output_summary["raw_output_empty_count"]
        == empty_output_summary["attempt_count"]
    )
    any_empty_raw_output = empty_output_summary["raw_output_empty_count"] > 0

    failure_codes = list(report.get("failure_codes") or [])
    if incomplete_records:
        failure_codes.append(PREFLIGHT_FAIL_INCOMPLETE_RECORDS)
    if request_over_limit:
        failure_codes.append(PREFLIGHT_FAIL_REQUEST_LIMIT)
    if cost_over_budget:
        failure_codes.append(PREFLIGHT_FAIL_COST)
    if all_raw_output_empty:
        failure_codes.append(PREFLIGHT_FAIL_EMPTY_OUTPUT)
        failure_codes.append(PREFLIGHT_FAIL_OUTPUT_EXTRACTION)
    elif any_empty_raw_output:
        failure_codes.append(PREFLIGHT_FAIL_OUTPUT_EXTRACTION)
    if float(report.get("json_parse_success_rate", 0.0)) < 1.0:
        failure_codes.append("PREFLIGHT_FAIL_SCHEMA")
    if float(report.get("schema_success_rate", 0.0)) < 1.0:
        failure_codes.append("PREFLIGHT_FAIL_SCHEMA")
    if float(report.get("tag_extraction_success_rate", 0.0)) < 1.0:
        failure_codes.append("PREFLIGHT_FAIL_TAG")
    if float(report.get("final_answer_parse_success_rate", 0.0)) < 1.0:
        failure_codes.append("PREFLIGHT_FAIL_FINAL_ANSWER")
    metadata_disclosure_missing_counts = dict(
        report.get("metadata_disclosure_missing_counts") or {}
    )
    metadata_disclosure_failure = any(
        int(count or 0) > 0 for count in metadata_disclosure_missing_counts.values()
    )
    if (
        float(report.get("required_metadata_success_rate", 0.0)) < 1.0
        or metadata_disclosure_failure
    ):
        failure_codes.append(PREFLIGHT_FAIL_METADATA)
    failure_codes = sorted({code for code in failure_codes if code})

    schema_or_tag_or_final_failure = (
        report.get("status") == PREFLIGHT_FAIL_SCHEMA_OR_TAGS
        or "PREFLIGHT_FAIL_SCHEMA" in failure_codes
        or "PREFLIGHT_FAIL_TAG" in failure_codes
        or "PREFLIGHT_FAIL_FINAL_ANSWER" in failure_codes
        or float(report.get("json_parse_success_rate", 0.0)) < 1.0
        or float(report.get("schema_success_rate", 0.0)) < 1.0
        or float(report.get("tag_extraction_success_rate", 0.0)) < 1.0
        or float(report.get("final_answer_parse_success_rate", 0.0)) < 1.0
    )
    required_metadata_failure = float(report.get("required_metadata_success_rate", 0.0)) < 1.0
    metadata_failure = required_metadata_failure or metadata_disclosure_failure
    request_and_budget_ok = (
        not incomplete_records
        and not request_over_limit
        and not cost_over_budget
        and actual_requests <= max_requests
    )

    if cost_over_budget or request_over_limit:
        report["status"] = PREFLIGHT_FAIL_COST
    elif all_raw_output_empty:
        report["status"] = PREFLIGHT_FAIL_EMPTY_OUTPUT
    elif schema_or_tag_or_final_failure:
        report["status"] = PREFLIGHT_FAIL_SCHEMA_OR_TAGS
    elif metadata_failure and report.get("drift_status") != PREFLIGHT_FAIL_DRIFT:
        report["status"] = PREFLIGHT_FAIL_METADATA

    drift_disclosed = report.get("drift_status") in {
        PREFLIGHT_FAIL_DRIFT,
        "DETERMINISTIC_REPLAY_FEASIBLE",
    }
    stochastic_smoke_request_allowed = (
        request_and_budget_ok
        and not schema_or_tag_or_final_failure
        and not all_raw_output_empty
        and not any_empty_raw_output
        and not metadata_failure
        and drift_disclosed
        and report.get("status") in {API_PREFLIGHT_READY, PREFLIGHT_FAIL_DRIFT}
    )

    root_cause_classification = "not_empty_output_failure"
    if all_raw_output_empty:
        root_cause_classification = "transport_or_output_extraction_failure_suspected"
    elif any_empty_raw_output:
        root_cause_classification = "partial_output_extraction_failure_suspected"

    report.update(
        {
            "scope": V2_2_API_PREFLIGHT_ONLY,
            "failure_codes": failure_codes,
            "empty_output_summary": empty_output_summary,
            "raw_output_nonempty_rate": raw_output_nonempty_rate,
            "root_cause_classification": root_cause_classification,
            "approved_budget_usd": approved_budget,
            "max_api_requests": max_requests,
            "actual_api_requests": actual_requests,
            "actual_cost_usd": cost_used,
            "records_expected": expected_records,
            "v2_2_stochastic_smoke_approval_request_allowed": stochastic_smoke_request_allowed,
            "v2_2_stochastic_smoke_approval_request_scope": (
                V2_2_STOCHASTIC_SMOKE_APPROVAL_REQUEST_ONLY
                if stochastic_smoke_request_allowed
                else "not_allowed"
            ),
            "smoke_execution_allowed": False,
            "no_smoke": True,
            "no_pilot": True,
            "no_full_validation": True,
            "no_full_generation": True,
            "no_replay": True,
            "no_v2_2_scoring": True,
            "no_prm_claim": True,
            "task_specific_pass_claim_allowed": False,
            "global_pass_claim_allowed": False,
            "deterministic_replay_claim_allowed": False,
            "claim_upgrade_allowed": False,
            "current_status_remains": "PILOT_BLOCKED",
            "s_fma_v2_2_status": "planned-only-api-preflight-run",
            "next_allowed_step": (
                "REQUEST_V2_2_STOCHASTIC_SMOKE_APPROVAL"
                if stochastic_smoke_request_allowed
                else "STOP_AND_FIX_PREFLIGHT"
            ),
        }
    )
    return report


def _validate_prompt_version_lock(
    *,
    config: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    current_prompt_version: str,
) -> None:
    prompt_lock = config.get("prompt_lock", {})
    contract_prompt = contract_audit.get("checks", {}).get("prompt_lock", {})
    observed = {
        "config": str(prompt_lock.get("prompt_version") or ""),
        "contract": str(contract_audit.get("prompt_version") or ""),
        "contract_check": str(contract_prompt.get("details", {}).get("prompt_version") or ""),
        "approval": str(approval_request.get("prompt_version") or ""),
        "current": current_prompt_version,
    }
    expected = set(observed.values())
    if expected != {current_prompt_version}:
        raise V2_2PreflightError(
            "v2.2 prompt hash mismatch across config, contract audit, approval request, "
            "generation prompt, or replay prompt."
        )


def _validate_failed_v2_1_provenance(failure_audit: Mapping[str, Any]) -> None:
    boundary = failure_audit.get("status_boundary", {})
    clean = (
        failure_audit.get("provenance_status") == "failed_full_validation_provenance"
        and failure_audit.get("source_full_validation_status")
        == "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS"
        and boundary.get("full_validation_task_specific_pass") is False
        and boundary.get("full_validation_global_pass") is False
        and boundary.get("current_status_remains") == "PILOT_BLOCKED"
    )
    if not clean:
        raise V2_2PreflightError(
            "v2.1 full validation failure provenance must remain failed and PILOT_BLOCKED."
        )


def _configured_manifest_counts(config: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
    tasks = config.get("fresh_split_policy", {}).get("tasks", {})
    if not isinstance(tasks, Mapping) or not tasks:
        raise V2_2PreflightError("fresh_split_policy.tasks must be configured.")
    counts = {
        str(task_type): int(task_config.get("planned_sample_count", 0))
        for task_type, task_config in tasks.items()
    }
    return sum(counts.values()), counts


def _empty_output_summary(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    raw_values = [attempt.get("raw_output") for attempt in attempts]
    empty_count = sum(1 for value in raw_values if not _has_nonempty_raw_output(value))
    diagnostics_present = sum(
        1
        for attempt in attempts
        if isinstance(attempt.get("output_extraction_diagnostics"), Mapping)
        and bool(attempt.get("output_extraction_diagnostics"))
    )
    response_id_present = sum(1 for attempt in attempts if attempt.get("response_id"))
    usage_present = sum(
        1
        for attempt in attempts
        if isinstance(attempt.get("usage"), Mapping) and bool(attempt.get("usage"))
    )
    return {
        "attempt_count": len(attempts),
        "raw_output_empty_count": empty_count,
        "raw_output_nonempty_count": len(attempts) - empty_count,
        "any_nonempty_raw_output": empty_count < len(attempts) if attempts else False,
        "response_id_present_count": response_id_present,
        "usage_present_count": usage_present,
        "output_extraction_diagnostics_present_count": diagnostics_present,
    }


def _has_nonempty_raw_output(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    return True
