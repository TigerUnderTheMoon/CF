"""Guarded stochastic smoke utilities for the s_FMA_v2.1 fresh holdout."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .fresh_holdout_v2_1 import V2_1_CONTRACT_CLEAN, score_v2_1_answer
from .fresh_preflight import PREFLIGHT_FAIL_DRIFT, FreshPreflightError, select_preflight_records
from .fresh_transport_canary import TRANSPORT_CANARY_PASS
from .replay import build_replay_prefix


V2_1_STOCHASTIC_SMOKE_ONLY = "V2_1_STOCHASTIC_SMOKE_ONLY"
V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX = (
    "V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX"
)
V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST = (
    "V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST"
)
V2_1_STOCHASTIC_SMOKE_FAIL_COST = "V2_1_STOCHASTIC_SMOKE_FAIL_COST"
V2_1_STOCHASTIC_SMOKE_FAIL_REQUEST_LIMIT = "V2_1_STOCHASTIC_SMOKE_FAIL_REQUEST_LIMIT"
V2_1_STOCHASTIC_SMOKE_FAIL_MISSING_DIAGNOSTICS = (
    "V2_1_STOCHASTIC_SMOKE_FAIL_MISSING_DIAGNOSTICS"
)
V2_1_STOCHASTIC_SMOKE_FAIL_SCHEMA_OR_TAGS = "V2_1_STOCHASTIC_SMOKE_FAIL_SCHEMA_OR_TAGS"
V2_1_STOCHASTIC_SMOKE_FAIL_GENERATION = "V2_1_STOCHASTIC_SMOKE_FAIL_GENERATION"
V2_1_STOCHASTIC_SMOKE_FAIL_REPLAY = "V2_1_STOCHASTIC_SMOKE_FAIL_REPLAY"
V2_1_STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL = "V2_1_STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL"
V2_1_REPLAY_ALLOWED_REFLECTION_TYPES = [
    "verification",
    "error_diagnosis",
    "plan_revision",
    "self-evaluation",
    "uncertainty_monitoring",
    "strategy_critique",
    "planning",
    "other",
]
V2_1_REPLAY_REFLECTION_TYPE_ALIASES = {
    "final_check": "verification",
    "correction": "error_diagnosis",
}


class V2_1StochasticSmokeError(FreshPreflightError):
    """Raised when a hard v2.1 stochastic smoke boundary is violated."""


def validate_v2_1_stochastic_smoke_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    preflight_report: Mapping[str, Any],
    transport_canary_report: Mapping[str, Any],
    drift_failure_audit: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    current_readiness: Mapping[str, Any],
    allow_stochastic_smoke_only: bool,
    approved_budget_usd: float,
    current_prompt_version: str | None = None,
) -> dict[str, Any]:
    """Validate all user-approved gates before any stochastic smoke API call."""

    if not allow_stochastic_smoke_only:
        raise V2_1StochasticSmokeError(
            "v2.1 stochastic smoke requires explicit --allow-stochastic-smoke-only."
        )
    if (
        approval_request.get("requested_scope")
        != V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX
    ):
        raise V2_1StochasticSmokeError(
            "stochastic_smoke_rerun_approval_request.json must request "
            f"{V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX}."
        )
    if approval_request.get("approval_status") != "REQUEST_ONLY_NOT_APPROVED":
        raise V2_1StochasticSmokeError(
            "stochastic_smoke_rerun_approval_request.json must still be REQUEST_ONLY_NOT_APPROVED."
        )
    if current_readiness.get("status") != "PILOT_BLOCKED":
        raise V2_1StochasticSmokeError("current readiness status must remain PILOT_BLOCKED.")
    if current_readiness.get("pilot_pass") is True:
        raise V2_1StochasticSmokeError("current readiness must not report pilot_pass=true.")

    _validate_manifest_and_overlap(config=config, manifest=manifest, overlap_audit=overlap_audit)
    _validate_contract(contract_audit)
    if current_prompt_version:
        _validate_prompt_lock(
            manifest=manifest,
            contract_audit=contract_audit,
            current_prompt_version=current_prompt_version,
        )
    _validate_preflight_report(preflight_report)
    _validate_transport_canary(transport_canary_report)
    _validate_drift_failure_audit(drift_failure_audit)

    sample_count = _approval_int(
        approval_request,
        "records",
        "sample_count",
        nested=(
            "proposed_rerun_design",
            "proposed_smoke_design",
            "smoke_feasibility_gates_if_approved",
        ),
    )
    records_per_task = dict(
        approval_request.get("records_per_task")
        or approval_request.get("proposed_rerun_design", {}).get("records_per_task")
        or approval_request.get("proposed_smoke_design", {}).get("records_per_task")
        or approval_request.get("smoke_feasibility_gates_if_approved", {}).get("records_per_task")
        or {}
    )
    max_requests = _approval_int(
        approval_request,
        "max_requests",
        "max_api_requests",
        "max_total_requests",
        "request_cap",
        nested=(
            "request_estimate",
            "proposed_rerun_design",
            "proposed_smoke_design",
            "smoke_feasibility_gates_if_approved",
        ),
    )
    repeats = _approval_int(
        approval_request,
        "stochastic_repeats_per_span",
        "stochastic_replay_repeats_per_span",
        "replay_repeats_per_span",
        nested=(
            "proposed_rerun_design",
            "proposed_smoke_design",
            "smoke_feasibility_gates_if_approved",
        ),
    )
    max_spans = _approval_int(
        approval_request,
        "target_spans_per_trace_max",
        "max_target_spans_per_trace",
        nested=(
            "proposed_rerun_design",
            "proposed_smoke_design",
            "smoke_feasibility_gates_if_approved",
        ),
    )
    recommended_budget = _approval_float(
        approval_request,
        "budget_ceiling_usd",
        "recommended_budget_ceiling_usd",
        "cost_ceiling_usd",
        nested=("cost_estimate", "proposed_rerun_design", "smoke_feasibility_gates_if_approved"),
    )

    if sample_count != 20 or records_per_task != {"gsm8k": 10, "hotpotqa": 10}:
        raise V2_1StochasticSmokeError("v2.1 stochastic smoke must be exactly 20 records, 10 per task.")
    if max_requests != 140:
        raise V2_1StochasticSmokeError("v2.1 stochastic smoke max_requests must be exactly 140.")
    if repeats != 3:
        raise V2_1StochasticSmokeError("v2.1 stochastic smoke repeats per span must be exactly 3.")
    if max_spans != 2:
        raise V2_1StochasticSmokeError("v2.1 stochastic smoke max target spans per trace must be 2.")
    if float(approved_budget_usd) != float(recommended_budget):
        raise V2_1StochasticSmokeError(
            "approved budget must match recommended_budget_ceiling_usd in the smoke request."
        )

    selected = select_preflight_records(
        manifest,
        samples_per_task=10,
        task_order=["gsm8k", "hotpotqa"],
    )
    selected_counts = Counter(str(row.get("task_type") or "") for row in selected)
    if len(selected) != sample_count or dict(selected_counts) != records_per_task:
        raise V2_1StochasticSmokeError("balanced stochastic smoke selection did not match approval scope.")

    smoke_gate = config.get("smoke_gate", {}) if isinstance(config.get("smoke_gate", {}), Mapping) else {}
    gates = approval_request.get("smoke_feasibility_gates_if_approved", {})
    return {
        "scope": V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX,
        "api_call_allowed": True,
        "sample_count": sample_count,
        "sample_count_by_task": records_per_task,
        "approved_budget_usd": float(approved_budget_usd),
        "max_api_requests": max_requests,
        "stochastic_repeats_per_span": repeats,
        "max_target_spans_per_trace": max_spans,
        "valid_original_traces_min": int(gates.get("valid_original_traces_min") or 15),
        "min_replay_success_rate": float(
            gates.get("replay_success_rate_min")
            or smoke_gate.get("min_replay_success_rate")
            or 0.85
        ),
        "min_nonzero_delta_u_pooled": int(
            gates.get("pooled_nonzero_delta_u_rows_min")
            or smoke_gate.get("min_nonzero_delta_u_pooled")
            or 3
        ),
        "min_nonzero_delta_u_per_task": int(
            gates.get("per_task_nonzero_delta_u_rows_min")
            or smoke_gate.get("min_nonzero_delta_u_per_task")
            or 1
        ),
        "min_schema_success_rate": float(smoke_gate.get("min_schema_success_rate") or 0.95),
        "min_tag_extraction_success_rate": float(
            smoke_gate.get("min_tag_extraction_success_rate") or 0.95
        ),
        "current_status_remains": "PILOT_BLOCKED",
        "deterministic_replay_claim_allowed": False,
        "claim_upgrade_allowed": False,
        "full_validation_allowed": False,
        "prm_filtering_allowed": False,
    }


def build_v2_1_stochastic_smoke_generation_config(
    config: Mapping[str, Any],
    *,
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a live smoke config without mutating the planned-only YAML."""

    cloned = deepcopy(dict(config))
    experiment = dict(cloned.get("experiment", {}))
    experiment["user_approved_budget_usd"] = float(readiness["approved_budget_usd"])
    experiment["max_api_requests_pilot"] = int(readiness["max_api_requests"])
    experiment["pilot_generation_requests"] = int(readiness["max_api_requests"])
    experiment["current_task_scope"] = V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX
    cloned["experiment"] = experiment

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
    pricing.setdefault("basis", "s_FMA_v2.1 stochastic smoke ceiling")
    cloned["pricing"] = pricing

    generation = dict(cloned.get("generation", {}))
    generation.setdefault(
        "prompt_file",
        cloned.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        ),
    )
    generation.setdefault("required_tag", "reflection")
    generation.setdefault("minimum_schema_success_rate", 0.95)
    generation.setdefault("minimum_tag_success_rate", 0.95)
    cloned["generation"] = generation

    smoke = dict(cloned.get("stochastic_smoke", {}))
    smoke.setdefault("replay_prompt_file", "prompts/real_task_replay.txt")
    smoke.setdefault("mask_token", "[REASONING_MASK]")
    smoke.setdefault(
        "replay_reflection_type_policy",
        {
            "policy_name": "v2_1_replay_schema_compatibility",
            "allowed_types": list(V2_1_REPLAY_ALLOWED_REFLECTION_TYPES),
            "alias_canonicalization": dict(V2_1_REPLAY_REFLECTION_TYPE_ALIASES),
            "unknown_type_policy": "reject",
        },
    )
    smoke["replay_repeats_per_span"] = int(readiness["stochastic_repeats_per_span"])
    smoke["max_target_spans_per_trace"] = int(readiness["max_target_spans_per_trace"])
    cloned["stochastic_smoke"] = smoke
    return cloned


