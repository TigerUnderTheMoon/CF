"""Manifest-only utilities for the s_FMA_v2.2 fresh-holdout route."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .fresh_holdout import (
    BLOCKED_INSUFFICIENT_FRESH_ROWS,
    MANIFEST_OVERLAP_CLEAN,
    OVERLAP_AUDIT_FAIL,
    alias_hash,
    build_current_pilot_overlap_index,
    dataset_config_split_source_index,
    has_non_empty_aliases,
    normalized_text_hash,
    row_overlap_keys,
)


S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT = "S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT"
V2_2_CONTRACT_CLEAN = "V2_2_CONTRACT_CLEAN"
V2_2_CONTRACT_BLOCKED = "V2_2_CONTRACT_BLOCKED"

V2_2_REQUIRED_NON_OVERLAP_KEYS = (
    "sample_id",
    "task_id",
    "dataset_config_split_source_index",
    "normalized_question_hash",
    "reference_answer_hash",
    "alias_hash",
)

V2_2_MANIFEST_FIELDS = (
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
    "manifest_item_hash",
)

V2_2_FORBIDDEN_SELECTION_FIELDS = {
    "correctness",
    "original_score",
    "intervened_score",
    "delta_u",
    "replay_outcome",
    "final_answer",
    "reference_answer_similarity_after_generation",
    "rank_signal",
    "target_outcome",
    "v2_1_full_validation_result",
}


def build_v2_2_fresh_holdout_manifest(
    source_rows_by_task: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    config: Mapping[str, Any],
    overlap_sources: Mapping[str, Iterable[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the v2.2 manifest and selected-row non-overlap audit.

    This is a manifest-only operation. It performs no API calls, replay,
    scoring, trace generation, threshold tuning, or PRM/filtering work.
    """

    overlap_index = build_current_pilot_overlap_index(overlap_sources)
    seed = int(config.get("experiment", {}).get("seed", 0))
    target_name = str(
        config.get("utility_target", {}).get("target_name") or "graded_stochastic_delta_u_v2_2"
    )
    tasks_config = config.get("fresh_split_policy", {}).get("tasks", {})

    selected_by_task: dict[str, list[dict[str, Any]]] = {}
    task_reports: dict[str, dict[str, Any]] = {}
    overlap_counts = {key: 0 for key in V2_2_REQUIRED_NON_OVERLAP_KEYS}
    selected_overlap_counts = {key: 0 for key in V2_2_REQUIRED_NON_OVERLAP_KEYS}
    overlap_examples: dict[str, list[dict[str, Any]]] = {
        key: [] for key in V2_2_REQUIRED_NON_OVERLAP_KEYS
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

        ordered = sort_v2_2_eligible_items(eligible)
        sample_count = int(
            task_config.get("planned_sample_count", task_config.get("sample_count", 0))
        )
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
            "selection_policy": str(
                task_config.get("selection_policy") or "deterministic_manifest_order"
            ),
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
        "hard_stop_policy": "any selected-row overlap or insufficient fresh rows stops before API, replay, scoring, validation reporting, or PRM/filtering",
        "current_status_remains": "PILOT_BLOCKED",
        "s_fma_v2_2_status": "manifest-only",
        "task_scope": S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT,
        "no_api_run": True,
        "no_replay": True,
        "no_scoring": True,
        "no_traces_generated": True,
        "no_prm_filtering_claim": True,
        "validation_or_pass_claim_allowed": False,
        "claim_upgrade_allowed": False,
        "api_execution_allowed": False,
        "api_preflight_approval_request_generated": False,
        "next_allowed_step": (
            "V2_2_API_PREFLIGHT_APPROVAL_REQUEST_ONLY"
            if status == MANIFEST_OVERLAP_CLEAN
            else "PREREGISTER_ALTERNATE_SPLIT_DATASET_OR_SOURCE"
        ),
        "v2_1_full_validation_artifacts_used_as": "failed_provenance_and_overlap_exclusion_only",
        "v2_1_full_validation_artifacts_used_as_tuning_source": False,
        "target_policy": {
            "target_name": target_name,
            "gsm8k_primary_score_field": _primary_score_field(config, "gsm8k"),
            "hotpotqa_primary_score_field": _primary_score_field(config, "hotpotqa"),
        },
        "selection_policy": {
            "policy": "deterministic_source_order_after_six_key_non_overlap_exclusion",
            "forbidden_selection_fields": sorted(V2_2_FORBIDDEN_SELECTION_FIELDS),
            "v2_1_full_validation_artifact_tuning_forbidden": True,
        },
        "alias_policy": {
            "empty_alias_set_blocking": False,
            "non_empty_alias_hash_blocking": True,
        },
        "required_non_overlap_keys": list(V2_2_REQUIRED_NON_OVERLAP_KEYS),
        "fresh_manifest_fields": list(V2_2_MANIFEST_FIELDS),
        "selection_seed": seed,
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


def sort_v2_2_eligible_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(item) for item in items),
        key=lambda item: (
            str(item.get("task_type") or ""),
            int(item.get("source_index", 0)),
            str(item.get("manifest_item_hash") or ""),
        ),
    )


