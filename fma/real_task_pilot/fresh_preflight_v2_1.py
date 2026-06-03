"""Guarded API preflight-only gates for the s_FMA_v2.1 fresh holdout."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .fresh_holdout_v2_1 import V2_1_CONTRACT_CLEAN
from .fresh_preflight import (
    API_PREFLIGHT_READY,
    PREFLIGHT_FAIL_COST,
    PREFLIGHT_FAIL_DRIFT,
    PREFLIGHT_FAIL_SCHEMA_OR_TAGS,
    FreshPreflightError,
    select_preflight_records,
    summarize_fresh_preflight,
)


V2_1_API_PREFLIGHT_ONLY = "V2_1_API_PREFLIGHT_ONLY"
PREFLIGHT_FAIL_INCOMPLETE_RECORDS = "PREFLIGHT_FAIL_INCOMPLETE_RECORDS"
PREFLIGHT_FAIL_REQUEST_LIMIT = "PREFLIGHT_FAIL_REQUEST_LIMIT"


class V2_1PreflightError(FreshPreflightError):
    """Raised when a hard v2.1 preflight boundary is violated."""


def validate_v2_1_preflight_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    current_readiness: Mapping[str, Any],
    allow_api_preflight_only: bool,
    approved_budget_usd: float,
    current_prompt_version: str | None = None,
) -> dict[str, Any]:
    """Validate all user-approved v2.1 gates before any live API call."""

    if not allow_api_preflight_only:
        raise V2_1PreflightError(
            "v2.1 API preflight requires explicit --allow-api-preflight-only."
        )
    if approval_request.get("requested_scope") != V2_1_API_PREFLIGHT_ONLY:
        raise V2_1PreflightError(
            f"api_preflight_approval_request.json must request {V2_1_API_PREFLIGHT_ONLY}."
        )
    if current_readiness.get("status") != "PILOT_BLOCKED":
        raise V2_1PreflightError("current readiness status must remain PILOT_BLOCKED.")
    if current_readiness.get("pilot_pass") is True:
        raise V2_1PreflightError("current readiness must not report pilot_pass=true.")
    if contract_audit.get("status") != V2_1_CONTRACT_CLEAN:
        raise V2_1PreflightError("v2_1_contract_audit.json must be V2_1_CONTRACT_CLEAN.")
    if contract_audit.get("claim_upgrade_allowed") is not False:
        raise V2_1PreflightError("v2.1 contract audit must not allow claim upgrade.")
    if current_prompt_version:
        _validate_prompt_version_lock(
            manifest=manifest,
            contract_audit=contract_audit,
            current_prompt_version=current_prompt_version,
        )

    expected_total, expected_by_task = _configured_manifest_counts(config)
    if len(manifest) != expected_total:
        raise V2_1PreflightError(
            f"v2.1 fresh manifest row count is {len(manifest)}, expected {expected_total}."
        )
    observed_by_task = Counter(str(row.get("task_type") or "") for row in manifest)
    for task_type, expected_count in expected_by_task.items():
        observed_count = observed_by_task.get(task_type, 0)
        if observed_count != expected_count:
            raise V2_1PreflightError(
                f"v2.1 manifest has {observed_count} {task_type} rows, expected {expected_count}."
            )

    if overlap_audit.get("status") != "MANIFEST_OVERLAP_CLEAN":
        raise V2_1PreflightError("manifest_overlap_audit.json must be MANIFEST_OVERLAP_CLEAN.")
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
        raise V2_1PreflightError(
            "all six selected overlap keys must be present and zero before v2.1 API preflight."
        )

    requested_records = int(approval_request.get("requested_records") or 0)
    records_per_task = dict(approval_request.get("records_per_task") or {})
    if requested_records != 20 or records_per_task != {"gsm8k": 10, "hotpotqa": 10}:
        raise V2_1PreflightError("v2.1 API preflight approval must be exactly 20 records, 10 per task.")
    recommended_budget = float(approval_request.get("recommended_budget_ceiling_usd") or 0)
    if float(approved_budget_usd) != recommended_budget:
        raise V2_1PreflightError(
            "approved budget must match api_preflight_approval_request.json recommended_budget_ceiling_usd."
        )
    max_api_requests = int(approval_request.get("max_api_requests") or 0)
    if max_api_requests <= 0 or max_api_requests > 25:
        raise V2_1PreflightError("v2.1 API preflight max_api_requests must be positive and no more than 25.")

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
        raise V2_1PreflightError(
            f"v2.1 API preflight plans {planned_requests} API requests, above max {max_api_requests}."
        )

    selected_counts = Counter(str(row.get("task_type") or "") for row in selected)
    return {
        "scope": V2_1_API_PREFLIGHT_ONLY,
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
        "current_status_remains": "PILOT_BLOCKED",
    }


def _validate_prompt_version_lock(
    *,
    manifest: Sequence[Mapping[str, Any]],
    contract_audit: Mapping[str, Any],
    current_prompt_version: str,
) -> None:
    manifest_versions = {
        str(row.get("prompt_version") or "")
        for row in manifest
    }
    manifest_versions.discard("")
    prompt_policy = contract_audit.get("checks", {}).get("prompt_policy", {})
    contract_version = str(
        contract_audit.get("prompt_version")
        or prompt_policy.get("details", {}).get("prompt_version")
        or ""
    )
    if manifest_versions != {current_prompt_version} or contract_version != current_prompt_version:
        raise V2_1PreflightError(
            "v2.1 prompt version lock mismatch; regenerate the manifest, contract audit, "
            "and approval request before API preflight."
        )


def build_v2_1_generation_config(
    config: Mapping[str, Any],
    *,
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a live preflight config without mutating the planned-only YAML."""

    cloned = deepcopy(dict(config))
    experiment = dict(cloned.get("experiment", {}))
    planned_requests = int(readiness.get("planned_api_requests") or readiness.get("max_api_requests") or 25)
    experiment["user_approved_budget_usd"] = float(readiness["approved_budget_usd"])
    experiment["max_api_requests_pilot"] = planned_requests
    experiment["pilot_generation_requests"] = planned_requests
    cloned["experiment"] = experiment

    api_preflight = dict(cloned.get("api_preflight", {}))
    api_preflight.setdefault("mode", "API_PREFLIGHT_ONLY")
    api_preflight.setdefault("samples_per_task", 10)
    api_preflight.setdefault("total_records", 20)
    api_preflight.setdefault("determinism_probe_repeats", int(readiness.get("determinism_probe_repeats", 3)))
    api_preflight.setdefault("cost_ceiling_usd", float(readiness["approved_budget_usd"]))
    api_preflight.setdefault("max_api_requests", int(readiness["max_api_requests"]))
    cloned["api_preflight"] = api_preflight

    api = dict(cloned.get("api", {}))
    api.setdefault("endpoint", "/v1/responses")
    api.setdefault("api_date", "2026-06-03")
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
    pricing.setdefault("basis", "s_FMA_v2.1 API preflight-only ceiling")
    cloned["pricing"] = pricing

    generation = dict(cloned.get("generation", {}))
    generation.setdefault(
        "prompt_file",
        cloned.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        ),
    )
    generation.setdefault("required_tag", "reflection")
    generation.setdefault("trace_field", "observable_trace")
    generation.setdefault("minimum_schema_success_rate", 0.95)
    generation.setdefault("minimum_tag_success_rate", 0.95)
    cloned["generation"] = generation

    api_policy = dict(cloned.get("api_policy", {}))
    logging = dict(api_policy.get("api_logging", {}))
    logging.setdefault(
        "required_fields",
        [
            "api_date",
            "endpoint",
            "model",
            "fallback_model",
            "service_tier",
            "request_parameters",
            "response_id",
            "sdk_or_transport_version",
        ],
    )
    logging.setdefault("disclosure_fields", ["system_fingerprint"])
    api_policy["api_logging"] = logging
    cloned["api_policy"] = api_policy
    return cloned


