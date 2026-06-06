"""Transport/output-extraction canary for the s_FMA_v2.1 fresh holdout."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from .fresh_holdout_v2_1 import V2_1_CONTRACT_CLEAN
from .fresh_preflight import (
    FreshPreflightError,
    select_preflight_records,
    summarize_fresh_preflight,
)
from .fresh_preflight_v2_1 import (
    V2_1_API_PREFLIGHT_ONLY,
    estimate_attempt_cost_usd,
)
from .parsing import extract_final_answer, parse_json_object
from .preflight import evaluate_preflight
from .schema import validate_trace_record


TRANSPORT_CANARY_ONLY = "TRANSPORT_CANARY_ONLY"
TRANSPORT_CANARY_PASS = "TRANSPORT_CANARY_PASS"
TRANSPORT_CANARY_FAIL_EMPTY_OUTPUT = "TRANSPORT_CANARY_FAIL_EMPTY_OUTPUT"
TRANSPORT_CANARY_FAIL_MISSING_DIAGNOSTICS = "TRANSPORT_CANARY_FAIL_MISSING_DIAGNOSTICS"
TRANSPORT_CANARY_FAIL_NO_JSON_PARSE = "TRANSPORT_CANARY_FAIL_NO_JSON_PARSE"
TRANSPORT_CANARY_FAIL_BUDGET = "TRANSPORT_CANARY_FAIL_BUDGET"
TRANSPORT_CANARY_FAIL_REQUEST_LIMIT = "TRANSPORT_CANARY_FAIL_REQUEST_LIMIT"
TRANSPORT_CANARY_FAIL_INCOMPLETE_ATTEMPTS = "TRANSPORT_CANARY_FAIL_INCOMPLETE_ATTEMPTS"


class TransportCanaryError(FreshPreflightError):
    """Raised when a hard transport-canary boundary is violated."""


def transport_canary_paths(output_root: Path) -> dict[str, Path]:
    """Return canary output paths independent of API preflight artifacts."""

    return {
        "report": output_root / "transport_canary_report.json",
        "attempts": output_root / "transport_canary_attempts.jsonl",
        "traces": output_root / "transport_canary_traces.jsonl",
        "cost": output_root / "logs" / "transport_canary_cost_report.json",
    }


def validate_transport_canary_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    empty_output_failure_audit: Mapping[str, Any],
    current_readiness: Mapping[str, Any],
    allow_transport_canary_only: bool,
    approved_budget_usd: float,
    current_prompt_version: str | None = None,
) -> dict[str, Any]:
    """Validate every pre-run gate before a tiny transport canary API call."""

    if not allow_transport_canary_only:
        raise TransportCanaryError(
            "s_FMA_v2.1 transport canary requires explicit --allow-transport-canary-only."
        )
    if float(approved_budget_usd) != 0.5:
        raise TransportCanaryError("transport canary approved budget must be exactly 0.5 USD.")
    if current_readiness.get("status") != "PILOT_BLOCKED":
        raise TransportCanaryError("current readiness status must remain PILOT_BLOCKED.")
    if current_readiness.get("pilot_pass") is True:
        raise TransportCanaryError("current readiness must not report pilot_pass=true.")

    _validate_empty_output_failure_audit(empty_output_failure_audit)
    _validate_manifest_and_overlap(config=config, manifest=manifest, overlap_audit=overlap_audit)
    _validate_contract_and_approval(
        contract_audit=contract_audit,
        approval_request=approval_request,
    )
    if current_prompt_version:
        _validate_prompt_lock(
            manifest=manifest,
            contract_audit=contract_audit,
            approval_request=approval_request,
            current_prompt_version=current_prompt_version,
        )

    selected = select_preflight_records(
        manifest,
        samples_per_task=1,
        task_order=["gsm8k", "hotpotqa"],
    )
    selected_counts = Counter(str(row.get("task_type") or "") for row in selected)
    return {
        "scope": TRANSPORT_CANARY_ONLY,
        "api_call_allowed": True,
        "approved_budget_usd": 0.5,
        "max_api_requests": 3,
        "planned_api_requests": len(selected),
        "selected_records": len(selected),
        "selected_counts_by_task": dict(selected_counts),
        "manifest_rows": len(manifest),
        "current_status_remains": "PILOT_BLOCKED",
        "historical_preflight_report_used_as_ready_evidence": False,
        "no_v2_1_evidence_claim": True,
        "claim_upgrade_allowed": False,
    }


def build_transport_canary_generation_config(
    config: Mapping[str, Any],
    *,
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Return live canary config without mutating the planned-only YAML."""

    cloned = deepcopy(dict(config))
    experiment = dict(cloned.get("experiment", {}))
    experiment["user_approved_budget_usd"] = float(readiness["approved_budget_usd"])
    experiment["max_api_requests_pilot"] = int(readiness["max_api_requests"])
    experiment["pilot_generation_requests"] = int(readiness.get("planned_api_requests") or 2)
    cloned["experiment"] = experiment

    canary = dict(cloned.get("transport_canary", {}))
    canary["mode"] = TRANSPORT_CANARY_ONLY
    canary["samples_per_task"] = 1
    canary["total_records"] = 2
    canary["cost_ceiling_usd"] = float(readiness["approved_budget_usd"])
    canary["max_api_requests"] = int(readiness["max_api_requests"])
    cloned["transport_canary"] = canary

    api = dict(cloned.get("api", {}))
    api.setdefault("endpoint", "/v1/responses")
    api.setdefault("api_date", "2026-06-04")
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
    pricing.setdefault("basis", "s_FMA_v2.1 transport canary ceiling")
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


