"""Guarded v2.1 mini downstream filtering validation helpers."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Mapping, Sequence

from .candidate_score import (
    SCORE_NAME,
    build_candidate_score_leakage_audit,
    build_structurally_calibrated_fma_scores,
)
from .fresh_holdout_v2_1 import score_v2_1_answer
from .replay import build_replay_prefix


V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY = (
    "V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY"
)
V2_1_DOWNSTREAM_FILTERING_MINI_PASS = "V2_1_DOWNSTREAM_FILTERING_MINI_PASS"
V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_GATE = "V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_GATE"
V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_COST = "V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_COST"
V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_REQUEST_LIMIT = (
    "V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_REQUEST_LIMIT"
)
V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_INCOMPLETE = (
    "V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_INCOMPLETE"
)
V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_FILTERING_SIGNAL = (
    "V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_FILTERING_SIGNAL"
)

MASK_LOW_RETAIN_HIGH = "mask_low_retain_high"
MASK_HIGH_ANTI_FILTER = "mask_high_anti_filter"
DEFAULT_RECORDS_PER_TASK = {"gsm8k": 10, "hotpotqa": 10}
DEFAULT_SAMPLE_COUNT = 20
DEFAULT_PLANNED_API_CALLS = 40
DEFAULT_MAX_API_REQUESTS = 60
DEFAULT_BUDGET_USD = 5.0
DEFAULT_SELECTION_SEED = 20260606


class V2_1DownstreamFilteringError(RuntimeError):
    """Raised when the v2.1 mini downstream filtering boundary is violated."""


def build_downstream_filtering_preregistration() -> dict[str, Any]:
    """Return the fixed preregistration contract for the one-shot mini validation."""

    return {
        "artifact": "v2_1_downstream_filtering_preregistration",
        "requested_scope": V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY,
        "approval_status": "REQUEST_ONLY_NOT_APPROVED",
        "sample_count": DEFAULT_SAMPLE_COUNT,
        "sample_count_by_task": dict(DEFAULT_RECORDS_PER_TASK),
        "conditions": [MASK_LOW_RETAIN_HIGH, MASK_HIGH_ANTI_FILTER],
        "planned_api_calls": DEFAULT_PLANNED_API_CALLS,
        "max_api_requests": DEFAULT_MAX_API_REQUESTS,
        "recommended_budget_ceiling_usd": DEFAULT_BUDGET_USD,
        "selection_seed": DEFAULT_SELECTION_SEED,
        "selection_rule": "target_blind_balanced_hash_order_requires_two_clean_candidate_spans",
        "filtering_policy": {
            MASK_LOW_RETAIN_HIGH: "mask the lowest-scored span and retain the highest-scored span",
            MASK_HIGH_ANTI_FILTER: "mask the highest-scored span as a negative-control anti-filter",
        },
        "source_artifacts": {
            "original_traces": (
                "outputs/s_fma_v2_1_fresh_holdout/"
                "v2_1_pilot_stochastic_original_traces.jsonl"
            ),
            "pilot_report": (
                "outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_report.json"
            ),
            "full_abandonment_audit": (
                "outputs/s_fma_v2_1_fresh_holdout/"
                "v2_1_full_validation_abandonment_audit.json"
            ),
            "structural_diagnostics": "outputs/structural_diagnostics.json",
            "redundancy_analysis": "outputs/redundancy_analysis.json",
        },
        "target_blind_forbidden_selection_fields": [
            "correctness",
            "delta_u",
            "final_answer",
            "intervened_score",
            "original_score",
            "rank_signal",
            "replay_outcome",
        ],
        "pass_criteria": {
            "min_valid_pairs": 16,
            "min_valid_pairs_per_task": 8,
            "pooled_mean_advantage": "strictly_greater_than_zero",
            "per_task_mean_advantage": "nonnegative_for_each_task",
            "budget_within_usd": DEFAULT_BUDGET_USD,
            "request_cap": DEFAULT_MAX_API_REQUESTS,
        },
        "current_status_remains": "PILOT_BLOCKED",
        "claim_upgrade_allowed": False,
        "allowed_claim_scope": [
            "one small preregistered online filtering diagnostic",
            "task-balanced v2.1 pilot-sourced paired replay result",
        ],
        "forbidden_claim_scope": [
            "full validation claim",
            "deterministic replay claim",
            "top-tier-ready claim",
            "submission-ready claim",
            "PRM/filtering superiority claim",
            "v2.4 route claim",
        ],
    }


def validate_downstream_filtering_readiness(
    *,
    preregistration: Mapping[str, Any],
    pilot_report: Mapping[str, Any],
    abandonment_audit: Mapping[str, Any],
    current_status: str,
    allow_downstream_filtering_validation_only: bool,
    approved_budget_usd: float,
) -> dict[str, Any]:
    """Validate the fixed mini-validation gates before any API call."""

    if not allow_downstream_filtering_validation_only:
        raise V2_1DownstreamFilteringError("explicit downstream filtering guard is required.")
    if preregistration.get("requested_scope") != V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY:
        raise V2_1DownstreamFilteringError("requested scope does not match mini validation.")
    if preregistration.get("approval_status") != "REQUEST_ONLY_NOT_APPROVED":
        raise V2_1DownstreamFilteringError("preregistration must remain REQUEST_ONLY_NOT_APPROVED.")
    if int(preregistration.get("sample_count", 0) or 0) != DEFAULT_SAMPLE_COUNT:
        raise V2_1DownstreamFilteringError("sample_count must be exactly 20.")
    if dict(preregistration.get("sample_count_by_task") or {}) != DEFAULT_RECORDS_PER_TASK:
        raise V2_1DownstreamFilteringError("sample_count_by_task must be exactly 10/10.")
    if int(preregistration.get("planned_api_calls", 0) or 0) != DEFAULT_PLANNED_API_CALLS:
        raise V2_1DownstreamFilteringError("planned_api_calls must be exactly 40.")
    if int(preregistration.get("max_api_requests", 0) or 0) != DEFAULT_MAX_API_REQUESTS:
        raise V2_1DownstreamFilteringError("max_api_requests must be exactly 60.")
    recommended_budget = float(preregistration.get("recommended_budget_ceiling_usd", 0.0) or 0.0)
    if float(approved_budget_usd) != recommended_budget or recommended_budget != DEFAULT_BUDGET_USD:
        raise V2_1DownstreamFilteringError("approved budget must exactly match USD 5.0.")
    if current_status != "PILOT_BLOCKED":
        raise V2_1DownstreamFilteringError("current status must remain PILOT_BLOCKED.")
    if (
        pilot_report.get("status") != "V2_1_PILOT_STOCHASTIC_PASS"
        or pilot_report.get("GLOBAL_pass") is not True
    ):
        raise V2_1DownstreamFilteringError("pilot stochastic report must be the pilot pass source.")
    if abandonment_audit.get("route_decision") != "ABANDON_STRICT_V2_1_FULL_VALIDATION":
        raise V2_1DownstreamFilteringError("full validation abandonment audit is required.")
    if _mentions_full_validation_source(preregistration.get("source_artifacts", {})):
        raise V2_1DownstreamFilteringError("full validation artifacts cannot be source evidence.")

    return {
        "scope": V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY,
        "api_call_allowed": True,
        "sample_count": DEFAULT_SAMPLE_COUNT,
        "sample_count_by_task": dict(DEFAULT_RECORDS_PER_TASK),
        "planned_api_calls": DEFAULT_PLANNED_API_CALLS,
        "max_api_requests": DEFAULT_MAX_API_REQUESTS,
        "approved_budget_usd": DEFAULT_BUDGET_USD,
        "selection_seed": int(preregistration.get("selection_seed") or DEFAULT_SELECTION_SEED),
        "min_valid_pairs": int(preregistration.get("pass_criteria", {}).get("min_valid_pairs") or 16),
        "min_valid_pairs_per_task": int(
            preregistration.get("pass_criteria", {}).get("min_valid_pairs_per_task") or 8
        ),
        "current_status_remains": "PILOT_BLOCKED",
        "claim_upgrade_allowed": False,
        "full_validation_allowed": False,
        "prm_filtering_superiority_claim_allowed": False,
    }


def build_candidate_scores_for_records(
    records: Sequence[Mapping[str, Any]],
    *,
    config: Mapping[str, Any],
    structural_diagnostics: Mapping[str, Any],
    redundancy_analysis: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build leakage-safe candidate scores and their audit for pilot records."""

    rows = build_structurally_calibrated_fma_scores(
        records,
        config=config,
        structural_diagnostics=structural_diagnostics,
        redundancy_analysis=redundancy_analysis,
    )
    return rows, build_candidate_score_leakage_audit(rows)


