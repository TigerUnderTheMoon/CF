"""S3: ProcessBench cross-distribution preview for SC-FMA Ridge.

Loads ProcessBench via fma.data loader, converts OpenTraceRecord → RankingSample
using the same build_feature_rows() as PRM800K pipeline, fits w_struct on a dev
split, and evaluates step-ranking on a locked split.

This is an EXPLORATORY cross-distribution preview, not a preregistered validation.
Labels are ProcessBench step_labels (binary +1/-1 correctness), which are coarser
than PRM800K's continuous ratings.

CPU only. No GPU required. No API calls.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections.abc import Sequence as RuntimeSequence
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import stats as scipy_stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Reuse PRM800K pipeline functions
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from run_scfma_variants_prm800k import (  # noqa: E402
    RankingSample,
    build_feature_rows,
    feature_names,
    fit_w_struct_model,
    predict_w_struct,
)

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "s3_processbench_preview"
RIDGE_LAMBDA = 1.0
DEV_MOD_UPPER = 30  # 30% dev, 70% locked (matches PRM800K v3.6 ratio)
SALT = "processbench_s3_preview"
MAX_SAMPLES = 2000  # Cap to keep runtime reasonable
GUARD_REPORT_NAME = "s3_processbench_label_shape_guard.json"


def make_sample_id(question: str, idx: int) -> str:
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()[:12]
    return f"processbench_test_{digest}_{idx:06d}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_bucket(sample_id: str, *, salt: str) -> int:
    digest = hashlib.sha256(f"{sample_id}|{salt}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def opentrace_to_ranking_sample(record: dict, idx: int) -> RankingSample | None:
    """Convert ProcessBench record dict → RankingSample using build_feature_rows."""
    steps_data = []
    for ann in record["steps"]:
        if ann["ground_truth_importance"] is None:
            continue
        # ProcessBench labels: +1 (correct) / -1 (incorrect)
        # Normalize to [0, 1] like PRM800K: (label + 1) / 2
        raw_label = ann["ground_truth_importance"]
        if raw_label > 1.0:
            raw_label = 1.0
        elif raw_label < -1.0:
            raw_label = -1.0
        label_value = (raw_label + 1.0) / 2.0  # +1 → 1.0, -1 → 0.0
        steps_data.append({
            "source_step_index": float(ann["step_index"]),
            "text": ann["step_text"],
            "label": label_value,
        })

    # Filter: need at least 3 steps and label variation
    if len(steps_data) < 3:
        return None
    labels = [s["label"] for s in steps_data]
    if len(set(labels)) < 2:
        return None

    feature_rows, raw_scores = build_feature_rows(steps_data)
    texts = tuple(s["text"] for s in steps_data)

    return RankingSample(
        sample_id=make_sample_id(record["question"], idx),
        source_kind="processbench",
        split_name="test",
        row_index=idx,
        question_hash=sha256_text(record["question"]),
        step_texts=texts,
        labels=tuple(labels),
        raw_local_utility=tuple(raw_scores),
        feature_rows=tuple(feature_rows),
    )


def split_samples(samples: Sequence[RankingSample]) -> tuple[list, list]:
    dev, locked = [], []
    for sample in samples:
        if hash_bucket(sample.sample_id, salt=SALT) < DEV_MOD_UPPER:
            dev.append(sample)
        else:
            locked.append(sample)
    return dev, locked


def compute_spearman(pred: np.ndarray, labels: np.ndarray) -> float:
    if len(pred) < 2 or len(set(pred)) < 2 or len(set(labels)) < 2:
        return 0.0
    rho, _ = scipy_stats.spearmanr(pred, labels)
    return float(rho) if np.isfinite(rho) else 0.0


def compute_kendall(pred: np.ndarray, labels: np.ndarray) -> float:
    if len(pred) < 2 or len(set(pred)) < 2 or len(set(labels)) < 2:
        return 0.0
    tau, _ = scipy_stats.kendalltau(pred, labels)
    return float(tau) if np.isfinite(tau) else 0.0


def load_processbench_raw_rows() -> list[dict[str, Any]]:
    raw_path = PROJECT_ROOT / "outputs" / "s3_processbench_preview" / "raw_data" / "all_processbench.json"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"ProcessBench raw data not found at {raw_path}. "
            "Run scripts/download_processbench_direct.py first."
        )
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TypeError(f"Expected a JSON array in {raw_path}")
    return [row for row in data if isinstance(row, dict)]


def load_processbench_direct(raw_rows: Sequence[Mapping[str, Any]] | None = None) -> list:
    """Load ProcessBench from directly downloaded JSON files."""
    if raw_rows is None:
        raw_rows = load_processbench_raw_rows()
    records = []
    for row in raw_rows:
        problem = str(row.get("problem", ""))
        steps = row.get("steps", [])
        raw_labels = row.get("label", [])
        labels = (
            list(raw_labels)
            if isinstance(raw_labels, RuntimeSequence)
            and not isinstance(raw_labels, (str, bytes, bytearray))
            else []
        )
        is_correct = bool(row.get("final_answer_correct", True))
        generator = str(row.get("generator", "unknown"))
        source_file = str(row.get("_source_file", "unknown"))

        if not problem or not steps:
            continue

        # Build step annotations
        step_annotations = []
        for idx, step_text in enumerate(steps):
            text = str(step_text).strip()
            if not text:
                continue
            importance = None
            if idx < len(labels):
                label = labels[idx]
                if isinstance(label, bool):
                    importance = 1.0 if label else 0.0
                elif isinstance(label, (int, float)):
                    importance = float(label)
            step_annotations.append({
                "step_text": text,
                "step_index": idx,
                "ground_truth_importance": importance,
            })

        if not step_annotations:
            continue

        records.append({
            "question": problem,
            "steps": step_annotations,
            "is_correct": is_correct,
            "model_name": generator,
            "dataset": source_file,
        })
    return records


def build_label_shape_audit(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(records)
    step_label_records = 0
    trace_level_records = 0
    invalid_records = 0
    examples: list[dict[str, Any]] = []

    for record in records:
        steps = record.get("steps", [])
        labels = record.get("label")
        if isinstance(labels, RuntimeSequence) and not isinstance(labels, (str, bytes, bytearray)):
            if len(labels) == len(steps) and len(labels) > 0:
                step_label_records += 1
            else:
                invalid_records += 1
                examples.append(
                    {
                        "problem": record.get("problem", ""),
                        "label_type": type(labels).__name__,
                        "label_length": len(labels),
                        "step_length": len(steps),
                    }
                )
        else:
            trace_level_records += 1
            examples.append(
                {
                    "problem": record.get("problem", ""),
                    "label_type": type(labels).__name__,
                    "label_value_preview": labels,
                    "step_length": len(steps),
                }
            )

    step_label_available = total > 0 and step_label_records == total and invalid_records == 0
    failure_reason = (
        "per-step labels unavailable: raw ProcessBench labels are trace-level values, not a "
        "step-wise ranking target"
        if not step_label_available
        else ""
    )

    return {
        "dataset": "processbench/ProcessBench",
        "total_records": total,
        "step_label_records": step_label_records,
        "trace_level_records": trace_level_records,
        "invalid_records": invalid_records,
        "step_label_available": step_label_available,
        "claim_boundary": (
            "step_ranking_validation"
            if step_label_available
            else "not_step_ranking_validation"
        ),
        "failure_reason": failure_reason,
        "examples": examples[:5],
        "validated_kbs_workflow": False,
    }


def write_guard_report(audit: Mapping[str, Any], output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / GUARD_REPORT_NAME
    out_path.write_text(json.dumps(dict(audit), indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def main() -> None:
    print("=" * 80)
    print("S3: ProcessBench Cross-Distribution Preview (EXPLORATORY)")
    print("=" * 80)
    print(f"\nMax samples: {MAX_SAMPLES}")
    print(f"Dev/locked split: {DEV_MOD_UPPER}/{100 - DEV_MOD_UPPER}%")
    print(f"Ridge lambda: {RIDGE_LAMBDA}")

    print("\nLoading ProcessBench from local download...")
    t0 = time.time()
    all_records = load_processbench_raw_rows()
    elapsed_load = time.time() - t0
    print(f"Loaded {len(all_records)} raw records in {elapsed_load:.1f}s")

    label_audit = build_label_shape_audit(all_records)
    if not label_audit["step_label_available"]:
        guard_path = write_guard_report(label_audit)
        print("\nProcessBench labels are not step-wise; writing guard report only.")
        print(f"Guard report saved to {guard_path}")
        return

    # Cap samples
    raw_records = all_records[:MAX_SAMPLES] if MAX_SAMPLES > 0 else all_records
    print(f"Using first {len(raw_records)} raw records (cap={MAX_SAMPLES})")

    if not raw_records:
        print("ERROR: No ProcessBench records loaded")
        return

    records = load_processbench_direct(raw_records)
    print(f"Converted {len(records)} records with per-step labels")

    # Show sample structure
    sample_rec = records[0]
    print(f"\nSample record:")
    print(f"  question: {sample_rec['question'][:100]}...")
    print(f"  dataset: {sample_rec['dataset']}")
    print(f"  is_correct: {sample_rec['is_correct']}")
    print(f"  n_steps: {len(sample_rec['steps'])}")
    if sample_rec["steps"]:
        step = sample_rec["steps"][0]
        print(f"  first step: text={step['step_text'][:80]}... importance={step['ground_truth_importance']}")

    # Convert to RankingSample
    print("\nConverting to RankingSample format...")
    samples = []
    for idx, record in enumerate(records):
        sample = opentrace_to_ranking_sample(record, idx)
        if sample is not None:
            samples.append(sample)

    print(f"Converted: {len(samples)}/{len(records)} samples passed filter (≥3 steps, label variation)")
    if not samples:
        print("ERROR: No samples passed filter")
        return

    total_steps = sum(len(s.labels) for s in samples)
    print(f"Total steps: {total_steps}")

    # Split dev/locked
    dev_samples, locked_samples = split_samples(samples)
    print(f"Dev: {len(dev_samples)} samples, Locked: {len(locked_samples)} samples")

    if len(dev_samples) < 10 or len(locked_samples) < 10:
        print("WARNING: Too few samples for meaningful evaluation")
        # Fall back to using all samples for both fit and evaluate (in-sample)
        dev_samples = samples
        locked_samples = samples
        print("Falling back to in-sample evaluation (fit and evaluate on same data)")

    # Fit w_struct on dev
    print("\nFitting w_struct ridge regression on dev split...")
    t0 = time.time()
    model = fit_w_struct_model(dev_samples, ridge_lambda=RIDGE_LAMBDA)
    elapsed_fit = time.time() - t0
    print(f"Model fitted in {elapsed_fit:.2f}s")
    print(f"Training samples: {model['training_samples']}, training steps: {model['training_steps']}")

    # Evaluate on locked split
    print("\nEvaluating on locked split...")
    w_struct_spearmans = []
    w_struct_kendalls = []
    raw_ciu_spearmans = []
    relative_position_spearmans = []

    for sample in locked_samples:
        labels = np.array(sample.labels, dtype=float)
        pred = predict_w_struct(sample, model)
        w_struct_spearmans.append(compute_spearman(pred, labels))
        w_struct_kendalls.append(compute_kendall(pred, labels))

        # Raw CIU baseline
        raw = np.array(sample.raw_local_utility, dtype=float)
        raw_ciu_spearmans.append(compute_spearman(raw, labels))

        # Relative position baseline
        n = len(labels)
        rel_pos = np.arange(n, dtype=float) / max(1, n - 1)
        relative_position_spearmans.append(compute_spearman(rel_pos, labels))

    mean_w_struct = float(np.mean(w_struct_spearmans)) if w_struct_spearmans else 0.0
    mean_w_struct_kendall = float(np.mean(w_struct_kendalls)) if w_struct_kendalls else 0.0
    mean_raw = float(np.mean(raw_ciu_spearmans)) if raw_ciu_spearmans else 0.0
    mean_relpos = float(np.mean(relative_position_spearmans)) if relative_position_spearmans else 0.0

    # Bootstrap CI for w_struct
    rng = np.random.default_rng(42)
    n_bootstrap = 1000
    bootstrap_means = []
    if len(w_struct_spearmans) > 10:
        for _ in range(n_bootstrap):
            idx = rng.integers(0, len(w_struct_spearmans), len(w_struct_spearmans))
            bootstrap_means.append(np.mean([w_struct_spearmans[i] for i in idx]))
        ci_lower = float(np.percentile(bootstrap_means, 2.5))
        ci_upper = float(np.percentile(bootstrap_means, 97.5))
    else:
        ci_lower = ci_upper = mean_w_struct

    # Summary
    print("\n" + "=" * 80)
    print("S3 Results: ProcessBench Step-Ranking (Exploratory)")
    print("=" * 80)
    print(f"\nDataset: ProcessBench (test split)")
    print(f"Samples loaded: {len(records)}")
    print(f"Samples passed filter: {len(samples)}")
    print(f"Total steps: {total_steps}")
    print(f"Dev split: {len(dev_samples)}, Locked split: {len(locked_samples)}")
    print(f"\n{'Method':<30} {'Mean Spearman':>14} {'95% CI':>22}")
    print("-" * 70)
    print(f"{'w_struct (frozen ridge)':<30} {mean_w_struct:>14.4f} {'[' + f'{ci_lower:.4f}, {ci_upper:.4f}' + ']':>22}")
    print(f"{'raw_local_utility':<30} {mean_raw:>14.4f} {'':>22}")
    print(f"{'relative_position':<30} {mean_relpos:>14.4f} {'':>22}")
    print(f"\n{'w_struct Kendall τ':<30} {mean_w_struct_kendall:>14.4f}")

    # Compare to PRM800K
    print("\n## Cross-Distribution Comparison")
    print(f"\n{'Dataset':<20} {'w_struct ρ':>12} {'raw CIU ρ':>12} {'n_samples':>10}")
    print("-" * 58)
    print(f"{'PRM800K (v3.6)':<20} {'0.6113':>12} {'-0.0775':>12} {'4417':>10}")
    print(f"{'ProcessBench (S3)':<20} {mean_w_struct:>12.4f} {mean_raw:>12.4f} {len(locked_samples):>10}")

    # Save
    summary = {
        "experiment": "S3_processbench_cross_distribution_preview",
        "exploratory": True,
        "preregistered": False,
        "dataset": "processbench/ProcessBench",
        "split": "test",
        "max_samples_requested": MAX_SAMPLES,
        "records_loaded": len(records),
        "samples_passed_filter": len(samples),
        "total_steps": total_steps,
        "dev_samples": len(dev_samples),
        "locked_samples": len(locked_samples),
        "ridge_lambda": RIDGE_LAMBDA,
        "dev_mod_upper": DEV_MOD_UPPER,
        "results": {
            "w_struct": {
                "mean_spearman": mean_w_struct,
                "mean_kendall": mean_w_struct_kendall,
                "bootstrap_ci_lower": ci_lower,
                "bootstrap_ci_upper": ci_upper,
                "n_bootstrap": n_bootstrap,
            },
            "raw_local_utility": {
                "mean_spearman": mean_raw,
            },
            "relative_position": {
                "mean_spearman": mean_relpos,
            },
        },
        "label_normalization": "ProcessBench +1/-1 → (label+1)/2 → [0, 1]",
        "filter_criteria": "≥3 steps, ≥2 distinct label values",
        "claim_boundary": "exploratory_cross_distribution_preview_not_validation",
        "forbidden_claims": [
            "external generalization",
            "processbench validation pass",
            "cross-distribution superiority",
            "causal identification",
        ],
        "elapsed_seconds": {
            "load": elapsed_load,
            "fit": elapsed_fit,
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "s3_processbench_preview.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSummary saved to {out_path}")


if __name__ == "__main__":
    main()
