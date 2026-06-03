"""API preflight-only gates for the s_FMA_v2 fresh holdout."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from typing import Any, Mapping, Sequence

from .generation import GeneratedTraceResult
from .parsing import extract_final_answer, parse_json_object
from .preflight import evaluate_preflight


API_PREFLIGHT_READY = "API_PREFLIGHT_READY"
PREFLIGHT_FAIL_COST = "PREFLIGHT_FAIL_COST"
PREFLIGHT_FAIL_DRIFT = "PREFLIGHT_FAIL_DRIFT"
PREFLIGHT_FAIL_METADATA = "PREFLIGHT_FAIL_METADATA"
PREFLIGHT_METADATA_MISSING = "PREFLIGHT_METADATA_MISSING"
PREFLIGHT_FAIL_SCHEMA_OR_TAGS = "PREFLIGHT_FAIL_SCHEMA_OR_TAGS"
DETERMINISTIC_REPLAY_FEASIBLE = "DETERMINISTIC_REPLAY_FEASIBLE"
DETERMINISTIC_REPLAY_ROUTE = "DETERMINISTIC_REPLAY_ROUTE"
STOCHASTIC_REPEATED_REPLAY_ROUTE = "STOCHASTIC_REPEATED_REPLAY_ROUTE"
PREREGISTER_STOCHASTIC_ROUTE = "PREREGISTER_STOCHASTIC_ROUTE"
RERUN_PREFLIGHT_WITH_STRONGER_DETERMINISM_SETTINGS = (
    "RERUN_PREFLIGHT_WITH_STRONGER_DETERMINISM_SETTINGS"
)


class FreshPreflightError(RuntimeError):
    """Raised when a hard fresh-holdout preflight boundary is violated."""


def select_preflight_records(
    manifest: Sequence[Mapping[str, Any]],
    *,
    samples_per_task: int = 10,
    task_order: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Select a fixed small per-task API preflight sample from a locked manifest."""

    if samples_per_task <= 0:
        raise FreshPreflightError("samples_per_task must be positive.")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest:
        grouped[str(row.get("task_type") or "")].append(dict(row))
    ordered_tasks = list(task_order or [])
    ordered_tasks.extend(task for task in sorted(grouped) if task not in ordered_tasks)
    selected: list[dict[str, Any]] = []
    for task_type in ordered_tasks:
        if not task_type:
            continue
        rows = grouped.get(task_type, [])
        if len(rows) < samples_per_task:
            raise FreshPreflightError(
                f"manifest has only {len(rows)} rows for {task_type}, "
                f"but API preflight requires {samples_per_task}."
            )
        selected.extend(rows[:samples_per_task])
    return selected