def build_v2_2_contract_audit(
    *,
    config: Mapping[str, Any],
    preregistration_plan_text: str,
    transition_audit_text: str,
    failure_audit: Mapping[str, Any],
    manifest_audit: Mapping[str, Any],
    task_scope: str,
    current_submission_ready: bool,
) -> dict[str, Any]:
    """Audit v2.2 manifest-only contract boundaries."""

    checks = {
        "manifest_only_scope": _status_check(
            task_scope == S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT,
            {"task_scope": task_scope},
        ),
        "no_api_replay_scoring_prm_boundary": _check_no_api_replay_scoring_prm_boundary(config),
        "current_status_not_submission_ready": _status_check(
            not current_submission_ready,
            {"current_submission_ready": current_submission_ready},
        ),
        "failed_v2_1_provenance_present": _check_failed_v2_1_provenance(config, failure_audit),
        "v2_1_non_use_policy": _check_v2_1_non_use_policy(config, transition_audit_text),
        "fresh_split_non_overlap_policy": _check_fresh_split_policy(config),
        "utility_target_policy": _check_utility_target_policy(config),
        "schema_transport_policy": _check_schema_transport_policy(config),
        "rank_signal_reporting_policy": _check_rank_signal_policy(config),
        "prompt_lock": _check_prompt_lock(config),
        "claim_policy": _check_claim_policy(config),
        "preregistration_plan_boundary": _check_preregistration_plan(preregistration_plan_text),
        "manifest_overlap_audit": _status_check(
            bool(manifest_audit.get("overlap_clean"))
            and manifest_audit.get("status") == MANIFEST_OVERLAP_CLEAN
            and _selected_overlaps_all_zero(manifest_audit),
            {
                "manifest_status": manifest_audit.get("status"),
                "selected_overlaps_by_key": manifest_audit.get("overlap_summary", {}).get(
                    "selected_overlaps_by_key", {}
                ),
            },
        ),
    }
    blockers = [name for name, check in checks.items() if check["status"] != "clean"]
    status = V2_2_CONTRACT_CLEAN if not blockers else V2_2_CONTRACT_BLOCKED
    prompt_lock = config.get("prompt_lock", {})
    prompt_version = _prompt_bundle_hash(prompt_lock)
    return {
        "status": status,
        "current_status_remains": "PILOT_BLOCKED",
        "s_fma_v2_2_status": "manifest-only",
        "manifest_generation_scope": task_scope,
        "manifest_generation_performed_by_this_task": True,
        "manifest_generation_authorized_by_task_scope": task_scope
        == S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT,
        "manifest_generation_authorized_by_config": bool(
            config.get("fresh_split_policy", {}).get(
                "manifest_generation_authorized_by_this_config"
            )
        ),
        "api_execution_allowed": False,
        "replay_allowed": False,
        "scoring_allowed": False,
        "prm_filtering_allowed": False,
        "validation_or_pass_claim_allowed": False,
        "claim_upgrade_allowed": False,
        "prompt_file": str(prompt_lock.get("generation_prompt_file") or ""),
        "replay_prompt_file": str(prompt_lock.get("replay_prompt_file") or ""),
        "prompt_version": prompt_version,
        "prompt_lock_status": str(prompt_lock.get("prompt_lock_status") or ""),
        "prompt_hash_scope": str(prompt_lock.get("prompt_hash_scope") or ""),
        "v2_1_failed_full_artifacts_used_as_tuning_source": False,
        "v2_1_failed_full_artifacts_used_for_row_selection": False,
        "api_preflight_approval_request_generated": False,
        "next_allowed_step": (
            "V2_2_API_PREFLIGHT_APPROVAL_REQUEST_ONLY"
            if status == V2_2_CONTRACT_CLEAN
            and manifest_audit.get("status") == MANIFEST_OVERLAP_CLEAN
            else "REPAIR_V2_2_MANIFEST_ONLY_CONTRACT"
        ),
        "checks": checks,
        "blockers": blockers,
    }


