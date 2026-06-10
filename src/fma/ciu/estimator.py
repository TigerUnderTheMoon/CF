"""Phase 1 CIU estimation from paired original and masked replay traces."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_ORIGINAL_PATH = Path("outputs") / "reflection_traces.jsonl"
DEFAULT_INTERVENED_PATH = Path("outputs") / "counterfactual_results.jsonl"
DEFAULT_OUTPUT_PATH = Path("outputs") / "ciu_results.jsonl"
CIU_MIN = -1.0
CIU_MAX = 1.0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if stripped:
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number} is not valid JSON.") from exc
    return records


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def get_sample_id(record: dict[str, Any]) -> str:
    sample_id = record.get("sample_id") or record.get("task_id")
    if sample_id is None or str(sample_id) == "":
        raise ValueError("Record is missing both sample_id and task_id.")
    return str(sample_id)


def infer_task_type(record: dict[str, Any], sample_id: str) -> str:
    generation_config = record.get("generation_config") or {}
    task_type = record.get("task_type") or generation_config.get("dataset")
    if task_type:
        return str(task_type)

    prefix = re.split(r"[-_]", sample_id, maxsplit=1)[0]
    return prefix or "unknown"


def index_by_sample_id(records: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        sample_id = get_sample_id(record)
        if sample_id in indexed:
            raise ValueError(f"Duplicate {label} record for sample_id={sample_id!r}.")
        indexed[sample_id] = record
    return indexed


def coerce_binary_outcome(value: Any, field_name: str, sample_id: str) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float) and value in (0, 1, 0.0, 1.0):
        return float(value)
    raise ValueError(
        f"Outcome field {field_name!r} for sample_id={sample_id!r} must be boolean or 0/1."
    )


def require_outcome(
    record: dict[str, Any],
    field_names: tuple[str, ...],
    sample_id: str,
    label: str,
) -> float:
    for field_name in field_names:
        if field_name in record and record[field_name] is not None:
            return coerce_binary_outcome(record[field_name], field_name, sample_id)
    expected = ", ".join(field_names)
    raise ValueError(f"{label} record for sample_id={sample_id!r} lacks {expected}.")


def span_operation_type(span: dict[str, Any]) -> str:
    return str(
        span.get("operation_type")
        or span.get("reflection_type")
        or span.get("type")
        or "unknown"
    )


def span_start_token(span: dict[str, Any]) -> int:
    value = span.get("start_token", span.get("start_idx", 0))
    return max(0, int(value or 0))


def span_length(span: dict[str, Any]) -> int:
    if "span_length" in span:
        return max(0, int(span["span_length"] or 0))
    if "token_count" in span:
        return max(0, int(span["token_count"] or 0))
    if "start_token" in span and "end_token" in span:
        return max(0, int(span["end_token"] or 0) - int(span["start_token"] or 0))
    if "start_idx" in span and "end_idx" in span:
        return max(0, int(span["end_idx"] or 0) - int(span["start_idx"] or 0))
    return len(str(span.get("content") or "").split())


def trajectory_length(
    original_record: dict[str, Any],
    intervened_record: dict[str, Any],
    spans: list[dict[str, Any]],
) -> int:
    for field_name in ("trajectory_length", "original_token_count", "masked_trace_token_count"):
        for record in (original_record, intervened_record):
            value = record.get(field_name)
            if isinstance(value, int | float) and value > 0:
                return int(value)

    max_span_end = 0
    for span in spans:
        end_value = span.get("end_token", span.get("end_idx", 0))
        max_span_end = max(max_span_end, int(end_value or 0))
    word_count = len(str(original_record.get("reasoning_trace") or "").split())
    return max(1, max_span_end, word_count)


def relative_step_index(span: dict[str, Any], total_length: int) -> float:
    if "step_index" in span and span["step_index"] is not None:
        value = float(span["step_index"])
    else:
        value = span_start_token(span) / max(1, total_length)
    return min(1.0, max(0.0, value))


def compute_ciu_records(
    original_records: list[dict[str, Any]],
    intervened_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    intervened_by_id = index_by_sample_id(intervened_records, "intervened")
    ciu_records: list[dict[str, Any]] = []

    for original in original_records:
        sample_id = get_sample_id(original)
        if sample_id not in intervened_by_id:
            raise ValueError(f"No intervened record found for sample_id={sample_id!r}.")

        spans = list(original.get("reflection_spans") or original.get("metacognitive_spans") or [])
        if not spans:
            continue

        intervened = intervened_by_id[sample_id]
        original_outcome = require_outcome(
            original,
            ("correctness", "original_correctness", "original_outcome"),
            sample_id,
            "original",
        )
        intervened_outcome = require_outcome(
            intervened,
            (
                "counterfactual_correctness",
                "intervened_correctness",
                "counterfactual_outcome",
                "intervened_outcome",
            ),
            sample_id,
            "intervened",
        )
        ciu = original_outcome - intervened_outcome
        if not (CIU_MIN - 1e-9 <= ciu <= CIU_MAX + 1e-9):
            ciu = max(CIU_MIN, min(CIU_MAX, ciu))

        total_length = trajectory_length(original, intervened, spans)
        task_type = infer_task_type(original, sample_id)
        for span_idx, span in enumerate(spans):
            ciu_records.append(
                {
                    "sample_id": sample_id,
                    "span_idx": span_idx,
                    "operation_type": span_operation_type(span),
                    "ciu": ciu,
                    "original_outcome": original_outcome,
                    "intervened_outcome": intervened_outcome,
                    "span_length": span_length(span),
                    "task_type": task_type,
                    "step_index": relative_step_index(span, total_length),
                    "trajectory_length": total_length,
                }
            )

    return ciu_records


def estimate_ciu_file(
    original_path: Path,
    intervened_path: Path,
    output_path: Path,
) -> list[dict[str, Any]]:
    original_records = read_jsonl(original_path)
    intervened_records = read_jsonl(intervened_path)
    ciu_records = compute_ciu_records(original_records, intervened_records)
    write_jsonl(ciu_records, output_path)
    return ciu_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute Phase 1 CIU records from paired JSONL inputs."
    )
    parser.add_argument("--original", type=Path, default=DEFAULT_ORIGINAL_PATH)
    parser.add_argument("--intervened", type=Path, default=DEFAULT_INTERVENED_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = estimate_ciu_file(args.original, args.intervened, args.output)
    print(f"Wrote {len(records)} CIU records to {args.output}")


if __name__ == "__main__":
    main()
