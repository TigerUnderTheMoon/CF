"""Manifest-only contract utilities for the s_FMA_v2.1 fresh-holdout route."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .baselines import question_difficulty_proxy
from .fresh_holdout import (
    BLOCKED_INSUFFICIENT_FRESH_ROWS,
    MANIFEST_OVERLAP_CLEAN,
    alias_hash,
    build_current_pilot_overlap_index,
    dataset_config_split_source_index,
    has_non_empty_aliases,
    normalized_text_hash,
    row_overlap_keys,
)
from .metrics import alias_match, exact_match, normalized_token_f1, score_answer


V2_1_CONTRACT_CLEAN = "V2_1_CONTRACT_CLEAN"
V2_1_CONTRACT_BLOCKED = "V2_1_CONTRACT_BLOCKED"
OVERLAP_AUDIT_FAIL = "OVERLAP_AUDIT_FAIL"
V2_1_API_PREFLIGHT_ONLY = "V2_1_API_PREFLIGHT_ONLY"

V2_1_REQUIRED_NON_OVERLAP_KEYS = (
    "sample_id",
    "task_id",
    "dataset_config_split_source_index",
    "normalized_question_hash",
    "reference_answer_hash",
    "alias_hash",
)

V2_1_MANIFEST_FIELDS = (
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
    "target_name",
    "primary_score_field",
    "selection_seed",
    "selection_policy",
    "prompt_version",
    "manifest_item_hash",
)

V2_1_FORBIDDEN_SELECTION_FIELDS = {
    "correctness",
    "original_score",
    "intervened_score",
    "delta_u",
    "replay_outcome",
    "final_answer",
    "reference_answer_similarity_after_generation",
    "rank_signal",
    "target_outcome",
}

V2_1_NON_VERIFICATION_TYPES = {
    "error_diagnosis",
    "plan_revision",
    "self-evaluation",
    "uncertainty_monitoring",
}


def score_v2_1_answer(
    task_type: str,
    prediction: str,
    reference: str,
    aliases: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return the preregistered v2.1 primary target score for a task."""

    if task_type == "hotpotqa":
        raw_exact = exact_match(prediction, reference, task_type=task_type)
        alias_aware_exact = raw_exact or alias_match(prediction, aliases)
        token_f1 = normalized_token_f1(prediction, reference)
        return {
            "task_type": task_type,
            "primary_score_field": "normalized_token_f1",
            "primary_score": token_f1,
            "normalized_token_f1": token_f1,
            "exact_match": raw_exact,
            "alias_aware_exact_match": bool(alias_aware_exact),
        }
    if task_type == "gsm8k":
        scored = score_answer(task_type, prediction, reference, aliases)
        return {
            "task_type": task_type,
            "primary_score_field": "exact_match_numeric",
            "primary_score": float(scored["score"]),
            "exact_match": bool(scored["exact_match"]),
            "normalized_token_f1": float(scored["normalized_token_f1"]),
        }
    raise ValueError(f"unsupported v2.1 task_type: {task_type}")


