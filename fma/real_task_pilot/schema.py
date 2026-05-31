"""Schema validation for real-task observable reflection traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "real_task_trace.schema.json"
REAL_TASK_TRACE_SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
REAL_TASK_API_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["observable_trace", "final_answer"],
    "properties": {
        "observable_trace": {"type": "string", "minLength": 1},
        "final_answer": {"type": "string"},
    },
}


def structured_output_text_format() -> dict[str, Any]:
    """Return the Responses API text.format payload for Structured Outputs."""

    return {
        "type": "json_schema",
        "name": "real_task_reflection_trace",
        "strict": True,
        "schema": REAL_TASK_API_OUTPUT_SCHEMA,
    }


def validate_trace_record(record: Mapping[str, Any]) -> list[str]:
    """Return validation errors without requiring callers to catch exceptions."""

    try:
        import jsonschema
    except ImportError:  # pragma: no cover - fallback for minimal installs
        return _minimal_validate(record)

    validator = jsonschema.Draft202012Validator(REAL_TASK_TRACE_SCHEMA)
    errors = []
    for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
        path = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{path}: {error.message}")
    return errors


def _minimal_validate(record: Mapping[str, Any]) -> list[str]:
    required = REAL_TASK_TRACE_SCHEMA["required"]
    errors = [f"{field}: missing required field" for field in required if field not in record]
    if record.get("task_type") not in {"gsm8k", "hotpotqa"}:
        errors.append("task_type: must be gsm8k or hotpotqa")
    spans = record.get("reflection_spans")
    if not isinstance(spans, list) or not spans:
        errors.append("reflection_spans: must be a non-empty list")
    return errors