def select_filtering_samples(
    records: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    records_per_task: Mapping[str, int] | None = None,
    seed: int = DEFAULT_SELECTION_SEED,
) -> list[dict[str, Any]]:
    """Select task-balanced, target-blind samples with two clean candidate spans."""

    quotas = dict(records_per_task or DEFAULT_RECORDS_PER_TASK)
    candidate_by_sample = _candidate_rows_by_sample(candidate_rows)
    selected: list[dict[str, Any]] = []
    for task_type in sorted(quotas):
        eligible = []
        for record in records:
            if str(record.get("task_type") or "") != task_type:
                continue
            span_pair = _high_low_candidate_pair(candidate_by_sample.get(str(record.get("sample_id")), []))
            if span_pair is None:
                continue
            eligible.append(dict(record))
        eligible.sort(key=lambda row: _selection_key(row, seed=seed))
        quota = int(quotas[task_type])
        if len(eligible) < quota:
            raise V2_1DownstreamFilteringError(
                f"insufficient eligible {task_type} records for downstream filtering."
            )
        selected.extend(eligible[:quota])
    return selected


def build_filtering_replay_jobs(
    selected_records: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    mask_token: str = "[REASONING_MASK]",
) -> list[dict[str, Any]]:
    """Build two replay jobs per selected record: candidate filter and anti-filter."""

    candidate_by_sample = _candidate_rows_by_sample(candidate_rows)
    jobs: list[dict[str, Any]] = []
    for record in selected_records:
        sample_id = str(record.get("sample_id") or "")
        span_pair = _high_low_candidate_pair(candidate_by_sample.get(sample_id, []))
        if span_pair is None:
            raise V2_1DownstreamFilteringError(f"missing clean high/low candidates for {sample_id}.")
        high, low = span_pair
        jobs.append(
            _job_from_prefix(
                record,
                target=low,
                retained=high,
                condition=MASK_LOW_RETAIN_HIGH,
                mask_token=mask_token,
            )
        )
        jobs.append(
            _job_from_prefix(
                record,
                target=high,
                retained=low,
                condition=MASK_HIGH_ANTI_FILTER,
                mask_token=mask_token,
            )
        )
    return jobs