def build_transport_canary_report(
    attempts: Sequence[Mapping[str, Any]],
    *,
    selected_records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize canary attempts without unlocking validation or claim language."""

    base_report = summarize_fresh_preflight(
        attempts,
        selected_records=selected_records,
        drift_outputs=(),
        config=config,
        cost_attempts=attempts,
    )
    extraction = _output_extraction_summary(attempts)
    parse_counts = _parse_success_counts(attempts)
    actual_requests = len(attempts)
    approved_budget = float(readiness.get("approved_budget_usd") or 0.5)
    max_requests = int(readiness.get("max_api_requests") or 3)
    cost_used = estimate_attempt_cost_usd(attempts, config=config)
    if cost_used is None:
        cost_used = base_report.get("cost_used_usd")
    cost_within_cap = cost_used is None or float(cost_used) <= approved_budget
    request_within_cap = actual_requests <= max_requests
    complete_attempt_count = actual_requests >= int(readiness.get("selected_records") or 2)

    status = TRANSPORT_CANARY_PASS
    failure_codes: list[str] = []
    if not request_within_cap:
        status = TRANSPORT_CANARY_FAIL_REQUEST_LIMIT
        failure_codes.append(TRANSPORT_CANARY_FAIL_REQUEST_LIMIT)
    elif not cost_within_cap:
        status = TRANSPORT_CANARY_FAIL_BUDGET
        failure_codes.append(TRANSPORT_CANARY_FAIL_BUDGET)
    elif not extraction["output_extraction_diagnostics_complete"]:
        status = TRANSPORT_CANARY_FAIL_MISSING_DIAGNOSTICS
        failure_codes.append(TRANSPORT_CANARY_FAIL_MISSING_DIAGNOSTICS)
    elif extraction["raw_output_nonempty_count"] == 0:
        status = TRANSPORT_CANARY_FAIL_EMPTY_OUTPUT
        failure_codes.append(TRANSPORT_CANARY_FAIL_EMPTY_OUTPUT)
    elif parse_counts["json_parse_success_count"] < 1:
        status = TRANSPORT_CANARY_FAIL_NO_JSON_PARSE
        failure_codes.append(TRANSPORT_CANARY_FAIL_NO_JSON_PARSE)
    elif not complete_attempt_count:
        status = TRANSPORT_CANARY_FAIL_INCOMPLETE_ATTEMPTS
        failure_codes.append(TRANSPORT_CANARY_FAIL_INCOMPLETE_ATTEMPTS)

    api_preflight_rerun_request_allowed = status == TRANSPORT_CANARY_PASS
    report = dict(base_report)
    cost_report = dict(report.get("cost_report", {}))
    cost_report["preflight_only"] = False
    cost_report["transport_canary_only"] = True
    report.update(
        {
            "status": status,
            "scope": TRANSPORT_CANARY_ONLY,
            "failure_codes": sorted(set(failure_codes)),
            "api_attempts": actual_requests,
            "actual_api_requests": actual_requests,
            "records_expected": int(readiness.get("selected_records") or len(selected_records)),
            "approved_budget_usd": approved_budget,
            "max_api_requests": max_requests,
            "cost_used_usd": cost_used,
            "budget_within_cap": cost_within_cap,
            "request_within_cap": request_within_cap,
            **extraction,
            **parse_counts,
            "canary_pass_conditions": {
                "attempt_count_2_or_3": 2 <= actual_requests <= max_requests,
                "raw_output_nonempty_rate_gt_0": extraction["raw_output_nonempty_rate"] > 0.0,
                "output_extraction_diagnostics_every_attempt": extraction[
                    "output_extraction_diagnostics_complete"
                ],
                "at_least_1_json_parse_success": parse_counts["json_parse_success_count"] >= 1,
                "budget_lte_approved_usd": cost_within_cap,
                "no_claim_upgrade": True,
            },
            "api_preflight_rerun_approval_request_allowed": api_preflight_rerun_request_allowed,
            "api_preflight_rerun_allowed_without_approval": False,
            "api_preflight_rerun_scope_if_requested": (
                "20-row API_PREFLIGHT_ONLY rerun approval request only"
                if api_preflight_rerun_request_allowed
                else "not_allowed"
            ),
            "historical_preflight_report_used_as_ready_evidence": False,
            "claim_upgrade_allowed": False,
            "current_status_remains": "PILOT_BLOCKED",
            "no_v2_1_evidence_claim": True,
            "no_smoke": True,
            "no_replay": True,
            "no_scoring": True,
            "no_full_generation": True,
            "no_prm_claim": True,
            "task_specific_pass_claim_allowed": False,
            "global_pass_claim_allowed": False,
            "deterministic_replay_claim_allowed": False,
            "transport_canary_only": True,
            "s_fma_v2_status": "not_applicable_to_v2_1_transport_canary",
            "s_fma_v2_1_status": "planned-only-transport-canary",
            "cost_report": cost_report,
            "next_allowed_step": (
                "REQUEST_20_ROW_API_PREFLIGHT_ONLY_RERUN_APPROVAL"
                if api_preflight_rerun_request_allowed
                else "STOP_AND_FIX_TRANSPORT_CANARY"
            ),
        }
    )
    return report


def _validate_empty_output_failure_audit(audit: Mapping[str, Any]) -> None:
    if not audit:
        raise TransportCanaryError("api_preflight_empty_output_failure_audit.json is required.")
    if "EMPTY_OUTPUT" not in str(audit.get("audit_name") or ""):
        raise TransportCanaryError("empty-output failure audit name must identify EMPTY_OUTPUT.")
    raw_audit = audit.get("raw_output_audit", {})
    if raw_audit.get("any_nonempty_raw_output") is not False:
        raise TransportCanaryError("empty-output audit must preserve all-empty raw_output finding.")
    claim_boundary = audit.get("claim_boundary", {})
    if claim_boundary.get("current_status_remains") != "PILOT_BLOCKED":
        raise TransportCanaryError("empty-output audit must keep current status PILOT_BLOCKED.")
    if claim_boundary.get("v2_1_evidence_signal_available") is not False:
        raise TransportCanaryError("empty-output audit must not expose v2.1 evidence signal.")


def _validate_manifest_and_overlap(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
) -> None:
    expected_total, expected_by_task = _configured_manifest_counts(config)
    if len(manifest) != expected_total:
        raise TransportCanaryError(
            f"v2.1 fresh manifest row count is {len(manifest)}, expected {expected_total}."
        )
    observed_by_task = Counter(str(row.get("task_type") or "") for row in manifest)
    for task_type, expected_count in expected_by_task.items():
        observed_count = observed_by_task.get(task_type, 0)
        if observed_count != expected_count:
            raise TransportCanaryError(
                f"v2.1 manifest has {observed_count} {task_type} rows, expected {expected_count}."
            )
    if overlap_audit.get("status") != "MANIFEST_OVERLAP_CLEAN":
        raise TransportCanaryError("manifest_overlap_audit.json must be MANIFEST_OVERLAP_CLEAN.")
    if overlap_audit.get("claim_upgrade_allowed") is not False:
        raise TransportCanaryError("manifest overlap audit must not allow claim upgrade.")
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
    missing = [key for key in required_overlap_keys if key not in selected_overlaps]
    nonzero = [
        key
        for key in required_overlap_keys
        if int(selected_overlaps.get(key) or 0) != 0
    ]
    if missing or nonzero:
        raise TransportCanaryError(
            "all six selected overlap keys must be present and zero before transport canary."
        )


def _validate_contract_and_approval(
    *,
    contract_audit: Mapping[str, Any],
    approval_request: Mapping[str, Any],
) -> None:
    if contract_audit.get("status") != V2_1_CONTRACT_CLEAN:
        raise TransportCanaryError("v2_1_contract_audit.json must be V2_1_CONTRACT_CLEAN.")
    if contract_audit.get("claim_upgrade_allowed") is not False:
        raise TransportCanaryError("v2.1 contract audit must not allow claim upgrade.")
    if contract_audit.get("current_status_remains") != "PILOT_BLOCKED":
        raise TransportCanaryError("v2.1 contract audit must keep PILOT_BLOCKED.")
    if approval_request.get("requested_scope") != V2_1_API_PREFLIGHT_ONLY:
        raise TransportCanaryError(
            f"api_preflight_approval_request.json must request {V2_1_API_PREFLIGHT_ONLY}."
        )
    if approval_request.get("request_valid_for_review") is not True:
        raise TransportCanaryError("api preflight approval package must be valid for review.")
    if approval_request.get("api_execution_authorized_by_this_request") is not False:
        raise TransportCanaryError("approval package must not authorize API execution by itself.")
    if approval_request.get("current_status_remains") != "PILOT_BLOCKED":
        raise TransportCanaryError("approval package must keep PILOT_BLOCKED.")


def _validate_prompt_lock(
    *,
    manifest: Sequence[Mapping[str, Any]],
    contract_audit: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    current_prompt_version: str,
) -> None:
    manifest_versions = {str(row.get("prompt_version") or "") for row in manifest}
    manifest_versions.discard("")
    contract_version = str(
        contract_audit.get("prompt_version")
        or contract_audit.get("checks", {})
        .get("prompt_policy", {})
        .get("details", {})
        .get("prompt_version")
        or ""
    )
    approval_version = str(approval_request.get("prompt_version") or "")
    if (
        manifest_versions != {current_prompt_version}
        or contract_version != current_prompt_version
        or approval_version not in {"", current_prompt_version}
    ):
        raise TransportCanaryError(
            "v2.1 prompt version lock mismatch; regenerate package artifacts before canary."
        )


def _output_extraction_summary(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attempt_count = len(attempts)
    raw_nonempty = sum(1 for attempt in attempts if _has_nonempty_raw_output(attempt.get("raw_output")))
    diagnostics_present = sum(
        1
        for attempt in attempts
        if isinstance(attempt.get("output_extraction_diagnostics"), Mapping)
        and bool(attempt.get("output_extraction_diagnostics"))
    )
    return {
        "raw_output_nonempty_count": raw_nonempty,
        "raw_output_empty_count": attempt_count - raw_nonempty,
        "raw_output_nonempty_rate": raw_nonempty / attempt_count if attempt_count else 0.0,
        "output_extraction_diagnostics_present_count": diagnostics_present,
        "output_extraction_diagnostics_complete": diagnostics_present == attempt_count
        and attempt_count > 0,
    }


def _parse_success_counts(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    parsed_records = [_parsed_attempt(attempt) for attempt in attempts]
    json_count = sum(1 for record in parsed_records if record is not None)
    schema_count = sum(1 for record in parsed_records if record is not None and not validate_trace_record(record))
    tag_count = sum(
        1
        for record in parsed_records
        if record is not None
        and bool(
            evaluate_preflight([record], drift_outputs=(), config={})["api_preflight_report"][
                "tag_extraction_success_rate"
            ]
        )
    )
    final_answer_count = sum(1 for record in parsed_records if _has_final_answer(record))
    attempt_count = len(attempts)
    return {
        "json_parse_success_count": json_count,
        "schema_success_count": schema_count,
        "tag_extraction_success_count": tag_count,
        "final_answer_parse_success_count": final_answer_count,
        "json_parse_success_rate": json_count / attempt_count if attempt_count else 0.0,
        "schema_success_rate": schema_count / attempt_count if attempt_count else 0.0,
        "tag_extraction_success_rate": tag_count / attempt_count if attempt_count else 0.0,
        "final_answer_parse_success_rate": final_answer_count / attempt_count
        if attempt_count
        else 0.0,
    }


def _parsed_attempt(attempt: Mapping[str, Any]) -> dict[str, Any] | None:
    record = attempt.get("record") if attempt.get("preflight_attempt") is True else attempt
    raw_output = record if record is not None else attempt.get("raw_output")
    return parse_json_object(raw_output)


def _has_final_answer(record: Mapping[str, Any] | None) -> bool:
    if not record:
        return False
    if str(record.get("final_answer") or "").strip():
        return True
    return bool(extract_final_answer(str(record.get("observable_trace") or "")))


def _has_nonempty_raw_output(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    return True


def _configured_manifest_counts(config: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
    tasks = config.get("fresh_selection_policy", {}).get("tasks", {})
    if not isinstance(tasks, Mapping) or not tasks:
        raise TransportCanaryError("fresh_selection_policy.tasks must be configured.")
    counts = {
        str(task_type): int(task_config.get("sample_count", 0))
        for task_type, task_config in tasks.items()
    }
    return sum(counts.values()), counts