def validate_preflight_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
    plan_text: str,
    allow_api_preflight_only: bool,
) -> dict[str, Any]:
    """Validate the hard gates that must pass before any preflight API call."""

    if not allow_api_preflight_only:
        raise FreshPreflightError(
            "fresh-holdout API preflight requires explicit --allow-api-preflight-only."
        )
    if "preflight" not in plan_text.lower():
        raise FreshPreflightError("paper/s_fma_v2_fresh_holdout_plan.md must describe API preflight.")
    if config.get("claim_policy", {}).get("C_S_FMA_V2_FRESH_HOLDOUT") != "planned":
        raise FreshPreflightError("C_S_FMA_V2_FRESH_HOLDOUT must remain planned before preflight.")

    expected_total, expected_by_task = _configured_manifest_counts(config)
    if len(manifest) != expected_total:
        raise FreshPreflightError(
            f"fresh manifest row count is {len(manifest)}, expected configured count {expected_total}."
        )
    observed_by_task = Counter(str(row.get("task_type") or "") for row in manifest)
    for task_type, expected_count in expected_by_task.items():
        observed_count = observed_by_task.get(task_type, 0)
        if observed_count != expected_count:
            raise FreshPreflightError(
                f"fresh manifest has {observed_count} {task_type} rows, expected {expected_count}."
            )

    if overlap_audit.get("status") != "MANIFEST_OVERLAP_CLEAN":
        raise FreshPreflightError("manifest overlap audit status must be MANIFEST_OVERLAP_CLEAN.")
    if not overlap_audit.get("api_preflight_only", False):
        raise FreshPreflightError("manifest overlap audit must allow API_PREFLIGHT_ONLY as the next step.")
    selected_overlaps = (
        overlap_audit.get("overlap_summary", {}).get("selected_overlaps_by_key", {})
    )
    nonzero_selected_overlaps = {
        key: value for key, value in selected_overlaps.items() if int(value or 0) != 0
    }
    if nonzero_selected_overlaps:
        raise FreshPreflightError(
            "selected manifest overlaps must all be zero before API preflight-only."
        )

    budget_report = _preflight_budget_report(config)
    return {
        "gate": "API_PREFLIGHT_ONLY",
        "manifest_rows": len(manifest),
        "configured_manifest_rows": expected_total,
        "manifest_counts_by_task": dict(observed_by_task),
        "overlap_audit_status": overlap_audit.get("status"),
        "selected_overlaps_by_key": dict(selected_overlaps),
        "current_status_remains": "PILOT_BLOCKED",
        "budget": budget_report,
        "api_call_allowed": budget_report["budget_gate_pass"],
    }


