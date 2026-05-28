"""Lightweight Phase 1 attribution metrics."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fma.fma.aggregator import bucket_ciu_distribution, read_jsonl


DEFAULT_CIU_PATH = Path("outputs") / "ciu_results.jsonl"
DEFAULT_FMA_PATH = Path("outputs") / "fma_scores.jsonl"
DEFAULT_REPORT_PATH = Path("outputs") / "phase1_eval_report.json"
TOP_K_PCTS = (10, 25, 50)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def fma_lookup(fma_scores: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    lookup: dict[tuple[str, str], float] = {}
    for record in fma_scores:
        key = (str(record.get("task_distribution") or "unknown"), str(record.get("span_type") or "unknown"))
        lookup[key] = float(record["fma_score"])
    return lookup


def ciu_with_fma_scores(
    ciu_results: list[dict[str, Any]],
    fma_scores: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = fma_lookup(fma_scores)
    joined: list[dict[str, Any]] = []
    for record in ciu_results:
        key = (str(record.get("task_type") or "unknown"), str(record.get("operation_type") or "unknown"))
        if key not in lookup:
            continue
        joined.append({**record, "fma_score": lookup[key]})
    return joined


def intervention_sensitivity(
    ciu_results: list[dict[str, Any]],
    fma_scores: list[dict[str, Any]],
) -> dict[str, float | None]:
    joined = ciu_with_fma_scores(ciu_results, fma_scores)
    joined.sort(key=lambda record: float(record["fma_score"]), reverse=True)

    drops: dict[str, float | None] = {}
    for pct in TOP_K_PCTS:
        key = f"top_{pct}pct_drop"
        if len(joined) < 2:
            drops[key] = None
            continue
        group_size = max(1, math.ceil(len(joined) * pct / 100.0))
        top_group = joined[:group_size]
        bottom_group = joined[-group_size:]
        top_success = mean([float(record["intervened_outcome"]) for record in top_group])
        bottom_success = mean([float(record["intervened_outcome"]) for record in bottom_group])
        if top_success is None or bottom_success is None:
            drops[key] = None
        else:
            drops[key] = bottom_success - top_success
    return drops


def pearson_with_p_value(x_values: list[float], y_values: list[float]) -> tuple[float | None, float | None]:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return None, None

    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    x_diffs = [value - x_mean for value in x_values]
    y_diffs = [value - y_mean for value in y_values]
    x_ss = sum(value * value for value in x_diffs)
    y_ss = sum(value * value for value in y_diffs)
    if x_ss == 0.0 or y_ss == 0.0:
        return None, None

    numerator = sum(x_diff * y_diff for x_diff, y_diff in zip(x_diffs, y_diffs, strict=True))
    r_value = numerator / math.sqrt(x_ss * y_ss)
    r_value = max(-1.0, min(1.0, r_value))

    if abs(r_value) == 1.0:
        return r_value, 0.0
    if len(x_values) <= 3:
        return r_value, None

    fisher_z = 0.5 * math.log((1.0 + r_value) / (1.0 - r_value))
    z_score = abs(fisher_z) * math.sqrt(len(x_values) - 3)
    p_value = math.erfc(z_score / math.sqrt(2.0))
    return r_value, p_value


def utility_calibration(ciu_results: list[dict[str, Any]]) -> dict[str, float | str | None]:
    ciu_values = [float(record["ciu"]) for record in ciu_results]
    span_lengths = [float(record["span_length"]) for record in ciu_results]
    step_indices = [float(record["step_index"]) for record in ciu_results]

    length_r, length_p = pearson_with_p_value(ciu_values, span_lengths)
    step_r, step_p = pearson_with_p_value(ciu_values, step_indices)

    if length_r is None:
        status = "insufficient or constant span length data"
    elif abs(length_r) < 0.1:
        status = "weak length confound signal"
    else:
        status = "length confound signal present"

    return {
        "pearson_ciu_vs_span_length": length_r,
        "pearson_ciu_vs_step_index": step_r,
        "p_value": length_p,
        "step_index_p_value": step_p,
        "status": status,
    }


def dataset_counts(ciu_results: list[dict[str, Any]]) -> dict[str, int]:
    samples_by_task: dict[str, set[str]] = defaultdict(set)
    for record in ciu_results:
        task_type = str(record.get("task_type") or "unknown")
        samples_by_task[task_type].add(str(record.get("sample_id") or ""))
    return {task_type: len(samples) for task_type, samples in sorted(samples_by_task.items())}


def build_phase1_eval_report(
    ciu_results: list[dict[str, Any]],
    fma_scores: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "experiment": "phase1_attribution",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_counts": dataset_counts(ciu_results),
        "fma_distribution": bucket_ciu_distribution(ciu_results),
        "intervention_sensitivity": intervention_sensitivity(ciu_results, fma_scores),
        "utility_calibration": utility_calibration(ciu_results),
        "notes": "Matching and DR deferred to Phase 2",
    }


def write_phase1_eval_report(ciu_path: Path, fma_path: Path, output_path: Path) -> dict[str, Any]:
    ciu_results = read_jsonl(ciu_path)
    fma_scores = read_jsonl(fma_path)
    report = build_phase1_eval_report(ciu_results, fma_scores)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the Phase 1 attribution evaluation report.")
    parser.add_argument("--ciu", type=Path, default=DEFAULT_CIU_PATH)
    parser.add_argument("--fma", type=Path, default=DEFAULT_FMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = write_phase1_eval_report(args.ciu, args.fma, args.output)
    print(json.dumps({"output": str(args.output), "keys": sorted(report.keys())}, sort_keys=True))


if __name__ == "__main__":
    main()
