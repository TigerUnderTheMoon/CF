"""Fresh-holdout manifest and overlap audit utilities for s_FMA_v2."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping


BLOCKED_INSUFFICIENT_FRESH_ROWS = "BLOCKED_INSUFFICIENT_FRESH_ROWS"
MANIFEST_OVERLAP_CLEAN = "MANIFEST_OVERLAP_CLEAN"
OVERLAP_AUDIT_CLEAN = MANIFEST_OVERLAP_CLEAN
OVERLAP_AUDIT_FAIL = "OVERLAP_AUDIT_FAIL"

REQUIRED_NON_OVERLAP_KEYS = (
    "sample_id",
    "task_id",
    "dataset_config_split_source_index",
    "normalized_question_hash",
    "reference_answer_hash",
    "alias_hash",
)

FRESH_MANIFEST_FIELDS = (
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
    "selection_seed",
    "formula_hash",
    "prompt_version",
    "manifest_item_hash",
)


def normalize_text(value: Any) -> str:
    """Apply the preregistered NFKC/lowercase/whitespace text normalization."""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", normalized.lower()).strip()


def normalized_text_hash(value: Any) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def alias_hash(aliases: Any) -> str:
    normalized = _normalized_aliases(aliases)
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()


def has_non_empty_aliases(aliases: Any) -> bool:
    return len(_normalized_aliases(aliases)) > 0


def dataset_config_split_source_index(row: Mapping[str, Any]) -> str | None:
    dataset = row.get("dataset", row.get("source_dataset"))
    config = row.get("config", row.get("source_config"))
    split = row.get("split", row.get("source_split"))
    source_index = row.get("source_index")
    if dataset is None or config is None or split is None or source_index is None:
        return None
    return f"{dataset}/{config}/{split}/{source_index}"


def build_fresh_holdout_manifest(
    source_rows_by_task: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    config: Mapping[str, Any],
    current_pilot_sources: Mapping[str, Iterable[Mapping[str, Any]]],
    prompt_version: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the fresh manifest and the hard non-overlap audit.

    Rows are selected only from candidates with no overlap on any required key.
    If a task cannot meet its configured sample count, the manifest is empty and
    the audit reports BLOCKED_INSUFFICIENT_FRESH_ROWS.
    """

    current_index = build_current_pilot_overlap_index(current_pilot_sources)
    seed = int(config.get("experiment", {}).get("seed", 0))
    formula_hash = str(config.get("scorer", {}).get("formula_hash") or "")
    tasks_config = config.get("fresh_holdout", {}).get("tasks", {})

    selected_by_task: dict[str, list[dict[str, Any]]] = {}
    task_reports: dict[str, dict[str, Any]] = {}
    overlap_counts = {key: 0 for key in REQUIRED_NON_OVERLAP_KEYS}
    selected_overlap_counts = {key: 0 for key in REQUIRED_NON_OVERLAP_KEYS}
    overlap_examples: dict[str, list[dict[str, Any]]] = {key: [] for key in REQUIRED_NON_OVERLAP_KEYS}

    for task_type in sorted(tasks_config):
        task_config = tasks_config[task_type]
        candidates = [
            _candidate_manifest_item(
                row,
                task_type=task_type,
                task_config=task_config,
                seed=seed,
                formula_hash=formula_hash,
                prompt_version=prompt_version,
            )
            for row in source_rows_by_task.get(task_type, [])
        ]
        candidates = sorted(candidates, key=lambda item: item["selection_order_key"])
        empty_alias_candidate_count = sum(
            1 for item in candidates if not has_non_empty_aliases(item.get("aliases"))
        )
        non_empty_alias_candidate_count = len(candidates) - empty_alias_candidate_count
        eligible: list[dict[str, Any]] = []
        excluded = 0
        for item in candidates:
            overlaps = _overlaps_for_item(item, current_index)
            if overlaps:
                excluded += 1
                for key, source_hits in overlaps.items():
                    overlap_counts[key] += 1
                    if len(overlap_examples[key]) < 10:
                        overlap_examples[key].append(_overlap_example(item, key, source_hits))
                continue
            eligible.append(item)

        sample_count = int(task_config.get("sample_count", 0))
        selected = eligible[:sample_count]
        selected_by_task[task_type] = selected
        for item in selected:
            selected_overlaps = _overlaps_for_item(item, current_index)
            for key in selected_overlaps:
                selected_overlap_counts[key] += 1

        task_status = OVERLAP_AUDIT_CLEAN
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
        status = OVERLAP_AUDIT_CLEAN
        manifest = []
        for task_type in sorted(selected_by_task):
            manifest.extend(selected_by_task[task_type])
        manifest = [_finalize_manifest_item(item) for item in manifest]

    audit = {
        "status": status,
        "overlap_clean": status == OVERLAP_AUDIT_CLEAN,
        "hard_stop": status != OVERLAP_AUDIT_CLEAN,
        "hard_stop_policy": "any selected-row overlap or insufficient fresh rows stops before scoring, replay, or reporting",
        "blocker": status if status != OVERLAP_AUDIT_CLEAN else None,
        "current_status_remains": "PILOT_BLOCKED",
        "s_fma_v2_status": "planned-only",
        "no_api_run": True,
        "no_v2_scoring": True,
        "no_replay": True,
        "no_traces_generated": True,
        "no_prm_claim_yet": True,
        "next_allowed_step": (
            "API_PREFLIGHT_ONLY"
            if status == OVERLAP_AUDIT_CLEAN
            else "PREREGISTER_ALTERNATE_SPLIT_DATASET_OR_SOURCE"
        ),
        "api_preflight_only": status == OVERLAP_AUDIT_CLEAN,
        "alias_policy": {
            "empty_alias_set_blocking": False,
            "non_empty_alias_hash_blocking": True,
            "rationale": "empty alias set is non-informative and not blocking; non-empty alias_hash remains blocking",
        },
        "blocker_diagnosis": {
            "prior_blocker": BLOCKED_INSUFFICIENT_FRESH_ROWS,
            "root_cause": "empty alias sets shared the SHA256 hash of the empty string and were previously treated as blocking alias_hash overlaps",
            "policy_revision": "empty alias set is non-informative and not blocking; non-empty alias_hash remains blocking",
            "reviewer_safety_preserved_keys": [
                "sample_id",
                "task_id",
                "dataset_config_split_source_index",
                "normalized_question_hash",
                "reference_answer_hash",
                "non_empty_alias_hash",
            ],
        },
        "required_non_overlap_keys": list(REQUIRED_NON_OVERLAP_KEYS),
        "fresh_manifest_fields": list(FRESH_MANIFEST_FIELDS),
        "selection_seed": seed,
        "formula_hash": formula_hash,
        "prompt_version": prompt_version,
        "tasks": task_reports,
        "current_pilot_sources": current_index["source_reports"],
        "overlap_summary": {
            "candidate_pool_overlaps_by_key": overlap_counts,
            "selected_overlaps_by_key": selected_overlap_counts,
            "total_overlaps_by_key": overlap_counts,
        },
        "overlap_examples": overlap_examples,
    }
    return manifest, audit


