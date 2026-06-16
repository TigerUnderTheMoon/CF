"""Offline audit-prioritization report for the PRM800K locked split.

This script reuses the locked PRM800K split and scoring helpers from
``run_scfma_variants_prm800k.py``. It does not call any model API and does not
claim downstream PRM training or filtering gains.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_scfma_variants_prm800k as variants
from fma.eval.prm800k_audit_prioritization import (
    label_mass_at_budget,
    max_label_hit_at_budget,
    ndcg_at_budget,
    summarize_audit_prioritization,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash"
DEFAULT_FROZEN_PRM_SCORES = (
    PROJECT_ROOT
    / "outputs"
    / "real_task_v3_8_prm_locked_scoring"
    / "locked_prm_scores.jsonl"
)

METHOD_ORDER = [
    "w_struct",
    "scfma_ridge",
    "scfma_qp",
    "scfma_projection",
    "raw_local_utility",
    "relative_position",
    "span_length",
    "random",
    "frozen_prm_prefix_score",
]

DISPLAY_NAMES = {
    "w_struct": "w_struct",
    "scfma_ridge": "SC-FMA Ridge",
    "scfma_qp": "SC-FMA QP",
    "scfma_projection": "SC-FMA Projection",
    "raw_local_utility": "raw_local_utility",
    "relative_position": "relative_position",
    "span_length": "span_length",
    "random": "random",
    "frozen_prm_prefix_score": "Frozen PRM prefix score",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=variants.DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    parser.add_argument("--frozen-prm-scores", type=Path, default=DEFAULT_FROZEN_PRM_SCORES)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()

    config = variants.load_config(args.config)
    print("Loading PRM800K locked split...")
    pool_rows = variants.load_pool_rows(config)
    pool_samples = variants.build_samples(
        pool_rows,
        split_name="pool",
        row_start=int(config["data"]["pool"]["start_row"]),
    )
    dev_samples, locked_samples = variants.split_samples(
        pool_samples,
        config["data"]["split_strategy"],
    )
    print(
        f"Pool: {len(pool_samples)}, Dev: {len(dev_samples)}, "
        f"Locked: {len(locked_samples)}"
    )

    model = variants.fit_w_struct_model(
        dev_samples,
        ridge_lambda=float(config["model"]["ridge_lambda"]),
    )
    frozen_scores = load_frozen_prm_scores(args.frozen_prm_scores)

    print("Computing audit-prioritization rows...")
    rows = build_audit_rows(locked_samples, model, frozen_scores=frozen_scores)
    methods = [method for method in METHOD_ORDER if any(method in row["scores_by_method"] for row in rows)]
    summaries = summarize_audit_prioritization(rows, methods=methods)

    report = build_report(
        rows,
        summaries,
        methods=methods,
        config_path=args.config,
        frozen_prm_scores_path=args.frozen_prm_scores,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
    )
    report["elapsed_seconds"] = round(time.time() - started, 2)

    report_path = args.output_dir / "audit_prioritization_report.json"
    summary_path = args.output_dir / "audit_prioritization_summary.md"
    write_json(report_path, report)
    summary_path.write_text(render_markdown_summary(report), encoding="utf-8")

    print(f"Report written to {report_path}")
    print(f"Summary written to {summary_path}")


def load_frozen_prm_scores(path: Path) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    scores: dict[str, list[float]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            sample_id = str(row.get("sample_id") or "")
            values = row.get("scores")
            if sample_id and isinstance(values, list):
                scores[sample_id] = [float(value) for value in values]
    return scores


def build_audit_rows(
    samples: Sequence[variants.RankingSample],
    model: Mapping[str, Any],
    *,
    frozen_scores: Mapping[str, Sequence[float]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        labels = np.asarray(sample.labels, dtype=float)
        raw_ciu = np.asarray(sample.raw_local_utility, dtype=float)
        w_struct_pred = variants.predict_w_struct(sample, model)
        necessity = variants.compute_necessity_vector(sample, model)
        redundancy = variants.compute_redundancy_matrix(sample, model)
        bottleneck = variants.detect_bottleneck_indices(necessity, redundancy)
        scores = {
            "w_struct": w_struct_pred,
            "raw_local_utility": raw_ciu,
            "relative_position": np.arange(len(labels), dtype=float),
            "span_length": np.asarray(
                [len(text.split()) for text in sample.step_texts],
                dtype=float,
            ),
            "random": variants.random_scores(sample.sample_id, len(labels)),
        }
        scores.update(compute_scfma_scores(sample, w_struct_pred, necessity, redundancy, bottleneck))

        frozen = frozen_scores.get(sample.sample_id)
        if frozen is not None and len(frozen) == len(labels):
            scores["frozen_prm_prefix_score"] = np.asarray(frozen, dtype=float)

        rows.append(
            {
                "sample_id": sample.sample_id,
                "row_index": sample.row_index,
                "question_hash": sample.question_hash,
                "n_steps": len(labels),
                "labels": labels.tolist(),
                "scores_by_method": {
                    method: np.asarray(values, dtype=float).tolist()
                    for method, values in scores.items()
                },
            }
        )
    return rows


def compute_scfma_scores(
    sample: variants.RankingSample,
    w_struct_pred: np.ndarray,
    necessity: np.ndarray,
    redundancy: np.ndarray,
    bottleneck: set[int],
) -> dict[str, np.ndarray]:
    scores: dict[str, np.ndarray] = {}
    try:
        qp_result = variants.scfma_calibrate(
            w_struct_pred,
            necessity,
            redundancy,
            bottleneck_constraints=[
                variants.BottleneckConstraint(idx, 0.01) for idx in sorted(bottleneck)
            ],
            sample_id=sample.sample_id,
            alpha=1.0,
            beta=0.5,
            gamma=0.2,
            delta=0.1,
        )
        scores["scfma_qp"] = (
            np.asarray(qp_result.weights[0].weights, dtype=float)
            if qp_result.weights and qp_result.converged
            else w_struct_pred
        )
    except Exception:
        scores["scfma_qp"] = w_struct_pred

    try:
        ridge_result = variants.scfma_calibrate_ridge(
            w_struct_pred,
            necessity,
            sample_id=sample.sample_id,
            alpha_ciui=0.7,
            alpha_nec=0.3,
            temperature=1.0,
        )
        scores["scfma_ridge"] = (
            np.asarray(ridge_result.weights[0].weights, dtype=float)
            if ridge_result.weights
            else w_struct_pred
        )
    except Exception:
        scores["scfma_ridge"] = w_struct_pred

    try:
        scores["scfma_projection"] = variants.project_weights(
            w_struct_pred,
            necessity,
            redundancy,
            bottleneck,
            fidelity_weight=0.6,
            structure_weight=0.4,
        )
    except Exception:
        scores["scfma_projection"] = w_struct_pred

    return scores


def build_report(
    rows: Sequence[Mapping[str, Any]],
    summaries: Sequence[Any],
    *,
    methods: Sequence[str],
    config_path: Path,
    frozen_prm_scores_path: Path,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    method_entries = []
    summary_by_method = {summary.method: summary for summary in summaries}
    for method in methods:
        values = method_metric_values(rows, method)
        summary = summary_by_method[method]
        method_entries.append(
            {
                **asdict(summary),
                "display_name": DISPLAY_NAMES.get(method, method),
                "claim_permission": "audit_prioritization_context_only",
                "n_samples": len(values["top1_max_label_hit"]),
                "n_steps": count_method_steps(rows, method),
                "bootstrap_ci": {
                    metric: bootstrap_mean_ci(
                        np.asarray(metric_values, dtype=float),
                        n_bootstrap=bootstrap_samples,
                        seed=bootstrap_seed,
                    )
                    for metric, metric_values in values.items()
                },
            }
        )

    return {
        "route_id": "real_task_v3_6_prm800k_hash_audit_prioritization",
        "claim_boundary": "real_prm800k_audit_prioritization_only",
        "claim_permissions": {
            "audit_prioritization_context": True,
            "downstream_prm_training": False,
            "gsm8k_hotpotqa_replay_validation": False,
            "external_generalization": False,
        },
        "n_samples": len(rows),
        "n_steps": sum(int(row["n_steps"]) for row in rows),
        "methods": method_entries,
        "method_order": list(methods),
        "source": {
            "config": str(config_path),
            "frozen_prm_scores": str(frozen_prm_scores_path),
            "git_revision": git_revision(),
        },
    }


def method_metric_values(
    rows: Sequence[Mapping[str, Any]],
    method: str,
) -> dict[str, list[float]]:
    values = {
        "top1_max_label_hit": [],
        "label_mass_at_25": [],
        "label_mass_at_50": [],
        "ndcg_at_25": [],
        "ndcg_at_50": [],
    }
    for row in rows:
        scores_by_method = row["scores_by_method"]
        if not isinstance(scores_by_method, Mapping) or method not in scores_by_method:
            continue
        labels = row["labels"]
        scores = scores_by_method[method]
        values["top1_max_label_hit"].append(
            max_label_hit_at_budget(scores, labels, keep_fraction=1.0 / len(labels))
        )
        values["label_mass_at_25"].append(
            label_mass_at_budget(scores, labels, keep_fraction=0.25)
        )
        values["label_mass_at_50"].append(
            label_mass_at_budget(scores, labels, keep_fraction=0.50)
        )
        values["ndcg_at_25"].append(ndcg_at_budget(scores, labels, keep_fraction=0.25))
        values["ndcg_at_50"].append(ndcg_at_budget(scores, labels, keep_fraction=0.50))
    return values


def count_method_steps(rows: Sequence[Mapping[str, Any]], method: str) -> int:
    total = 0
    for row in rows:
        scores_by_method = row["scores_by_method"]
        if isinstance(scores_by_method, Mapping) and method in scores_by_method:
            total += int(row["n_steps"])
    return total


def bootstrap_mean_ci(values: np.ndarray, *, n_bootstrap: int, seed: int) -> dict[str, float]:
    if values.size == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    if n_bootstrap <= 0:
        mean = float(np.mean(values))
        return {"mean": mean, "ci_lower": mean, "ci_upper": mean}
    rng = np.random.default_rng(seed)
    means = np.empty(n_bootstrap, dtype=float)
    n = len(values)
    for idx in range(n_bootstrap):
        means[idx] = float(np.mean(values[rng.integers(0, n, n)]))
    return {
        "mean": float(np.mean(values)),
        "ci_lower": float(np.percentile(means, 2.5)),
        "ci_upper": float(np.percentile(means, 97.5)),
    }


def render_markdown_summary(report: Mapping[str, Any]) -> str:
    methods = sorted(
        report["methods"],
        key=lambda item: float(item["mean_ndcg_at_25"]),
        reverse=True,
    )
    top_methods = methods[:6]
    lines = [
        "# PRM800K Audit-Prioritization Summary",
        "",
        "This report is an offline audit-prioritization readout on the locked "
        "PRM800K split. It is not PRM training evidence, not filtering "
        "superiority evidence, and not GSM8K/HotpotQA replay validation.",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Samples: {report['n_samples']}",
        f"- Steps: {report['n_steps']}",
        "",
        "| Method | Top-1 max-label hit | Label mass@25% | Label mass@50% | "
        "NDCG@25% | NDCG@50% | Claim permission |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for method in top_methods:
        lines.append(
            "| {display} | {top1:.4f} | {mass25:.4f} | {mass50:.4f} | "
            "{ndcg25:.4f} | {ndcg50:.4f} | `{permission}` |".format(
                display=method["display_name"],
                top1=float(method["mean_top1_hit"]),
                mass25=float(method["mean_mass_at_25"]),
                mass50=float(method["mean_mass_at_50"]),
                ndcg25=float(method["mean_ndcg_at_25"]),
                ndcg50=float(method["mean_ndcg_at_50"]),
                permission=method["claim_permission"],
            )
        )
    lines.extend(["", operational_note(report), ""])
    return "\n".join(lines)


def operational_note(report: Mapping[str, Any]) -> str:
    methods = {method["method"]: method for method in report["methods"]}
    controls = [
        methods[name]["mean_ndcg_at_25"]
        for name in ("raw_local_utility", "relative_position", "span_length", "random")
        if name in methods
    ]
    best_control = max(controls) if controls else 0.0
    positives = [
        DISPLAY_NAMES[name]
        for name in ("w_struct", "scfma_ridge")
        if name in methods and methods[name]["mean_ndcg_at_25"] > best_control
    ]
    if positives:
        joined = " and ".join(positives)
        verb = "concentrates" if len(positives) == 1 else "concentrate"
        return (
            f"Operational note: {joined} {verb} high-rated PRM800K process "
            "steps better than the best simple control under the 25% review "
            "budget. This remains a locked-split step-ranking use case, not "
            "downstream PRM training or task replay validation."
        )
    return (
        "Operational note: w_struct and SC-FMA Ridge do not exceed the best simple "
        "control on NDCG@25% in this audit-prioritization readout. The result "
        "should be reported as context-only rather than as an operational "
        "improvement."
    )


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