def build_downstream_filtering_report(
    *,
    jobs: Sequence[Mapping[str, Any]],
    original_records: Sequence[Mapping[str, Any]],
    replay_records: Sequence[Mapping[str, Any]],
    api_attempts: int,
    cost_used_usd: float,
    approved_budget_usd: float,
    request_cap: int,
    min_valid_pairs: int = 16,
    min_valid_pairs_per_task: int = 8,
    budget_stop_triggered: bool = False,
    request_stop_triggered: bool = False,
) -> dict[str, Any]:
    """Build a claim-safe paired filtering diagnostic report."""

    originals_by_id = {str(row.get("sample_id") or ""): row for row in original_records}
    replay_by_key = {
        (str(row.get("sample_id") or ""), str(row.get("condition") or "")): row
        for row in replay_records
        if row.get("status") in {None, "success", "replayed"}
    }
    pairs = []
    jobs_by_sample: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for job in jobs:
        jobs_by_sample[str(job.get("sample_id") or "")][str(job.get("condition") or "")] = job

    for sample_id, sample_jobs in sorted(jobs_by_sample.items()):
        original = originals_by_id.get(sample_id)
        low_replay = replay_by_key.get((sample_id, MASK_LOW_RETAIN_HIGH))
        high_replay = replay_by_key.get((sample_id, MASK_HIGH_ANTI_FILTER))
        if original is None or low_replay is None or high_replay is None:
            continue
        low_score = _primary_score(original, low_replay)
        high_score = _primary_score(original, high_replay)
        task_type = str(original.get("task_type") or "")
        pairs.append(
            {
                "sample_id": sample_id,
                "task_type": task_type,
                "mask_low_retain_high_score": low_score,
                "mask_high_anti_filter_score": high_score,
                "advantage": low_score - high_score,
                "mask_low_span_index": sample_jobs[MASK_LOW_RETAIN_HIGH].get("span_index"),
                "mask_high_span_index": sample_jobs[MASK_HIGH_ANTI_FILTER].get("span_index"),
            }
        )

    pooled = _advantage_metrics(pairs)
    per_task = {}
    for task_type in sorted({str(row.get("task_type") or "") for row in original_records}):
        per_task[task_type] = _advantage_metrics(
            [row for row in pairs if row.get("task_type") == task_type]
        )

    failure_codes = []
    if float(cost_used_usd) > float(approved_budget_usd) or budget_stop_triggered:
        failure_codes.append(V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_COST)
    if int(api_attempts) > int(request_cap) or request_stop_triggered:
        failure_codes.append(V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_REQUEST_LIMIT)
    if pooled["n"] < min_valid_pairs or any(
        task_payload["n"] < min_valid_pairs_per_task for task_payload in per_task.values()
    ):
        failure_codes.append(V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_INCOMPLETE)
    if pooled["mean_advantage"] <= 0.0 or any(
        task_payload["mean_advantage"] < 0.0 for task_payload in per_task.values()
    ):
        failure_codes.append(V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_FILTERING_SIGNAL)

    status = V2_1_DOWNSTREAM_FILTERING_MINI_PASS if not failure_codes else failure_codes[0]
    return {
        "artifact": "v2_1_downstream_filtering_report",
        "scope": V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY,
        "status": status,
        "GLOBAL_pass": status == V2_1_DOWNSTREAM_FILTERING_MINI_PASS,
        "TASK_SPECIFIC_pass_by_task": {
            task_type: payload["n"] >= min_valid_pairs_per_task and payload["mean_advantage"] >= 0.0
            for task_type, payload in per_task.items()
        },
        "failure_codes": failure_codes,
        "api_execution_performed": True,
        "api_attempts": int(api_attempts),
        "planned_api_calls": DEFAULT_PLANNED_API_CALLS,
        "max_api_requests": int(request_cap),
        "request_within_cap": int(api_attempts) <= int(request_cap),
        "request_stop_triggered": bool(request_stop_triggered),
        "approved_budget_usd": float(approved_budget_usd),
        "cost_used_usd": float(cost_used_usd),
        "cost_within_budget": float(cost_used_usd) <= float(approved_budget_usd),
        "budget_stop_triggered": bool(budget_stop_triggered),
        "valid_pair_count": pooled["n"],
        "paired_metrics": {"pooled": pooled, "per_task": per_task},
        "paired_rows": pairs,
        "current_status_remains": "PILOT_BLOCKED",
        "claim_upgrade_allowed": False,
        "full_validation_claim_allowed": False,
        "deterministic_replay_claim_allowed": False,
        "prm_filtering_superiority_claim_allowed": False,
        "allowed_claim_scope": [
            "one small preregistered online filtering diagnostic"
            if status == V2_1_DOWNSTREAM_FILTERING_MINI_PASS
            else "failed or abandoned mini downstream filtering route"
        ],
        "forbidden_claim_scope": [
            "full validation claim",
            "deterministic replay claim",
            "top-tier-ready claim",
            "submission-ready claim",
            "PRM/filtering superiority claim",
            "v2.4 route claim",
        ],
        "next_allowed_step": (
            "REPORT_MINI_DIAGNOSTIC_ONLY"
            if status == V2_1_DOWNSTREAM_FILTERING_MINI_PASS
            else "ABANDON_MINI_DOWNSTREAM_FILTERING_ROUTE"
        ),
    }