def build_v2_1_fresh_holdout_manifest(
    source_rows_by_task: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    config: Mapping[str, Any],
    overlap_sources: Mapping[str, Iterable[Mapping[str, Any]]],
    prompt_version: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the v2.1 fresh manifest and six-key hard overlap audit.

    This function performs no API calls, replay, scoring run, trace generation,
    or claim upgrade. It only locks candidate rows and reports whether the
    manifest is clean enough to request a future API preflight approval.
    """

    overlap_index = build_current_pilot_overlap_index(overlap_sources)
    seed = int(config.get("experiment", {}).get("seed", 0))
    target_name = str(config.get("target_policy", {}).get("target_name") or "graded_delta_u_v2_1")
    tasks_config = config.get("fresh_selection_policy", {}).get("tasks", {})

    selected_by_task: dict[str, list[dict[str, Any]]] = {}
    task_reports: dict[str, dict[str, Any]] = {}
    overlap_counts = {key: 0 for key in V2_1_REQUIRED_NON_OVERLAP_KEYS}
    selected_overlap_counts = {key: 0 for key in V2_1_REQUIRED_NON_OVERLAP_KEYS}
    overlap_examples: dict[str, list[dict[str, Any]]] = {
        key: [] for key in V2_1_REQUIRED_NON_OVERLAP_KEYS
    }

    for task_type in sorted(tasks_config):
        task_config = tasks_config[task_type]
        candidates = [
            _candidate_manifest_item(
                row,
                task_type=task_type,
                task_config=task_config,
                config=config,
                seed=seed,
                target_name=target_name,
                prompt_version=prompt_version,
            )
            for row in source_rows_by_task.get(task_type, [])
        ]
        empty_alias_candidate_count = sum(
            1 for item in candidates if not has_non_empty_aliases(item.get("aliases"))
        )
        non_empty_alias_candidate_count = len(candidates) - empty_alias_candidate_count

        eligible: list[dict[str, Any]] = []
        excluded = 0
        for item in candidates:
            overlaps = _overlaps_for_item(item, overlap_index)
            if overlaps:
                excluded += 1
                for key, source_hits in overlaps.items():
                    overlap_counts[key] += 1
                    if len(overlap_examples[key]) < 10:
                        overlap_examples[key].append(_overlap_example(item, key, source_hits))
                continue
            eligible.append(item)

        ordered = sort_v2_1_eligible_items(task_type, eligible)
        sample_count = int(task_config.get("sample_count", 0))
        selected = ordered[:sample_count]
        selected_by_task[task_type] = selected
        for item in selected:
            for key in _overlaps_for_item(item, overlap_index):
                selected_overlap_counts[key] += 1

        task_status = MANIFEST_OVERLAP_CLEAN
        if len(eligible) < sample_count:
            task_status = BLOCKED_INSUFFICIENT_FRESH_ROWS
        elif any(selected_overlap_counts.values()):
            task_status = OVERLAP_AUDIT_FAIL

        difficulty_scores = [
            float(item.get("question_difficulty_proxy", {}).get("score", 0.0))
            for item in eligible
            if task_type == "gsm8k"
        ]
        task_reports[task_type] = {
            "dataset": str(task_config.get("dataset") or ""),
            "config": str(task_config.get("config") or ""),
            "split": str(task_config.get("split") or ""),
            "configured_sample_count": sample_count,
            "source_row_count": len(candidates),
            "empty_alias_candidate_count": empty_alias_candidate_count,
            "non_empty_alias_candidate_count": non_empty_alias_candidate_count,
            "excluded_overlap_count": excluded,
            "eligible_count": len(eligible),
            "selected_count": len(selected),
            "selection_policy": _selection_policy(task_type, task_config),
            "difficulty_proxy_min": min(difficulty_scores) if difficulty_scores else None,
            "difficulty_proxy_max": max(difficulty_scores) if difficulty_scores else None,
            "status": task_status,
        }

    insufficient_tasks = [
        task
        for task, report in task_reports.items()
        if report["status"] == BLOCKED_INSUFFICIENT_FRESH_ROWS
    ]
    selected_overlap = any(selected_overlap_counts.values())
    if insufficient_tasks:
        status = BLOCKED_INSUFFICIENT_FRESH_ROWS
        manifest: list[dict[str, Any]] = []
    elif selected_overlap:
        status = OVERLAP_AUDIT_FAIL
        manifest = []
    else:
        status = MANIFEST_OVERLAP_CLEAN
        manifest = []
        for task_type in sorted(selected_by_task):
            manifest.extend(_finalize_manifest_item(item) for item in selected_by_task[task_type])

    audit = {
        "status": status,
        "overlap_clean": status == MANIFEST_OVERLAP_CLEAN,
        "hard_stop": status != MANIFEST_OVERLAP_CLEAN,
        "blocker": status if status != MANIFEST_OVERLAP_CLEAN else None,
        "hard_stop_policy": "any selected-row overlap or insufficient fresh rows stops before API, scoring, replay, trace generation, or reporting",
        "current_status_remains": "PILOT_BLOCKED",
        "s_fma_v2_1_status": "planned-only",
        "no_api_run": True,
        "no_v2_1_scoring": True,
        "no_replay": True,
        "no_traces_generated": True,
        "no_prm_claim_yet": True,
        "claim_upgrade_allowed": False,
        "next_allowed_step": (
            "V2_1_API_PREFLIGHT_APPROVAL_REQUEST_ONLY"
            if status == MANIFEST_OVERLAP_CLEAN
            else "PREREGISTER_ALTERNATE_SPLIT_DATASET_OR_SOURCE"
        ),
        "api_preflight_approval_request_only": status == MANIFEST_OVERLAP_CLEAN,
        "api_execution_allowed": False,
        "target_policy": {
            "target_name": target_name,
            "hotpotqa_primary_score_field": _primary_score_field(config, "hotpotqa"),
            "gsm8k_primary_score_field": _primary_score_field(config, "gsm8k"),
        },
        "selection_policy": {
            "gsm8k": "rank_fresh_candidates_by_question_difficulty_proxy_desc",
            "hotpotqa": "deterministic_non_overlapping_manifest_order",
            "forbidden_selection_fields": sorted(V2_1_FORBIDDEN_SELECTION_FIELDS),
        },
        "alias_policy": {
            "empty_alias_set_blocking": False,
            "non_empty_alias_hash_blocking": True,
        },
        "required_non_overlap_keys": list(V2_1_REQUIRED_NON_OVERLAP_KEYS),
        "fresh_manifest_fields": list(V2_1_MANIFEST_FIELDS),
        "selection_seed": seed,
        "prompt_version": prompt_version,
        "manifest_rows": len(manifest),
        "tasks": task_reports,
        "overlap_sources": overlap_index["source_reports"],
        "overlap_summary": {
            "candidate_pool_overlaps_by_key": overlap_counts,
            "selected_overlaps_by_key": selected_overlap_counts,
            "total_overlaps_by_key": overlap_counts,
        },
        "overlap_examples": overlap_examples,
    }
    return manifest, audit


def sort_v2_1_eligible_items(
    task_type: str,
    items: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Sort eligible v2.1 candidates by the preregistered task policy."""

    rows = [dict(item) for item in items]
    if task_type == "gsm8k":
        return sorted(
            rows,
            key=lambda item: (
                -float(item.get("question_difficulty_proxy", {}).get("score", 0.0)),
                str(item.get("manifest_item_hash") or ""),
                int(item.get("source_index", 0)),
            ),
        )
    return sorted(
        rows,
        key=lambda item: (
            int(item.get("source_index", 0)),
            str(item.get("manifest_item_hash") or ""),
        ),
    )


def build_v2_1_contract_audit(
    *,
    config: Mapping[str, Any],
    plan_text: str,
    prompt_text: str,
    prompt_version: str,
    manifest_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit the non-API v2.1 target, selection, prompt, and gate contracts."""

    checks = {
        "no_api_boundary": _check_no_api_boundary(config),
        "hotpotqa_primary_target": _check_hotpotqa_target(config),
        "gsm8k_selection_policy": _check_gsm8k_selection(config),
        "selection_leakage_policy": _check_selection_leakage_policy(config),
        "prompt_policy": _check_prompt_policy(config, prompt_text, prompt_version),
        "span_diversity_policy": _check_span_diversity_policy(config),
        "smoke_gate": _check_smoke_gate(config),
        "claim_policy": _check_claim_policy(config),
        "plan_boundary": _check_plan_boundary(plan_text),
    }
    if manifest_audit is not None:
        checks["manifest_overlap_audit"] = _status_check(
            bool(manifest_audit.get("overlap_clean"))
            and manifest_audit.get("status") == MANIFEST_OVERLAP_CLEAN,
            {"manifest_status": manifest_audit.get("status")},
        )

    blockers = [name for name, check in checks.items() if check["status"] != "clean"]
    status = V2_1_CONTRACT_CLEAN if not blockers else V2_1_CONTRACT_BLOCKED
    return {
        "status": status,
        "current_status_remains": "PILOT_BLOCKED",
        "s_fma_v2_1_status": "planned-only",
        "no_api_run": True,
        "no_v2_1_scoring": True,
        "no_replay": True,
        "no_traces_generated": True,
        "no_prm_claim_yet": True,
        "claim_upgrade_allowed": False,
        "api_execution_allowed": False,
        "next_allowed_step": (
            "V2_1_API_PREFLIGHT_APPROVAL_REQUEST_ONLY"
            if status == V2_1_CONTRACT_CLEAN
            and (manifest_audit is None or manifest_audit.get("status") == MANIFEST_OVERLAP_CLEAN)
            else "REPAIR_V2_1_NON_API_CONTRACT"
        ),
        "prompt_version": prompt_version,
        "checks": checks,
        "blockers": blockers,
    }


def build_v2_1_api_preflight_approval_request(
    *,
    config: Mapping[str, Any],
    manifest_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    prompt_version: str,
    output_root: str | Path,
) -> dict[str, Any]:
    """Build a request-only v2.1 API preflight approval package.

    This request is intentionally not an approval and performs no API work.
    It records the prompt lock that a future preflight runner must verify
    before any live call.
    """

    output_path = Path(output_root)
    prompt_file = str(
        config.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        )
    )
    records_per_task = {"gsm8k": 10, "hotpotqa": 10}
    request_valid_for_review = (
        manifest_audit.get("status") == MANIFEST_OVERLAP_CLEAN
        and manifest_audit.get("overlap_clean") is True
        and contract_audit.get("status") == V2_1_CONTRACT_CLEAN
        and contract_audit.get("prompt_version") == prompt_version
    )
    selected_overlaps = dict(
        manifest_audit.get("overlap_summary", {}).get("selected_overlaps_by_key", {})
    )
    return {
        "requested_scope": V2_1_API_PREFLIGHT_ONLY,
        "approval_status": "REQUEST_ONLY_NOT_APPROVED",
        "request_valid_for_review": request_valid_for_review,
        "api_execution_authorized_by_this_request": False,
        "api_execution_performed_by_package_regeneration": False,
        "current_status_remains": "PILOT_BLOCKED",
        "requested_records": sum(records_per_task.values()),
        "records_per_task": records_per_task,
        "recommended_budget_ceiling_usd": 2,
        "max_api_requests": 25,
        "prompt_file": prompt_file,
        "prompt_version": prompt_version,
        "prompt_lock_status": "CURRENT_PACKAGE_PROMPT_LOCK",
        "model_config_source": "configs/s_fma_v2_1_fresh_holdout.yaml",
        "manifest_source": str(output_path / "fresh_manifest.json"),
        "supporting_audits": {
            "manifest_overlap_audit": str(output_path / "manifest_overlap_audit.json"),
            "v2_1_contract_audit": str(output_path / "v2_1_contract_audit.json"),
        },
        "supporting_audit_status": {
            "manifest_overlap_audit": manifest_audit.get("status"),
            "selected_overlaps_by_key": selected_overlaps,
            "v2_1_contract_audit": contract_audit.get("status"),
        },
        "historical_preflight_provenance_not_rewritten": [
            str(output_path / "api_preflight_report.json"),
            str(output_path / "api_preflight_attempts.jsonl"),
            str(output_path / "api_preflight_traces.jsonl"),
            str(output_path / "logs" / "api_preflight_cost_report.json"),
        ],
        "regenerated_package_artifacts": [
            str(output_path / "fresh_manifest.json"),
            str(output_path / "manifest_overlap_audit.json"),
            str(output_path / "manifest_overlap_audit.md"),
            str(output_path / "v2_1_contract_audit.json"),
            str(output_path / "v2_1_contract_audit.md"),
            str(output_path / "api_preflight_approval_request.json"),
            str(output_path / "api_preflight_approval_request.md"),
        ],
        "required_pre_run_checks": [
            {
                "check": "v2.1 manifest rows",
                "required_value": 400,
                "evidence": str(output_path / "fresh_manifest.json"),
            },
            {
                "check": "manifest_overlap_audit.status",
                "required_value": MANIFEST_OVERLAP_CLEAN,
                "evidence": str(output_path / "manifest_overlap_audit.json"),
            },
            {
                "check": "selected overlaps all zero",
                "required_value": {
                    "sample_id": 0,
                    "task_id": 0,
                    "dataset_config_split_source_index": 0,
                    "normalized_question_hash": 0,
                    "reference_answer_hash": 0,
                    "alias_hash": 0,
                },
                "evidence": str(output_path / "manifest_overlap_audit.json"),
            },
            {
                "check": "v2_1_contract_audit.status",
                "required_value": V2_1_CONTRACT_CLEAN,
                "evidence": str(output_path / "v2_1_contract_audit.json"),
            },
            {
                "check": "prompt hash lock",
                "required_value": prompt_version,
                "evidence": prompt_file,
            },
            {
                "check": "tests pass",
                "required_value": "python -m pytest -q exits 0 before any approved API execution",
                "evidence": "local verification command",
            },
        ],
        "allowed_outputs_after_future_approval": [
            "api_preflight_report.json",
            "api_preflight_attempts.jsonl",
            "api_preflight_traces.jsonl",
            "logs/api_preflight_cost_report.json",
        ],
        "forbidden_in_this_approval_request": [
            "smoke",
            "replay",
            "full generation",
            "v2.1 scoring",
            "task/global pass claim",
            "PRM/filtering",
            "deterministic replay claim",
            "submission-ready claim",
        ],
        "forbidden_without_separate_future_approval": [
            "API execution",
            "trace generation beyond the API preflight outputs listed above",
            "replay",
            "v2.1 scoring",
            "full validation",
            "task/global pass wording",
            "PRM/filtering design or claim",
        ],
        "only_allowed_next_step_after_user_approval": (
            "Run V2_1_API_PREFLIGHT_ONLY for 20 records, 10 gsm8k and 10 hotpotqa, "
            "with max_api_requests 25 and recommended_budget_ceiling_usd 2, producing "
            "only the allowed API preflight outputs."
        ),
        "next_allowed_step_without_user_approval": "USER_REVIEW_APPROVAL_REQUEST_ONLY",
        "claim_boundary": {
            "no_validation_claim": True,
            "no_pass_claim": True,
            "no_prm_claim": True,
            "current_status_remains": "PILOT_BLOCKED",
        },
    }


def render_v2_1_overlap_audit_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# s_FMA_v2.1 Fresh-Holdout Manifest Overlap Audit",
        "",
        f"Status: `{audit['status']}`",
        f"Overlap clean: `{str(audit['overlap_clean']).lower()}`",
        f"Hard stop: `{str(audit['hard_stop']).lower()}`",
        "",
        "## Execution Boundary",
        "",
        "- Manifest generation and overlap audit only.",
        "- No API run.",
        "- No v2.1 scoring.",
        "- No replay.",
        "- No traces generated.",
        "- No PRM/filtering claim.",
        "- Current status remains `PILOT_BLOCKED`.",
        "- `s_FMA_v2.1` remains planned-only.",
        f"- Next allowed step: `{audit.get('next_allowed_step')}`.",
        "",
        "## Target And Selection Contract",
        "",
        "- HotpotQA primary target: `normalized_token_f1`.",
        "- GSM8K primary target: numeric exact match; unsaturated selection uses `question_difficulty_proxy` only before outcomes.",
        "- Empty alias sets are non-informative; non-empty `alias_hash` remains blocking.",
        "",
        "## Task Status",
        "",
        "| Task | Source rows | Eligible fresh rows | Required rows | Selected rows | Selection policy | Status |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for task_type, report in sorted(audit["tasks"].items()):
        lines.append(
            "| {task} | {source} | {eligible} | {required} | {selected} | `{policy}` | `{status}` |".format(
                task=task_type,
                source=report["source_row_count"],
                eligible=report["eligible_count"],
                required=report["configured_sample_count"],
                selected=report["selected_count"],
                policy=report["selection_policy"],
                status=report["status"],
            )
        )
    lines.extend(
        [
            "",
            "## Required Non-Overlap Keys",
            "",
            "| Key | Candidate pool overlaps | Selected manifest overlaps |",
            "|---|---:|---:|",
        ]
    )
    overlap_summary = audit["overlap_summary"]
    for key in audit["required_non_overlap_keys"]:
        lines.append(
            "| {key} | {candidate} | {selected} |".format(
                key=key,
                candidate=overlap_summary["candidate_pool_overlaps_by_key"][key],
                selected=overlap_summary["selected_overlaps_by_key"][key],
            )
        )
    lines.extend(["", "## Overlap Sources", "", "| Source | Rows loaded |", "|---|---:|"])
    for source, report in sorted(audit["overlap_sources"].items()):
        lines.append(f"| `{source}` | {report['rows_loaded']} |")
    lines.extend(["", "## Decision", ""])
    if audit["status"] == MANIFEST_OVERLAP_CLEAN:
        lines.append(
            "The v2.1 manifest is clean. The only allowed next step is generating a bounded API preflight approval request; API execution, scoring, replay, trace generation, and PRM/filtering remain forbidden."
        )
    elif audit["status"] == BLOCKED_INSUFFICIENT_FRESH_ROWS:
        lines.append(
            "The v2.1 manifest is blocked by insufficient fresh rows after applying the required overlap keys."
        )
    else:
        lines.append("The v2.1 manifest is blocked by selected-row overlap.")
    lines.append("")
    return "\n".join(lines)


def render_v2_1_contract_audit_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# s_FMA_v2.1 Non-API Contract Audit",
        "",
        f"Status: `{audit['status']}`",
        f"Current status remains: `{audit['current_status_remains']}`",
        f"Claim upgrade allowed: `{str(audit['claim_upgrade_allowed']).lower()}`",
        "",
        "## Execution Boundary",
        "",
        "- No API run.",
        "- No v2.1 scoring.",
        "- No replay.",
        "- No traces generated.",
        "- No PRM/filtering claim.",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "|---|---|",
    ]
    for name, check in audit["checks"].items():
        lines.append(f"| `{name}` | `{check['status']}` |")
    lines.extend(["", "## Blockers", ""])
    if audit["blockers"]:
        for blocker in audit["blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- None at the non-API contract layer.")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"Next allowed step: `{audit.get('next_allowed_step')}`.",
            "This is not an API approval and not a validation/pass claim.",
            "",
        ]
    )
    return "\n".join(lines)


def render_v2_1_api_preflight_approval_request_markdown(request: Mapping[str, Any]) -> str:
    selected_overlaps = request.get("supporting_audit_status", {}).get(
        "selected_overlaps_by_key", {}
    )
    lines = [
        "# s_FMA_v2.1 API Preflight Approval Request",
        "",
        "This is a request only. It does not authorize or execute API calls.",
        "",
        "## Scope",
        "",
        f"- `requested_scope`: `{request['requested_scope']}`",
        f"- `approval_status`: `{request['approval_status']}`",
        f"- `request_valid_for_review`: `{str(request['request_valid_for_review']).lower()}`",
        f"- `api_execution_authorized_by_this_request`: `{str(request['api_execution_authorized_by_this_request']).lower()}`",
        f"- `current_status_remains`: `{request['current_status_remains']}`",
        f"- `requested_records`: `{request['requested_records']}`",
        f"- `records_per_task`: `{json.dumps(request['records_per_task'], sort_keys=True)}`",
        f"- `max_api_requests`: `{request['max_api_requests']}`",
        f"- `recommended_budget_ceiling_usd`: `{request['recommended_budget_ceiling_usd']}`",
        f"- `prompt_version`: `{request['prompt_version']}`",
        "",
        "## Required Checks",
        "",
        "| Check | Required value | Evidence |",
        "|---|---|---|",
    ]
    for check in request["required_pre_run_checks"]:
        lines.append(
            "| {check} | `{required}` | `{evidence}` |".format(
                check=check["check"],
                required=json.dumps(check["required_value"], sort_keys=True)
                if isinstance(check["required_value"], dict)
                else check["required_value"],
                evidence=check["evidence"],
            )
        )
    lines.extend(
        [
            "",
            "## Selected Overlaps",
            "",
            "| Key | Selected overlaps |",
            "|---|---:|",
        ]
    )
    for key, value in sorted(selected_overlaps.items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## Historical Provenance Not Rewritten",
            "",
        ]
    )
    for path in request["historical_preflight_provenance_not_rewritten"]:
        lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "## Forbidden",
            "",
        ]
    )
    for item in request["forbidden_in_this_approval_request"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- No validation claim.",
            "- No pass claim.",
            "- No PRM/filtering claim.",
            "- Current status remains `PILOT_BLOCKED`.",
            "",
            "## Next Step",
            "",
            request["only_allowed_next_step_after_user_approval"],
            "",
        ]
    )
    return "\n".join(lines)


def write_v2_1_outputs(
    *,
    manifest: list[dict[str, Any]],
    manifest_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    approval_request: Mapping[str, Any] | None = None,
    output_root: str | Path,
) -> None:
    output_path = Path(output_root)
    _write_json(output_path / "fresh_manifest.json", manifest)
    _write_json(output_path / "manifest_overlap_audit.json", manifest_audit)
    (output_path / "manifest_overlap_audit.md").write_text(
        render_v2_1_overlap_audit_markdown(manifest_audit),
        encoding="utf-8",
    )
    _write_json(output_path / "v2_1_contract_audit.json", contract_audit)
    (output_path / "v2_1_contract_audit.md").write_text(
        render_v2_1_contract_audit_markdown(contract_audit),
        encoding="utf-8",
    )
    if approval_request is not None:
        _write_json(output_path / "api_preflight_approval_request.json", approval_request)
        (output_path / "api_preflight_approval_request.md").write_text(
            render_v2_1_api_preflight_approval_request_markdown(approval_request),
            encoding="utf-8",
        )


def _candidate_manifest_item(
    row: Mapping[str, Any],
    *,
    task_type: str,
    task_config: Mapping[str, Any],
    config: Mapping[str, Any],
    seed: int,
    target_name: str,
    prompt_version: str,
) -> dict[str, Any]:
    source_index = int(row.get("source_index", 0))
    question = str(row.get("question") or "")
    reference_answer = str(row.get("reference_answer") or row.get("answer") or "")
    aliases = _normalized_aliases(row.get("aliases"))
    dataset = str(task_config.get("dataset") or row.get("source_dataset") or task_type)
    dataset_config = str(task_config.get("config") or row.get("source_config") or "")
    split = str(task_config.get("split") or row.get("source_split") or "")
    sample_id = f"{task_type}-{source_index:05d}"
    task_id = str(row.get("task_id") or row.get("id") or row.get("_id") or sample_id)
    selection_policy = _selection_policy(task_type, task_config)
    source_fields_used = sorted(
        {
            "aliases",
            "question",
            "reference_answer",
            "source_config",
            "source_dataset",
            "source_index",
            "source_split",
            "task_id",
            "task_type",
        }
    )
    item: dict[str, Any] = {
        "dataset": dataset,
        "config": dataset_config,
        "split": split,
        "source_index": source_index,
        "sample_id": sample_id,
        "task_id": task_id,
        "question": question,
        "reference_answer": reference_answer,
        "aliases": list(aliases),
        "task_type": task_type,
        "target_name": target_name,
        "primary_score_field": _primary_score_field(config, task_type),
        "selection_seed": seed,
        "selection_policy": selection_policy,
        "prompt_version": prompt_version,
        "selection_source_fields_used": source_fields_used,
        "forbidden_selection_fields_used": sorted(
            set(source_fields_used).intersection(V2_1_FORBIDDEN_SELECTION_FIELDS)
        ),
    }
    if task_type == "gsm8k":
        difficulty = question_difficulty_proxy(row)
        item["question_difficulty_proxy"] = difficulty
        item["selection_source_fields_used"] = sorted(
            set(source_fields_used).union(difficulty["source_fields_used"])
        )
        item["forbidden_selection_fields_used"] = sorted(
            set(item["selection_source_fields_used"]).intersection(V2_1_FORBIDDEN_SELECTION_FIELDS)
        )
    item["dataset_config_split_source_index"] = dataset_config_split_source_index(item)
    item["normalized_question_hash"] = normalized_text_hash(question)
    item["reference_answer_hash"] = normalized_text_hash(reference_answer)
    item["alias_hash"] = alias_hash(aliases)
    item["manifest_item_hash"] = _manifest_item_hash(item)
    return item


def _finalize_manifest_item(item: Mapping[str, Any]) -> dict[str, Any]:
    finalized = dict(item)
    finalized["manifest_item_hash"] = _manifest_item_hash(
        {key: value for key, value in finalized.items() if key != "manifest_item_hash"}
    )
    return finalized


def _overlaps_for_item(
    item: Mapping[str, Any],
    overlap_index: Mapping[str, Any],
) -> dict[str, list[str]]:
    index = overlap_index["index"]
    item_keys = row_overlap_keys(item)
    overlaps: dict[str, list[str]] = {}
    for key, value in item_keys.items():
        audit_key = "alias_hash" if key == "alias_hash" else key
        if audit_key in index and value in index[audit_key]:
            overlaps[audit_key] = sorted(index[audit_key][value])[:10]
    return overlaps


def _overlap_example(item: Mapping[str, Any], key: str, source_hits: list[str]) -> dict[str, Any]:
    return {
        "candidate_sample_id": item.get("sample_id"),
        "candidate_task_id": item.get("task_id"),
        "candidate_task_type": item.get("task_type"),
        "candidate_source_index": item.get("source_index"),
        "key": key,
        "key_value": item.get(key),
        "source_hits": source_hits[:5],
    }


def _selection_policy(task_type: str, task_config: Mapping[str, Any]) -> str:
    if task_type == "gsm8k":
        return str(
            task_config.get("unsaturated_selection", {}).get(
                "policy", "rank_fresh_candidates_by_question_difficulty_proxy_desc"
            )
        )
    return str(task_config.get("selection_policy") or "deterministic_non_overlapping_manifest_order")


def _primary_score_field(config: Mapping[str, Any], task_type: str) -> str:
    return str(
        config.get("target_policy", {})
        .get("task_targets", {})
        .get(task_type, {})
        .get("primary_score_field")
        or ("normalized_token_f1" if task_type == "hotpotqa" else "exact_match_numeric")
    )


def _normalized_aliases(aliases: Any) -> list[str]:
    values = aliases if isinstance(aliases, list) else []
    return sorted(str(value).strip().lower() for value in values if str(value).strip())


def _manifest_item_hash(item: Mapping[str, Any]) -> str:
    payload = json.dumps(item, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _status_check(clean: bool, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"status": "clean" if clean else "blocked", "details": dict(details or {})}


def _check_no_api_boundary(config: Mapping[str, Any]) -> dict[str, Any]:
    experiment = config.get("experiment", {})
    smoke_gate = config.get("smoke_gate", {})
    future = config.get("future_execution_boundary", {})
    required_true = {
        "no_api_execution_without_user_approval": experiment.get("no_api_execution_without_user_approval"),
        "no_api_run_in_current_task": experiment.get("no_api_run_in_current_task"),
        "no_full_api_generation_in_current_task": experiment.get("no_full_api_generation_in_current_task"),
        "no_v2_scoring_in_current_task": experiment.get("no_v2_scoring_in_current_task"),
        "no_replay_in_current_task": experiment.get("no_replay_in_current_task"),
        "smoke_gate_requires_explicit_budget_approval": smoke_gate.get("requires_explicit_budget_approval"),
    }
    required_false = {
        "smoke_gate_api_authorized_by_this_config": smoke_gate.get("api_authorized_by_this_config"),
        "future_api_calls_authorized": future.get("api_calls_authorized"),
    }
    clean = (
        all(value is True for value in required_true.values())
        and all(value is False for value in required_false.values())
        and experiment.get("user_approved_budget_usd") is None
    )
    return _status_check(clean, {"required_true": required_true, "required_false": required_false})


def _check_hotpotqa_target(config: Mapping[str, Any]) -> dict[str, Any]:
    target = config.get("target_policy", {}).get("task_targets", {}).get("hotpotqa", {})
    clean = (
        target.get("primary_score_field") == "normalized_token_f1"
        and target.get("llm_judge_allowed") is False
    )
    return _status_check(clean, target)


def _check_gsm8k_selection(config: Mapping[str, Any]) -> dict[str, Any]:
    task = config.get("fresh_selection_policy", {}).get("tasks", {}).get("gsm8k", {})
    selection = task.get("unsaturated_selection", {})
    clean = (
        selection.get("policy") == "rank_fresh_candidates_by_question_difficulty_proxy_desc"
        and selection.get("proxy_helper") == "fma.real_task_pilot.baselines.question_difficulty_proxy"
        and selection.get("tie_breakers") == ["manifest_item_hash", "source_index"]
        and selection.get("target_outcomes_allowed_for_selection") is False
    )
    return _status_check(clean, selection)


def _check_selection_leakage_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = config.get("fresh_selection_policy", {})
    configured_forbidden = set(policy.get("forbidden_selection_fields", []))
    tasks = policy.get("tasks", {})
    task_target_flags = [
        _target_outcomes_forbidden(task)
        for task in tasks.values()
    ]
    clean = (
        policy.get("non_overlap_required") is True
        and V2_1_FORBIDDEN_SELECTION_FIELDS.issubset(configured_forbidden)
        and all(task_target_flags)
    )
    return _status_check(
        clean,
        {
            "configured_forbidden_selection_fields": sorted(configured_forbidden),
            "required_forbidden_selection_fields": sorted(V2_1_FORBIDDEN_SELECTION_FIELDS),
            "target_outcomes_allowed_for_selection_all_false": all(task_target_flags),
        },
    )


def _target_outcomes_forbidden(task_config: Mapping[str, Any]) -> bool:
    if task_config.get("target_outcomes_allowed_for_selection") is False:
        return True
    nested = task_config.get("unsaturated_selection", {})
    return isinstance(nested, Mapping) and nested.get("target_outcomes_allowed_for_selection") is False


def _check_prompt_policy(
    config: Mapping[str, Any],
    prompt_text: str,
    prompt_version: str,
) -> dict[str, Any]:
    policy = config.get("span_diversity_policy", {})
    requirements = policy.get("future_prompt_requirements", {})
    lower_prompt = prompt_text.lower()
    has_verification = '<reflection type="verification">' in lower_prompt
    has_non_verification = any(
        f'<reflection type="{operation_type}">' in lower_prompt
        for operation_type in V2_1_NON_VERIFICATION_TYPES
    )
    clean = (
        policy.get("prompt_snapshot_required") is True
        and policy.get("prompt_version_lock_required") is True
        and bool(prompt_version)
        and requirements.get("visible_text_only") is True
        and requirements.get("hidden_reasoning_forbidden") is True
        and requirements.get("reflection_blocks_requested") == 2
        and has_verification
        and has_non_verification
        and "hidden reasoning" in lower_prompt
    )
    return _status_check(
        clean,
        {
            "prompt_version": prompt_version,
            "has_verification_block": has_verification,
            "has_non_verification_block": has_non_verification,
            "reflection_blocks_requested": requirements.get("reflection_blocks_requested"),
        },
    )


def _check_span_diversity_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = config.get("span_diversity_policy", {})
    target = policy.get("target_span_policy", {})
    reporting = policy.get("reporting", {})
    configured_non_verification = set(target.get("eligible_non_verification_types", []))
    clean = (
        target.get("max_target_spans_per_trace") == 2
        and target.get("include_first_verification_span") is True
        and target.get("include_first_non_verification_span") is True
        and V2_1_NON_VERIFICATION_TYPES.issubset(configured_non_verification)
        and reporting.get("report_operation_type_distribution") is True
        and reporting.get("report_non_verification_span_count_by_task") is True
        and reporting.get("keep_trajectory_controls_separate_from_span_attribution") is True
    )
    return _status_check(
        clean,
        {
            "max_target_spans_per_trace": target.get("max_target_spans_per_trace"),
            "eligible_non_verification_types": sorted(configured_non_verification),
        },
    )


def _check_smoke_gate(config: Mapping[str, Any]) -> dict[str, Any]:
    smoke = config.get("smoke_gate", {})
    clean = (
        smoke.get("api_authorized_by_this_config") is False
        and smoke.get("requires_explicit_budget_approval") is True
        and smoke.get("sample_count_by_task", {}).get("gsm8k") == 10
        and smoke.get("sample_count_by_task", {}).get("hotpotqa") == 10
        and smoke.get("min_nonzero_delta_u_per_task") == 1
        and smoke.get("min_nonzero_delta_u_pooled") == 3
    )
    return _status_check(
        clean,
        {
            "sample_count_by_task": smoke.get("sample_count_by_task"),
            "min_nonzero_delta_u_per_task": smoke.get("min_nonzero_delta_u_per_task"),
            "min_nonzero_delta_u_pooled": smoke.get("min_nonzero_delta_u_pooled"),
        },
    )


def _check_claim_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    current = set(config.get("claim_policy", {}).get("current_status_must_remain", []))
    required = {
        "PILOT_BLOCKED",
        "v2_1_planned_only",
        "no_api_authorized",
        "no_v2_1_validation",
        "no_prm_claim",
    }
    clean = required.issubset(current)
    return _status_check(clean, {"required_current_status": sorted(required), "configured": sorted(current)})


def _check_plan_boundary(plan_text: str) -> dict[str, Any]:
    required = [
        "PILOT_BLOCKED",
        "normalized_token_f1",
        "question_difficulty_proxy",
    ]
    clean = all(value in plan_text for value in required)
    return _status_check(clean, {"required_plan_terms": required})
