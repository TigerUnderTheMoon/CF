"""Validate a pre-materialized real_task_v3 GSM8K train JSONL/provenance pair."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_real_task_v3_gsm8k_source import (
    DECLARED_GSM8K_CONFIG,
    DECLARED_GSM8K_DATASET_ID,
    DECLARED_GSM8K_REVISION,
    DECLARED_GSM8K_SPLIT,
    file_sha256,
    validate_declared_jsonl_schema,
)


REQUIRED_PROVENANCE_FIELDS = (
    "full_revision",
    "generated_file_hash",
    "row_count",
    "row_order_policy",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate pre-materialized GSM8K source files for real_task_v3."
    )
    parser.add_argument("--jsonl-path", type=Path, required=True)
    parser.add_argument("--provenance-path", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        validate_pair(jsonl_path=args.jsonl_path, provenance_path=args.provenance_path)
    except Exception as exc:
        print(f"PREMATERIALIZED_VALIDATION_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("PREMATERIALIZED_VALIDATION_PASSED")


def validate_pair(*, jsonl_path: Path, provenance_path: Path) -> dict[str, Any]:
    rows = validate_declared_jsonl_schema(jsonl_path)
    provenance = _read_json(provenance_path)
    _validate_provenance(provenance, jsonl_path=jsonl_path, row_count=len(rows))
    return {
        "status": "PREMATERIALIZED_VALIDATION_PASSED",
        "row_count": len(rows),
        "jsonl_path": str(jsonl_path),
        "provenance_path": str(provenance_path),
    }


def _validate_provenance(
    provenance: Mapping[str, Any],
    *,
    jsonl_path: Path,
    row_count: int,
) -> None:
    missing = [key for key in REQUIRED_PROVENANCE_FIELDS if key not in provenance]
    if missing:
        raise ValueError(f"provenance missing required fields: {', '.join(missing)}")
    if provenance.get("full_revision") != DECLARED_GSM8K_REVISION:
        raise ValueError("full_revision mismatch")
    observed_hash = file_sha256(jsonl_path)
    if provenance.get("generated_file_hash") != observed_hash:
        raise ValueError("generated_file_hash mismatch")
    if int(provenance.get("row_count")) != row_count:
        raise ValueError("row_count mismatch")
    if provenance.get("row_order_policy") != "source_index equals raw HF row index":
        raise ValueError("row_order_policy mismatch")
    if "dataset_id" in provenance and provenance.get("dataset_id") != DECLARED_GSM8K_DATASET_ID:
        raise ValueError("dataset_id mismatch")
    if "config" in provenance and provenance.get("config") != DECLARED_GSM8K_CONFIG:
        raise ValueError("config mismatch")
    if "split" in provenance and provenance.get("split") != DECLARED_GSM8K_SPLIT:
        raise ValueError("split mismatch")


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


if __name__ == "__main__":
    main()
