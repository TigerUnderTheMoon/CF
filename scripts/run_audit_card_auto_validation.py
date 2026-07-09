"""Oracle-based automatic audit-target validation for SC-FMA Audit Cards.

This script treats failure-mode localization as an information-retrieval task.
It compares a scalar-only view (``w_struct`` ranking score summaries) with the
SC-FMA decomposition view (fidelity, necessity, redundancy, bottleneck, and
recommended action signals).  It uses automatic oracle labels derived from the
existing PRM800K failure taxonomy rules; it does not use human subjects or
manual adjudication.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
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
import build_failure_taxonomy as taxonomy  # noqa: E402
from reviewer_v2_common import Timer, common_metadata, write_json, write_markdown  # noqa: E402


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "kbs_audit_card_auto_validation_v1"
TARGETS = (
    "bottleneck_protection",
    "redundancy_consolidation",
    "weak_utility_anchor",
    "structural_over_correction",
)
TARGET_TO_TAXONOMY = {
    "bottleneck_protection": "bottleneck_over_protection",
    "redundancy_consolidation": "redundancy_misclassification",
    "weak_utility_anchor": "weak_utility_anchor",
    "structural_over_correction": "structural_over_correction",
}
METHODS = ("w_struct_only", "raw_field_bundle", "scfma_decomposition")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--fixture-size", type=int, default=200)
    parser.add_argument("--budget", type=float, default=0.25)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    parser.add_argument("--model", type=Path, default=error_cases.FROZEN_MODEL_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    timer = Timer.start()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    model = error_cases.load_frozen_model(args.model)
    samples, source_artifacts = taxonomy._load_samples(args.fixture, args.fixture_size)
    traces = taxonomy._classify_samples(samples, model)
    rows = [_trace_record(trace) for trace in traces]
    per_target = {
        target: _evaluate_target(rows, target, budget=args.budget)
        for target in TARGETS
    }
    methods = {
        method: _aggregate_method(
            per_target,
            method,
            bootstrap_samples=args.bootstrap_samples,
            bootstrap_seed=args.bootstrap_seed,
        )
        for method in METHODS
    }
    report = {
        **common_metadata(
            output_dir=args.output_dir,
            evidence_level="oracle_auto_audit_validation",
            source_artifacts=[
                *source_artifacts,
                str(args.model),
                "automatic oracle labels from failure-taxonomy rules",
            ],
            known_limitations=[
                "Automatic oracle labels are rule-derived and are not human adjudication.",
                "Supports decision traceability and information-gain claims only.",
                "Does not validate human audit speed or accuracy.",
                "Does not validate a live KBS workflow.",
                "Does not validate downstream PRM training.",
            ],
        ),
        "experiment": "audit_card_auto_validation",
        "human_subjects": False,
        "human_efficiency_claim": False,
        "validated_kbs_workflow": False,
        "zero_manual_adjudication": True,
        "targets": list(TARGETS),
        "budget": args.budget,
        "n_traces": len(rows),
        "n_steps": int(sum(row["n_steps"] for row in rows)),
        "elapsed_seconds": timer.elapsed(),
        "available_fields": {
            "w_struct_only": ["w_struct_scalar"],
            "raw_field_bundle": [
                "fidelity",
                "raw_local_utility",
                "structural_necessity",
                "redundancy_density",
                "bottleneck_indicator",
            ],
            "scfma_decomposition": [
                "fidelity",
                "necessity",
                "redundancy",
                "bottleneck",
                "recommended_action",
                "upstream_utility_anchor",
            ],
        },
        "oracle_definition": {
            "source": "PRM800K labels plus SC-FMA failure-taxonomy rules",
            "target_to_taxonomy": TARGET_TO_TAXONOMY,
            "human_subjects": False,
        },
        "methods": methods,
        "per_target": per_target,
        "boundary_header": {
            "human_subjects": False,
            "human_efficiency_claim": False,
            "validated_kbs_workflow": False,
            "evidence_level": "oracle_auto_audit_validation",
        },
        "interpretation_rule": (
            "A positive result supports automatic recovery of rule-defined audit "
            "targets from decomposition fields. It is not human-performance evidence."
        ),
    }
    write_json(args.output_dir / "audit_card_auto_validation.json", report)
    _write_csv(args.output_dir / "audit_card_auto_validation.csv", per_target)
    write_markdown(
        args.output_dir / "audit_card_auto_validation.md",
        _render_markdown(report),
    )
    print(f"Wrote {args.output_dir / 'audit_card_auto_validation.json'}")
    print(f"Wrote {args.output_dir / 'audit_card_auto_validation.csv'}")
    print(f"Wrote {args.output_dir / 'audit_card_auto_validation.md'}")


def _trace_record(trace: taxonomy.TraceFailure) -> dict[str, Any]:
    w_struct = np.asarray(trace.w_struct, dtype=float)
    raw = np.asarray(trace.raw_local_utility, dtype=float)
    necessity = np.asarray(trace.necessity, dtype=float)
    qp = np.asarray(trace.scfma_qp, dtype=float)
    ridge = np.asarray(trace.scfma_ridge, dtype=float)
    bottlenecks = list(trace.bottleneck_indices)
    bottleneck_strength = float(np.mean(necessity[bottlenecks])) if bottlenecks else 0.0
    scalar_salience = float(np.max(w_struct) - np.median(w_struct)) if w_struct.size else 0.0
    anchor_gap = float(np.max(np.abs(w_struct - raw))) if w_struct.size and raw.size else 0.0
    structural_gap = float(np.max(np.abs(qp - w_struct))) if qp.size and w_struct.size else 0.0
    ridge_gap = float(np.max(np.abs(ridge - w_struct))) if ridge.size and w_struct.size else 0.0
    qp_drop = max(0.0, float(trace.rho_w_struct) - float(trace.rho_qp))
    redundancy_signal = float(trace.redundancy_density) * (1.0 + qp_drop)
    bottleneck_signal = _bottleneck_oracle_signal(trace, qp, necessity)
    weak_anchor_signal = max(0.0, -float(trace.rho_raw)) + max(0.0, float(trace.rho_w_struct))
    raw_bottleneck_signal = float(len(bottlenecks)) + bottleneck_strength
    raw_structural_disagreement = (
        float(np.max(np.abs(necessity - w_struct)))
        if necessity.size and w_struct.size and necessity.shape == w_struct.shape
        else 0.0
    )
    return {
        "sample_id": trace.sample_id,
        "n_steps": trace.n_steps,
        "taxonomy_labels": list(trace.taxonomy_labels),
        "w_struct_scalar_score": scalar_salience,
        "scores": {
            "w_struct_only": {
                "bottleneck_protection": scalar_salience,
                "redundancy_consolidation": scalar_salience,
                "weak_utility_anchor": scalar_salience,
                "structural_over_correction": scalar_salience,
            },
            "raw_field_bundle": {
                "bottleneck_protection": raw_bottleneck_signal,
                "redundancy_consolidation": float(trace.redundancy_density),
                "weak_utility_anchor": weak_anchor_signal + 0.01 * anchor_gap,
                "structural_over_correction": raw_structural_disagreement,
            },
            "scfma_decomposition": {
                "bottleneck_protection": bottleneck_signal + bottleneck_strength,
                "redundancy_consolidation": redundancy_signal,
                "weak_utility_anchor": weak_anchor_signal + 0.01 * anchor_gap,
                "structural_over_correction": qp_drop + 0.01 * (structural_gap + ridge_gap),
            },
        },
        "recommended_action": _recommended_action(trace),
    }


def _bottleneck_oracle_signal(
    trace: taxonomy.TraceFailure,
    qp: np.ndarray,
    necessity: np.ndarray,
) -> float:
    labels = np.asarray(trace.labels, dtype=float)
    if qp.size == 0 or labels.size == 0 or not trace.bottleneck_indices:
        return 0.0
    top_count = max(1, int(math.ceil(len(qp) * 0.25)))
    top_indices = set(int(index) for index in np.argsort(-qp, kind="mergesort")[:top_count])
    median_label = float(np.median(labels))
    signal = 0.0
    for index in trace.bottleneck_indices:
        if index in top_indices and float(labels[index]) < median_label:
            signal += 1.0 + float(necessity[index])
    return signal


def _recommended_action(trace: taxonomy.TraceFailure) -> str:
    labels = set(trace.taxonomy_labels)
    if "bottleneck_over_protection" in labels:
        return "protect_bottleneck"
    if "redundancy_misclassification" in labels:
        return "consolidate_redundant_cluster"
    if "weak_utility_anchor" in labels:
        return "repair_upstream_utility_anchor"
    if "structural_over_correction" in labels:
        return "inspect_structural_reallocation"
    return "inspect_low_signal_trace"


def _evaluate_target(
    rows: Sequence[Mapping[str, Any]],
    target: str,
    *,
    budget: float,
) -> dict[str, Any]:
    taxonomy_label = TARGET_TO_TAXONOMY[target]
    labels = np.asarray(
        [1.0 if taxonomy_label in row["taxonomy_labels"] else 0.0 for row in rows],
        dtype=float,
    )
    metrics = {}
    for method in METHODS:
        scores = np.asarray([row["scores"][method][target] for row in rows], dtype=float)
        metrics[method] = _ir_metrics(scores, labels, budget=budget)
    return {
        "oracle_taxonomy_label": taxonomy_label,
        "n_positive": int(np.sum(labels)),
        "methods": metrics,
    }


def _ir_metrics(scores: np.ndarray, labels: np.ndarray, *, budget: float) -> dict[str, float]:
    n = len(labels)
    if n == 0:
        return {
            "recall_at_budget": 0.0,
            "ndcg_at_budget": 0.0,
            "mrr": 0.0,
            "top1_failure_mode_hit": 0.0,
            "inspection_cost_proxy": 1.0,
        }
    order = np.argsort(-scores, kind="mergesort")
    k = max(1, min(n, int(math.ceil(n * budget))))
    selected = order[:k]
    positives = float(np.sum(labels))
    recall = float(np.sum(labels[selected]) / positives) if positives > 0 else 0.0
    gains = labels[selected]
    discounts = 1.0 / np.log2(np.arange(2, len(selected) + 2))
    dcg = float(np.sum(gains * discounts))
    ideal_labels = np.sort(labels)[::-1][:k]
    ideal_dcg = float(np.sum(ideal_labels * discounts))
    ndcg = 0.0 if ideal_dcg <= 0.0 else dcg / ideal_dcg
    positive_ranks = np.where(labels[order] > 0.0)[0]
    if len(positive_ranks) == 0:
        mrr = 0.0
        cost = 1.0
    else:
        first_rank = int(positive_ranks[0]) + 1
        mrr = 1.0 / first_rank
        cost = first_rank / n
    return {
        "recall_at_budget": recall,
        "ndcg_at_budget": ndcg,
        "mrr": float(mrr),
        "top1_failure_mode_hit": float(labels[order[0]] > 0.0),
        "inspection_cost_proxy": float(cost),
    }


def _aggregate_method(
    per_target: Mapping[str, Mapping[str, Any]],
    method: str,
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    metric_names = [
        "recall_at_budget",
        "ndcg_at_budget",
        "mrr",
        "top1_failure_mode_hit",
        "inspection_cost_proxy",
    ]
    values_by_metric = {
        metric: np.asarray(
            [
                per_target[target]["methods"][method][metric]
                for target in TARGETS
            ],
            dtype=float,
        )
        for metric in metric_names
    }
    return {
        "mean_recall_at_budget": float(np.mean(values_by_metric["recall_at_budget"])),
        "mean_ndcg_at_budget": float(np.mean(values_by_metric["ndcg_at_budget"])),
        "mean_mrr": float(np.mean(values_by_metric["mrr"])),
        "mean_top1_failure_mode_hit": float(
            np.mean(values_by_metric["top1_failure_mode_hit"])
        ),
        "mean_inspection_cost_proxy": float(
            np.mean(values_by_metric["inspection_cost_proxy"])
        ),
        "bootstrap_ci": {
            metric: _bootstrap_ci(
                values,
                n_bootstrap=bootstrap_samples,
                seed=bootstrap_seed,
            )
            for metric, values in values_by_metric.items()
        },
    }


def _bootstrap_ci(values: np.ndarray, *, n_bootstrap: int, seed: int) -> dict[str, float]:
    if values.size == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    rng = np.random.default_rng(seed)
    means = np.empty(max(1, n_bootstrap), dtype=float)
    for index in range(len(means)):
        means[index] = float(np.mean(values[rng.integers(0, len(values), len(values))]))
    return {
        "mean": float(np.mean(values)),
        "ci_lower": float(np.percentile(means, 2.5)),
        "ci_upper": float(np.percentile(means, 97.5)),
    }


def _write_csv(path: Path, per_target: Mapping[str, Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "target",
                "method",
                "n_positive",
                "recall_at_budget",
                "ndcg_at_budget",
                "mrr",
                "top1_failure_mode_hit",
                "inspection_cost_proxy",
            ],
        )
        writer.writeheader()
        for target, payload in per_target.items():
            for method, metrics in payload["methods"].items():
                writer.writerow(
                    {
                        "target": target,
                        "method": method,
                        "n_positive": payload["n_positive"],
                        **metrics,
                    }
                )


def _render_markdown(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "# Oracle-based Auto Audit-Target Validation",
        "",
        "## Boundary Header",
        "",
        "- human_subjects=false",
        "- human_efficiency_claim=false",
        "- validated_kbs_workflow=false",
        "- evidence_level=oracle_auto_audit_validation",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Zero API calls: `{report['zero_api_calls']}`",
        f"- Zero manual adjudication: `{report['zero_manual_adjudication']}`",
        "",
        "## Method Summary",
        "",
        "Failure-mode localization is treated as an automatic retrieval task. "
        "The scalar condition receives only the `w_struct` scalar summary; the "
        "SC-FMA condition receives decomposition fields and recommended actions.",
        "",
        "| Method | Recall@Budget | NDCG@Budget | MRR | Top-1 Hit | Inspection Cost |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, metrics in report["methods"].items():
        lines.append(
            f"| `{method}` | {metrics['mean_recall_at_budget']:.4f} | "
            f"{metrics['mean_ndcg_at_budget']:.4f} | {metrics['mean_mrr']:.4f} | "
            f"{metrics['mean_top1_failure_mode_hit']:.4f} | "
            f"{metrics['mean_inspection_cost_proxy']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Per-Target Results",
            "",
            "| Target | Positives | Method | Recall@Budget | NDCG@Budget | MRR | Top-1 Hit |",
            "|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    for target, payload in report["per_target"].items():
        for method, metrics in payload["methods"].items():
            lines.append(
                f"| `{target}` | {payload['n_positive']} | `{method}` | "
                f"{metrics['recall_at_budget']:.4f} | {metrics['ndcg_at_budget']:.4f} | "
                f"{metrics['mrr']:.4f} | {metrics['top1_failure_mode_hit']:.4f} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            str(report["interpretation_rule"]),
        ]
    )
    return lines


if __name__ == "__main__":
    main()
