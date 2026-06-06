"""Shared helper functions used across FMA subpackages."""

from __future__ import annotations

from typing import Any, Mapping


def trace_id_for_record(record: Mapping[str, Any], index: int) -> str:
    return str(record.get("trace_id") or record.get("sample_id") or record.get("task_id") or f"trace_{index:03d}")