def build_v2_1_preflight_report(
    attempts: Sequence[Mapping[str, Any]],
    *,
    selected_records: Sequence[Mapping[str, Any]],
    drift_outputs: Sequence[str],
    config: Mapping[str, Any],
    readiness: Mapping[str, Any],
    cost_attempts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize v2.1 preflight attempts without unlocking smoke/replay/scoring."""

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

    failure_codes = list(report.get("failure_codes") or [])
    if incomplete_records:
        failure_codes.append(PREFLIGHT_FAIL_INCOMPLETE_RECORDS)
    if request_over_limit:
        failure_codes.append(PREFLIGHT_FAIL_REQUEST_LIMIT)
    if cost_over_budget:
        failure_codes.append(PREFLIGHT_FAIL_COST)
    if float(report.get("json_parse_success_rate", 0.0)) < 1.0:
        failure_codes.append("PREFLIGHT_FAIL_SCHEMA")
    if float(report.get("schema_success_rate", 0.0)) < 1.0:
        failure_codes.append("PREFLIGHT_FAIL_SCHEMA")
    if float(report.get("tag_extraction_success_rate", 0.0)) < 1.0:
        failure_codes.append("PREFLIGHT_FAIL_TAG")
    if float(report.get("final_answer_parse_success_rate", 0.0)) < 1.0:
        failure_codes.append("PREFLIGHT_FAIL_FINAL_ANSWER")
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
    request_and_budget_ok = (
        not incomplete_records
        and not request_over_limit
        and not cost_over_budget
        and actual_requests <= max_requests
    )
    smoke_request_allowed = (
        request_and_budget_ok
        and not schema_or_tag_or_final_failure
        and report.get("status") == API_PREFLIGHT_READY
    )
    smoke_scope = "not_allowed"
    if smoke_request_allowed:
        smoke_scope = "api_ready_smoke_request_only"

    if cost_over_budget or request_over_limit:
        report["status"] = PREFLIGHT_FAIL_COST
    elif schema_or_tag_or_final_failure:
        report["status"] = PREFLIGHT_FAIL_SCHEMA_OR_TAGS

    report.update(
        {
            "scope": V2_1_API_PREFLIGHT_ONLY,
            "failure_codes": failure_codes,
            "approved_budget_usd": approved_budget,
            "max_api_requests": max_requests,
            "actual_api_requests": actual_requests,
            "records_expected": expected_records,
            "v2_1_smoke_approval_request_allowed": smoke_request_allowed,
            "v2_1_smoke_approval_request_scope": smoke_scope,
            "smoke_execution_allowed": False,
            "no_smoke": True,
            "no_full_generation": True,
            "no_replay": True,
            "no_v2_1_scoring": True,
            "no_prm_claim": True,
            "task_specific_pass_claim_allowed": False,
            "global_pass_claim_allowed": False,
            "deterministic_replay_claim_allowed": False
            if report.get("status") == PREFLIGHT_FAIL_DRIFT
            else report.get("deterministic_replay_claim_allowed", False),
            "claim_upgrade_allowed": False,
            "current_status_remains": "PILOT_BLOCKED",
            "s_fma_v2_1_status": "planned-only-api-preflight-run",
            "next_allowed_step": (
                "REQUEST_V2_1_SMOKE_APPROVAL"
                if smoke_request_allowed
                else "STOP_AND_FIX_PREFLIGHT"
            ),
        }
    )
    return report


def estimate_attempt_cost_usd(
    attempts: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
) -> float | None:
    """Estimate actual observed request cost from attempt usage totals."""

    pricing = config.get("pricing", {}) if isinstance(config, Mapping) else {}
    input_rate = pricing.get("input_per_million_usd")
    output_rate = pricing.get("output_per_million_usd")
    if input_rate is None or output_rate is None:
        return None
    input_tokens = 0
    output_tokens = 0
    for attempt in attempts:
        usage = attempt.get("usage") or {}
        input_tokens += int(usage.get("input_tokens", 0) or 0)
        output_tokens += int(usage.get("output_tokens", 0) or 0)
    return float(
        (input_tokens / 1_000_000) * float(input_rate)
        + (output_tokens / 1_000_000) * float(output_rate)
    )


def _configured_manifest_counts(config: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
    tasks = config.get("fresh_selection_policy", {}).get("tasks", {})
    if not isinstance(tasks, Mapping) or not tasks:
        raise V2_1PreflightError("fresh_selection_policy.tasks must be configured.")
    counts = {
        str(task_type): int(task_config.get("sample_count", 0))
        for task_type, task_config in tasks.items()
    }
    return sum(counts.values()), counts
