"""Run taxonomy-driven stratified FMA evaluation."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.eval.stratified_eval import BucketMetrics, MIN_BUCKET_SIZE, StratifiedEvaluator
from fma.eval.attribution_utility_correlation import evaluate_attribution_utility_correlation
from fma.eval.counterfactual_attribution import (
    analyze_redundancy,
    compute_faithfulness_metrics,
    compute_necessity_scores,
    run_minimal_subset_analysis,
)
from fma.eval.functional_validity import evaluate_functional_validity, utility_bucket_warnings
from fma.eval.utility_annotation import (
    AttributionAlignment,
    UtilityAnnotation,
    annotate_utility_records,
    write_utility_annotations,
)
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
from fma.visualization.validity_plots import plot_validity_suite


DEFAULT_ATTRIBUTION_PATH = Path("outputs") / "attribution_records.jsonl"
FALLBACK_CIU_PATH = Path("outputs") / "ciu_results.jsonl"
DEFAULT_TRACE_PATH = Path("outputs") / "reflection_traces.jsonl"
DEFAULT_FUNCTIONAL_TRACE_PATH = Path("data") / "traces" / "synthetic_100x8.json"
DEFAULT_REPORT_PATH = Path("outputs") / "stratified_report.json"
DEFAULT_UTILITY_ANNOTATIONS_PATH = Path("outputs") / "utility_annotations.jsonl"
DEFAULT_FUNCTIONAL_VALIDITY_PATH = Path("outputs") / "functional_validity_report.json"
DEFAULT_ATTRIBUTION_UTILITY_PATH = Path("outputs") / "attribution_utility_correlation.json"
DEFAULT_FIGURE_DIR = Path("outputs") / "figures"
LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stratified FMA evaluation.")
    parser.add_argument("--attribution-records", type=Path, default=DEFAULT_ATTRIBUTION_PATH)
    parser.add_argument("--reflection-traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--functional-traces", type=Path, default=DEFAULT_FUNCTIONAL_TRACE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--utility-annotations-output", type=Path, default=DEFAULT_UTILITY_ANNOTATIONS_PATH)
    parser.add_argument("--functional-validity-output", type=Path, default=DEFAULT_FUNCTIONAL_VALIDITY_PATH)
    parser.add_argument("--attribution-utility-output", type=Path, default=DEFAULT_ATTRIBUTION_UTILITY_PATH)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--counterfactual-utility-threshold", type=float, default=0.9)
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


def has_valid_stratified_rows(inputs: StratifiedInput) -> bool:
    """Return whether attribution rows overlap trace annotations."""
    return any(record.trace_id in inputs.annotations for record in inputs.records)


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
            "utility_status": metrics.utility_status,
            "necessity_status": metrics.necessity_status,
            "redundancy_status": metrics.redundancy_status,
            "faithfulness_status": metrics.faithfulness_status,
            "bucket_size": metrics.n_samples,
            "required": metrics.required,
            "utility_required": metrics.utility_required,
            "metrics": None,
        }
    return {
        "status": "ok",
        "utility_status": metrics.utility_status,
        "necessity_status": metrics.necessity_status,
        "redundancy_status": metrics.redundancy_status,
        "faithfulness_status": metrics.faithfulness_status,
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
        "utility_required": metrics.utility_required,
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
        "necessity_buckets": {},
        "redundancy_buckets": {},
        "faithfulness_buckets": {},
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
        "necessity": "necessity_buckets",
        "redundancy": "redundancy_buckets",
        "faithfulness": "faithfulness_buckets",
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


def resolve_functional_trace_path(path: Path, fallback_path: Path) -> tuple[Path, list[str]]:
    if path.exists():
        return path, []
    if fallback_path.exists():
        return fallback_path, [
            f"{path} not found; using {fallback_path} for functional validity annotations."
        ]
    return path, []


def build_functional_outputs(
    trace_path: Path,
    attribution_path: Path,
) -> tuple[list[UtilityAnnotation], dict[str, Any], dict[str, Any]]:
    traces = load_records(trace_path)
    attributions = load_records(attribution_path)
    annotations = annotate_utility_records(traces, attributions)
    functional_report = evaluate_functional_validity(annotations)
    correlation_report = evaluate_attribution_utility_correlation(annotations)
    return annotations, functional_report, correlation_report


def build_utility_warnings(
    annotations: list[UtilityAnnotation],
    functional_report: dict[str, Any],
    min_bucket_size: int = 5,
) -> list[str]:
    warnings = utility_bucket_warnings(annotations, min_bucket_size=min_bucket_size)
    distribution = functional_report["utility_distribution"]
    if float(distribution.get("spurious_ratio", 0.0)) > 0.25:
        warnings.append("high spurious utility ratio exceeds 0.25.")

    alignment_metrics = functional_report["alignment_metrics"]
    if float(alignment_metrics.get("misattribution_rate", 0.0)) > 0.35:
        warnings.append("attribution mismatch spike: global misattribution rate exceeds 0.35.")

    grouped: dict[str, list[UtilityAnnotation]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation.intervention_type or "unknown"].append(annotation)
    for intervention, group in sorted(grouped.items()):
        if len(group) < min_bucket_size:
            continue
        incorrect = sum(
            1
            for annotation in group
            if annotation.attribution_alignment is AttributionAlignment.INCORRECT
        )
        mismatch_rate = incorrect / len(group)
        if mismatch_rate > 0.35:
            warnings.append(
                f"attribution mismatch spike for {intervention}: {mismatch_rate:.3f} exceeds 0.35."
            )
    return sorted(set(warnings))


def build_counterfactual_report_sections(
    traces: list[dict[str, Any]],
    annotations: list[UtilityAnnotation],
    utility_threshold: float,
) -> tuple[dict[str, Any], list[str]]:
    """Build Phase 5 report sections for the stratified runner."""
    necessity_scores = compute_necessity_scores(annotations)
    faithfulness = compute_faithfulness_metrics(necessity_scores)
    redundancy = analyze_redundancy(annotations, necessity_scores, traces=traces)
    minimal_subsets = run_minimal_subset_analysis(annotations, utility_threshold=utility_threshold)

    necessity_values = [score.necessity for score in necessity_scores]
    compression_values = [result.compression_ratio for result in minimal_subsets]
    sections: dict[str, Any] = {
        "necessity_distribution_summary": _numeric_summary(necessity_values),
        "necessity_buckets": _rank_bucket_table(
            necessity_scores,
            value_fn=lambda score: score.necessity,
            metric_fn=lambda score: score.necessity,
            bucket_names=("q1", "q2", "q3", "q4"),
            status_name="necessity_status",
        ),
        "redundancy_buckets": _rank_bucket_table(
            redundancy,
            value_fn=lambda result: result.redundancy_ratio,
            metric_fn=lambda result: result.redundancy_ratio,
            bucket_names=("t1", "t2", "t3"),
            status_name="redundancy_status",
        ),
        "faithfulness_correlation_summary": {
            "pearson": faithfulness.pearson,
            "spearman": faithfulness.spearman,
            "rank_agreement": faithfulness.rank_agreement,
            "top_k_overlap": {
                str(k): value for k, value in sorted(faithfulness.top_k_overlap.items())
            },
            "num_samples": faithfulness.num_samples,
        },
        "faithfulness_buckets": _rank_bucket_table(
            necessity_scores,
            value_fn=lambda score: score.attribution_score,
            metric_fn=lambda score: score.necessity,
            bucket_names=tuple(f"d{index:02d}" for index in range(1, 11)),
            status_name="faithfulness_status",
        ),
        "minimal_subset_statistics": {
            "num_traces": len(minimal_subsets),
            "mean_compression_ratio": float(np.mean(compression_values)) if compression_values else 0.0,
            "median_compression_ratio": float(np.median(compression_values)) if compression_values else 0.0,
            "mean_minimal_step_count": float(
                np.mean([result.minimal_step_count for result in minimal_subsets])
            )
            if minimal_subsets
            else 0.0,
            "mean_utility_retained": float(
                np.mean([result.utility_retained for result in minimal_subsets])
            )
            if minimal_subsets
            else 0.0,
            "utility_threshold": utility_threshold,
        },
    }
    warnings = _counterfactual_bucket_warnings(sections)
    return sections, warnings


def _numeric_summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {
            "num_samples": 0,
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "q25": 0.0,
            "median": 0.0,
            "q75": 0.0,
            "max": 0.0,
        }
    array = np.asarray(values, dtype=float)
    return {
        "num_samples": len(values),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "min": float(np.min(array)),
        "q25": float(np.quantile(array, 0.25)),
        "median": float(np.median(array)),
        "q75": float(np.quantile(array, 0.75)),
        "max": float(np.max(array)),
    }


def _rank_bucket_table(
    items: list[Any],
    value_fn: Any,
    metric_fn: Any,
    bucket_names: tuple[str, ...],
    status_name: str,
) -> dict[str, dict[str, Any]]:
    values = [
        (index, item, float(value_fn(item)), float(metric_fn(item)))
        for index, item in enumerate(items)
        if math.isfinite(float(value_fn(item))) and math.isfinite(float(metric_fn(item)))
    ]
    values.sort(key=lambda item: (item[2], item[0]))
    grouped: dict[str, list[float]] = {name: [] for name in bucket_names}
    if values:
        for rank, (_index, _item, _value, metric_value) in enumerate(values):
            bucket_index = min(
                len(bucket_names) - 1,
                int(rank * len(bucket_names) / len(values)),
            )
            grouped[bucket_names[bucket_index]].append(metric_value)

    table: dict[str, dict[str, Any]] = {}
    for bucket_name in bucket_names:
        bucket_values = grouped[bucket_name]
        status = "ok" if len(bucket_values) >= MIN_BUCKET_SIZE else "insufficient_samples"
        table[bucket_name] = {
            "frequency": len(bucket_values),
            "mean": float(np.mean(bucket_values)) if bucket_values else None,
            "std": float(np.std(bucket_values)) if bucket_values else None,
            "status": status,
            status_name: status,
        }
    return table


def _counterfactual_bucket_warnings(sections: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for section_name in ("necessity_buckets", "redundancy_buckets", "faithfulness_buckets"):
        for bucket_name, bucket in sections[section_name].items():
            if bucket["status"] != "insufficient_samples":
                continue
            warnings.append(
                f"insufficient-bucket {section_name}.{bucket_name} has "
                f"{bucket['frequency']} samples; required {MIN_BUCKET_SIZE}."
            )
    return warnings


def run(args: argparse.Namespace) -> dict[str, Any]:
    attribution_path, path_warnings = resolve_attribution_path(args.attribution_records)
    functional_trace_path, functional_trace_warnings = resolve_functional_trace_path(
        args.functional_traces,
        args.reflection_traces,
    )
    inputs, annotations, input_warnings = build_inputs(attribution_path, args.reflection_traces)
    warnings = [*path_warnings, *functional_trace_warnings, *input_warnings]
    if not has_valid_stratified_rows(inputs) and args.reflection_traces != functional_trace_path:
        fallback_inputs, fallback_annotations, fallback_warnings = build_inputs(
            attribution_path,
            functional_trace_path,
        )
        if has_valid_stratified_rows(fallback_inputs):
            warnings.extend(fallback_warnings)
            warnings.append(
                f"{args.reflection_traces} has no attribution overlap; "
                f"using {functional_trace_path} for stratified trace metadata."
            )
            inputs = fallback_inputs
            annotations = fallback_annotations
    evaluator = StratifiedEvaluator(random_seed=args.seed)
    metrics = evaluator.evaluate(inputs)
    report = build_report(inputs, metrics, args.seed, warnings, evaluator)
    utility_annotations, functional_report, correlation_report = build_functional_outputs(
        functional_trace_path,
        attribution_path,
    )
    utility_warnings = build_utility_warnings(utility_annotations, functional_report)
    counterfactual_sections, counterfactual_warnings = build_counterfactual_report_sections(
        load_records(functional_trace_path),
        utility_annotations,
        utility_threshold=args.counterfactual_utility_threshold,
    )
    report["functional_validity"] = functional_report
    report["alignment_metrics"] = functional_report["alignment_metrics"]
    report["utility_warnings"] = utility_warnings
    report.update(counterfactual_sections)
    report["warnings"] = sorted(set([*report["warnings"], *utility_warnings, *counterfactual_warnings]))

    if args.dry_run:
        LOGGER.info(
            "%s",
            json.dumps(
                {
                    "dry_run": True,
                    "attribution_records": str(attribution_path),
                    "reflection_traces": str(args.reflection_traces),
                    "functional_traces": str(functional_trace_path),
                    "output": str(args.output),
                    "utility_annotations_output": str(args.utility_annotations_output),
                    "functional_validity_output": str(args.functional_validity_output),
                    "attribution_utility_output": str(args.attribution_utility_output),
                    "n_records": len(inputs.records),
                    "n_utility_annotations": len(utility_annotations),
                    "warnings": report["warnings"],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        return report

    write_utility_annotations(utility_annotations, args.utility_annotations_output)
    write_report(functional_report, args.functional_validity_output)
    write_report(correlation_report, args.attribution_utility_output)
    write_report(report, args.output)
    plot_category_distribution(annotations)
    plot_utility_by_category(report)
    plot_stability_scatter(report)
    plot_locality_sensitivity(report)
    plot_validity_suite(utility_annotations, args.figures_dir)
    LOGGER.info("Wrote stratified report to %s", args.output)
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