def render_v2_2_overlap_audit_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# s_FMA_v2.2 Fresh-Holdout Manifest Overlap Audit",
        "",
        f"Status: `{audit['status']}`",
        f"Overlap clean: `{str(audit['overlap_clean']).lower()}`",
        f"Hard stop: `{str(audit['hard_stop']).lower()}`",
        "",
        "## Execution Boundary",
        "",
        "- Fresh manifest generation and non-overlap audit only.",
        "- No API run.",
        "- No replay.",
        "- No scoring.",
        "- No traces generated.",
        "- No PRM/filtering claim.",
        "- No validation or pass claim.",
        "- Current status remains `PILOT_BLOCKED`.",
        f"- Next allowed step: `{audit.get('next_allowed_step')}`.",
        "",
        "## Non-Use Boundary",
        "",
        "- v2.1 full-validation artifacts are failed provenance and overlap-exclusion inputs only.",
        "- v2.1 full-validation artifacts are not tuning, weighting, threshold, or row-selection sources.",
        "",
        "## Task Status",
        "",
        "| Task | Source rows | Empty alias rows | Non-empty alias rows | Eligible fresh rows | Required rows | Selected rows | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for task_type, report in sorted(audit["tasks"].items()):
        lines.append(
            "| {task} | {source} | {empty_alias} | {non_empty_alias} | {eligible} | {required} | {selected} | `{status}` |".format(
                task=task_type,
                source=report["source_row_count"],
                empty_alias=report.get("empty_alias_candidate_count", 0),
                non_empty_alias=report.get("non_empty_alias_candidate_count", 0),
                eligible=report["eligible_count"],
                required=report["configured_sample_count"],
                selected=report["selected_count"],
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
            "The v2.2 manifest is clean at the manifest-only layer. The only allowed next step is a separate API preflight approval request; API execution, replay, scoring, validation/pass claims, and PRM/filtering remain forbidden."
        )
    elif audit["status"] == BLOCKED_INSUFFICIENT_FRESH_ROWS:
        lines.append(
            "The v2.2 manifest is blocked by insufficient fresh rows after the required overlap exclusions."
        )
    else:
        lines.append("The v2.2 manifest is blocked by selected-row overlap.")
    lines.append("")
    return "\n".join(lines)


def render_v2_2_contract_audit_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# s_FMA_v2.2 Manifest-Only Contract Audit",
        "",
        f"Status: `{audit['status']}`",
        f"Current status remains: `{audit['current_status_remains']}`",
        f"Manifest generation scope: `{audit['manifest_generation_scope']}`",
        f"Validation/pass claim allowed: `{str(audit['validation_or_pass_claim_allowed']).lower()}`",
        "",
        "## Execution Boundary",
        "",
        "- No API execution.",
        "- No replay.",
        "- No scoring.",
        "- No PRM/filtering.",
        "- No validation/pass claim.",
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
        lines.append("- None at the manifest-only contract layer.")
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


def write_v2_2_outputs(
    *,
    manifest: list[dict[str, Any]],
    manifest_audit: Mapping[str, Any],
    contract_audit: Mapping[str, Any],
    output_root: str | Path,
) -> None:
    output_path = Path(output_root)
    _write_json(output_path / "fresh_manifest.json", manifest)
    _write_json(output_path / "manifest_overlap_audit.json", manifest_audit)
    (output_path / "manifest_overlap_audit.md").write_text(
        render_v2_2_overlap_audit_markdown(manifest_audit),
        encoding="utf-8",
    )
    _write_json(output_path / "v2_2_contract_audit.json", contract_audit)
    (output_path / "v2_2_contract_audit.md").write_text(
        render_v2_2_contract_audit_markdown(contract_audit),
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
) -> dict[str, Any]:
    source_index = int(row.get("source_index", 0))
    question = str(row.get("question") or "")
    reference_answer = str(row.get("reference_answer") or row.get("answer") or "")
    aliases = _normalized_aliases(row.get("aliases"))
    dataset = str(task_config.get("dataset") or row.get("source_dataset") or task_type)
    dataset_config = str(task_config.get("config") or row.get("source_config") or "")
    split = str(row.get("source_split") or task_config.get("split") or "")
    sample_id = f"{task_type}-{source_index:05d}"
    task_id = str(row.get("task_id") or row.get("id") or row.get("_id") or sample_id)
    selection_source_fields_used = sorted(
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
        "selection_policy": str(
            task_config.get("selection_policy") or "deterministic_manifest_order"
        ),
        "selection_source_fields_used": selection_source_fields_used,
        "forbidden_selection_fields_used": sorted(
            set(selection_source_fields_used).intersection(V2_2_FORBIDDEN_SELECTION_FIELDS)
        ),
        "v2_1_full_validation_tuning_source": False,
        "v2_1_full_validation_row_selection_source": False,
    }
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


def _primary_score_field(config: Mapping[str, Any], task_type: str) -> str:
    return str(
        config.get("utility_target", {})
        .get("tasks", {})
        .get(task_type, {})
        .get("primary_score_field")
        or (
            "normalized_token_f1"
            if task_type == "hotpotqa"
            else "repeated_numeric_success_probability"
        )
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


def _check_no_api_replay_scoring_prm_boundary(config: Mapping[str, Any]) -> dict[str, Any]:
    experiment = config.get("experiment", {})
    future = config.get("future_execution_boundary", {})
    required_true = {
        "no_api_execution_without_user_approval": experiment.get(
            "no_api_execution_without_user_approval"
        ),
        "no_api_run_in_current_task": experiment.get("no_api_run_in_current_task"),
        "no_full_api_generation_in_current_task": experiment.get(
            "no_full_api_generation_in_current_task"
        ),
        "no_replay_in_current_task": experiment.get("no_replay_in_current_task"),
        "no_scoring_in_current_task": experiment.get("no_scoring_in_current_task"),
        "no_prm_filtering_in_current_task": experiment.get("no_prm_filtering_in_current_task"),
    }
    required_false = {
        "future_api_calls_authorized": future.get("api_calls_authorized"),
        "future_replay_authorized": future.get("replay_authorized"),
        "future_scoring_authorized": future.get("scoring_authorized"),
        "future_prm_filtering_authorized": future.get("prm_filtering_authorized"),
    }
    clean = (
        all(value is True for value in required_true.values())
        and all(value is False for value in required_false.values())
        and experiment.get("user_approved_budget_usd") is None
    )
    return _status_check(clean, {"required_true": required_true, "required_false": required_false})


def _check_failed_v2_1_provenance(
    config: Mapping[str, Any],
    failure_audit: Mapping[str, Any],
) -> dict[str, Any]:
    boundary = failure_audit.get("status_boundary", {})
    clean = (
        config.get("provenance_boundary", {}).get("current_project_status") == "PILOT_BLOCKED"
        and config.get("provenance_boundary", {}).get("source_status")
        == "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS"
        and failure_audit.get("provenance_status") == "failed_full_validation_provenance"
        and failure_audit.get("source_full_validation_status")
        == "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS"
        and boundary.get("full_validation_task_specific_pass") is False
        and boundary.get("full_validation_global_pass") is False
        and boundary.get("current_status_remains") == "PILOT_BLOCKED"
    )
    return _status_check(
        clean,
        {
            "config_source_status": config.get("provenance_boundary", {}).get("source_status"),
            "failure_provenance_status": failure_audit.get("provenance_status"),
            "full_validation_task_specific_pass": boundary.get(
                "full_validation_task_specific_pass"
            ),
            "full_validation_global_pass": boundary.get("full_validation_global_pass"),
        },
    )


def _check_v2_1_non_use_policy(config: Mapping[str, Any], transition_text: str) -> dict[str, Any]:
    forbidden = set(config.get("provenance_boundary", {}).get("forbidden_uses", []))
    required = {
        "tune_v2_2_thresholds_from_v2_1_full_artifacts",
        "fit_v2_2_weights_from_v2_1_full_artifacts",
        "select_v2_2_rows_from_v2_1_full_artifacts",
    }
    lower_transition = transition_text.lower()
    clean = (
        required.issubset(forbidden) and "failed" in lower_transition and "tune" in lower_transition
    )
    return _status_check(
        clean, {"required_forbidden_uses": sorted(required), "configured": sorted(forbidden)}
    )


def _check_fresh_split_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = config.get("fresh_split_policy", {})
    configured_keys = set(policy.get("required_non_overlap_keys", []))
    configured_forbidden = set(policy.get("forbidden_selection_fields", []))
    required_keys = {
        "sample_id",
        "task_id",
        "dataset_config_split_source_index",
        "normalized_question_hash",
        "reference_answer_hash",
        "non_empty_alias_hash",
    }
    clean = (
        policy.get("non_overlap_required_before_execution") is True
        and required_keys.issubset(configured_keys)
        and V2_2_FORBIDDEN_SELECTION_FIELDS.issubset(configured_forbidden)
        and policy.get("overlap_policy", {}).get("non_empty_alias_hash_overlap") == "hard_stop"
    )
    return _status_check(
        clean,
        {
            "required_non_overlap_keys": sorted(required_keys),
            "configured_non_overlap_keys": sorted(configured_keys),
            "required_forbidden_selection_fields": sorted(V2_2_FORBIDDEN_SELECTION_FIELDS),
        },
    )


def _check_utility_target_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    targets = config.get("utility_target", {}).get("tasks", {})
    gsm8k = targets.get("gsm8k", {})
    hotpotqa = targets.get("hotpotqa", {})
    clean = (
        config.get("utility_target", {}).get("target_name") == "graded_stochastic_delta_u_v2_2"
        and gsm8k.get("primary_score_field") == "repeated_numeric_success_probability"
        and hotpotqa.get("primary_score_field") == "normalized_token_f1"
        and hotpotqa.get("llm_judge_allowed") is False
    )
    return _status_check(clean, {"gsm8k": gsm8k, "hotpotqa": hotpotqa})


def _check_schema_transport_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    repair = config.get("schema_transport_policy", {}).get("bounded_repair_policy", {})
    clean = (
        repair.get("allowed") is True
        and repair.get("authorized_by_this_config") is False
        and repair.get("preserve_all_failed_attempts") is True
        and repair.get("answer_content_editing_allowed") is False
    )
    return _status_check(clean, repair)


def _check_rank_signal_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = config.get("rank_signal_reporting", {})
    metrics = set(policy.get("metrics", []))
    uncertainty = policy.get("uncertainty", {})
    clean = (
        {"spearman", "kendall_tau_b", "ndcg_at_3", "top_10_percent_high_utility_auc"}.issubset(
            metrics
        )
        and uncertainty.get("bootstrap_ci_required") is True
        and uncertainty.get("bootstrap_standard_error_required") is True
        and uncertainty.get("bootstrap_variance_required") is True
        and uncertainty.get("bootstrap_unit") == "sample_id"
    )
    return _status_check(clean, {"metrics": sorted(metrics), "uncertainty": uncertainty})


def _check_prompt_lock(config: Mapping[str, Any]) -> dict[str, Any]:
    prompt_lock = config.get("prompt_lock", {})
    observed = _prompt_bundle_hash(prompt_lock)
    configured = str(prompt_lock.get("prompt_version") or "")
    clean = (
        bool(observed)
        and configured == observed
        and prompt_lock.get("prompt_lock_status") == "CURRENT_PACKAGE_PROMPT_LOCK"
        and prompt_lock.get("prompt_hash_scope") == "generation_and_replay_prompt_bundle"
        and prompt_lock.get("model_must_not_invent_new_types") is True
        and prompt_lock.get("utility_target_supported") == "graded_stochastic_delta_u_v2_2"
    )
    return _status_check(
        clean,
        {
            "generation_prompt_file": str(prompt_lock.get("generation_prompt_file") or ""),
            "replay_prompt_file": str(prompt_lock.get("replay_prompt_file") or ""),
            "prompt_version": observed,
            "configured_prompt_version": configured,
            "prompt_lock_status": str(prompt_lock.get("prompt_lock_status") or ""),
            "prompt_hash_scope": str(prompt_lock.get("prompt_hash_scope") or ""),
            "allowed_reflection_types": list(prompt_lock.get("allowed_reflection_types") or []),
            "model_must_not_invent_new_types": prompt_lock.get("model_must_not_invent_new_types"),
            "utility_target_supported": prompt_lock.get("utility_target_supported"),
        },
    )


def _prompt_bundle_hash(prompt_lock: Mapping[str, Any]) -> str:
    generation_prompt_file = str(prompt_lock.get("generation_prompt_file") or "")
    replay_prompt_file = str(prompt_lock.get("replay_prompt_file") or "")
    generation_path = Path(generation_prompt_file)
    replay_path = Path(replay_prompt_file)
    if not generation_path.exists() or not replay_path.exists():
        return ""
    payload = {
        "generation_prompt_file": generation_path.as_posix(),
        "generation_prompt_text": generation_path.read_text(encoding="utf-8"),
        "replay_prompt_file": replay_path.as_posix(),
        "replay_prompt_text": replay_path.read_text(encoding="utf-8"),
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "prompt-sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_claim_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    current = set(config.get("claim_policy", {}).get("current_status_must_remain", []))
    required = {
        "PILOT_BLOCKED",
        "v2_2_preregistered_only",
        "no_api_authorized",
        "no_replay_run",
        "no_scoring_run",
        "no_prm_filtering_claim",
    }
    clean = required.issubset(current)
    return _status_check(
        clean, {"required_current_status": sorted(required), "configured": sorted(current)}
    )


def _check_preregistration_plan(plan_text: str) -> dict[str, Any]:
    required = [
        "PILOT_BLOCKED",
        "repeated_numeric_success_probability",
        "normalized_token_f1",
        "bootstrap",
        "PRM/filtering",
    ]
    clean = all(value in plan_text for value in required)
    return _status_check(clean, {"required_plan_terms": required})


def _selected_overlaps_all_zero(manifest_audit: Mapping[str, Any]) -> bool:
    selected = manifest_audit.get("overlap_summary", {}).get("selected_overlaps_by_key", {})
    return bool(selected) and all(int(value) == 0 for value in selected.values())