def build_budget_blocked_report(
    *,
    config: Mapping[str, Any],
    selected_records: Sequence[Mapping[str, Any]],
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a preflight report when the budget gate blocks before API calls."""

    cost_report = dict(readiness.get("budget") or _preflight_budget_report(config))
    return _base_report(
        status=PREFLIGHT_FAIL_COST,
        failure_codes=[PREFLIGHT_FAIL_COST],
        selected_records=selected_records,
        records_evaluated=0,
        json_rate=0.0,
        schema_rate=0.0,
        tag_rate=0.0,
        final_answer_rate=0.0,
        metadata_rate=0.0,
        drift_status="PREFLIGHT_DRIFT_NOT_MEASURED",
        deterministic_claim_allowed=False,
        stochastic_candidate=False,
        cost_report=cost_report,
        api_metadata=_configured_api_metadata(config),
        metadata_disclosure_status="PREFLIGHT_METADATA_NOT_MEASURED",
    )


def summarize_fresh_preflight(
    attempts: Sequence[Mapping[str, Any]],
    *,
    selected_records: Sequence[Mapping[str, Any]],
    drift_outputs: Sequence[str],
    config: Mapping[str, Any],
    cost_attempts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize fresh-holdout API preflight attempts into claim-safe status codes."""

    cost_inputs = list(cost_attempts or attempts)
    eval_config = _preflight_only_cost_config(config, request_count=len(cost_inputs))
    base = evaluate_preflight(attempts, drift_outputs=drift_outputs, config=eval_config)
    api_report = base["api_preflight_report"]
    schema_report = base["schema_compliance_report"]
    drift_report = base["determinism_drift_report"]
    cost_report = dict(
        evaluate_preflight(cost_inputs, drift_outputs=(), config=eval_config)[
            "cost_and_rate_limit_report"
        ]
    )
    cost_report["preflight_only"] = True

    parsed_records = [_parsed_attempt(attempt) for attempt in attempts]
    final_answer_success = [_has_final_answer(record) for record in parsed_records]
    metadata_payloads = [_attempt_metadata(attempt) for attempt in attempts]
    required_metadata = _required_metadata_fields(config)
    disclosure_metadata = _metadata_disclosure_fields(config)
    metadata_success = [
        _metadata_has_required_fields(metadata, required_metadata)
        for metadata in metadata_payloads
    ]
    metadata_missing_counts = _metadata_missing_counts(metadata_payloads, required_metadata)
    metadata_disclosure_missing_counts = _metadata_missing_counts(
        metadata_payloads,
        disclosure_metadata,
    )
    metadata_disclosure_status = (
        PREFLIGHT_METADATA_MISSING
        if any(count > 0 for count in metadata_disclosure_missing_counts.values())
        else "PREFLIGHT_METADATA_COMPLETE"
    )

    final_answer_rate = _mean_bool(final_answer_success)
    metadata_rate = _mean_bool(metadata_success)
    final_answer_gate = final_answer_rate >= 1.0
    metadata_gate = metadata_rate >= 1.0
    schema_or_tag_failure = (
        "PREFLIGHT_FAIL_SCHEMA" in api_report.get("failure_codes", [])
        or "PREFLIGHT_FAIL_TAG" in api_report.get("failure_codes", [])
        or not final_answer_gate
    )
    drift_failure = "PREFLIGHT_FAIL_DRIFT" in api_report.get("failure_codes", [])
    cost_failure = not cost_report.get("budget_gate_pass", False)
    metadata_failure = not metadata_gate

    failure_codes = list(api_report.get("failure_codes", []))
    if not final_answer_gate:
        failure_codes.append("PREFLIGHT_FAIL_FINAL_ANSWER")
    if not metadata_gate:
        failure_codes.append(PREFLIGHT_FAIL_METADATA)
    failure_codes = _unique_sorted(failure_codes)

    drift_status = (
        PREFLIGHT_FAIL_DRIFT
        if drift_failure
        else DETERMINISTIC_REPLAY_FEASIBLE
        if len(drift_outputs) >= 2
        else "PREFLIGHT_DRIFT_NOT_MEASURED"
    )
    if cost_failure:
        status = PREFLIGHT_FAIL_COST
    elif schema_or_tag_failure:
        status = PREFLIGHT_FAIL_SCHEMA_OR_TAGS
    elif drift_failure:
        status = PREFLIGHT_FAIL_DRIFT
    elif metadata_failure:
        status = PREFLIGHT_FAIL_METADATA
    else:
        status = API_PREFLIGHT_READY

    return _base_report(
        status=status,
        failure_codes=failure_codes,
        selected_records=selected_records,
        records_evaluated=len(attempts),
        json_rate=float(api_report.get("json_parse_success_rate", 0.0)),
        schema_rate=float(api_report.get("schema_success_rate", 0.0)),
        tag_rate=float(api_report.get("tag_extraction_success_rate", 0.0)),
        final_answer_rate=final_answer_rate,
        metadata_rate=metadata_rate,
        drift_status=drift_status,
        deterministic_claim_allowed=status == API_PREFLIGHT_READY
        and drift_status == DETERMINISTIC_REPLAY_FEASIBLE,
        stochastic_candidate=drift_status == PREFLIGHT_FAIL_DRIFT,
        cost_report=cost_report,
        api_metadata=_observed_api_metadata(config, metadata_payloads),
        determinism_drift_max=drift_report.get("max_token_diff_ratio"),
        schema_report=schema_report,
        metadata_missing_counts=metadata_missing_counts,
        metadata_disclosure_missing_counts=metadata_disclosure_missing_counts,
        metadata_disclosure_status=metadata_disclosure_status,
        metadata_disclosure_explanation=_metadata_disclosure_explanation(
            metadata_disclosure_missing_counts,
            records_evaluated=len(attempts),
        ),
        metadata_policy={
            "required_fields": required_metadata,
            "disclosure_fields": disclosure_metadata,
        },
        api_attempts=len(cost_inputs),
    )


def attempt_payloads_from_results(
    results: Sequence[GeneratedTraceResult],
    *,
    role: str,
    samples: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Convert generation results to the JSONL attempt contract."""

    attempts = []
    for index, result in enumerate(results):
        sample = samples[index] if samples is not None and index < len(samples) else {}
        generation_config = (
            result.record.get("generation_config", {})
            if result.record is not None
            else {}
        )
        sample_context = _attempt_sample_context(sample=sample, record=result.record)
        attempts.append(
            {
                "preflight_attempt": True,
                "attempt_role": role,
                **sample_context,
                "record": result.record,
                "raw_output": result.raw_output,
                "usage": result.usage,
                "model_name": result.model_name,
                "structured_output_mode": result.structured_output_mode
                or generation_config.get("structured_output_mode"),
                "system_fingerprint": result.system_fingerprint,
                "response_id": getattr(result, "response_id", None)
                or generation_config.get("response_id"),
                "validation_errors": list(result.validation_errors),
                "fallback_events": list(result.fallback_events),
            }
        )
    return attempts


def _attempt_sample_context(
    *,
    sample: Mapping[str, Any],
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = record if record is not None else sample
    question = str(source.get("question") or sample.get("question") or "")
    return {
        "sample_id": _string_or_none(source.get("sample_id") or sample.get("sample_id")),
        "task_id": _string_or_none(source.get("task_id") or sample.get("task_id")),
        "task_type": _string_or_none(source.get("task_type") or sample.get("task_type")),
        "question_hash": hashlib.sha256(question.encode("utf-8")).hexdigest()
        if question
        else None,
        "question_preview": question[:160] if question else None,
    }


def _base_report(
    *,
    status: str,
    failure_codes: Sequence[str],
    selected_records: Sequence[Mapping[str, Any]],
    records_evaluated: int,
    json_rate: float,
    schema_rate: float,
    tag_rate: float,
    final_answer_rate: float,
    metadata_rate: float,
    drift_status: str,
    deterministic_claim_allowed: bool,
    stochastic_candidate: bool,
    cost_report: Mapping[str, Any],
    api_metadata: Mapping[str, Any],
    determinism_drift_max: float | None = None,
    schema_report: Mapping[str, Any] | None = None,
    metadata_missing_counts: Mapping[str, int] | None = None,
    metadata_disclosure_missing_counts: Mapping[str, int] | None = None,
    metadata_disclosure_status: str = "PREFLIGHT_METADATA_COMPLETE",
    metadata_disclosure_explanation: str | None = None,
    metadata_policy: Mapping[str, Any] | None = None,
    api_attempts: int | None = None,
) -> dict[str, Any]:
    generation_approval_allowed = status == API_PREFLIGHT_READY
    drift_failed = status == PREFLIGHT_FAIL_DRIFT or drift_status == PREFLIGHT_FAIL_DRIFT
    allowed_remediation_steps = (
        [PREREGISTER_STOCHASTIC_ROUTE, RERUN_PREFLIGHT_WITH_STRONGER_DETERMINISM_SETTINGS]
        if drift_failed
        else []
    )
    allowed_claim_wording, forbidden_claim_wording = _route_claim_wording(
        drift_failed=drift_failed,
        deterministic_claim_allowed=deterministic_claim_allowed,
        stochastic_candidate=stochastic_candidate,
    )
    return {
        "status": status,
        "failure_codes": _unique_sorted(failure_codes),
        "records_evaluated": records_evaluated,
        "api_attempts": records_evaluated if api_attempts is None else api_attempts,
        "selected_records": len(selected_records),
        "selected_counts_by_task": dict(Counter(str(row.get("task_type") or "") for row in selected_records)),
        "json_parse_success_rate": json_rate,
        "schema_success_rate": schema_rate,
        "tag_extraction_success_rate": tag_rate,
        "final_answer_parse_success_rate": final_answer_rate,
        "required_metadata_success_rate": metadata_rate,
        "schema_report": dict(schema_report or {}),
        "metadata_missing_counts": dict(metadata_missing_counts or {}),
        "metadata_disclosure_missing_counts": dict(metadata_disclosure_missing_counts or {}),
        "metadata_disclosure_status": metadata_disclosure_status,
        "metadata_disclosure_explanation": metadata_disclosure_explanation
        or "Disclosure-only metadata fields were not missing.",
        "metadata_policy": dict(metadata_policy or {}),
        "drift_status": drift_status,
        "determinism_drift_max": determinism_drift_max,
        "deterministic_replay_claim_allowed": deterministic_claim_allowed,
        "stochastic_repeated_replay_estimand_candidate": stochastic_candidate,
        "allowed_remediation_steps": allowed_remediation_steps,
        "route_policy": _route_policy(
            status=status,
            drift_status=drift_status,
            deterministic_claim_allowed=deterministic_claim_allowed,
            stochastic_candidate=stochastic_candidate,
            cost_report=cost_report,
        ),
        "allowed_claim_wording": allowed_claim_wording,
        "forbidden_claim_wording": forbidden_claim_wording,
        "fresh_generation_approval_request_allowed": generation_approval_allowed,
        "next_allowed_step": (
            "REQUEST_FRESH_GENERATION_APPROVAL"
            if generation_approval_allowed
            else "STOP_AND_FIX_PREFLIGHT"
        ),
        "cost_report": dict(cost_report),
        "cost_used_usd": cost_report.get("projected_cost_usd"),
        "api_metadata": dict(api_metadata),
        "current_status_remains": "PILOT_BLOCKED",
        "s_fma_v2_status": "planned-only",
        "no_full_generation": True,
        "no_v2_scoring": True,
        "no_replay": True,
        "no_prm_claim": True,
        "claim_upgrade_allowed": False,
    }


def _route_policy(
    *,
    status: str,
    drift_status: str,
    deterministic_claim_allowed: bool,
    stochastic_candidate: bool,
    cost_report: Mapping[str, Any],
) -> dict[str, Any]:
    drift_failed = status == PREFLIGHT_FAIL_DRIFT or drift_status == PREFLIGHT_FAIL_DRIFT
    deterministic_passed = (
        status == API_PREFLIGHT_READY
        and drift_status == DETERMINISTIC_REPLAY_FEASIBLE
        and deterministic_claim_allowed
    )
    return {
        "allowed_routes_after_drift": (
            [STOCHASTIC_REPEATED_REPLAY_ROUTE] if drift_failed else []
        ),
        DETERMINISTIC_REPLAY_ROUTE: {
            "requires_preflight_drift_pass": True,
            "preflight_drift_passed": deterministic_passed,
            "route_status": (
                "available_after_preflight_drift_pass"
                if deterministic_passed
                else "blocked_preflight_drift"
                if drift_failed
                else "blocked_preflight_not_ready"
            ),
            "full_generation_allowed": deterministic_passed,
            "deterministic_replay_language_allowed": deterministic_passed,
        },
        STOCHASTIC_REPEATED_REPLAY_ROUTE: {
            "requires_drift_disclosure": True,
            "drift_disclosed": drift_failed,
            "planning_allowed": bool(stochastic_candidate and drift_failed),
            "api_execution_allowed": False,
            "requires_explicit_budget_approval": True,
            "cost_ceiling_required": True,
            "preflight_budget_gate_passed": bool(cost_report.get("budget_gate_pass", False)),
            "claim_scope": "stochastic_repeated_replay_evidence_only",
            "deterministic_replay_language_allowed": False,
        },
    }


def _route_claim_wording(
    *,
    drift_failed: bool,
    deterministic_claim_allowed: bool,
    stochastic_candidate: bool,
) -> tuple[list[str], list[str]]:
    allowed = [
        "fresh-holdout status remains planned-only",
        "current status remains PILOT_BLOCKED",
    ]
    forbidden = [
        "deterministic causal",
        "true causal effect",
        "full generation ready",
        "task/global v2 pass",
        "PRM/filtering claim",
    ]
    if deterministic_claim_allowed:
        allowed.append("deterministic replay evidence after drift gate pass")
    else:
        forbidden.append("deterministic replay")
    if drift_failed and stochastic_candidate:
        allowed.append(
            "stochastic repeated-replay evidence only after explicit budget approval"
        )
    return allowed, forbidden


def _configured_manifest_counts(config: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
    tasks = config.get("fresh_holdout", {}).get("tasks", {})
    if not isinstance(tasks, Mapping) or not tasks:
        raise FreshPreflightError("fresh_holdout.tasks must be configured.")
    counts = {
        str(task_type): int(task_config.get("sample_count", 0))
        for task_type, task_config in tasks.items()
    }
    return sum(counts.values()), counts


def _preflight_budget_report(config: Mapping[str, Any]) -> dict[str, Any]:
    experiment = config.get("experiment", {}) if isinstance(config, Mapping) else {}
    api_preflight = config.get("api_preflight", {}) if isinstance(config, Mapping) else {}
    budget = experiment.get("user_approved_budget_usd")
    ceiling = api_preflight.get("cost_ceiling_usd")
    ceiling_value = float(ceiling) if ceiling is not None else None
    budget_gate = budget is not None and (
        ceiling_value is None or float(budget) >= ceiling_value
    )
    return {
        "preflight_only": True,
        "user_approved_budget_usd": budget,
        "preflight_cost_ceiling_usd": ceiling_value,
        "budget_gate_pass": budget_gate,
        "failure_reasons": [] if budget_gate else ["user_approved_budget_usd_not_set_or_below_preflight_ceiling"],
    }


def _preflight_only_cost_config(config: Mapping[str, Any], *, request_count: int) -> dict[str, Any]:
    cloned = dict(config)
    experiment = dict(cloned.get("experiment", {}))
    experiment["max_api_requests_pilot"] = max(1, request_count)
    experiment["pilot_generation_requests"] = max(1, request_count)
    cloned["experiment"] = experiment
    cloned.pop("data", None)
    return cloned


def _parsed_attempt(attempt: Mapping[str, Any]) -> dict[str, Any] | None:
    if attempt.get("preflight_attempt") is True:
        record = attempt.get("record")
        raw_output = record if record is not None else attempt.get("raw_output")
        return parse_json_object(raw_output)
    return parse_json_object(attempt)


def _has_final_answer(record: Mapping[str, Any] | None) -> bool:
    if not record:
        return False
    if str(record.get("final_answer") or "").strip():
        return True
    return bool(extract_final_answer(str(record.get("observable_trace") or "")))


def _attempt_metadata(attempt: Mapping[str, Any]) -> dict[str, Any]:
    record = attempt.get("record")
    if not isinstance(record, Mapping):
        record = {}
    generation_config = record.get("generation_config", {})
    if not isinstance(generation_config, Mapping):
        generation_config = {}
    fallback_order = list(generation_config.get("fallback_order") or [])
    request_parameters = {
        "temperature": generation_config.get("temperature"),
        "max_output_tokens": generation_config.get("max_output_tokens"),
        "seed": generation_config.get("seed"),
        "structured_output_mode": generation_config.get("structured_output_mode"),
    }
    return {
        "api_date": _string_or_none(generation_config.get("api_date")),
        "endpoint": _string_or_none(generation_config.get("endpoint")),
        "model": _string_or_none(attempt.get("model_name") or record.get("model_name")),
        "fallback_model": _string_or_none(fallback_order[1]) if len(fallback_order) > 1 else None,
        "service_tier": _string_or_none(generation_config.get("service_tier")),
        "request_parameters": request_parameters,
        "response_id": _string_or_none(attempt.get("response_id") or generation_config.get("response_id")),
        "system_fingerprint": _string_or_none(attempt.get("system_fingerprint") or record.get("system_fingerprint")),
        "sdk_or_transport_version": _string_or_none(generation_config.get("sdk_version")),
    }


def _required_metadata_fields(config: Mapping[str, Any]) -> list[str]:
    configured = (
        config.get("api_policy", {})
        .get("api_logging", {})
        .get("required_fields")
    )
    if isinstance(configured, list) and configured:
        disclosure_fields = set(_metadata_disclosure_fields(config))
        return [str(field) for field in configured if str(field) not in disclosure_fields]
    return [
        "api_date",
        "endpoint",
        "model",
        "fallback_model",
        "service_tier",
        "request_parameters",
        "response_id",
        "sdk_or_transport_version",
    ]


def _metadata_disclosure_fields(config: Mapping[str, Any]) -> list[str]:
    configured = (
        config.get("api_policy", {})
        .get("api_logging", {})
        .get("disclosure_fields")
    )
    if isinstance(configured, list) and configured:
        return [str(field) for field in configured]
    return ["system_fingerprint"]


def _metadata_has_required_fields(
    metadata: Mapping[str, Any],
    required_fields: Sequence[str],
) -> bool:
    return all(_metadata_field_present(metadata, field) for field in required_fields)


def _metadata_field_present(metadata: Mapping[str, Any], field: str) -> bool:
    if field not in metadata:
        return False
    value = metadata.get(field)
    if field == "request_parameters":
        return isinstance(value, Mapping)
    return value is not None and value != ""


def _metadata_missing_counts(
    metadata_payloads: Sequence[Mapping[str, Any]],
    required_fields: Sequence[str],
) -> dict[str, int]:
    return {
        field: sum(
            1
            for metadata in metadata_payloads
            if not _metadata_field_present(metadata, field)
        )
        for field in required_fields
    }


def _metadata_disclosure_explanation(
    missing_counts: Mapping[str, int],
    *,
    records_evaluated: int,
) -> str:
    missing = {field: count for field, count in missing_counts.items() if count > 0}
    if not missing:
        return "Disclosure-only metadata fields were not missing."
    if records_evaluated <= 0:
        return "Disclosure-only metadata fields were not measured before API calls."
    if missing.get("system_fingerprint") == records_evaluated:
        return (
            "`system_fingerprint` is disclosure-only provider metadata; it was null "
            f"or missing for all {records_evaluated} evaluated records and is "
            "reported separately from schema, tag, and final-answer success."
        )
    missing_text = ", ".join(f"{field}={count}" for field, count in sorted(missing.items()))
    return (
        "Disclosure-only metadata was missing and is reported separately from "
        f"schema, tag, and final-answer success: {missing_text}."
    )


def _configured_api_metadata(config: Mapping[str, Any]) -> dict[str, Any]:
    api = config.get("api", {}) if isinstance(config, Mapping) else {}
    model = config.get("model", {}) if isinstance(config, Mapping) else {}
    fallback_order = list(model.get("fallback_order") or [])
    return {
        "api_date": _string_or_none(api.get("api_date")),
        "endpoint": _string_or_none(api.get("endpoint")),
        "model": _string_or_none(model.get("primary")),
        "fallback_model": _string_or_none(fallback_order[1]) if len(fallback_order) > 1 else None,
        "service_tier": _string_or_none(api.get("service_tier")),
        "request_parameters": {
            "temperature": model.get("temperature"),
            "top_p": model.get("top_p"),
            "max_output_tokens": model.get("max_output_tokens"),
        },
        "sdk_or_transport_version": None,
    }


def _observed_api_metadata(
    config: Mapping[str, Any],
    metadata_payloads: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    configured = _configured_api_metadata(config)
    if not metadata_payloads:
        return configured
    first = dict(metadata_payloads[0])
    for key, value in configured.items():
        first.setdefault(key, value)
    first["observed_models"] = sorted(
        {
            str(metadata.get("model"))
            for metadata in metadata_payloads
            if metadata.get("model")
        }
    )
    first["system_fingerprints"] = sorted(
        {
            str(metadata.get("system_fingerprint"))
            for metadata in metadata_payloads
            if metadata.get("system_fingerprint")
        }
    )
    return first


def _mean_bool(values: Sequence[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


def _unique_sorted(values: Sequence[str]) -> list[str]:
    return sorted({str(value) for value in values if value})


def _string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)
