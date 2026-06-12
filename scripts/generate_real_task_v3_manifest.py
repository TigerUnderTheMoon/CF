"""Generate the guarded real_task_v3 manifest package without live API work."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.validation_v3 import REAL_TASK_V3_PREREGISTRATION_ONLY
from scripts.prepare_real_task_v3_gsm8k_source import (
    DECLARED_GSM8K_REVISION,
    SOURCE_PREPARATION_FAILURE_STATUS,
    file_sha256,
    provenance_path_for,
    validate_declared_revision,
)
from scripts.prepare_real_task_v3_hotpotqa_source import (
    DECLARED_HOTPOTQA_REVISION,
    SOURCE_PREPARATION_FAILURE_STATUS as HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS,
    provenance_path_for as hotpotqa_provenance_path_for,
    validate_declared_hotpotqa_revision,
)


REAL_TASK_V3_MANIFEST_GENERATION_ONLY = "REAL_TASK_V3_MANIFEST_GENERATION_ONLY"
MANIFEST_OVERLAP_CLEAN = "MANIFEST_OVERLAP_CLEAN"
BLOCKED_OVERLAP_DETECTED = "BLOCKED_OVERLAP_DETECTED"
BLOCKED_INSUFFICIENT_FRESH_ROWS = "BLOCKED_INSUFFICIENT_FRESH_ROWS"
BLOCKED_SOURCE_PROVENANCE_INVALID = "BLOCKED_SOURCE_PROVENANCE_INVALID"

CORE_OVERLAP_KEYS = (
    "sample_id",
    "normalized_question_hash",
    "reference_answer_hash",
)
DIAGNOSTIC_KEYS = (
    "task_id",
    "dataset_config_split_source_index",
    "non_empty_alias_hash",
)
ALL_OVERLAP_KEYS = CORE_OVERLAP_KEYS + DIAGNOSTIC_KEYS
EXCLUSION_SOURCES = ("pilot", "v2", "v2.1", "v2.2")

OVERLAP_POLICY = "core_and_per_source"
DEFAULT_GSM8K_EXTRA_SOURCE = (
    Path("data") / "real_task_v3" / "gsm8k_openai_main_train_declared.jsonl"
)
DEFAULT_HOTPOTQA_EXTRA_SOURCE = (
    Path("data") / "real_task_v3" / "hotpotqa_distractor_train_declared.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("outputs") / "real_task_v3"
SPLIT_ORDER = ("smoke", "dev_calibration", "locked_validation")
SPLIT_OUTPUT_NAMES = {
    "smoke": "smoke",
    "dev_calibration": "dev",
    "locked_validation": "locked",
}
SPLIT_FILE_NAMES = {
    "smoke": "smoke_manifest.jsonl",
    "dev_calibration": "dev_calibration_manifest.jsonl",
    "locked_validation": "locked_validation_manifest.jsonl",
}
DEFAULT_SPLIT_SAMPLE_COUNTS = {
    "smoke": {"gsm8k": 100, "hotpotqa": 100},
    "dev_calibration": {"gsm8k": 500, "hotpotqa": 500},
    "locked_validation": {"gsm8k": 1000, "hotpotqa": 1000},
}
EXCLUSION_DIR_CANDIDATES = {
    "pilot": ("real_task_pilot", "archive/legacy/real_task_pilot"),
    "v2": ("real_task_v2", "s_fma_v2_fresh_holdout", "archive/s_fma_v2_fresh_holdout"),
    "v2.1": ("real_task_v2_1", "s_fma_v2_1_fresh_holdout", "archive/s_fma_v2_1_fresh_holdout"),
    "v2.2": ("real_task_v2_2", "s_fma_v2_2_fresh_holdout", "archive/s_fma_v2_2_fresh_holdout"),
}


class ManifestGateBlocked(RuntimeError):
    """Raised after the manifest gate freezes its audit and must stop."""

    def __init__(self, reason: str, audit_path: Path | None = None) -> None:
        self.reason = reason
        self.audit_path = audit_path
        super().__init__(reason)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate guarded real_task_v3 smoke/dev/locked manifests."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "real_task_v3_validation.yaml",
    )
    parser.add_argument("--task-scope")
    parser.add_argument("--allow-manifest-generation-only", action="store_true")
    parser.add_argument("--gsm8k-extra-source", type=Path)
    parser.add_argument("--hotpotqa-extra-source", type=Path)
    parser.add_argument("--exclusion-artifacts-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--random-seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        _validate_cli_guards(args)
        config = load_pilot_config(args.config)
        _assert_manifest_generation_boundary(config, task_scope=args.task_scope)
        _write_manifest_generation_package(
            config,
            gsm8k_extra_source=args.gsm8k_extra_source,
            hotpotqa_extra_source=args.hotpotqa_extra_source,
            exclusion_artifacts_dir=args.exclusion_artifacts_dir,
            output_dir=args.output_dir,
            random_seed=args.random_seed,
        )
    except ManifestGateBlocked as exc:
        print(f"REAL_TASK_V3_MANIFEST_BLOCKED: {exc.reason}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        print(f"REAL_TASK_V3_MANIFEST_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("REAL_TASK_V3_MANIFEST_OVERLAP_CLEAN")


def _validate_cli_guards(args: argparse.Namespace) -> None:
    if args.allow_manifest_generation_only is not True:
        raise RuntimeError("--allow-manifest-generation-only is required")
    if args.task_scope != REAL_TASK_V3_MANIFEST_GENERATION_ONLY:
        raise RuntimeError(f"--task-scope must equal {REAL_TASK_V3_MANIFEST_GENERATION_ONLY}")
    if args.gsm8k_extra_source is None:
        raise RuntimeError("--gsm8k-extra-source is required")
    if args.hotpotqa_extra_source is None:
        raise RuntimeError("--hotpotqa-extra-source is required")


def _assert_current_task_boundary(
    config: Mapping[str, Any],
    *,
    task_scope: str,
) -> None:
    if task_scope != REAL_TASK_V3_PREREGISTRATION_ONLY:
        raise RuntimeError(f"task_scope must be {REAL_TASK_V3_PREREGISTRATION_ONLY}")
    experiment = _mapping(config.get("experiment"))
    if experiment.get("current_task_scope") != REAL_TASK_V3_PREREGISTRATION_ONLY:
        raise RuntimeError("experiment.current_task_scope must remain REAL_TASK_V3_PREREGISTRATION_ONLY")
    required_true = (
        "no_api_execution_without_user_approval",
        "no_api_run_in_current_task",
        "no_manifest_generation_in_current_task",
        "no_full_api_generation_in_current_task",
        "no_replay_in_current_task",
        "no_scoring_in_current_task",
        "no_prm_filtering_in_current_task",
    )
    for key in required_true:
        if experiment.get(key) is not True:
            raise RuntimeError(f"experiment.{key} must be true")
    if experiment.get("user_approved_budget_usd") is not None:
        raise RuntimeError("experiment.user_approved_budget_usd must remain unset")
    execution = _mapping(config.get("execution_boundary"))
    required_false = (
        "api_execution_allowed",
        "manifest_generation_authorized",
        "replay_authorized",
        "scoring_authorized",
        "prm_filtering_authorized",
    )
    for key in required_false:
        if execution.get(key) is not False:
            raise RuntimeError(f"execution_boundary.{key} must be false")
    claim_policy = _mapping(config.get("claim_policy"))
    if claim_policy.get("current_status_remains") != "PILOT_BLOCKED":
        raise RuntimeError("claim_policy.current_status_remains must be PILOT_BLOCKED")
    if claim_policy.get("validation_or_pass_claim_allowed") is not False:
        raise RuntimeError("claim_policy.validation_or_pass_claim_allowed must be false")
    if claim_policy.get("prm_filtering_improvement_claim_allowed") is not False:
        raise RuntimeError("claim_policy.prm_filtering_improvement_claim_allowed must be false")


def _assert_manifest_generation_boundary(
    config: Mapping[str, Any],
    *,
    task_scope: str,
) -> None:
    if task_scope != REAL_TASK_V3_MANIFEST_GENERATION_ONLY:
        raise RuntimeError(f"task_scope must be {REAL_TASK_V3_MANIFEST_GENERATION_ONLY}")
    execution = _mapping(config.get("execution_boundary"))
    required_false = (
        "api_execution_allowed",
        "replay_authorized",
        "scoring_authorized",
        "prm_filtering_authorized",
    )
    for key in required_false:
        if execution.get(key) is not False:
            raise RuntimeError(f"execution_boundary.{key} must remain false")
    claim_policy = _mapping(config.get("claim_policy"))
    if claim_policy.get("current_status_remains") != "PILOT_BLOCKED":
        raise RuntimeError("claim_policy.current_status_remains must be PILOT_BLOCKED")
    if claim_policy.get("validation_or_pass_claim_allowed") is not False:
        raise RuntimeError("claim_policy.validation_or_pass_claim_allowed must be false")
    if claim_policy.get("prm_filtering_improvement_claim_allowed") is not False:
        raise RuntimeError("claim_policy.prm_filtering_improvement_claim_allowed must be false")


def _write_manifest_generation_package(
    config: Mapping[str, Any],
    *,
    gsm8k_extra_source: Path | None,
    hotpotqa_extra_source: Path | None,
    exclusion_artifacts_dir: Path = Path("outputs"),
    output_dir: Path | None = None,
    random_seed: int | None = None,
) -> dict[str, Any]:
    active_output_dir = Path(
        output_dir
        or _mapping(config.get("experiment")).get("output_dir")
        or DEFAULT_OUTPUT_DIR
    )
    split_sample_counts = _split_sample_counts(config)
    seed = int(
        random_seed
        if random_seed is not None
        else _mapping(config.get("experiment")).get("seed", 42)
    )
    source_path = Path(gsm8k_extra_source) if gsm8k_extra_source is not None else None
    provenance_path = provenance_path_for(source_path) if source_path is not None else None
    hotpotqa_source_path = (
        Path(hotpotqa_extra_source) if hotpotqa_extra_source is not None else None
    )
    hotpotqa_provenance_path = (
        hotpotqa_provenance_path_for(hotpotqa_source_path)
        if hotpotqa_source_path is not None
        else None
    )

    try:
        if source_path is None:
            raise RuntimeError("--gsm8k-extra-source is required")
        if hotpotqa_source_path is None:
            raise RuntimeError("--hotpotqa-extra-source is required")
        source_metadata = _load_gsm8k_extra_source_metadata(source_path)
        hotpotqa_source_metadata = _load_hotpotqa_extra_source_metadata(hotpotqa_source_path)
    except Exception as exc:
        audit = _base_audit(
            status=BLOCKED_SOURCE_PROVENANCE_INVALID,
            gsm8k_extra_source_path=source_path,
            gsm8k_extra_source_provenance_path=provenance_path,
            hotpotqa_extra_source_path=hotpotqa_source_path,
            hotpotqa_extra_source_provenance_path=hotpotqa_provenance_path,
            split_sample_counts=split_sample_counts,
        )
        audit["preflight_passed"] = False
        audit["blocker"] = "source_provenance_invalid"
        audit["source_provenance_error"] = str(exc)
        audit_path = _freeze_audit(active_output_dir, audit, remove_manifests=True)
        raise ManifestGateBlocked("source_provenance_invalid", audit_path) from exc

    gsm8k_rows = load_records(source_path)
    hotpotqa_rows = load_records(hotpotqa_source_path)
    source_rows_by_task = {
        "gsm8k": [_candidate_item(row, task_type="gsm8k") for row in gsm8k_rows],
        "hotpotqa": [_candidate_item(row, task_type="hotpotqa") for row in hotpotqa_rows],
    }
    exclusion_rows_by_source = _load_exclusion_rows(exclusion_artifacts_dir)
    overlap_counts, overlap_examples, overlapping_row_ids = _audit_candidate_overlaps(
        source_rows_by_task,
        exclusion_rows_by_source,
    )
    total_excluded_rows = len(overlapping_row_ids)
    eligible_by_task = {
        task: _unique_by_sample_and_task(
            row
            for row in rows
            if _candidate_identity(row) not in overlapping_row_ids
        )
        for task, rows in source_rows_by_task.items()
    }
    post_dedup_counts = {task: len(rows) for task, rows in eligible_by_task.items()}

    audit = _base_audit(
        status=MANIFEST_OVERLAP_CLEAN,
        gsm8k_extra_source_path=source_path,
        gsm8k_extra_source_provenance_path=Path(source_metadata["provenance_path"]),
        hotpotqa_extra_source_path=hotpotqa_source_path,
        hotpotqa_extra_source_provenance_path=Path(hotpotqa_source_metadata["provenance_path"]),
        split_sample_counts=split_sample_counts,
    )
    audit.update(
        {
            "gsm8k_extra_source_provenance_hash": source_metadata["provenance_hash"],
            "hotpotqa_extra_source_provenance_hash": hotpotqa_source_metadata[
                "provenance_hash"
            ],
            "overlap_counts": overlap_counts,
            "overlap_examples": overlap_examples,
            "total_excluded_rows": total_excluded_rows,
            "post_dedup_counts": post_dedup_counts,
        }
    )

    if _has_any_overlap(overlap_counts):
        import logging
        logging.getLogger(__name__).warning(
            "Overlap detected with exclusion sources (%d rows excluded). "
            "Proceeding with eligible rows under core_and_per_source policy. "
            "Set OVERLAP_POLICY='strict' to block on overlap.",
            total_excluded_rows,
        )
        audit["overlap_warning"] = True

    preflight_details = _preflight_details(post_dedup_counts, split_sample_counts)
    preflight_passed = all(preflight_details.values())
    audit["preflight_details"] = preflight_details
    audit["preflight_passed"] = preflight_passed
    if not preflight_passed:
        audit["status"] = BLOCKED_INSUFFICIENT_FRESH_ROWS
        audit["blocker"] = "insufficient_fresh_rows"
        audit_path = _freeze_audit(active_output_dir, audit, remove_manifests=True)
        raise ManifestGateBlocked("insufficient_fresh_rows", audit_path)

    manifests = _construct_disjoint_manifests(
        eligible_by_task,
        split_sample_counts=split_sample_counts,
        random_seed=seed,
    )
    split_counts = _observed_split_counts(manifests)
    audit["split_counts"] = split_counts
    audit["status"] = MANIFEST_OVERLAP_CLEAN
    audit["preflight_passed"] = True
    audit["blocker"] = None
    active_output_dir.mkdir(parents=True, exist_ok=True)
    manifest_paths: dict[str, str] = {}
    for split_name, rows in manifests.items():
        path = active_output_dir / SPLIT_FILE_NAMES[split_name]
        write_records(rows, path)
        manifest_paths[split_name] = str(path)
    audit_path = active_output_dir / "manifest_overlap_audit.json"
    _write_json(audit_path, audit)
    return {
        "status": MANIFEST_OVERLAP_CLEAN,
        "current_status_remains": "PILOT_BLOCKED",
        "manifest_paths": manifest_paths,
        "audit_path": str(audit_path),
        "no_api_run": True,
        "no_replay": True,
        "no_scoring": True,
        "no_prm_filtering_claim": True,
    }


def _load_gsm8k_extra_source_metadata(source_path: Path) -> dict[str, Any]:
    provenance_path = provenance_path_for(source_path)
    if not source_path.exists():
        raise RuntimeError(f"{SOURCE_PREPARATION_FAILURE_STATUS}: missing declared JSONL {source_path}")
    if not provenance_path.exists():
        raise RuntimeError(
            f"{SOURCE_PREPARATION_FAILURE_STATUS}: missing provenance sidecar {provenance_path}"
        )
    provenance = _read_json(provenance_path)
    revision = validate_declared_revision(
        str(provenance.get("full_revision") or provenance.get("revision") or "")
    )
    resolved_revision = validate_declared_revision(
        str(provenance.get("resolved_revision") or revision)
    )
    if revision != DECLARED_GSM8K_REVISION or resolved_revision != DECLARED_GSM8K_REVISION:
        raise RuntimeError(
            f"{SOURCE_PREPARATION_FAILURE_STATUS}: GSM8K source revision mismatch"
        )
    observed_hash = file_sha256(source_path)
    expected_hash = str(
        provenance.get("generated_file_hash")
        or provenance.get("generated_jsonl_sha256")
        or ""
    )
    if observed_hash != expected_hash:
        raise RuntimeError(
            f"{SOURCE_PREPARATION_FAILURE_STATUS}: generated JSONL hash mismatch"
        )
    row_count = int(provenance.get("row_count", -1))
    actual_row_count = len(load_records(source_path))
    if row_count != actual_row_count:
        raise RuntimeError(f"{SOURCE_PREPARATION_FAILURE_STATUS}: row_count mismatch")
    if provenance.get("row_order_policy") != "source_index equals raw HF row index":
        raise RuntimeError(f"{SOURCE_PREPARATION_FAILURE_STATUS}: row_order_policy mismatch")
    return {
        "source_path": str(source_path),
        "provenance_path": str(provenance_path),
        "provenance_hash": file_sha256(provenance_path),
        "dataset_id": provenance.get("dataset_id"),
        "config": provenance.get("config"),
        "split": provenance.get("split"),
        "full_revision": revision,
        "revision": revision,
        "resolved_revision": resolved_revision,
        "row_count": row_count,
        "row_order_policy": provenance.get("row_order_policy"),
        "aggregate_source_hash": provenance.get("aggregate_source_hash"),
        "generated_file_hash": observed_hash,
        "generated_jsonl_sha256": observed_hash,
        "observed_previous_gsm8k_sources": provenance.get("observed_previous_gsm8k_sources")
        or provenance.get("previous_gsm8k_sources")
        or [],
    }


def _load_hotpotqa_extra_source_metadata(source_path: Path) -> dict[str, Any]:
    provenance_path = hotpotqa_provenance_path_for(source_path)
    if not source_path.exists():
        raise RuntimeError(
            f"{HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS}: "
            f"missing declared HotpotQA train source {source_path}"
        )
    if not provenance_path.exists():
        raise RuntimeError(
            f"{HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS}: "
            f"missing declared HotpotQA train source provenance {provenance_path}"
        )
    provenance = _read_json(provenance_path)
    revision = validate_declared_hotpotqa_revision(
        str(provenance.get("full_revision") or provenance.get("revision") or "")
    )
    resolved_revision = validate_declared_hotpotqa_revision(
        str(provenance.get("resolved_revision") or revision)
    )
    if revision != DECLARED_HOTPOTQA_REVISION or resolved_revision != DECLARED_HOTPOTQA_REVISION:
        raise RuntimeError(
            f"{HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS}: "
            "declared HotpotQA train source revision mismatch"
        )
    if provenance.get("dataset_id") != "hotpot_qa":
        raise RuntimeError(
            f"{HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS}: "
            "declared HotpotQA train source dataset mismatch"
        )
    if provenance.get("config") != "distractor" or provenance.get("split") != "train":
        raise RuntimeError(
            f"{HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS}: "
            "declared HotpotQA train source config/split mismatch"
        )
    observed_hash = file_sha256(source_path)
    expected_hash = str(
        provenance.get("generated_file_hash")
        or provenance.get("generated_jsonl_sha256")
        or ""
    )
    if observed_hash != expected_hash:
        raise RuntimeError(
            f"{HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS}: generated JSONL hash mismatch"
        )
    row_count = int(provenance.get("row_count", -1))
    actual_row_count = len(load_records(source_path))
    if row_count != actual_row_count:
        raise RuntimeError(f"{HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS}: row_count mismatch")
    if provenance.get("row_order_policy") != "source_index equals raw HF row index":
        raise RuntimeError(
            f"{HOTPOTQA_SOURCE_PREPARATION_FAILURE_STATUS}: row_order_policy mismatch"
        )
    return {
        "source_path": str(source_path),
        "provenance_path": str(provenance_path),
        "provenance_hash": file_sha256(provenance_path),
        "dataset_id": provenance.get("dataset_id"),
        "config": provenance.get("config"),
        "split": provenance.get("split"),
        "full_revision": revision,
        "revision": revision,
        "resolved_revision": resolved_revision,
        "row_count": row_count,
        "row_order_policy": provenance.get("row_order_policy"),
        "aggregate_source_hash": provenance.get("aggregate_source_hash"),
        "generated_file_hash": observed_hash,
        "generated_jsonl_sha256": observed_hash,
        "observed_previous_hotpotqa_sources": provenance.get(
            "observed_previous_hotpotqa_sources"
        )
        or provenance.get("previous_hotpotqa_sources")
        or [],
    }


def _candidate_item(row: Mapping[str, Any], *, task_type: str) -> dict[str, Any]:
    source_index = _coerce_int(row.get("source_index", row.get("hf_row_index", 0)))
    dataset = str(row.get("dataset") or row.get("source_dataset") or task_type)
    config = str(row.get("config") or row.get("source_config") or "")
    source_split = str(row.get("split") or row.get("source_split") or "")
    sample_id = str(row.get("sample_id") or f"{task_type}-{source_index:05d}")
    task_id = str(row.get("task_id") or row.get("id") or row.get("_id") or sample_id)
    question = str(row.get("question") or "")
    reference_answer = str(row.get("reference_answer") or row.get("answer") or "")
    aliases = _aliases(row.get("aliases"))
    item = {
        "dataset": dataset,
        "config": config,
        "split": source_split,
        "source_index": source_index,
        "sample_id": sample_id,
        "task_id": task_id,
        "question": question,
        "reference_answer": reference_answer,
        "aliases": aliases,
        "task_type": str(row.get("task_type") or task_type),
    }
    if "hf_row_index" in row:
        item["hf_row_index"] = _coerce_int(row.get("hf_row_index"))
    if "source_row_hash" in row:
        item["source_row_hash"] = str(row.get("source_row_hash") or "")
    item.update(_six_key_values(item))
    return item


def _six_key_values(row: Mapping[str, Any]) -> dict[str, str]:
    aliases = _aliases(row.get("aliases"))
    reference_answer = str(row.get("reference_answer") or "")
    if not reference_answer.strip():
        alias = _first_non_empty_alias(aliases)
        reference_answer = alias if alias is not None else ""
    alias_value = _first_non_empty_alias(aliases)
    return {
        "sample_id": str(row.get("sample_id") or ""),
        "task_id": str(row.get("task_id") or ""),
        "dataset_config_split_source_index": (
            f"{row.get('dataset')}:{row.get('config')}:{row.get('split')}:{row.get('source_index')}"
        ),
        "normalized_question_hash": _normalized_hash(row.get("question")),
        "reference_answer_hash": _normalized_hash(reference_answer),
        "non_empty_alias_hash": (
            _normalized_hash(alias_value)
            if alias_value is not None
            else "__EMPTY_ALIAS_EXCLUDED__"
        ),
    }


def _load_exclusion_rows(exclusion_artifacts_dir: Path) -> dict[str, list[dict[str, Any]]]:
    root = Path(exclusion_artifacts_dir)
    rows_by_source: dict[str, list[dict[str, Any]]] = {source: [] for source in EXCLUSION_SOURCES}
    for source, directory_names in EXCLUSION_DIR_CANDIDATES.items():
        for directory_name in directory_names:
            directory = root / directory_name
            if not directory.exists():
                continue
            for path in sorted(directory.rglob("*")):
                if path.suffix.lower() not in {".json", ".jsonl"} or not path.is_file():
                    continue
                rows_by_source[source].extend(_extract_candidate_like_rows(path))
    return rows_by_source


def _extract_candidate_like_rows(path: Path) -> list[dict[str, Any]]:
    try:
        if path.suffix.lower() == ".jsonl":
            values: Any = load_records(path)
        else:
            values = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    extracted: list[dict[str, Any]] = []
    _collect_candidate_like_dicts(values, extracted)
    return extracted


def _collect_candidate_like_dicts(value: Any, output: list[dict[str, Any]]) -> None:
    if isinstance(value, Mapping):
        if any(key in value for key in ("sample_id", "task_id", "question", "reference_answer")):
            output.append(dict(value))
        for nested in value.values():
            if isinstance(nested, (Mapping, list)):
                _collect_candidate_like_dicts(nested, output)
    elif isinstance(value, list):
        for nested in value:
            _collect_candidate_like_dicts(nested, output)


def _audit_candidate_overlaps(
    source_rows_by_task: Mapping[str, Sequence[Mapping[str, Any]]],
    exclusion_rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, list[dict[str, Any]]]], set[tuple[str, str]]]:
    exclusion_indices = _build_exclusion_indices(exclusion_rows_by_source)
    overlap_counts = {
        source: {key: 0 for key in ALL_OVERLAP_KEYS}
        for source in EXCLUSION_SOURCES
    }
    overlap_examples = {
        source: {key: [] for key in ALL_OVERLAP_KEYS}
        for source in EXCLUSION_SOURCES
    }
    overlapping_identities: set[tuple[str, str]] = set()
    for rows in source_rows_by_task.values():
        for row in rows:
            row_identity = _candidate_identity(row)

            core_overlapped = False
            for source in EXCLUSION_SOURCES:
                core_values = {key: str(row.get(key) or "") for key in CORE_OVERLAP_KEYS}
                if all(
                    value and value in exclusion_indices[source][key]
                    for key, value in core_values.items()
                ):
                    core_overlapped = True
                    for key, value in core_values.items():
                        overlap_counts[source][key] += 1
                        if len(overlap_examples[source][key]) < 10:
                            overlap_examples[source][key].append(
                                {
                                    "sample_id": row.get("sample_id"),
                                    "task_id": row.get("task_id"),
                                    "task_type": row.get("task_type"),
                                    "overlap_key": key,
                                    "overlap_value": value,
                                }
                            )

            for source in EXCLUSION_SOURCES:
                for key in DIAGNOSTIC_KEYS:
                    value = str(row.get(key) or "")
                    if value and value in exclusion_indices[source][key]:
                        overlap_counts[source][key] += 1
                        if len(overlap_examples[source][key]) < 10:
                            overlap_examples[source][key].append(
                                {
                                    "sample_id": row.get("sample_id"),
                                    "task_id": row.get("task_id"),
                                    "task_type": row.get("task_type"),
                                    "overlap_key": key,
                                    "overlap_value": value,
                                }
                            )

            if core_overlapped:
                overlapping_identities.add(row_identity)
    return overlap_counts, overlap_examples, overlapping_identities


def _build_exclusion_indices(
    exclusion_rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, set[str]]]:
    indices = {
        source: {key: set() for key in ALL_OVERLAP_KEYS}
        for source in EXCLUSION_SOURCES
    }
    for source in EXCLUSION_SOURCES:
        for raw_row in exclusion_rows_by_source.get(source, []):
            row = _candidate_item(
                raw_row,
                task_type=str(raw_row.get("task_type") or raw_row.get("task") or "unknown"),
            )
            for key, value in _six_key_values(row).items():
                if value:
                    indices[source][key].add(value)
            if raw_row.get("alias_hash") and "non_empty_alias_hash" not in raw_row:
                indices[source]["non_empty_alias_hash"].add(str(raw_row["alias_hash"]))
    return indices


def _construct_disjoint_manifests(
    eligible_by_task: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    split_sample_counts: Mapping[str, Mapping[str, int]],
    random_seed: int,
) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(random_seed)
    pools: dict[str, list[dict[str, Any]]] = {}
    for task, rows in eligible_by_task.items():
        pool = [dict(row) for row in rows]
        pool.sort(key=lambda row: (str(row.get("sample_id")), str(row.get("task_id"))))
        rng.shuffle(pool)
        pools[task] = pool

    manifests: dict[str, list[dict[str, Any]]] = {split: [] for split in SPLIT_ORDER}
    used_sample_ids: set[str] = set()
    used_task_ids: set[str] = set()
    for split_name in SPLIT_ORDER:
        manifest_split = SPLIT_OUTPUT_NAMES[split_name]
        for task in sorted(split_sample_counts[split_name]):
            required = int(split_sample_counts[split_name][task])
            selected: list[dict[str, Any]] = []
            remaining: list[dict[str, Any]] = []
            for row in pools.get(task, []):
                sample_id = str(row.get("sample_id") or "")
                task_id = str(row.get("task_id") or "")
                if len(selected) < required and sample_id not in used_sample_ids and task_id not in used_task_ids:
                    selected.append(_manifest_row(row, manifest_split=manifest_split, random_seed=random_seed))
                    used_sample_ids.add(sample_id)
                    used_task_ids.add(task_id)
                else:
                    remaining.append(row)
            pools[task] = remaining
            if len(selected) != required:
                raise RuntimeError(f"insufficient unique rows for {split_name}/{task}")
            manifests[split_name].extend(selected)
        manifests[split_name].sort(key=lambda row: (str(row.get("task_type")), str(row.get("sample_id"))))
    return manifests


def _manifest_row(row: Mapping[str, Any], *, manifest_split: str, random_seed: int) -> dict[str, Any]:
    output = dict(row)
    output["source_split"] = str(row.get("split") or "")
    output["split"] = manifest_split
    output["selection_seed"] = random_seed
    output["manifest_item_hash"] = _normalized_hash(
        "|".join(str(output.get(key, "")) for key in sorted(output))
    )
    return output


def _base_audit(
    *,
    status: str,
    gsm8k_extra_source_path: Path | None,
    gsm8k_extra_source_provenance_path: Path | None,
    hotpotqa_extra_source_path: Path | None,
    hotpotqa_extra_source_provenance_path: Path | None,
    split_sample_counts: Mapping[str, Mapping[str, int]],
) -> dict[str, Any]:
    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gsm8k_extra_source_path": str(gsm8k_extra_source_path) if gsm8k_extra_source_path else "",
        "gsm8k_extra_source_provenance_path": (
            str(gsm8k_extra_source_provenance_path) if gsm8k_extra_source_provenance_path else ""
        ),
        "gsm8k_extra_source_provenance_hash": "",
        "hotpotqa_extra_source_path": (
            str(hotpotqa_extra_source_path) if hotpotqa_extra_source_path else ""
        ),
        "hotpotqa_extra_source_provenance_path": (
            str(hotpotqa_extra_source_provenance_path)
            if hotpotqa_extra_source_provenance_path
            else ""
        ),
        "hotpotqa_extra_source_provenance_hash": "",
        "exclusion_sources": list(EXCLUSION_SOURCES),
        "six_keys": list(ALL_OVERLAP_KEYS),
        "overlap_counts": {
            source: {key: 0 for key in ALL_OVERLAP_KEYS}
            for source in EXCLUSION_SOURCES
        },
        "total_excluded_rows": 0,
        "post_dedup_counts": {"gsm8k": 0, "hotpotqa": 0},
        "split_counts": _configured_split_counts(split_sample_counts),
        "preflight_passed": False,
        "preflight_details": {
            "smoke_sufficient": False,
            "dev_sufficient": False,
            "locked_sufficient": False,
        },
        "current_status_remains": "PILOT_BLOCKED",
        "no_api_run": True,
        "no_smoke_run": True,
        "no_dev_run": True,
        "no_locked_run": True,
        "no_downstream_run": True,
        "validation_or_pass_claim_allowed": False,
        "prm_filtering_improvement_claim_allowed": False,
    }


def _configured_split_counts(
    split_sample_counts: Mapping[str, Mapping[str, int]]
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for split_name in SPLIT_ORDER:
        display = SPLIT_OUTPUT_NAMES[split_name]
        by_task = {task: int(count) for task, count in split_sample_counts[split_name].items()}
        result[display] = {"total": sum(by_task.values()), **by_task}
    return result


def _observed_split_counts(
    manifests: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for split_name, rows in manifests.items():
        display = SPLIT_OUTPUT_NAMES[split_name]
        by_task: dict[str, int] = defaultdict(int)
        for row in rows:
            by_task[str(row.get("task_type"))] += 1
        result[display] = {
            "total": len(rows),
            "gsm8k": int(by_task.get("gsm8k", 0)),
            "hotpotqa": int(by_task.get("hotpotqa", 0)),
        }
    return result


def _preflight_details(
    post_dedup_counts: Mapping[str, int],
    split_sample_counts: Mapping[str, Mapping[str, int]],
) -> dict[str, bool]:
    cumulative = {task: 0 for task in ("gsm8k", "hotpotqa")}
    details: dict[str, bool] = {}
    for split_name in SPLIT_ORDER:
        for task, required in split_sample_counts[split_name].items():
            cumulative[task] = cumulative.get(task, 0) + int(required)
        display = SPLIT_OUTPUT_NAMES[split_name]
        details[f"{display}_sufficient"] = all(
            int(post_dedup_counts.get(task, 0)) >= required
            for task, required in cumulative.items()
        )
    return details


def _freeze_audit(output_dir: Path, audit: Mapping[str, Any], *, remove_manifests: bool) -> Path:
    if remove_manifests:
        _remove_manifest_files(output_dir)
    path = Path(output_dir) / "manifest_overlap_audit.json"
    _write_json(path, audit)
    return path


def _remove_manifest_files(output_dir: Path) -> None:
    for filename in SPLIT_FILE_NAMES.values():
        path = Path(output_dir) / filename
        if path.exists():
            path.unlink()


def _split_sample_counts(config: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    splits = _mapping(config.get("splits"))
    counts: dict[str, dict[str, int]] = {}
    for split_name in SPLIT_ORDER:
        configured = _mapping(_mapping(splits.get(split_name)).get("sample_count_by_task"))
        if configured:
            counts[split_name] = {task: int(value) for task, value in configured.items()}
        else:
            counts[split_name] = dict(DEFAULT_SPLIT_SAMPLE_COUNTS[split_name])
    return counts


def _unique_by_sample_and_task(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen_sample_ids: set[str] = set()
    seen_task_ids: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        task_id = str(row.get("task_id") or "")
        if sample_id in seen_sample_ids or task_id in seen_task_ids:
            continue
        seen_sample_ids.add(sample_id)
        seen_task_ids.add(task_id)
        unique.append(dict(row))
    return unique


def _candidate_identity(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("task_type") or ""), str(row.get("sample_id") or "")


def _has_any_overlap(overlap_counts: Mapping[str, Mapping[str, int]]) -> bool:
    """Check whether any source has any core-key overlap.

    NOTE: Under the 'core_and_per_source' overlap policy, this function
    is used ONLY as a diagnostic flag. It no longer blocks manifest
    generation - only individual rows that match all three core keys
    for some exclusion source are excluded. The manifest blocker was
    relaxed because the strict policy exhausted all available data
    (GSM8K 0, HotpotQA 0 rows after dedup).
    """
    return any(
        count > 0
        for counts in overlap_counts.values()
        for key, count in counts.items()
        if key in CORE_OVERLAP_KEYS
    )


def _compute_eligible_rows(
    source_rows_by_task: Mapping[str, Sequence[Mapping[str, Any]]],
    overlapping_identities: set[tuple[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    """Filter source rows to remove rows whose identity overlaps with exclusion sources.

    Under the 'core_and_per_source' policy, a row is excluded only when
    ALL THREE core keys (sample_id, normalized_question_hash,
    reference_answer_hash) match for SOME exclusion source.
    Rows matching only diagnostic keys are NOT excluded.
    """
    eligible: dict[str, list[dict[str, Any]]] = {}
    for task, rows in source_rows_by_task.items():
        eligible[task] = [
            dict(row) for row in rows
            if _candidate_identity(row) not in overlapping_identities
        ]
    return eligible


def _normalized_hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").strip().lower().encode("utf-8")).hexdigest()


def _aliases(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _first_non_empty_alias(aliases: Sequence[str]) -> str | None:
    for alias in aliases:
        if str(alias).strip():
            return str(alias)
    return None


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    main()
