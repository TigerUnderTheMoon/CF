"""Guarded stochastic smoke utilities for the s_FMA_v2 fresh holdout."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .fresh_preflight import PREFLIGHT_FAIL_DRIFT, FreshPreflightError
from .replay import build_replay_prefix


STOCHASTIC_SMOKE_ONLY = "STOCHASTIC_SMOKE_ONLY"
STOCHASTIC_SMOKE_ENGINEERING_PASS = "STOCHASTIC_SMOKE_ENGINEERING_PASS"
STOCHASTIC_SMOKE_FAIL_COST = "STOCHASTIC_SMOKE_FAIL_COST"
STOCHASTIC_SMOKE_FAIL_GENERATION = "STOCHASTIC_SMOKE_FAIL_GENERATION"
STOCHASTIC_SMOKE_FAIL_REPLAY = "STOCHASTIC_SMOKE_FAIL_REPLAY"
STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL = "STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL"


def validate_stochastic_smoke_readiness(
    *,
    config: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    overlap_audit: Mapping[str, Any],
    preflight_report: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    allow_stochastic_smoke_only: bool,
    approved_budget_usd: float | None,
) -> dict[str, Any]:
    """Validate hard boundaries before the approved minimal smoke API run."""

    if not allow_stochastic_smoke_only:
        raise FreshPreflightError(
            "stochastic smoke requires explicit --allow-stochastic-smoke-only."
        )
    if approved_budget_usd is None:
        raise FreshPreflightError("stochastic smoke requires an approved budget ceiling.")
    approved_budget = float(approved_budget_usd)
    if approved_budget <= 0:
        raise FreshPreflightError("approved stochastic smoke budget must be positive.")

    approval_payload = approval_request.get("approval_request", {})
    requested_route = str(approval_payload.get("requested_route") or "")
    requested_scale = str(approval_payload.get("requested_scale") or "")
    sample_count = int(approval_payload.get("sample_count", 0) or 0)
    expected_requests = int(approval_payload.get("expected_api_requests", 0) or 0)
    recommended_ceiling = float(
        approval_payload.get("recommended_approval_ceiling_usd", approved_budget) or 0.0
    )
    if requested_route != "STOCHASTIC_REPEATED_REPLAY_ROUTE":
        raise FreshPreflightError("approval request must target STOCHASTIC_REPEATED_REPLAY_ROUTE.")
    if requested_scale != "minimal smoke only":
        raise FreshPreflightError("approval request must be limited to minimal smoke only.")
    if sample_count != 20:
        raise FreshPreflightError("stochastic smoke approval must request exactly 20 samples.")
    if expected_requests != 80:
        raise FreshPreflightError("stochastic smoke approval must request exactly 80 API requests.")
    if approved_budget > recommended_ceiling:
        raise FreshPreflightError("approved budget exceeds the smoke approval ceiling.")

    if overlap_audit.get("status") != "MANIFEST_OVERLAP_CLEAN":
        raise FreshPreflightError("manifest overlap audit must be MANIFEST_OVERLAP_CLEAN.")
    selected_overlaps = (
        overlap_audit.get("overlap_summary", {}).get("selected_overlaps_by_key", {})
    )
    nonzero_selected_overlaps = {
        key: value for key, value in selected_overlaps.items() if int(value or 0) != 0
    }
    if nonzero_selected_overlaps:
        raise FreshPreflightError("selected manifest overlaps must all be zero before smoke.")
    if preflight_report.get("status") != PREFLIGHT_FAIL_DRIFT:
        raise FreshPreflightError("stochastic smoke is only allowed after disclosed PREFLIGHT_FAIL_DRIFT.")
    if bool(preflight_report.get("deterministic_replay_claim_allowed", False)):
        raise FreshPreflightError("deterministic replay claim must remain forbidden.")
    if preflight_report.get("stochastic_repeated_replay_estimand_candidate", True) is False:
        raise FreshPreflightError("preflight report must expose stochastic repeated-replay candidate route.")
    if len(manifest) < sample_count:
        raise FreshPreflightError("fresh manifest does not contain enough rows for smoke.")

    return {
        "scope": STOCHASTIC_SMOKE_ONLY,
        "api_call_allowed": True,
        "sample_count": sample_count,
        "max_api_requests": expected_requests,
        "approved_budget_usd": approved_budget,
        "requested_route": requested_route,
        "current_status_remains": "PILOT_BLOCKED",
        "deterministic_replay_claim_allowed": False,
        "v2_scoring_allowed": False,
        "prm_filtering_allowed": False,
    }


def select_stochastic_smoke_records(
    manifest: Sequence[Mapping[str, Any]],
    *,
    sample_count: int = 20,
) -> list[dict[str, Any]]:
    """Select the manifest prefix locked for minimal smoke."""

    if len(manifest) < sample_count:
        raise FreshPreflightError("fresh manifest does not contain enough rows for smoke.")
    return [dict(row) for row in manifest[:sample_count]]


def build_stochastic_smoke_prefixes(
    original_records: Sequence[Mapping[str, Any]],
    *,
    mask_token: str = "[REASONING_MASK]",
) -> list[dict[str, Any]]:
    """Build one replay prefix per original record using the first reflection span only."""

    prefixes: list[dict[str, Any]] = []
    for record in original_records:
        spans = record.get("reflection_spans") or []
        if not spans:
            continue
        prefixes.append(build_replay_prefix(record, span_index=0, mask_token=mask_token))
    return prefixes


def build_stochastic_smoke_report(
    *,
    original_records: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
    replay_attempts: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
    approved_budget_usd: float,
    cost_used_usd: float,
    expected_original_records: int = 20,
    expected_replay_jobs: int = 60,
) -> dict[str, Any]:
    """Build a claim-safe engineering-only smoke report."""

    valid_originals = len(original_records)
    successful_replays = [
        row for row in replay_results if row.get("status") in {None, "success", "replayed"}
    ]
    replay_success_rate = (
        len(successful_replays) / expected_replay_jobs if expected_replay_jobs else 0.0
    )
    nonzero_delta_rows = [
        row for row in delta_rows if abs(float(row.get("delta_u", 0.0) or 0.0)) > 0.0
    ]
    task_counts = Counter(str(record.get("task_type") or "") for record in original_records)
    cost_within_budget = float(cost_used_usd) <= float(approved_budget_usd)
    generation_complete = valid_originals == expected_original_records
    replay_complete = len(successful_replays) == expected_replay_jobs and replay_success_rate >= 0.85
    sparse_signal = len(nonzero_delta_rows) == 0

    if not cost_within_budget:
        status = STOCHASTIC_SMOKE_FAIL_COST
        next_allowed_step = "STOP_AND_FIX_SMOKE_COST"
    elif not generation_complete:
        status = STOCHASTIC_SMOKE_FAIL_GENERATION
        next_allowed_step = "FIX_SMOKE_GENERATION_PIPELINE"
    elif not replay_complete:
        status = STOCHASTIC_SMOKE_FAIL_REPLAY
        next_allowed_step = "FIX_SMOKE_REPLAY_PIPELINE"
    elif sparse_signal:
        status = STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL
        next_allowed_step = "STOP_OR_REVISE_EVIDENCE_TARGET"
    else:
        status = STOCHASTIC_SMOKE_ENGINEERING_PASS
        next_allowed_step = "REQUEST_PILOT_STOCHASTIC_BUDGET"

    return {
        "artifact": "stochastic_smoke_report",
        "scope": STOCHASTIC_SMOKE_ONLY,
        "status": status,
        "sample_count": valid_originals,
        "sample_count_by_task": dict(task_counts),
        "expected_original_records": expected_original_records,
        "expected_replay_jobs": expected_replay_jobs,
        "replay_attempt_count": len(replay_attempts),
        "successful_replay_count": len(successful_replays),
        "replay_success_rate": replay_success_rate,
        "delta_rows": len(delta_rows),
        "nonzero_delta_rows": len(nonzero_delta_rows),
        "cost_used_usd": float(cost_used_usd),
        "approved_budget_usd": float(approved_budget_usd),
        "cost_within_budget": cost_within_budget,
        "current_status_remains": "PILOT_BLOCKED",
        "next_allowed_step": next_allowed_step,
        "api_allowed_after_smoke": False,
        "claim_upgrade_allowed": False,
        "task_specific_pass_claim_allowed": False,
        "global_pass_claim_allowed": False,
        "deterministic_replay_claim_allowed": False,
        "prm_filtering_claim_allowed": False,
        "no_full_generation": True,
        "no_v2_scoring": True,
        "no_prm_claim": True,
        "allowed_claim_scope": [
            "engineering feasibility",
            "cost calibration",
            "preliminary replay agreement diagnostics",
        ],
        "forbidden_claim_scope": [
            "TASK_SPECIFIC_S_FMA_V2_PASS",
            "GLOBAL_S_FMA_V2_PASS",
            "deterministic replay claim",
            "v2 scoring validation",
            "PRM/filtering claim",
        ],
    }


__all__ = [
    "STOCHASTIC_SMOKE_ENGINEERING_PASS",
    "STOCHASTIC_SMOKE_FAIL_COST",
    "STOCHASTIC_SMOKE_FAIL_GENERATION",
    "STOCHASTIC_SMOKE_FAIL_REPLAY",
    "STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL",
    "STOCHASTIC_SMOKE_ONLY",
    "build_stochastic_smoke_prefixes",
    "build_stochastic_smoke_report",
    "select_stochastic_smoke_records",
    "validate_stochastic_smoke_readiness",
]