def markdown_for_preregistration(preregistration: Mapping[str, Any]) -> str:
    """Render a compact markdown preregistration companion."""

    return "\n".join(
        [
            "# v2.1 Downstream Filtering Mini-Validation Preregistration",
            "",
            f"Scope: `{preregistration['requested_scope']}`",
            "",
            "This is a one-shot, task-balanced online mini diagnostic. It does not run or rescue full validation, train a PRM, open v2.4, or permit submission/top-tier-ready wording.",
            "",
            "| Field | Value |",
            "|---|---:|",
            f"| Samples | {preregistration['sample_count']} |",
            f"| Planned API calls | {preregistration['planned_api_calls']} |",
            f"| Request cap | {preregistration['max_api_requests']} |",
            f"| Budget ceiling USD | {preregistration['recommended_budget_ceiling_usd']} |",
            "",
            "Current status remains `PILOT_BLOCKED`.",
            "",
        ]
    )


def markdown_for_report(report: Mapping[str, Any]) -> str:
    """Render a compact markdown report companion."""

    return "\n".join(
        [
            "# v2.1 Downstream Filtering Mini-Validation Report",
            "",
            f"Status: `{report['status']}`",
            "",
            "| Field | Value |",
            "|---|---:|",
            f"| API attempts | {report['api_attempts']} |",
            f"| Cost used USD | {report['cost_used_usd']} |",
            f"| Valid paired samples | {report['valid_pair_count']} |",
            f"| Pooled mean advantage | {report['paired_metrics']['pooled']['mean_advantage']} |",
            "",
            "Current status remains `PILOT_BLOCKED`.",
            "",
            "No full-validation, deterministic replay, top-tier-ready, submission-ready, PRM/filtering superiority, or v2.4 claim is allowed.",
            "",
        ]
    )


