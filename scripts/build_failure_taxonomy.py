"""Reviewer V2 failure taxonomy for PRM800K variant behavior.

Builds a diagnostic taxonomy plus representative cases. Uses the locked
PRM800K split by default or script-local fixture data in tests. Zero API calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import analyze_prm800k_error_cases as error_cases  # noqa: E402
import run_scfma_variants_prm800k as variants  # noqa: E402
from fma.calibration import BottleneckConstraint, scfma_calibrate, scfma_calibrate_ridge  # noqa: E402
from reviewer_v2_common import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    Timer,
    common_metadata,
    mean,
    safe_corr,
    write_json,
    write_markdown,
)


DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "failure_taxonomy"
TAXONOMY_LABELS = [
    "structural_over_correction",
    "redundancy_misclassification",
    "bottleneck_over_protection",
    "weak_utility_anchor",
    "low_signal_or_tie",
]


@dataclass(frozen=True)
class TraceFailure:
    sample_id: str
    n_steps: int
    step_texts: list[str]
    labels: list[float]
    raw_local_utility: list[float]
    w_struct: list[float]
    scfma_qp: list[float]
    scfma_ridge: list[float]
    necessity: list[float]
    redundancy_density: float
    bottleneck_indices: list[int]
    rho_w_struct: float
    rho_qp: float
    rho_ridge: float
    rho_raw: float
    taxonomy_labels: list[str]
    primary_label: str


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-artifact", type=Path, default=None)
    parser.add_argument(
        "--taxonomy-rules",
        default=",".join(TAXONOMY_LABELS),
        help="Comma-separated taxonomy labels to include in count/percentage outputs.",
    )
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument(
        "--output-format",
        choices=["standard", "appendix_page"],
        default="standard",
    )
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--fixture-size", type=int, default=200)
    parser.add_argument("--model", type=Path, default=error_cases.FROZEN_MODEL_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    timer = Timer.start()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    enabled_labels = _parse_taxonomy_rules(args.taxonomy_rules)

    model = error_cases.load_frozen_model(args.model)
    samples, source_artifacts = _load_samples(args.fixture, args.fixture_size)
    if args.input_artifact is not None:
        source_artifacts = [str(args.input_artifact), *source_artifacts]
    traces = _classify_samples(samples, model)
    taxonomy_counts = {
        label: int(sum(label in trace.taxonomy_labels for trace in traces))
        for label in enabled_labels
    }
    taxonomy_percentages = {
        label: round((count / len(traces) * 100.0) if traces else 0.0, 4)
        for label, count in taxonomy_counts.items()
    }
    cases = _representative_cases(traces, enabled_labels, max_cases=max(0, args.max_cases))
    report = {
        **common_metadata(
            output_dir=args.output_dir,
            evidence_level="diagnostic_support",
            source_artifacts=source_artifacts,
        ),
        "experiment": "failure_taxonomy",
        "n_samples": len(traces),
        "elapsed_seconds": timer.elapsed(),
        "taxonomy_rules": {
            "structural_over_correction": "rho_qp <= rho_w_struct - 0.10",
            "redundancy_misclassification": (
                "redundancy density in top tertile and QP trails Ridge or w_struct by >= 0.05"
            ),
            "bottleneck_over_protection": (
                "a bottleneck step enters QP top 25% while its label is below the trace median"
            ),
            "weak_utility_anchor": "rho_raw <= 0 and rho_w_struct >= 0.30",
            "low_signal_or_tie": "low label variance, short trace, or unstable correlation",
        },
        "taxonomy_rules_enabled": enabled_labels,
        "taxonomy_counts": taxonomy_counts,
        "taxonomy_percentages": taxonomy_percentages,
        "representative_cases": cases,
    }
    write_json(args.output_dir / "failure_taxonomy.json", report)
    write_markdown(args.output_dir / "failure_taxonomy.md", _render_markdown(report))
    if args.output_format == "appendix_page":
        write_markdown(
            args.output_dir / "failure_taxonomy_appendix.md",
            _render_appendix_markdown(report),
        )
    print(f"Wrote {args.output_dir / 'failure_taxonomy.json'}")
    print(f"Wrote {args.output_dir / 'failure_taxonomy.md'}")
    if args.output_format == "appendix_page":
        print(f"Wrote {args.output_dir / 'failure_taxonomy_appendix.md'}")


def _parse_taxonomy_rules(raw: str) -> list[str]:
    labels = [part.strip() for part in raw.split(",") if part.strip()]
    unknown = [label for label in labels if label not in TAXONOMY_LABELS]
    if unknown:
        raise SystemExit(f"Unknown taxonomy rule(s): {', '.join(unknown)}")
    return labels or list(TAXONOMY_LABELS)


def _load_samples(
    fixture: bool,
    fixture_size: int,
) -> tuple[list[variants.RankingSample], list[str]]:
    config = error_cases._load_config()
    split_config = config["data"]["split_strategy"]
    dev_upper = int(split_config["dev_mod_upper_exclusive"])
    if fixture:
        rows = error_cases._fixture_pool_rows(size=fixture_size)
        samples = variants.build_samples(rows, split_name="pool", row_start=5000)
        locked = [
            sample
            for sample in samples
            if _hash_bucket(sample.sample_id, split_config["salt"]) >= dev_upper
        ]
        return locked, ["fixture_prm800k_rows", str(error_cases.FROZEN_MODEL_PATH)]

    pool_rows = variants.load_pool_rows(config)
    pool_samples = variants.build_samples(
        pool_rows,
        split_name="pool",
        row_start=int(config["data"]["pool"]["start_row"]),
    )
    _dev, locked = variants.split_samples(pool_samples, split_config)
    return locked, [
        str(error_cases.CONFIG_PATH),
        str(error_cases.FROZEN_MODEL_PATH),
        "PRM800K HuggingFace source from frozen config",
    ]


def _hash_bucket(sample_id: str, salt: str) -> int:
    digest = hashlib.sha256(f"{sample_id}|{salt}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _classify_samples(
    samples: Sequence[variants.RankingSample],
    model: Mapping[str, Any],
) -> list[TraceFailure]:
    provisional: list[dict[str, Any]] = []
    for sample in samples:
        labels = np.asarray(sample.labels, dtype=float)
        if len(labels) == 0:
            continue
        w_struct = variants.predict_w_struct(sample, model)
        necessity = variants.compute_necessity_vector(sample, model)
        redundancy = variants.compute_redundancy_matrix(sample, model)
        bottlenecks = sorted(variants.detect_bottleneck_indices(necessity, redundancy))
        qp = _qp_scores(sample, w_struct, necessity, redundancy, bottlenecks)
        ridge = _ridge_scores(sample, w_struct, necessity)
        raw = np.asarray(sample.raw_local_utility, dtype=float)
        provisional.append(
            {
                "sample": sample,
                "labels": labels,
                "raw": raw,
                "w_struct": w_struct,
                "qp": qp,
                "ridge": ridge,
                "necessity": necessity,
                "redundancy_density": _redundancy_density(redundancy),
                "bottlenecks": bottlenecks,
                "rho_w_struct": safe_corr(w_struct.tolist(), labels.tolist(), "spearman"),
                "rho_qp": safe_corr(qp.tolist(), labels.tolist(), "spearman"),
                "rho_ridge": safe_corr(ridge.tolist(), labels.tolist(), "spearman"),
                "rho_raw": safe_corr(raw.tolist(), labels.tolist(), "spearman"),
            }
        )

    red_threshold = _top_tertile([row["redundancy_density"] for row in provisional])
    traces: list[TraceFailure] = []
    for row in provisional:
        labels = _labels_for_row(row, red_threshold)
        primary = labels[0] if labels else "low_signal_or_tie"
        sample = row["sample"]
        traces.append(
            TraceFailure(
                sample_id=sample.sample_id,
                n_steps=len(row["labels"]),
                step_texts=list(sample.step_texts),
                labels=[float(value) for value in row["labels"]],
                raw_local_utility=[float(value) for value in row["raw"]],
                w_struct=[float(value) for value in row["w_struct"]],
                scfma_qp=[float(value) for value in row["qp"]],
                scfma_ridge=[float(value) for value in row["ridge"]],
                necessity=[float(value) for value in row["necessity"]],
                redundancy_density=float(row["redundancy_density"]),
                bottleneck_indices=[int(value) for value in row["bottlenecks"]],
                rho_w_struct=float(row["rho_w_struct"]),
                rho_qp=float(row["rho_qp"]),
                rho_ridge=float(row["rho_ridge"]),
                rho_raw=float(row["rho_raw"]),
                taxonomy_labels=labels or ["low_signal_or_tie"],
                primary_label=primary,
            )
        )
    return traces


def _qp_scores(
    sample: variants.RankingSample,
    w_struct: np.ndarray,
    necessity: np.ndarray,
    redundancy: np.ndarray,
    bottlenecks: Sequence[int],
) -> np.ndarray:
    try:
        result = scfma_calibrate(
            w_struct,
            necessity,
            redundancy,
            bottleneck_constraints=[
                BottleneckConstraint(int(index), 0.01) for index in bottlenecks
            ],
            sample_id=sample.sample_id,
            alpha=1.0,
            beta=0.5,
            gamma=0.2,
            delta=0.1,
        )
        if result.weights and result.converged:
            return np.asarray(result.weights[0].weights, dtype=float)
    except Exception:
        pass
    return w_struct


def _ridge_scores(
    sample: variants.RankingSample,
    w_struct: np.ndarray,
    necessity: np.ndarray,
) -> np.ndarray:
    try:
        result = scfma_calibrate_ridge(
            w_struct,
            necessity,
            sample_id=sample.sample_id,
            alpha_ciui=0.7,
            alpha_nec=0.3,
            temperature=1.0,
        )
        if result.weights:
            return np.asarray(result.weights[0].weights, dtype=float)
    except Exception:
        pass
    return w_struct


def _redundancy_density(redundancy: np.ndarray) -> float:
    if redundancy.size == 0 or redundancy.shape[0] < 2:
        return 0.0
    off_diag = redundancy.copy()
    np.fill_diagonal(off_diag, 0.0)
    return float(np.mean(off_diag))


def _top_tertile(values: Sequence[float]) -> float:
    return float(np.percentile(values, 66.6667)) if values else 0.0


def _labels_for_row(row: Mapping[str, Any], red_threshold: float) -> list[str]:
    labels: list[str] = []
    if float(row["rho_qp"]) <= float(row["rho_w_struct"]) - 0.10:
        labels.append("structural_over_correction")
    if float(row["redundancy_density"]) >= red_threshold and (
        float(row["rho_qp"]) <= max(float(row["rho_ridge"]), float(row["rho_w_struct"])) - 0.05
    ):
        labels.append("redundancy_misclassification")
    if _has_bottleneck_over_protection(row):
        labels.append("bottleneck_over_protection")
    if float(row["rho_raw"]) <= 0.0 and float(row["rho_w_struct"]) >= 0.30:
        labels.append("weak_utility_anchor")
    labels_array = np.asarray(row["labels"], dtype=float)
    if (
        len(labels_array) < 3
        or len(set(float(value) for value in labels_array)) < 2
        or float(np.std(labels_array)) < 0.05
        or any(not math.isfinite(float(row[key])) for key in ["rho_qp", "rho_w_struct", "rho_ridge"])
    ):
        labels.append("low_signal_or_tie")
    return labels


def _has_bottleneck_over_protection(row: Mapping[str, Any]) -> bool:
    labels = np.asarray(row["labels"], dtype=float)
    qp = np.asarray(row["qp"], dtype=float)
    bottlenecks = set(int(value) for value in row["bottlenecks"])
    if len(labels) == 0 or not bottlenecks:
        return False
    top_count = max(1, int(math.ceil(len(qp) * 0.25)))
    top_indices = set(int(index) for index in np.argsort(qp)[::-1][:top_count])
    median_label = float(np.median(labels))
    return any(index in top_indices and labels[index] < median_label for index in bottlenecks)


def _representative_cases(
    traces: Sequence[TraceFailure],
    enabled_labels: Sequence[str] | None = None,
    *,
    max_cases: int = 5,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    labels = list(enabled_labels or TAXONOMY_LABELS)
    for label in labels:
        candidates = [trace for trace in traces if label in trace.taxonomy_labels]
        if not candidates:
            continue
        candidates.sort(key=lambda trace: _severity(trace, label), reverse=True)
        selected = next((trace for trace in candidates if trace.sample_id not in seen), candidates[0])
        cases.append(_case_payload(selected))
        seen.add(selected.sample_id)
        if len(cases) >= max_cases:
            break
    if len(cases) < max_cases:
        for trace in sorted(traces, key=lambda item: item.rho_w_struct - item.rho_qp, reverse=True):
            if trace.sample_id in seen:
                continue
            cases.append(_case_payload(trace))
            seen.add(trace.sample_id)
            if len(cases) >= max_cases:
                break
    return cases[:max_cases]


def _severity(trace: TraceFailure, label: str) -> float:
    if label == "structural_over_correction":
        return trace.rho_w_struct - trace.rho_qp
    if label == "redundancy_misclassification":
        return trace.redundancy_density + max(trace.rho_w_struct, trace.rho_ridge) - trace.rho_qp
    if label == "bottleneck_over_protection":
        return float(len(trace.bottleneck_indices))
    if label == "weak_utility_anchor":
        return trace.rho_w_struct - trace.rho_raw
    return 1.0 - float(np.std(np.asarray(trace.labels, dtype=float)))


def _case_payload(trace: TraceFailure) -> dict[str, Any]:
    selected_step = _selected_step_index(trace)
    return {
        "sample_id": trace.sample_id,
        "n_steps": trace.n_steps,
        "taxonomy_labels": trace.taxonomy_labels,
        "primary_label": trace.primary_label,
        "taxonomy_label": trace.primary_label,
        "step_text_excerpt": _truncate_tokens(trace.step_texts[selected_step], max_tokens=100),
        "labels": trace.labels,
        "raw_utility": trace.raw_local_utility,
        "w_struct": trace.w_struct,
        "scfma_qp": trace.scfma_qp,
        "scfma_ridge": trace.scfma_ridge,
        "diagnostic_explanation": _diagnostic_explanation(trace),
        "rho": {
            "w_struct": trace.rho_w_struct,
            "scfma_qp": trace.rho_qp,
            "scfma_ridge": trace.rho_ridge,
            "raw_local_utility": trace.rho_raw,
        },
        "redundancy_density": trace.redundancy_density,
        "bottleneck_indices": trace.bottleneck_indices,
        "step_level": [
            {
                "step": index,
                "step_text_excerpt": _truncate_tokens(trace.step_texts[index], max_tokens=100),
                "label": trace.labels[index],
                "raw_utility": trace.raw_local_utility[index],
                "w_struct": trace.w_struct[index],
                "scfma_qp": trace.scfma_qp[index],
                "scfma_ridge": trace.scfma_ridge[index],
                "necessity": trace.necessity[index],
            }
            for index in range(trace.n_steps)
        ],
    }


def _selected_step_index(trace: TraceFailure) -> int:
    if trace.primary_label == "bottleneck_over_protection" and trace.bottleneck_indices:
        return min(max(trace.bottleneck_indices[0], 0), trace.n_steps - 1)
    if trace.scfma_qp:
        return int(np.argsort(np.asarray(trace.scfma_qp, dtype=float))[::-1][0])
    return 0


def _truncate_tokens(text: str, *, max_tokens: int) -> str:
    tokens = str(text).split()
    if len(tokens) <= max_tokens:
        return str(text)
    return " ".join(tokens[:max_tokens])


def _diagnostic_explanation(trace: TraceFailure) -> str:
    explanations = {
        "structural_over_correction": (
            "QP trails w_struct by at least 0.10 Spearman, indicating that full "
            "structural optimization can over-correct the stronger base signal."
        ),
        "redundancy_misclassification": (
            "High redundancy density coincides with lower QP ranking quality, "
            "suggesting possible over-merging of functionally distinct steps."
        ),
        "bottleneck_over_protection": (
            "A bottleneck-protected step enters the QP top budget despite a "
            "below-median label, so the floor constraint needs diagnostic review."
        ),
        "weak_utility_anchor": (
            "Raw local utility is non-positive while w_struct remains informative, "
            "supporting the need for a structured feature signal."
        ),
        "low_signal_or_tie": (
            "Low variance, short traces, or ties make rank-based interpretation unstable."
        ),
    }
    return " ".join(explanations[label] for label in trace.taxonomy_labels)


def _render_markdown(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "# Failure Taxonomy + Representative Cases",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Evidence level: `{report['evidence_level']}`",
        f"- Zero API calls: `{report['zero_api_calls']}`",
        "",
        "## Failure Taxonomy",
        "",
        "| Label | Count | Percentage |",
        "|---|---:|---:|",
    ]
    for label, count in report["taxonomy_counts"].items():
        percentage = report.get("taxonomy_percentages", {}).get(label, 0.0)
        lines.append(f"| `{label}` | {count} | {percentage:.2f}% |")
    lines.extend(["", "## Representative Cases", ""])
    for case in report["representative_cases"]:
        lines.extend(
            [
                f"### `{case['sample_id']}`",
                "",
                f"- Labels: `{', '.join(case['taxonomy_labels'])}`",
                f"- Primary label: `{case['primary_label']}`",
                f"- Diagnostic explanation: {case['diagnostic_explanation']}",
                "",
                "| Step | Label | w_struct | QP | Ridge | Excerpt |",
                "|---:|---:|---:|---:|---:|---|",
            ]
        )
        for step in case["step_level"]:
            excerpt = str(step["step_text_excerpt"]).replace("|", "/")
            lines.append(
                f"| {step['step']} | {step['label']:.2f} | {step['w_struct']:.4f} | "
                f"{step['scfma_qp']:.4f} | {step['scfma_ridge']:.4f} | {excerpt} |"
            )
        lines.append("")
    lines.append("These cases are diagnostic support only, not external validation.")
    return lines


def _render_appendix_markdown(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "# Failure Taxonomy Appendix",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Evidence level: `{report['evidence_level']}`",
        f"- Zero API calls: `{report['zero_api_calls']}`",
        f"- Output directory: `{report['output_dir']}`",
        "",
        "This appendix provides variant selection guidance for PRM800K-like audit prioritization.",
        "",
        "## Distribution",
        "",
        "| Label | Count | Percentage |",
        "|---|---:|---:|",
    ]
    percentages = report.get("taxonomy_percentages", {})
    for label, count in report["taxonomy_counts"].items():
        lines.append(f"| `{label}` | {count} | {percentages.get(label, 0.0):.2f}% |")

    redundancy = float(percentages.get("redundancy_misclassification", 0.0))
    bottleneck = float(percentages.get("bottleneck_over_protection", 0.0))
    lines.extend(["", "## Discussion Note", ""])
    if redundancy < 5.0 or bottleneck < 5.0:
        lines.append(
            "There were relatively few failure cases attributable to redundancy "
            "misclassification or bottleneck over-protection."
        )
    else:
        lines.append(
            "Redundancy misclassification and bottleneck over-protection appear often "
            "enough to discuss directly as variant selection guidance."
        )

    lines.extend(["", "## Representative Cases", ""])
    for index, case in enumerate(report["representative_cases"], start=1):
        scores = _selected_case_scores(case)
        excerpt = str(case["step_text_excerpt"]).replace("|", "/")
        lines.extend(
            [
                f"### Case {index}: `{case['sample_id']}`",
                "",
                f"- Taxonomy label: `{case['taxonomy_label']}`",
                f"- All labels: `{', '.join(case['taxonomy_labels'])}`",
                f"- Step text excerpt: {excerpt}",
                f"- Labels: `{_short_float_list(case['labels'])}`",
                (
                    "- Scores: "
                    f"raw utility `{_short_float_list(scores['raw_utility'])}`, "
                    f"w_struct `{_short_float_list(scores['w_struct'])}`, "
                    f"QP `{_short_float_list(scores['scfma_qp'])}`, "
                    f"Ridge `{_short_float_list(scores['scfma_ridge'])}`"
                ),
                f"- Diagnostic explanation: {case['diagnostic_explanation']}",
                "",
            ]
        )
    return lines


def _selected_case_scores(case: Mapping[str, Any], max_items: int = 6) -> dict[str, list[float]]:
    return {
        key: [float(value) for value in list(case.get(key, []))[:max_items]]
        for key in ["raw_utility", "w_struct", "scfma_qp", "scfma_ridge"]
    }


def _short_float_list(values: Sequence[Any], max_items: int = 6) -> str:
    formatted = [f"{float(value):.4f}" for value in list(values)[:max_items]]
    suffix = ", ..." if len(values) > max_items else ""
    return "[" + ", ".join(formatted) + suffix + "]"


if __name__ == "__main__":
    main()