def build_current_pilot_overlap_index(
    sources: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    index: dict[str, dict[str, set[str]]] = {
        key: {} for key in REQUIRED_NON_OVERLAP_KEYS
    }
    source_reports: dict[str, dict[str, Any]] = {}
    for source_name, rows_iterable in sources.items():
        rows = list(rows_iterable)
        key_counts = {key: 0 for key in REQUIRED_NON_OVERLAP_KEYS}
        for row_number, row in enumerate(rows):
            keys = row_overlap_keys(row)
            for key, value in keys.items():
                key_counts[key] += 1
                index[key].setdefault(value, set()).add(f"{source_name}:{row_number}")
        source_reports[source_name] = {
            "rows_loaded": len(rows),
            "indexed_key_counts": key_counts,
        }
    return {
        "index": index,
        "source_reports": source_reports,
    }


def row_overlap_keys(row: Mapping[str, Any]) -> dict[str, str]:
    keys: dict[str, str] = {}
    if row.get("sample_id") is not None:
        keys["sample_id"] = str(row.get("sample_id"))
    if row.get("task_id") is not None:
        keys["task_id"] = str(row.get("task_id"))
    composite = dataset_config_split_source_index(row)
    if composite is not None:
        keys["dataset_config_split_source_index"] = composite
    if "question" in row:
        keys["normalized_question_hash"] = normalized_text_hash(row.get("question"))
    if "reference_answer" in row:
        keys["reference_answer_hash"] = normalized_text_hash(row.get("reference_answer"))
    elif "answer" in row:
        keys["reference_answer_hash"] = normalized_text_hash(row.get("answer"))
    if "aliases" in row and has_non_empty_aliases(row.get("aliases")):
        keys["alias_hash"] = alias_hash(row.get("aliases"))
    return keys


def render_overlap_audit_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# s_FMA_v2 Fresh-Holdout Manifest Overlap Audit",
        "",
        f"Status: `{audit['status']}`",
        f"Overlap clean: `{str(audit['overlap_clean']).lower()}`",
        f"Hard stop: `{str(audit['hard_stop']).lower()}`",
        "",
        "## Execution Boundary",
        "",
        "- Fresh manifest generation/audit only.",
        "- No API run.",
        "- No v2 scoring.",
        "- No replay.",
        "- No traces generated.",
        "- No PRM claim yet.",
        "- Current status remains `PILOT_BLOCKED`.",
        "- `s_FMA_v2` remains planned-only.",
        f"- Next allowed step: `{audit.get('next_allowed_step')}`.",
        "",
        "## Alias Policy",
        "",
        "- Empty alias set is non-informative and not blocking.",
        "- Non-empty `alias_hash` remains a hard blocking overlap key.",
        "- `sample_id`, `task_id`, dataset/config/split/source index, normalized question hash, and reference answer hash remain hard-stop keys.",
        "",
        "## Blocker Diagnosis",
        "",
        f"- Prior blocker: `{audit.get('blocker_diagnosis', {}).get('prior_blocker', '')}`.",
        f"- Root cause: {audit.get('blocker_diagnosis', {}).get('root_cause', '')}.",
        f"- Policy revision: {audit.get('blocker_diagnosis', {}).get('policy_revision', '')}.",
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
    lines.extend(["", "## Current Pilot Sources", "", "| Source | Rows loaded |", "|---|---:|"])
    for source, report in sorted(audit["current_pilot_sources"].items()):
        lines.append(f"| `{source}` | {report['rows_loaded']} |")
    lines.extend(["", "## Decision", ""])
    if audit["status"] == OVERLAP_AUDIT_CLEAN:
        lines.append(
            "Fresh manifest generated and hard non-overlap audit clean. The only allowed next step is API preflight-only; API full run, v2 scoring, replay, trace generation, and PRM/filtering remain forbidden."
        )
    elif audit["status"] == BLOCKED_INSUFFICIENT_FRESH_ROWS:
        lines.append(
            "Fresh manifest generation is blocked by insufficient fresh rows after applying all required hard non-overlap keys. No current-pilot rows were reused."
        )
    else:
        lines.append(
            "Fresh manifest generation is blocked because selected rows overlapped with current-pilot evidence. No pass label is allowed."
        )
    lines.append("")
    return "\n".join(lines)


def write_fresh_manifest_outputs(
    manifest: list[dict[str, Any]],
    audit: Mapping[str, Any],
    *,
    manifest_path: str | Path,
    audit_json_path: str | Path,
    audit_markdown_path: str | Path,
) -> None:
    _write_json(Path(manifest_path), manifest)
    _write_json(Path(audit_json_path), audit)
    Path(audit_markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(audit_markdown_path).write_text(render_overlap_audit_markdown(audit), encoding="utf-8")


def _candidate_manifest_item(
    row: Mapping[str, Any],
    *,
    task_type: str,
    task_config: Mapping[str, Any],
    seed: int,
    formula_hash: str,
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
    item = {
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
        "selection_seed": seed,
        "formula_hash": formula_hash,
        "prompt_version": prompt_version,
    }
    item["dataset_config_split_source_index"] = dataset_config_split_source_index(item)
    item["normalized_question_hash"] = normalized_text_hash(question)
    item["reference_answer_hash"] = normalized_text_hash(reference_answer)
    item["alias_hash"] = alias_hash(aliases)
    item["selection_order_key"] = _selection_order_key(seed, task_type, source_index, question)
    return item


def _finalize_manifest_item(item: Mapping[str, Any]) -> dict[str, Any]:
    finalized = dict(item)
    finalized.pop("selection_order_key", None)
    finalized["manifest_item_hash"] = _manifest_item_hash(finalized)
    return finalized


def _overlaps_for_item(
    item: Mapping[str, Any],
    current_index: Mapping[str, Any],
) -> dict[str, list[str]]:
    index = current_index["index"]
    item_keys = {
        "sample_id": str(item.get("sample_id") or ""),
        "task_id": str(item.get("task_id") or ""),
        "dataset_config_split_source_index": str(item.get("dataset_config_split_source_index") or ""),
        "normalized_question_hash": str(item.get("normalized_question_hash") or ""),
        "reference_answer_hash": str(item.get("reference_answer_hash") or ""),
    }
    if has_non_empty_aliases(item.get("aliases")):
        item_keys["alias_hash"] = str(item.get("alias_hash") or "")
    overlaps: dict[str, list[str]] = {}
    for key, value in item_keys.items():
        if value in index[key]:
            overlaps[key] = sorted(index[key][value])[:10]
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


def _selection_order_key(seed: int, task_type: str, source_index: int, question: str) -> str:
    payload = f"{seed}:{task_type}:{source_index}:{question}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized_aliases(aliases: Any) -> list[str]:
    values = aliases if isinstance(aliases, list) else []
    return sorted(alias for alias in (normalize_text(value) for value in values) if alias)


def _manifest_item_hash(item: Mapping[str, Any]) -> str:
    payload = json.dumps(item, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
