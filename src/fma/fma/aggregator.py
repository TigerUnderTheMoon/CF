"""Task-conditioned Phase 1 FMA aggregation."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_CIU_PATH = Path("outputs") / "ciu_results.jsonl"
DEFAULT_OUTPUT_PATH = Path("outputs") / "fma_scores.jsonl"
DISTRIBUTION_BUCKETS = ("high", "medium", "low", "negative")


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


def bucket_ciu_distribution(ciu_results: list[dict[str, Any]]) -> dict[str, int]:
    buckets = {bucket: 0 for bucket in DISTRIBUTION_BUCKETS}
    for record in ciu_results:
        ciu = float(record["ciu"])
        if ciu < 0.0:
            buckets["negative"] += 1
        elif ciu < 0.1:
            buckets["low"] += 1
        elif ciu <= 0.5:
            buckets["medium"] += 1
        else:
            buckets["high"] += 1
    return buckets


def normalize_within_task(records: list[dict[str, Any]]) -> None:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_task[str(record["task_distribution"])].append(record)

    for task_records in by_task.values():
        means = [float(record["mean_ciu"]) for record in task_records]
        min_mean = min(means)
        max_mean = max(means)
        if max_mean == min_mean:
            for record in task_records:
                record["fma_score"] = 0.5
            continue
        for record in task_records:
            record["fma_score"] = (float(record["mean_ciu"]) - min_mean) / (max_mean - min_mean)


def aggregate_fma(ciu_results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in ciu_results:
        task_type = str(record.get("task_type") or "unknown")
        operation_type = str(record.get("operation_type") or "unknown")
        grouped[(task_type, operation_type)].append(float(record["ciu"]))

    fma_scores: list[dict[str, Any]] = []
    for (task_type, operation_type), scores in sorted(grouped.items()):
        fma_scores.append(
            {
                "span_type": operation_type,
                "task_distribution": task_type,
                "fma_score": 0.0,
                "mean_ciu": float(statistics.fmean(scores)),
                "std_ciu": float(statistics.pstdev(scores)) if len(scores) > 1 else 0.0,
                "sample_count": len(scores),
            }
        )

    if fma_scores:
        normalize_within_task(fma_scores)

    return fma_scores, bucket_ciu_distribution(ciu_results)


def aggregate_fma_file(ciu_path: Path, output_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    ciu_results = read_jsonl(ciu_path)
    fma_scores, distribution = aggregate_fma(ciu_results)
    write_jsonl(fma_scores, output_path)
    return fma_scores, distribution


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate Phase 1 CIU results into task-conditioned FMA scores.")
    parser.add_argument("--input", type=Path, default=DEFAULT_CIU_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fma_scores, distribution = aggregate_fma_file(args.input, args.output)
    print(json.dumps({"fma_records": len(fma_scores), "distribution": distribution}, sort_keys=True))


if __name__ == "__main__":
    main()
