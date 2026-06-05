"""Audit the real_task_v3 preregistration package without live execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.validation_v3 import (
    REAL_TASK_V3_PREREGISTRATION_ONLY,
    audit_v3_config_contract,
    build_v3_route_manifests,
)
from scripts.prepare_real_task_v3_gsm8k_source import (
    DECLARED_GSM8K_REVISION,
    SOURCE_PREPARATION_FAILURE_STATUS,
    file_sha256,
    provenance_path_for,
    validate_declared_revision,
)


REAL_TASK_V3_MANIFEST_GENERATION_ONLY = "REAL_TASK_V3_MANIFEST_GENERATION_ONLY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the real_task_v3 preregistration boundary."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "real_task_v3_validation.yaml",
    )
    parser.add_argument(
        "--task-scope",
        default=REAL_TASK_V3_PREREGISTRATION_ONLY,
    )
    parser.add_argument(
        "--allow-manifest-generation-only",
        action="store_true",
        help="Write only v3 split manifests and non-overlap audits.",
    )
    parser.add_argument(
        "--gsm8k-extra-source",
        type=Path,
        help="Optional fresh GSM8K source JSON/JSONL added after the local test split.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    if args.allow_manifest_generation_only:
        _assert_manifest_generation_boundary(config, task_scope=args.task_scope)
        result = _write_manifest_generation_package(
            config,
            gsm8k_extra_source=args.gsm8k_extra_source,
        )
        print(json.dumps(result, sort_keys=True))
    else:
        _assert_current_task_boundary(config, task_scope=args.task_scope)
        audit = audit_v3_config_contract(config)
        print(json.dumps(audit, sort_keys=True))


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
) -> dict[str, Any]:
    output_root = Path(
        _mapping(config.get("experiment")).get("output_dir", "outputs/real_task_v3")
    )
    input_source_provenance = {}
    if gsm8k_extra_source is not None:
        input_source_provenance["gsm8k_extra_source"] = _load_gsm8k_extra_source_metadata(
            gsm8k_extra_source
        )
    manifests, audit = build_v3_route_manifests(
        _load_source_rows(gsm8k_extra_source=gsm8k_extra_source),
        config=config,
        split_sample_counts=_split_sample_counts(config),
        overlap_sources=_load_overlap_sources(),
    )
    if input_source_provenance:
        audit["input_source_provenance"] = input_source_provenance
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_paths = {}
    for split_name, rows in manifests.items():
        path = output_root / f"{split_name}_manifest.jsonl"
        write_records(rows, path)
        manifest_paths[split_name] = str(path)
    audit_path = output_root / "manifest_overlap_audit.json"
    _write_json(audit_path, audit)
    return {
        "status": audit["status"],
        "current_status_remains": "PILOT_BLOCKED",
        "manifest_paths": manifest_paths,
        "audit_path": str(audit_path),
        "input_source_provenance": input_source_provenance,
        "no_api_run": True,
        "no_replay": True,
        "no_scoring": True,
        "no_prm_filtering_claim": True,
    }


def _load_source_rows(*, gsm8k_extra_source: Path | None) -> dict[str, list[dict[str, Any]]]:
    gsm8k_rows = load_records(Path("data") / "real_task_pilot" / "gsm8k_test.jsonl")
    if gsm8k_extra_source is not None:
        gsm8k_rows.extend(load_records(gsm8k_extra_source))
    return {
        "gsm8k": gsm8k_rows,
        "hotpotqa": load_records(Path("data") / "real_task_pilot" / "hotpotqa_validation.jsonl"),
    }


def _load_gsm8k_extra_source_metadata(source_path: Path) -> dict[str, Any]:
    provenance_path = provenance_path_for(source_path)
    if not provenance_path.exists():
        raise RuntimeError(
            f"{SOURCE_PREPARATION_FAILURE_STATUS}: missing provenance sidecar {provenance_path}"
        )
    provenance = _read_json(provenance_path)
    revision = validate_declared_revision(
        str(provenance.get("full_revision") or provenance.get("revision") or "")
    )
    resolved_revision = validate_declared_revision(
        str(provenance.get("resolved_revision") or "")
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
    return {
        "source_path": str(source_path),
        "provenance_path": str(provenance_path),
        "dataset_id": provenance.get("dataset_id"),
        "config": provenance.get("config"),
        "split": provenance.get("split"),
        "full_revision": revision,
        "revision": revision,
        "resolved_revision": resolved_revision,
        "row_count": provenance.get("row_count"),
        "row_order_policy": provenance.get("row_order_policy"),
        "aggregate_source_hash": provenance.get("aggregate_source_hash"),
        "generated_file_hash": observed_hash,
        "generated_jsonl_sha256": observed_hash,
        "observed_previous_gsm8k_sources": provenance.get("observed_previous_gsm8k_sources")
        or provenance.get("previous_gsm8k_sources")
        or [],
    }


def _load_overlap_sources() -> dict[str, list[dict[str, Any]]]:
    paths = {
        "real_task_pilot": Path("outputs") / "real_task_pilot" / "sample_manifest.json",
        "s_fma_v2": Path("outputs") / "s_fma_v2_fresh_holdout" / "fresh_manifest.json",
        "s_fma_v2_1": Path("outputs") / "s_fma_v2_1_fresh_holdout" / "fresh_manifest.json",
        "s_fma_v2_2": Path("outputs") / "s_fma_v2_2_fresh_holdout" / "fresh_manifest.json",
    }
    return {name: load_records(path) for name, path in paths.items() if path.exists()}


def _split_sample_counts(config: Mapping[str, Any]) -> dict[str, Mapping[str, int]]:
    splits = _mapping(config.get("splits"))
    return {
        split_name: _mapping(_mapping(splits.get(split_name)).get("sample_count_by_task"))
        for split_name in ("smoke", "dev_calibration", "locked_validation")
    }


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
