"""Run taxonomy-driven stratified FMA evaluation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.eval.stratified_eval import BucketMetrics, StratifiedEvaluator
from fma.io import load_records
from fma.taxonomy import ReflectionTaxonomizer
from fma.types import (
    AttributionRecord,
    ReflectionAnnotation,
    ReflectionCategory,
    ReflectionTrace,
    StratifiedInput,
)
from fma.visualization.stratified_plots import (
    plot_category_distribution,
    plot_locality_sensitivity,
    plot_stability_scatter,
    plot_utility_by_category,
)


DEFAULT_ATTRIBUTION_PATH = Path("outputs") / "attribution_records.jsonl"
FALLBACK_CIU_PATH = Path("outputs") / "ciu_results.jsonl"
DEFAULT_TRACE_PATH = Path("outputs") / "reflection_traces.jsonl"
DEFAULT_REPORT_PATH = Path("outputs") / "stratified_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stratified FMA evaluation.")
    parser.add_argument("--attribution-records", type=Path, default=DEFAULT_ATTRIBUTION_PATH)
    parser.add_argument("--reflection-traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without writing files.")
    return parser.parse_args()


def coerce_float(value: Any, fallback: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    if not math.isfinite(number):
        return fallback
    return number


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def trace_id_for_record(record: dict[str, Any], index: int) -> str:
    return str(record.get("trace_id") or record.get("sample_id") or record.get("task_id") or f"trace_{index:03d}")


def first_reflection_text(record: dict[str, Any]) -> str:
    value = record.get("reflection_text")
    if isinstance(value, str):
        return value
    chain = record.get("reflection_chain")
    if isinstance(chain, list):
        texts = [
            str(step.get("text"))
            for step in chain
            if isinstance(step, dict) and step.get("text") is not None
        ]
        if texts:
            return " ".join(texts)
    spans = record.get("reflection_spans") or record.get("metacognitive_spans") or []
    if isinstance(spans, list) and spans and isinstance(spans[0], dict):
        content = spans[0].get("content")
        if isinstance(content, str):
            return content
    return str(record.get("reasoning_trace") or "")


def infer_intervention_magnitude(record: dict[str, Any]) -> float:
    if "intervention_magnitude" in record:
        return clamp(coerce_float(record["intervention_magnitude"]), 0.0, 1.0)
    spans = record.get("reflection_spans") or record.get("metacognitive_spans") or []
    span_length = 0
    if isinstance(spans, list) and spans and isinstance(spans[0], dict):
        span = spans[0]
        if "start_token" in span and "end_token" in span:
            span_length = max(0, int(span.get("end_token") or 0) - int(span.get("start_token") or 0))
        else:
            span_length = len(str(span.get("content") or "").split())
    token_count = max(1, len(str(record.get("reasoning_trace") or "").split()))
    return clamp(span_length / token_count, 0.0, 1.0)


def trace_from_raw(record: dict[str, Any], index: int) -> ReflectionTrace:
    trace_id = trace_id_for_record(record, index)
    return ReflectionTrace(
        trace_id=trace_id,
        reflection_text=first_reflection_text(record),
        task_id=str(record.get("task_id") or trace_id),
        task_difficulty=int(clamp(coerce_float(record.get("task_difficulty"), 3.0), 1.0, 5.0)),
        intervention_magnitude=infer_intervention_magnitude(record),
        locality_score=clamp(coerce_float(record.get("locality_score"), 1.0), 0.0, 1.0),
    )


def annotation_from_raw(record: dict[str, Any], trace: ReflectionTrace, taxonomizer: ReflectionTaxonomizer) -> ReflectionAnnotation:
    category_name = record.get("category")
    if category_name:
        category = ReflectionCategory[str(category_name).strip().upper()]
        confidence = clamp(coerce_float(record.get("taxonomy_confidence"), 0.0), 0.0, 1.0)
        rationale = str(record.get("taxonomy_rationale") or "precomputed taxonomy label")[:200]
        return ReflectionAnnotation(category=category, confidence=confidence, rationale=rationale)
    return taxonomizer.classify(trace)


def attribution_score(record: dict[str, Any]) -> float:
    for field_name in ("attribution_score", "fma", "fma_score", "ciu"):
        if field_name in record:
            return clamp(coerce_float(record[field_name]), 0.0, 1.0)
    return 0.0


def utility_delta(record: dict[str, Any]) -> float:
    for field_name in ("utility_delta", "ciu", "reflection_ciu"):
        if field_name in record:
            return coerce_float(record[field_name])
    original = record.get("original_outcome")
    intervened = record.get("intervened_outcome")
    if original is not None and intervened is not None:
        return coerce_float(original) - coerce_float(intervened)
    return 0.0


def build_inputs(
    attribution_path: Path,
    trace_path: Path,
) -> tuple[StratifiedInput, list[ReflectionAnnotation], list[str]]:
    warnings: list[str] = []
    raw_traces = load_records(trace_path)
    taxonomizer = ReflectionTaxonomizer()
    traces: dict[str, ReflectionTrace] = {}
    annotations: dict[str, ReflectionAnnotation] = {}
    for index, raw_trace in enumerate(raw_traces):
        trace = trace_from_raw(raw_trace, index)
        traces[trace.trace_id] = trace
        annotations[trace.trace_id] = annotation_from_raw(raw_trace, trace, taxonomizer)

    raw_attributions = load_records(attribution_path)
    records: list[AttributionRecord] = []
    for index, raw_record in enumerate(raw_attributions):
        trace_id = trace_id_for_record(raw_record, index)
        trace = traces.get(trace_id)
        is_local = bool(raw_record.get("is_local", trace.locality_score >= 0.8 if trace else True))
        records.append(
            AttributionRecord(
                trace_id=trace_id,
                attribution_score=attribution_score(raw_record),
                utility_delta=utility_delta(raw_record),
                intervention_type=str(raw_record.get("intervention_type") or "masking"),
                is_local=is_local,
            )
        )

    if not records:
        warnings.append("no attribution records loaded")
    return StratifiedInput(records=records, annotations=annotations, traces=traces), list(annotations.values()), warnings


def resolve_attribution_path(path: Path) -> tuple[Path, list[str]]:
    if path.exists():
        return path, []
    if path == DEFAULT_ATTRIBUTION_PATH and FALLBACK_CIU_PATH.exists():
        return FALLBACK_CIU_PATH, [
            f"{DEFAULT_ATTRIBUTION_PATH} not found; using {FALLBACK_CIU_PATH} as Phase 1 attribution input."
        ]
    return path, []


def metrics_to_report(metrics: BucketMetrics, warning_path: str, warnings: list[str]) -> dict[str, Any]:
    if metrics.status == "insufficient_samples":
        return {
            "status": "insufficient_samples",
            "bucket_size": metrics.n_samples,
            "required": metrics.required,
            "metrics": None,
        }
    return {
        "status": "ok",
        "frequency": metrics.n_samples,
        "mean_utility_delta": clean_number(metrics.mean_utility_delta, f"{warning_path}.mean_utility_delta", warnings),
        "mean_intervention_impact": clean_number(
            metrics.mean_attribution_score,
            f"{warning_path}.mean_intervention_impact",
            warnings,
        ),
        "utility_variance": clean_number(metrics.utility_variance, f"{warning_path}.utility_variance", warnings),
        "attribution_consistency": clean_number(
            metrics.attribution_stability,
            f"{warning_path}.attribution_consistency",
            warnings,
        ),
        "intervention_sensitivity": clean_number(
            metrics.intervention_sensitivity,
            f"{warning_path}.intervention_sensitivity",
            warnings,
        ),
    }


def clean_number(value: float, path: str, warnings: list[str]) -> float | None:
    if not math.isfinite(float(value)):
        warnings.append(f"{path} is NaN or infinite; wrote null.")
        return None
    return float(value)


def locality_sensitivity(
    category: ReflectionCategory,
    inputs: StratifiedInput,
) -> float:
    traces = inputs.traces or {}
    local_values: list[float] = []
    global_values: list[float] = []
    category_values: list[float] = []
    for record in inputs.records:
        annotation = inputs.annotations.get(record.trace_id)
        trace = traces.get(record.trace_id)
        if annotation is None or trace is None or annotation.category is not category:
            continue
        category_values.append(record.utility_delta)
        if trace.locality_score >= 0.8:
            local_values.append(record.utility_delta)
        elif trace.locality_score < 0.4:
            global_values.append(record.utility_delta)

    if not local_values or not global_values:
        return float("nan")
    denominator = float(np.std(np.asarray(category_values, dtype=float))) + 1e-6
    return float(abs(np.mean(local_values) - np.mean(global_values)) / denominator)


def build_report(
    inputs: StratifiedInput,
    metrics: dict[str, dict[str, BucketMetrics]],
    seed: int,
    warnings: list[str],
    evaluator: StratifiedEvaluator,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "meta": {
            "n_records": len(inputs.records),
            "n_categories": len(ReflectionCategory),
            "timestamp": datetime.now().replace(microsecond=0).isoformat(),
            "seed": seed,
        },
        "per_category": {},
        "per_difficulty": {},
        "per_intervention": {},
        "per_locality": {},
        "per_length": {},
    }

    for category_name, bucket_metrics in metrics["category"].items():
        warning_path = f"per_category.{category_name}"
        category_report = metrics_to_report(bucket_metrics, warning_path, warnings)
        category = ReflectionCategory[category_name]
        if bucket_metrics.status == "ok":
            category_report["locality_sensitivity"] = clean_number(
                locality_sensitivity(category, inputs),
                f"{warning_path}.locality_sensitivity",
                warnings,
            )
        report["per_category"][category_name] = category_report

    dimension_map = {
        "difficulty": "per_difficulty",
        "intervention": "per_intervention",
        "locality": "per_locality",
        "trace_length": "per_length",
    }
    for dimension, report_key in dimension_map.items():
        for bucket_name, bucket_metrics in metrics[dimension].items():
            report[report_key][bucket_name] = metrics_to_report(
                bucket_metrics,
                f"{report_key}.{bucket_name}",
                warnings,
            )

    report["instability_cases"] = evaluator.get_instability_cases(inputs)
    report["top_categories_by_utility"] = top_categories(report["per_category"], "mean_utility_delta")
    report["locality_sensitive_categories"] = top_categories(report["per_category"], "locality_sensitivity")
    report["warnings"] = sorted(set(warnings))
    return report


def top_categories(per_category: dict[str, dict[str, Any]], metric_name: str) -> list[str]:
    candidates = [
        (name, metrics.get(metric_name))
        for name, metrics in per_category.items()
        if metrics.get(metric_name) is not None and int(metrics.get("frequency") or 0) > 0
    ]
    candidates.sort(key=lambda item: item[1], reverse=True)
    return [name for name, _ in candidates[:3]]


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    attribution_path, path_warnings = resolve_attribution_path(args.attribution_records)
    inputs, annotations, input_warnings = build_inputs(attribution_path, args.reflection_traces)
    warnings = [*path_warnings, *input_warnings]
    evaluator = StratifiedEvaluator(random_seed=args.seed)
    metrics = evaluator.evaluate(inputs)
    report = build_report(inputs, metrics, args.seed, warnings, evaluator)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "attribution_records": str(attribution_path),
                    "reflection_traces": str(args.reflection_traces),
                    "output": str(args.output),
                    "n_records": len(inputs.records),
                    "warnings": report["warnings"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return report

    write_report(report, args.output)
    plot_category_distribution(annotations)
    plot_utility_by_category(report)
    plot_stability_scatter(report)
    plot_locality_sensitivity(report)
    print(f"Wrote stratified report to {args.output}")
    return report


def main() -> None:
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