def _mentions_full_validation_source(source_artifacts: Mapping[str, Any]) -> bool:
    for key, value in source_artifacts.items():
        key_text = str(key).lower()
        value_text = str(value).lower()
        if "full" in key_text and "abandonment" not in key_text:
            return True
        if "full_stochastic_report" in value_text:
            return True
    return False


def _candidate_rows_by_sample(
    candidate_rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        if not _candidate_row_is_clean(row):
            continue
        grouped[str(row.get("sample_id") or "")].append(row)
    return grouped


def _candidate_row_is_clean(row: Mapping[str, Any]) -> bool:
    score_name = row.get("score_name") or row.get("candidate_name") or SCORE_NAME
    if score_name != SCORE_NAME:
        return False
    if (row.get("leakage_status") or row.get("target_leakage_status") or "clean") != "clean":
        return False
    if row.get("forbidden_fields_used"):
        return False
    return _candidate_score(row) is not None and "span_index" in row


def _candidate_score(row: Mapping[str, Any]) -> float | None:
    if "candidate_score" in row:
        return float(row["candidate_score"])
    if "score" in row:
        return float(row["score"])
    return None


def _high_low_candidate_pair(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    if len(rows) < 2:
        return None
    sorted_rows = sorted(rows, key=lambda row: (_candidate_score(row) or 0.0, -int(row["span_index"])))
    low = sorted_rows[0]
    high = sorted_rows[-1]
    if int(low["span_index"]) == int(high["span_index"]):
        return None
    if (_candidate_score(low) or 0.0) == (_candidate_score(high) or 0.0):
        return None
    return high, low


def _selection_key(record: Mapping[str, Any], *, seed: int) -> str:
    sample_id = str(record.get("sample_id") or "")
    task_type = str(record.get("task_type") or "")
    return hashlib.sha256(f"{seed}:{task_type}:{sample_id}".encode("utf-8")).hexdigest()


def _job_from_prefix(
    record: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    retained: Mapping[str, Any],
    condition: str,
    mask_token: str,
) -> dict[str, Any]:
    prefix = build_replay_prefix(
        record,
        span_index=int(target["span_index"]),
        mask_token=mask_token,
    )
    return {
        **prefix,
        "condition": condition,
        "filtering_policy": condition,
        "filtered_span_index": int(target["span_index"]),
        "filtered_candidate_score": float(_candidate_score(target) or 0.0),
        "retained_span_index": int(retained["span_index"]),
        "retained_candidate_score": float(_candidate_score(retained) or 0.0),
    }


def _primary_score(original: Mapping[str, Any], replay_record: Mapping[str, Any]) -> float:
    scored = score_v2_1_answer(
        str(original.get("task_type") or ""),
        str(replay_record.get("final_answer") or ""),
        str(original.get("reference_answer") or ""),
        original.get("aliases") or [],
    )
    return float(scored["primary_score"])


def _advantage_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [float(row.get("advantage", 0.0)) for row in rows]
    return {
        "n": len(values),
        "mean_advantage": float(sum(values) / len(values)) if values else 0.0,
        "nonnegative_pair_fraction": (
            float(sum(1 for value in values if value >= 0.0) / len(values)) if values else 0.0
        ),
    }


__all__ = [
    "DEFAULT_BUDGET_USD",
    "DEFAULT_MAX_API_REQUESTS",
    "MASK_HIGH_ANTI_FILTER",
    "MASK_LOW_RETAIN_HIGH",
    "V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_FILTERING_SIGNAL",
    "V2_1_DOWNSTREAM_FILTERING_MINI_PASS",
    "V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY",
    "V2_1DownstreamFilteringError",
    "build_candidate_scores_for_records",
    "build_downstream_filtering_preregistration",
    "build_downstream_filtering_report",
    "build_filtering_replay_jobs",
    "markdown_for_preregistration",
    "markdown_for_report",
    "select_filtering_samples",
    "validate_downstream_filtering_readiness",
]
