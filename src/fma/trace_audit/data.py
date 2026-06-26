"""WebQSP loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class WebQSPLoader:
    """Load WebQSP-style JSON or JSONL files into raw question records."""

    def load(self, path: str | Path, *, max_records: int | None = None) -> list[dict[str, Any]]:
        source = Path(path)
        records = self._load_jsonl(source) if source.suffix.lower() == ".jsonl" else self._load_json(source)
        if max_records is not None:
            records = records[:max_records]
        return records

    def _load_json(self, path: Path) -> list[dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            for key in ("Questions", "questions", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [dict(row) for row in value if isinstance(row, dict)]
            return [dict(payload)]
        if isinstance(payload, list):
            return [dict(row) for row in payload if isinstance(row, dict)]
        raise ValueError(f"Unsupported WebQSP JSON payload in {path}.")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                value = json.loads(stripped)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number} must be a JSON object.")
                rows.append(value)
        return rows