def build_v2_1_stochastic_smoke_prefixes(
    original_records: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    mask_token: str = "[REASONING_MASK]",
) -> list[dict[str, Any]]:
    """Build replay prefixes for the first verification and non-verification span."""

    prefixes: list[dict[str, Any]] = []
    for record in original_records:
        for span_index in _v2_1_target_span_indices(record, config=config):
            prefixes.append(build_replay_prefix(record, span_index=span_index, mask_token=mask_token))
    return prefixes


def aggregate_v2_1_delta_u_by_span(
    original_records: Sequence[Mapping[str, Any]],
    intervened_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate repeated replay outcomes with the preregistered v2.1 primary target."""

    original_by_id = {str(record.get("sample_id")): record for record in original_records}
    grouped: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for intervened in intervened_records:
        if intervened.get("status") not in {None, "success", "replayed"}:
            continue
        sample_id = str(intervened.get("sample_id") or "")
        if not sample_id or sample_id not in original_by_id or "span_index" not in intervened:
            continue
        grouped[(sample_id, int(intervened.get("span_index", 0) or 0))].append(intervened)

    rows = []
    for (sample_id, span_index), repeats in sorted(grouped.items()):
        original = original_by_id[sample_id]
        task_type = str(original.get("task_type") or "")
        reference = str(original.get("reference_answer") or "")
        aliases = original.get("aliases") or []
        original_score = score_v2_1_answer(
            task_type,
            str(original.get("final_answer") or ""),
            reference,
            aliases,
        )
        intervened_scores = [
            score_v2_1_answer(
                task_type,
                str(intervened.get("final_answer") or ""),
                reference,
                aliases,
            )
            for intervened in repeats
        ]
        intervened_primary = [float(score["primary_score"]) for score in intervened_scores]
        intervened_mean = sum(intervened_primary) / len(intervened_primary)
        rows.append(
            {
                "sample_id": sample_id,
                "task_type": task_type,
                "span_index": span_index,
                "repeat_count": len(repeats),
                "successful_repeats": len(intervened_primary),
                "primary_score_field": original_score["primary_score_field"],
                "original_score": float(original_score["primary_score"]),
                "intervened_mean_score": intervened_mean,
                "delta_u": float(original_score["primary_score"]) - intervened_mean,
                "metric": "v2_1_primary_score",
                "intervened_scores": intervened_primary,
            }
        )
    return rows


def build_v2_1_stochastic_smoke_report(
    *,
    original_records: Sequence[Mapping[str, Any]],
    original_attempts: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
    replay_attempts: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
    readiness: Mapping[str, Any],
    cost_used_usd: float,
    expected_replay_jobs: int,
) -> dict[str, Any]:
    """Build a claim-safe v2.1 stochastic smoke report."""

    all_attempts = [*original_attempts, *replay_attempts]
    actual_requests = len(all_attempts)
    max_requests = int(readiness["max_api_requests"])
    approved_budget = float(readiness["approved_budget_usd"])
    valid_originals = len(original_records)
    original_counts = Counter(str(record.get("task_type") or "") for record in original_records)
    successful_replays = [
        row for row in replay_results if row.get("status") in {None, "success", "replayed"}
    ]
    replay_success_rate = (
        len(successful_replays) / expected_replay_jobs if expected_replay_jobs else 0.0
    )
    nonzero_delta_rows = [
        row for row in delta_rows if abs(float(row.get("delta_u", 0.0) or 0.0)) > 0.0
    ]
    nonzero_by_task = Counter(str(row.get("task_type") or "") for row in nonzero_delta_rows)
    attempt_quality = _attempt_quality_summary(all_attempts)

    failure_codes: list[str] = []
    if float(cost_used_usd) > approved_budget:
        failure_codes.append(V2_1_STOCHASTIC_SMOKE_FAIL_COST)
    if actual_requests > max_requests:
        failure_codes.append(V2_1_STOCHASTIC_SMOKE_FAIL_REQUEST_LIMIT)
    if not attempt_quality["output_extraction_diagnostics_complete"]:
        failure_codes.append(V2_1_STOCHASTIC_SMOKE_FAIL_MISSING_DIAGNOSTICS)
    if (
        attempt_quality["schema_success_rate"] < float(readiness["min_schema_success_rate"])
        or attempt_quality["tag_extraction_success_rate"]
        < float(readiness["min_tag_extraction_success_rate"])
        or attempt_quality["final_answer_parse_success_rate"] < 0.95
    ):
        failure_codes.append(V2_1_STOCHASTIC_SMOKE_FAIL_SCHEMA_OR_TAGS)
    if valid_originals < int(readiness["valid_original_traces_min"]):
        failure_codes.append(V2_1_STOCHASTIC_SMOKE_FAIL_GENERATION)
    if replay_success_rate < float(readiness["min_replay_success_rate"]):
        failure_codes.append(V2_1_STOCHASTIC_SMOKE_FAIL_REPLAY)
    sparse_signal = (
        len(nonzero_delta_rows) < int(readiness["min_nonzero_delta_u_pooled"])
        or any(
            int(nonzero_by_task.get(task_type, 0)) < int(readiness["min_nonzero_delta_u_per_task"])
            for task_type in ("gsm8k", "hotpotqa")
        )
    )
    if sparse_signal:
        failure_codes.append(V2_1_STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL)

    status = failure_codes[0] if failure_codes else V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST
    next_allowed_step = _next_allowed_step(status)
    pilot_request_allowed = status == V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST
    return {
        "artifact": "stochastic_smoke_report",
        "scope": str(readiness.get("scope") or V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX),
        "status": status,
        "failure_codes": failure_codes,
        "sample_count": valid_originals,
        "expected_original_records": int(readiness["sample_count"]),
        "sample_count_by_task": dict(original_counts),
        "expected_replay_jobs": expected_replay_jobs,
        "replay_attempt_count": len(replay_attempts),
        "successful_replay_count": len(successful_replays),
        "replay_success_rate": replay_success_rate,
        "delta_rows": len(delta_rows),
        "nonzero_delta_rows": len(nonzero_delta_rows),
        "nonzero_delta_u_pooled_count": len(nonzero_delta_rows),
        "nonzero_delta_u_by_task": {
            "gsm8k": int(nonzero_by_task.get("gsm8k", 0)),
            "hotpotqa": int(nonzero_by_task.get("hotpotqa", 0)),
        },
        "cost_used_usd": float(cost_used_usd),
        "approved_budget_usd": approved_budget,
        "cost_within_budget": float(cost_used_usd) <= approved_budget,
        "api_attempts": actual_requests,
        "max_api_requests": max_requests,
        "request_within_cap": actual_requests <= max_requests,
        "current_status_remains": "PILOT_BLOCKED",
        "next_allowed_step": next_allowed_step,
        "v2_1_pilot_request_allowed": pilot_request_allowed,
        "v2_1_full_validation_request_allowed": False,
        "api_allowed_after_smoke": False,
        "claim_upgrade_allowed": False,
        "task_specific_pass_claim_allowed": False,
        "global_pass_claim_allowed": False,
        "deterministic_replay_claim_allowed": False,
        "prm_filtering_claim_allowed": False,
        "no_full_generation": True,
        "no_v2_1_validation_claim": True,
        "no_prm_claim": True,
        "allowed_claim_scope": [
            "smoke feasibility diagnostics",
            "cost calibration",
            "drift-disclosed stochastic repeated-replay evidence only",
        ],
        "forbidden_claim_scope": [
            "task/global pass claim",
            "deterministic replay claim",
            "v2.1 validation claim",
            "PRM/filtering claim",
            "submission-readiness upgrade claim",
        ],
        **attempt_quality,
    }


def _validate_manifest_and_overlap(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
) -> None:
    tasks = config.get("fresh_selection_policy", {}).get("tasks", {})
    expected_total = sum(int(task.get("sample_count", 0) or 0) for task in tasks.values())
    if expected_total and len(manifest) != expected_total:
        raise V2_1StochasticSmokeError(
            f"v2.1 fresh manifest row count is {len(manifest)}, expected {expected_total}."
        )
    if overlap_audit.get("status") != "MANIFEST_OVERLAP_CLEAN":
        raise V2_1StochasticSmokeError("manifest overlap audit must be MANIFEST_OVERLAP_CLEAN.")
    selected_overlaps = dict(
        overlap_audit.get("overlap_summary", {}).get("selected_overlaps_by_key", {})
    )
    required_keys = [
        "sample_id",
        "task_id",
        "dataset_config_split_source_index",
        "normalized_question_hash",
        "reference_answer_hash",
        "alias_hash",
    ]
    missing = [key for key in required_keys if key not in selected_overlaps]
    nonzero = {
        key: selected_overlaps.get(key)
        for key in required_keys
        if int(selected_overlaps.get(key) or 0) != 0
    }
    if missing or nonzero:
        raise V2_1StochasticSmokeError("manifest overlap audit must be clean on all six selected keys.")


def _validate_contract(contract_audit: Mapping[str, Any]) -> None:
    if contract_audit.get("status") != V2_1_CONTRACT_CLEAN:
        raise V2_1StochasticSmokeError("v2_1_contract_audit.json must be V2_1_CONTRACT_CLEAN.")
    if contract_audit.get("claim_upgrade_allowed") is not False:
        raise V2_1StochasticSmokeError("v2.1 contract audit must not allow claim upgrade.")


def _validate_prompt_lock(
    *,
    manifest: Sequence[Mapping[str, Any]],
    contract_audit: Mapping[str, Any],
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
    if manifest_versions != {current_prompt_version} or contract_version != current_prompt_version:
        raise V2_1StochasticSmokeError("v2.1 prompt version lock mismatch before stochastic smoke.")


def _validate_preflight_report(preflight_report: Mapping[str, Any]) -> None:
    if preflight_report.get("status") != PREFLIGHT_FAIL_DRIFT:
        raise V2_1StochasticSmokeError("latest preflight status must be PREFLIGHT_FAIL_DRIFT.")
    if preflight_report.get("current_status_remains") != "PILOT_BLOCKED":
        raise V2_1StochasticSmokeError("preflight report must keep current status as PILOT_BLOCKED.")
    for key in (
        "json_parse_success_rate",
        "schema_success_rate",
        "tag_extraction_success_rate",
        "final_answer_parse_success_rate",
    ):
        if float(preflight_report.get(key, 0.0) or 0.0) != 1.0:
            raise V2_1StochasticSmokeError(
                "latest preflight schema/tag/final-answer success rates must all be 1.0."
            )
    if preflight_report.get("deterministic_replay_claim_allowed") is not False:
        raise V2_1StochasticSmokeError("deterministic replay claim must remain forbidden.")
    if preflight_report.get("stochastic_repeated_replay_estimand_candidate") is not True:
        raise V2_1StochasticSmokeError("preflight report must expose stochastic repeated-replay route.")


def _validate_transport_canary(transport_canary_report: Mapping[str, Any]) -> None:
    if transport_canary_report.get("status") != TRANSPORT_CANARY_PASS:
        raise V2_1StochasticSmokeError("transport canary status must be TRANSPORT_CANARY_PASS.")


def _validate_drift_failure_audit(drift_failure_audit: Mapping[str, Any]) -> None:
    if not drift_failure_audit:
        raise V2_1StochasticSmokeError("drift failure audit must exist before stochastic smoke.")
    if drift_failure_audit.get("current_status_remains") != "PILOT_BLOCKED":
        raise V2_1StochasticSmokeError("drift failure audit must keep current status as PILOT_BLOCKED.")
    if drift_failure_audit.get("preflight_summary", {}).get("status") != PREFLIGHT_FAIL_DRIFT:
        raise V2_1StochasticSmokeError("drift failure audit must source a PREFLIGHT_FAIL_DRIFT report.")
    transport = drift_failure_audit.get("schema_and_transport_audit", {})
    if transport.get("schema_transport_blockers_resolved") is not True:
        raise V2_1StochasticSmokeError("drift failure audit must resolve schema/transport blockers.")
    if transport.get("output_extraction_diagnostics_complete") is False:
        raise V2_1StochasticSmokeError("drift failure audit must include extraction diagnostics.")
    drift = drift_failure_audit.get("drift_metric", {})
    if drift.get("determinism_gate_pass") is not False:
        raise V2_1StochasticSmokeError("drift failure audit must keep deterministic route blocked.")


def _v2_1_target_span_indices(record: Mapping[str, Any], *, config: Mapping[str, Any]) -> list[int]:
    spans = list(record.get("reflection_spans") or [])
    span_policy = config.get("span_diversity_policy", {}).get("target_span_policy", {})
    max_spans = int(span_policy.get("max_target_spans_per_trace") or 2)
    eligible_non_verification = set(
        span_policy.get("eligible_non_verification_types")
        or ["error_diagnosis", "plan_revision", "self-evaluation", "uncertainty_monitoring"]
    )
    selected: list[Mapping[str, Any]] = []
    if span_policy.get("include_first_verification_span", True):
        verification = _first_span_by_type(spans, {"verification"})
        if verification is not None:
            selected.append(verification)
    if span_policy.get("include_first_non_verification_span", True):
        non_verification = _first_span_by_type(spans, eligible_non_verification)
        if non_verification is not None:
            selected.append(non_verification)
    deduped: dict[int, Mapping[str, Any]] = {}
    for span in selected:
        deduped[int(span.get("span_index", 0) or 0)] = span
    ordered = sorted(
        deduped.values(),
        key=lambda span: int(span.get("start_char", span.get("span_index", 0)) or 0),
    )
    return [int(span.get("span_index", 0) or 0) for span in ordered[:max_spans]]


def _first_span_by_type(
    spans: Sequence[Mapping[str, Any]],
    operation_types: set[str],
) -> Mapping[str, Any] | None:
    for span in sorted(spans, key=lambda item: int(item.get("start_char", 0) or 0)):
        if str(span.get("operation_type") or "") in operation_types:
            return span
    return None


def _attempt_quality_summary(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(attempts)
    diagnostics_present = sum(1 for attempt in attempts if attempt.get("output_extraction_diagnostics"))
    schema_success = sum(1 for attempt in attempts if attempt.get("record") is not None and not attempt.get("validation_errors"))
    tag_success = sum(
        1
        for attempt in attempts
        if (attempt.get("record") or {}).get("reflection_spans")
    )
    final_answer_success = sum(
        1
        for attempt in attempts
        if str((attempt.get("record") or {}).get("final_answer") or "").strip()
    )
    json_success = sum(1 for attempt in attempts if attempt.get("record") is not None)
    return {
        "output_extraction_diagnostics_present_count": diagnostics_present,
        "output_extraction_diagnostics_complete": diagnostics_present == total,
        "json_parse_success_rate": json_success / total if total else 0.0,
        "schema_success_rate": schema_success / total if total else 0.0,
        "tag_extraction_success_rate": tag_success / total if total else 0.0,
        "final_answer_parse_success_rate": final_answer_success / total if total else 0.0,
    }


def _next_allowed_step(status: str) -> str:
    if status == V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST:
        return "REQUEST_V2_1_PILOT_STOCHASTIC_BUDGET"
    if status == V2_1_STOCHASTIC_SMOKE_FAIL_COST:
        return "STOP_AND_FIX_SMOKE_COST"
    if status == V2_1_STOCHASTIC_SMOKE_FAIL_REQUEST_LIMIT:
        return "STOP_AND_FIX_REQUEST_SCOPE"
    if status == V2_1_STOCHASTIC_SMOKE_FAIL_MISSING_DIAGNOSTICS:
        return "STOP_AND_FIX_OUTPUT_EXTRACTION_DIAGNOSTICS"
    if status == V2_1_STOCHASTIC_SMOKE_FAIL_SCHEMA_OR_TAGS:
        return "STOP_AND_FIX_SMOKE_SCHEMA_OR_TAGS"
    if status == V2_1_STOCHASTIC_SMOKE_FAIL_GENERATION:
        return "FIX_SMOKE_GENERATION_PIPELINE"
    if status == V2_1_STOCHASTIC_SMOKE_FAIL_REPLAY:
        return "FIX_SMOKE_REPLAY_PIPELINE"
    return "STOP_OR_REVISE_EVIDENCE_TARGET"


def _approval_int(
    payload: Mapping[str, Any],
    *keys: str,
    nested: Sequence[str] = (),
) -> int:
    value = _approval_value(payload, *keys, nested=nested)
    if value is None:
        raise V2_1StochasticSmokeError(f"approval request missing one of: {', '.join(keys)}")
    return int(value)


def _approval_float(
    payload: Mapping[str, Any],
    *keys: str,
    nested: Sequence[str] = (),
) -> float:
    value = _approval_value(payload, *keys, nested=nested)
    if value is None:
        raise V2_1StochasticSmokeError(f"approval request missing one of: {', '.join(keys)}")
    return float(value)


def _approval_value(
    payload: Mapping[str, Any],
    *keys: str,
    nested: Sequence[str] = (),
) -> Any:
    for key in keys:
        if payload.get(key) is not None:
            return payload[key]
    for section_name in nested:
        section = payload.get(section_name, {})
        if not isinstance(section, Mapping):
            continue
        for key in keys:
            if section.get(key) is not None:
                return section[key]
    return None


__all__ = [
    "V2_1_REPLAY_ALLOWED_REFLECTION_TYPES",
    "V2_1_REPLAY_REFLECTION_TYPE_ALIASES",
    "V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX",
    "V2_1_STOCHASTIC_SMOKE_FAIL_COST",
    "V2_1_STOCHASTIC_SMOKE_FAIL_GENERATION",
    "V2_1_STOCHASTIC_SMOKE_FAIL_MISSING_DIAGNOSTICS",
    "V2_1_STOCHASTIC_SMOKE_FAIL_REPLAY",
    "V2_1_STOCHASTIC_SMOKE_FAIL_REQUEST_LIMIT",
    "V2_1_STOCHASTIC_SMOKE_FAIL_SCHEMA_OR_TAGS",
    "V2_1_STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL",
    "V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST",
    "V2_1_STOCHASTIC_SMOKE_ONLY",
    "V2_1StochasticSmokeError",
    "aggregate_v2_1_delta_u_by_span",
    "build_v2_1_stochastic_smoke_generation_config",
    "build_v2_1_stochastic_smoke_prefixes",
    "build_v2_1_stochastic_smoke_report",
    "validate_v2_1_stochastic_smoke_readiness",
]
