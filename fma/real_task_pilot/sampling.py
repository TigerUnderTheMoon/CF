"""Deterministic sample manifest construction for the real-task pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


SOURCE_FIELDS = (
    "source_dataset",
    "source_config",
    "source_split",
    "source_index",
)


def stable_order_key(seed: int, task_type: str, index: int, question: str) -> str:
    payload = f"{seed}:{task_type}:{index}:{question}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_real_task_source_row(
    row: Mapping[str, Any],
    *,
    task_type: str,
    source_dataset: str,
    source_config: str,
    source_split: str,
    source_index: int,
) -> dict[str, Any]:
    """Normalize a HuggingFace benchmark row into the pilot source schema."""

    question = str(row.get("question") or "")
    reference = str(row.get("answer") or row.get("reference_answer") or "")
    task_id = str(row.get("id") or row.get("_id") or f"{task_type}-{source_split}-{source_index:05d}")
    aliases = row.get("aliases") if isinstance(row.get("aliases"), list) else []
    return {
        "source_dataset": source_dataset,
        "source_config": source_config,
        "source_split": source_split,
        "source_index": source_index,
        "task_id": task_id,
        "task_type": task_type,
        "question": question,
        "reference_answer": reference,
        "aliases": list(aliases),
    }


def build_sample_manifest(
    gsm8k_rows: Iterable[Mapping[str, Any]],
    hotpotqa_rows: Iterable[Mapping[str, Any]],
    *,
    seed: int,
    max_per_task: int = 200,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_task_rows("gsm8k", gsm8k_rows, seed, max_per_task))
    rows.extend(_task_rows("hotpotqa", hotpotqa_rows, seed, max_per_task))
    manifest = sorted(rows, key=lambda item: (item["task_type"], item["sample_id"]))
    manifest_hash = compute_manifest_hash(manifest)
    return [{**row, "manifest_hash": manifest_hash} for row in manifest]


def compute_manifest_hash(manifest: Iterable[Mapping[str, Any]]) -> str:
    rows = []
    for row in manifest:
        normalized = {key: value for key, value in row.items() if key != "manifest_hash"}
        rows.append(normalized)
    payload = json.dumps(rows, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_manifest_for_live_api(
    manifest: Iterable[Mapping[str, Any]],
    *,
    source_path: str | Path | None = None,
) -> list[str]:
    """Return blocking issues for live API stages."""

    errors: list[str] = []
    if source_path is not None and _is_fixture_path(Path(source_path)):
        errors.append("live API stages must not use tests/fixtures inputs")
    rows = list(manifest)
    if not rows:
        errors.append("live API manifest is empty")
        return errors
    hashes = {str(row.get("manifest_hash") or "") for row in rows}
    if len(hashes) != 1 or "" in hashes:
        errors.append("manifest_hash must be present and identical on every row")
    for index, row in enumerate(rows):
        missing = [
            field
            for field in (*SOURCE_FIELDS, "sample_id", "task_id", "task_type", "question", "reference_answer")
            if field not in row
        ]
        if missing:
            errors.append(f"row {index} missing required provenance fields: {', '.join(missing)}")
    return errors


def _task_rows(
    task_type: str,
    source_rows: Iterable[Mapping[str, Any]],
    seed: int,
    max_count: int,
) -> list[dict[str, Any]]:
    normalized = []
    for index, row in enumerate(source_rows):
        question = str(row.get("question") or row.get("context") or "")
        if task_type == "hotpotqa" and row.get("question"):
            question = str(row["question"])
        reference = str(row.get("reference_answer") or row.get("answer") or "")
        aliases = row.get("aliases") if isinstance(row.get("aliases"), list) else []
        source_index = int(row.get("source_index", index))
        normalized.append(
            {
                "sample_id": f"{task_type}-{source_index:05d}",
                "task_id": str(row.get("id") or row.get("_id") or f"{task_type}-{index:05d}"),
                "task_type": task_type,
                "question": question,
                "reference_answer": reference,
                "aliases": list(aliases),
                "manifest_order_key": stable_order_key(seed, task_type, source_index, question),
                "source_dataset": str(row.get("source_dataset") or task_type),
                "source_config": str(row.get("source_config") or ""),
                "source_split": str(row.get("source_split") or ""),
                "source_index": source_index,
            }
        )
    ordered = sorted(normalized, key=lambda item: item["manifest_order_key"])
    return ordered[:max_count]


def write_manifest(manifest: list[dict[str, Any]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _is_fixture_path(path: Path) -> bool:
    normalized = {part.lower() for part in path.parts}
    return "tests" in normalized and "fixtures" in normalized
