"""Small JSON helpers shared by FMA scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Load JSONL records or a JSON array of objects from a UTF-8 file."""
    record_path = Path(path)
    if record_path.suffix.lower() == ".json":
        try:
            value = json.loads(record_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            value = None
        if isinstance(value, list):
            if not all(isinstance(record, dict) for record in value):
                raise ValueError(f"{record_path} must contain a JSON array of objects.")
            return list(value)

    records: list[dict[str, Any]] = []
    with record_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{record_path}:{line_number} is not valid JSON.") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{record_path}:{line_number} must contain a JSON object.")
            records.append(value)
    return records


def write_records(records: list[dict[str, Any]], path: str | Path) -> None:
    """Write JSONL records as UTF-8 with deterministic key ordering."""
    record_path = Path(path)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with record_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
