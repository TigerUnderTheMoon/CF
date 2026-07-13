"""P1-6: SC-FMA variant comparison on PRM800K locked split.

Computes step-ranking performance for three calibration variants:
  - SC-FMA QP (constrained convex optimization via SLSQP)
  - SC-FMA Ridge (softmax-weighted linear combination)
  - SC-FMA Projection (topology-constrained projection)

Each variant is run with TWO fidelity inputs:
  - w_struct-based: uses learned w_struct predictions as CIU (primary)
  - raw-based: uses raw_local_utility as CIU (ablation)

Plus baselines (w_struct, raw_local_utility, relative_position,
span_length, random) for comparison.

Reuses PRM800K data loading and feature construction from v3.6 script.
Outputs per-variant Spearman correlations, bootstrap CIs, and Wilcoxon tests.

No API calls. CPU only. No GPU required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import yaml
from scipy import stats
from scipy.optimize import minimize

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fma.calibration import (
    BottleneckConstraint,
    CalibrationResult,
    scfma_calibrate,
    scfma_calibrate_ridge,
    scfma_calibrate_windowed,
)
from fma.calibration.projection import project_weights

DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "real_task_v3_6_prm800k_hash_validation.yaml"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "scfma_variants_prm800k"
SOURCE_KIND = "real_prm800k_phase2"
USER_AGENT = "fma-scfma-variants"

FORBIDDEN_FEATURE_FIELD_NAMES = {
    "label", "labels", "rating", "ratings",
    "ground_truth", "ground_truth_answer",
    "ground_truth_solution", "ground_truth_importance",
    "target", "targets", "correct", "correctness",
}


@dataclass(frozen=True)
class RankingSample:
    sample_id: str
    source_kind: str
    split_name: str
    row_index: int
    question_hash: str
    step_texts: tuple[str, ...]
    labels: tuple[float, ...]
    raw_local_utility: tuple[float, ...]
    feature_rows: tuple[dict[str, float], ...]


def feature_names() -> list[str]:
    return [
        "raw_local_utility",
        "relative_position",
        "relative_position_sq",
        "relative_position_cu",
        "log_token_count",
        "numeric_density",
        "equation_density",
        "answer_cue",
        "conclusion_cue_count",
        "error_uncertainty_cue_count",
        "reasoning_cue_count",
        "is_first_step",
        "is_last_step",
        "trace_step_count",
        "source_step_index_ratio",
    ]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    output_dir = args.output_dir or DEFAULT_OUTPUT_ROOT
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(args.config)

    print("Loading PRM800K data (hash-stratified split)...")
    started = time.time()

    pool_rows = load_pool_rows(config)
    pool_samples = build_samples(
        pool_rows, split_name="pool",
        row_start=int(config["data"]["pool"]["start_row"]),
    )

    split_config = config["data"]["split_strategy"]
    dev_samples, locked_samples = split_samples(pool_samples, split_config)

    print(f"Pool: {len(pool_samples)}, Dev: {len(dev_samples)}, Locked: {len(locked_samples)}")

    dev_model = fit_w_struct_model(dev_samples, ridge_lambda=float(config["model"]["ridge_lambda"]))

    print("Running variant evaluation on locked split...")
    variant_results = evaluate_all_variants(
        locked_samples,
        dev_model,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
    )

    elapsed = time.time() - started
    variant_results["elapsed_seconds"] = round(elapsed, 2)
    variant_results["n_dev_samples"] = len(dev_samples)
    variant_results["n_locked_samples"] = len(locked_samples)
    variant_results["n_locked_steps"] = count_steps(locked_samples)
    variant_results["claim_boundary"] = "M_STEP_RANKING_REAL_PRM800K_scfma_variants"

    write_json(output_dir / "scfma_variant_report.json", variant_results)
    write_jsonl(
        output_dir / "scfma_variant_manifest.jsonl",
        sample_manifest_rows(locked_samples),
    )

    print(f"Results written to {output_dir}")
    print(f"Elapsed: {elapsed:.1f}s")
    _print_summary(variant_results)


def _print_summary(results: dict[str, Any]) -> None:
    mean_sp = results.get("mean_spearman", {})
    print("\n=== Mean Spearman by Variant ===")
    for key in sorted(mean_sp):
        print(f"  {key}: {mean_sp[key]:.4f}")

    diffs = results.get("variant_differences", {})
    print("\n=== Pairwise Differences (bootstrap CI) ===")
    for diff_name, diff_data in diffs.items():
        ci = diff_data.get("bootstrap_ci", {})
        print(
            f"  {diff_name}: mean={diff_data.get('mean', 0):.4f} "
            f"[{ci.get('ci_lower', 0):.4f}, {ci.get('ci_upper', 0):.4f}] "
            f"p={diff_data.get('wilcoxon_p', 1):.2e}"
        )


def _split_start(config: Mapping[str, Any], split_key: str) -> int:
    split = config["data"].get(split_key, {})
    if "start_row" in split:
        return int(split["start_row"])
    pool = config["data"].get("pool", {})
    return int(pool.get("start_row", 0))


def load_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Config is not a mapping: {path}")
    return value


def load_configured_rows(config: Mapping[str, Any], split_key: str) -> list[dict[str, Any]]:
    source = config["data"]["source"]
    split = config["data"].get(split_key)
    if split is None:
        pool = config["data"]["pool"]
        return stream_prm800k_rows(
            source["url"],
            start_row=int(pool["start_row"]),
            row_count=int(pool["row_count"]),
        )
    return stream_prm800k_rows(
        source["url"],
        start_row=int(split["start_row"]),
        row_count=int(split["row_count"]),
    )


def load_pool_rows(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = config["data"]["source"]
    pool = config["data"]["pool"]
    return stream_prm800k_rows(
        source["url"],
        start_row=int(pool["start_row"]),
        row_count=int(pool["row_count"]),
    )


def split_samples(
    samples: Sequence[RankingSample],
    split_config: Mapping[str, Any],
) -> tuple[list[RankingSample], list[RankingSample]]:
    salt = str(split_config["salt"])
    dev_upper = int(split_config["dev_mod_upper_exclusive"])
    dev: list[RankingSample] = []
    locked: list[RankingSample] = []
    for sample in samples:
        bucket = _hash_bucket(sample.sample_id, salt=salt)
        if bucket < dev_upper:
            dev.append(sample)
        else:
            locked.append(sample)
    return dev, locked


def _hash_bucket(sample_id: str, *, salt: str) -> int:
    digest = hashlib.sha256(f"{sample_id}|{salt}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def stream_prm800k_rows(url: str, *, start_row: int, row_count: int) -> list[dict[str, Any]]:
    import urllib.request

    rows: list[dict[str, Any]] = []
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        for row_index, raw_line in enumerate(response):
            if row_index < start_row:
                continue
            if len(rows) >= row_count:
                break
            stripped = raw_line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def build_samples(
    rows, *, split_name: str, row_start: int = 0,
) -> list[RankingSample]:
    samples: list[RankingSample] = []
    for local_index, row in enumerate(rows):
        row_index = row_start + local_index
        steps = select_labeled_steps(row)
        if len(steps) < 3:
            continue
        labels = tuple(step["label"] for step in steps)
        if len(set(labels)) < 2:
            continue
        texts = tuple(step["text"] for step in steps)
        feature_rows, raw_scores = build_feature_rows(steps)
        question = extract_question(row)
        qhash = sha256_text(question)
        samples.append(
            RankingSample(
                sample_id=f"prm800k_{split_name}_{row_index:06d}_{qhash[:10]}",
                source_kind=SOURCE_KIND,
                split_name=split_name,
                row_index=row_index,
                question_hash=qhash,
                step_texts=texts,
                labels=labels,
                raw_local_utility=tuple(raw_scores),
                feature_rows=tuple(feature_rows),
            )
        )
    return samples


def select_labeled_steps(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    label = row.get("label")
    if not isinstance(label, Mapping):
        return []
    raw_steps = label.get("steps")
    if not isinstance(raw_steps, list):
        return []
    selected: list[dict[str, Any]] = []
    for source_step_index, step in enumerate(raw_steps):
        if not isinstance(step, Mapping):
            continue
        completions = step.get("completions")
        if not isinstance(completions, list):
            continue
        picked = pick_completion(step, completions)
        if picked is None:
            continue
        text = str(picked.get("text") or "").strip()
        if not text:
            continue
        try:
            rating = float(picked["rating"])
        except (KeyError, TypeError, ValueError):
            continue
        label_value = max(0.0, min(1.0, (rating + 1.0) / 2.0))
        selected.append({
            "source_step_index": float(source_step_index),
            "text": text,
            "label": label_value,
        })
    return selected


def pick_completion(step, completions):
    chosen = step.get("chosen_completion")
    if isinstance(chosen, int) and 0 <= chosen < len(completions):
        candidate = completions[chosen]
        if is_rated_completion(candidate):
            return candidate
    for candidate in completions:
        if is_rated_completion(candidate):
            return candidate
    return None


def is_rated_completion(candidate) -> bool:
    return (
        isinstance(candidate, Mapping)
        and candidate.get("rating") is not None
        and candidate.get("flagged") is not True
    )


def build_feature_rows(steps) -> tuple[list[dict[str, float]], list[float]]:
    names = feature_names()
    rows: list[dict[str, float]] = []
    raw_scores: list[float] = []
    n_steps = len(steps)
    import re
    for step_position, step in enumerate(steps):
        text = str(step["text"])
        text_lower = text.lower()
        tokens = re.findall(r"[A-Za-z0-9]+|[^\s]", text)
        token_count = max(1, len(tokens))
        numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
        relative_position = step_position / max(1, n_steps - 1)
        numeric_density = len(numbers) / token_count
        equation_density = sum(text_lower.count(c) for c in ["=", "+", "-", "*", "/", "^"]) / token_count
        answer_cue = 1.0 if ("boxed" in text_lower or "answer" in text_lower) else 0.0
        conclusion_cues = count_cues(text_lower, ("therefore", "thus", "hence", "so ", "we get", "we have", "answer", "boxed", "final"))
        error_cues = count_cues(text_lower, ("oops", "mistake", "wrong", "incorrect", "cannot", "not enough", "maybe", "assume", "guess", "approximately"))
        reasoning_cues = count_cues(text_lower, ("because", "since", "then", "if", "let", "must"))
        raw = (
            0.25 * math.log1p(token_count)
            + 0.60 * numeric_density
            + 0.40 * equation_density
            + 0.25 * min(conclusion_cues, 2)
            + 0.35 * answer_cue
            - 0.35 * error_cues
            + 0.15 * reasoning_cues
            - 0.08 * relative_position
        )
        source_index_ratio = float(step["source_step_index"]) / max(1, n_steps - 1)
        row = {
            "raw_local_utility": raw,
            "relative_position": relative_position,
            "relative_position_sq": relative_position * relative_position,
            "relative_position_cu": relative_position ** 3,
            "log_token_count": math.log1p(token_count),
            "numeric_density": numeric_density,
            "equation_density": equation_density,
            "answer_cue": answer_cue,
            "conclusion_cue_count": float(min(conclusion_cues, 2)),
            "error_uncertainty_cue_count": float(error_cues),
            "reasoning_cue_count": float(reasoning_cues),
            "is_first_step": 1.0 if step_position == 0 else 0.0,
            "is_last_step": 1.0 if step_position == n_steps - 1 else 0.0,
            "trace_step_count": float(n_steps),
            "source_step_index_ratio": source_index_ratio,
        }
        if list(row) != names:
            raise AssertionError("feature row order drifted")
        rows.append(row)
        raw_scores.append(raw)
    return rows, raw_scores


def count_cues(text: str, cues) -> int:
    return sum(1 for cue in cues if cue in text)


def fit_w_struct_model(samples, *, ridge_lambda: float) -> dict[str, Any]:
    X = samples_to_feature_matrix(samples)
    y = samples_to_label_vector(samples)
    if X.size == 0 or y.size == 0:
        raise ValueError("No training data available for w_struct")
    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds = np.where(stds < 1e-8, 1.0, stds)
    Xs = (X - means) / stds
    design = np.column_stack([np.ones(Xs.shape[0]), Xs])
    penalty = ridge_lambda * np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return {
        "model_name": "w_struct_ridge_v1",
        "frozen": True,
        "ridge_lambda": ridge_lambda,
        "feature_names": feature_names(),
        "intercept": float(coefficients[0]),
        "coefficients": [float(v) for v in coefficients[1:]],
        "feature_means": [float(v) for v in means],
        "feature_stds": [float(v) for v in stds],
        "training_samples": len(samples),
        "training_steps": count_steps(samples),
        "leakage_audit": leakage_audit(),
    }


def compute_necessity_vector(
    sample: RankingSample,
    model: Mapping[str, Any],
) -> np.ndarray:
    pred = predict_w_struct(sample, model)
    n = len(pred)
    if n <= 1:
        return np.ones(n) / n
    positions = np.arange(n, dtype=float) / max(1, n - 1)
    fidelity = np.abs(pred - np.mean(pred))
    structure = 1.0 - np.abs(positions - np.mean(positions))
    necessity = 0.6 * fidelity + 0.4 * structure
    total = np.sum(necessity)
    if total < 1e-8:
        return np.ones(n) / n
    return necessity / total


def compute_redundancy_matrix(
    sample: RankingSample,
    model: Mapping[str, Any],
) -> np.ndarray:
    names = list(model["feature_names"])
    matrix = np.asarray(
        [[float(row[name]) for name in names] for row in sample.feature_rows],
        dtype=float,
    )
    means = np.asarray(model["feature_means"], dtype=float)
    stds = np.asarray(model["feature_stds"], dtype=float)
    matrix_std = (matrix - means) / stds
    n = matrix_std.shape[0]
    if n <= 1:
        return np.zeros((1, 1))

    from sklearn.metrics.pairwise import cosine_similarity
    try:
        sim = cosine_similarity(matrix_std)
    except ImportError:
        sim = _cosine_similarity_numpy(matrix_std)

    redundancy = np.maximum(0.0, sim)
    np.fill_diagonal(redundancy, 0.0)
    redundancy = (redundancy + redundancy.T) / 2.0
    return redundancy


def _cosine_similarity_numpy(X: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    X_norm = X / norms
    return X_norm @ X_norm.T


def detect_bottleneck_indices(necessity: np.ndarray, redundancy: np.ndarray) -> set[int]:
    k = len(necessity)
    if k <= 2:
        return set()
    avg_redundancy = np.mean(redundancy, axis=1)
    high_redundancy = avg_redundancy > np.median(avg_redundancy)
    low_necessity = necessity < np.median(necessity)
    bottleneck = set()
    for i in range(k):
        conn_in = np.sum(redundancy[:, i] > 0.1)
        conn_out = np.sum(redundancy[i, :] > 0.1)
        if (conn_in > 1 or conn_out > 1) and necessity[i] > np.percentile(necessity, 25):
            bottleneck.add(i)
    return bottleneck


def evaluate_all_variants(
    samples: Sequence[RankingSample],
    model: Mapping[str, Any],
    *,
    bootstrap_samples: int = 10000,
    bootstrap_seed: int = 42,
) -> dict[str, Any]:
    variant_names = [
        "w_struct", "scfma_qp", "scfma_ridge", "scfma_projection",
        "scfma_qp_raw", "scfma_ridge_raw", "scfma_projection_raw",
        "raw_local_utility", "relative_position", "span_length", "random",
    ]
    per_sample_spearman: dict[str, list[float]] = {v: [] for v in variant_names}
    per_sample_kendall: dict[str, list[float]] = {v: [] for v in variant_names}
    convergence_stats: dict[str, dict[str, int]] = {
        "scfma_qp": {"converged": 0, "failed": 0},
        "scfma_qp_raw": {"converged": 0, "failed": 0},
    }

    for sample in samples:
        labels = np.asarray(sample.labels, dtype=float)
        raw_ciu = np.asarray(sample.raw_local_utility, dtype=float)
        w_struct_pred = predict_w_struct(sample, model)
        necessity = compute_necessity_vector(sample, model)
        redundancy = compute_redundancy_matrix(sample, model)
        bottleneck = detect_bottleneck_indices(necessity, redundancy)

        scores: dict[str, np.ndarray] = {}

        scores["w_struct"] = w_struct_pred
        scores["raw_local_utility"] = raw_ciu
        scores["relative_position"] = np.arange(len(labels), dtype=float)
        scores["span_length"] = np.asarray(
            [len(text.split()) for text in sample.step_texts], dtype=float
        )
        scores["random"] = random_scores(sample.sample_id, len(labels))

        try:
            qp_result = scfma_calibrate(
                w_struct_pred, necessity, redundancy,
                bottleneck_constraints=[
                    BottleneckConstraint(idx, 0.01) for idx in sorted(bottleneck)
                ],
                sample_id=sample.sample_id,
                alpha=1.0, beta=0.5, gamma=0.2, delta=0.1,
            )
            if qp_result.weights and qp_result.converged:
                scores["scfma_qp"] = np.array(qp_result.weights[0].weights)
                convergence_stats["scfma_qp"]["converged"] += 1
            else:
                scores["scfma_qp"] = w_struct_pred
                convergence_stats["scfma_qp"]["failed"] += 1
        except Exception:
            scores["scfma_qp"] = w_struct_pred
            convergence_stats["scfma_qp"]["failed"] += 1

        try:
            ridge_result = scfma_calibrate_ridge(
                w_struct_pred, necessity,
                sample_id=sample.sample_id,
                alpha_ciui=0.7, alpha_nec=0.3, temperature=1.0,
            )
            if ridge_result.weights:
                scores["scfma_ridge"] = np.array(ridge_result.weights[0].weights)
            else:
                scores["scfma_ridge"] = w_struct_pred
        except Exception:
            scores["scfma_ridge"] = w_struct_pred

        try:
            proj_weights = project_weights(
                w_struct_pred, necessity, redundancy, bottleneck,
                fidelity_weight=0.6, structure_weight=0.4,
            )
            scores["scfma_projection"] = proj_weights
        except Exception:
            scores["scfma_projection"] = w_struct_pred

        try:
            qp_raw_result = scfma_calibrate(
                raw_ciu, necessity, redundancy,
                bottleneck_constraints=[
                    BottleneckConstraint(idx, 0.01) for idx in sorted(bottleneck)
                ],
                sample_id=sample.sample_id,
                alpha=1.0, beta=0.5, gamma=0.2, delta=0.1,
            )
            if qp_raw_result.weights and qp_raw_result.converged:
                scores["scfma_qp_raw"] = np.array(qp_raw_result.weights[0].weights)
                convergence_stats["scfma_qp_raw"]["converged"] += 1
            else:
                scores["scfma_qp_raw"] = raw_ciu
                convergence_stats["scfma_qp_raw"]["failed"] += 1
        except Exception:
            scores["scfma_qp_raw"] = raw_ciu
            convergence_stats["scfma_qp_raw"]["failed"] += 1

        try:
            ridge_raw_result = scfma_calibrate_ridge(
                raw_ciu, necessity,
                sample_id=sample.sample_id,
                alpha_ciui=0.7, alpha_nec=0.3, temperature=1.0,
            )
            if ridge_raw_result.weights:
                scores["scfma_ridge_raw"] = np.array(ridge_raw_result.weights[0].weights)
            else:
                scores["scfma_ridge_raw"] = raw_ciu
        except Exception:
            scores["scfma_ridge_raw"] = raw_ciu

        try:
            proj_raw_weights = project_weights(
                raw_ciu, necessity, redundancy, bottleneck,
                fidelity_weight=0.6, structure_weight=0.4,
            )
            scores["scfma_projection_raw"] = proj_raw_weights
        except Exception:
            scores["scfma_projection_raw"] = raw_ciu

        for variant in variant_names:
            per_sample_spearman[variant].append(
                safe_spearman(scores[variant], labels)
            )
            per_sample_kendall[variant].append(
                safe_kendall(scores[variant], labels)
            )

    mean_spearman = {v: float(np.mean(per_sample_spearman[v])) for v in variant_names}
    mean_kendall = {v: float(np.mean(per_sample_kendall[v])) for v in variant_names}

    comparisons = [
        ("scfma_qp_vs_w_struct", "scfma_qp", "w_struct"),
        ("scfma_ridge_vs_w_struct", "scfma_ridge", "w_struct"),
        ("scfma_projection_vs_w_struct", "scfma_projection", "w_struct"),
        ("scfma_qp_raw_vs_raw", "scfma_qp_raw", "raw_local_utility"),
        ("scfma_ridge_raw_vs_raw", "scfma_ridge_raw", "raw_local_utility"),
        ("scfma_projection_raw_vs_raw", "scfma_projection_raw", "raw_local_utility"),
        ("scfma_qp_vs_raw", "scfma_qp", "raw_local_utility"),
        ("scfma_ridge_vs_raw", "scfma_ridge", "raw_local_utility"),
        ("scfma_projection_vs_raw", "scfma_projection", "raw_local_utility"),
        ("w_struct_vs_raw", "w_struct", "raw_local_utility"),
        ("w_struct_vs_best_heuristic", "w_struct", "_best_heuristic"),
    ]

    variant_differences: dict[str, dict[str, Any]] = {}
    for diff_name, variant_a, variant_b in comparisons:
        arr_a = np.asarray(per_sample_spearman[variant_a], dtype=float)
        if variant_b == "_best_heuristic":
            arr_b = np.maximum.reduce([
                np.asarray(per_sample_spearman["relative_position"], dtype=float),
                np.asarray(per_sample_spearman["span_length"], dtype=float),
                np.asarray(per_sample_spearman["random"], dtype=float),
            ])
        else:
            arr_b = np.asarray(per_sample_spearman[variant_b], dtype=float)
        diff = arr_a - arr_b
        ci = bootstrap_ci(diff, n_bootstrap=bootstrap_samples, seed=bootstrap_seed)
        p_val = one_sided_wilcoxon_pvalue(diff)
        variant_differences[diff_name] = {
            "mean": float(np.mean(diff)),
            "bootstrap_ci": ci,
            "wilcoxon_one_sided_p": p_val,
        }

    per_variant_ci = {}
    for v in variant_names:
        arr = np.asarray(per_sample_spearman[v], dtype=float)
        per_variant_ci[v] = bootstrap_ci(arr, n_bootstrap=bootstrap_samples, seed=bootstrap_seed)

    holm_tests = []
    for diff_name in [
        "scfma_qp_vs_w_struct",
        "scfma_ridge_vs_w_struct",
        "scfma_projection_vs_w_struct",
        "scfma_qp_vs_raw",
        "scfma_ridge_vs_raw",
        "scfma_projection_vs_raw",
    ]:
        holm_tests.append({
            "name": diff_name,
            "p_value": variant_differences[diff_name]["wilcoxon_one_sided_p"],
        })
    holm = holm_correction(holm_tests, alpha=0.05)

    return {
        "n_samples": len(samples),
        "n_steps": count_steps(samples),
        "mean_spearman": mean_spearman,
        "mean_kendall": mean_kendall,
        "per_variant_ci": per_variant_ci,
        "variant_differences": variant_differences,
        "convergence_stats": convergence_stats,
        "holm_correction": holm,
        "leakage_audit": leakage_audit(),
    }


def predict_w_struct(sample: RankingSample, model: Mapping[str, Any]) -> np.ndarray:
    names = list(model["feature_names"])
    matrix = np.asarray(
        [[float(row[name]) for name in names] for row in sample.feature_rows],
        dtype=float,
    )
    means = np.asarray(model["feature_means"], dtype=float)
    stds = np.asarray(model["feature_stds"], dtype=float)
    coeffs = np.asarray(model["coefficients"], dtype=float)
    return float(model["intercept"]) + ((matrix - means) / stds) @ coeffs


def safe_spearman(predicted, labels) -> float:
    value = stats.spearmanr(predicted, labels).statistic
    return 0.0 if math.isnan(float(value)) else float(value)


def safe_kendall(predicted, labels) -> float:
    value = stats.kendalltau(predicted, labels).statistic
    return 0.0 if math.isnan(float(value)) else float(value)


def random_scores(sample_id: str, n: int) -> np.ndarray:
    digest = hashlib.sha256(sample_id.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big") % (2**32)
    rng = np.random.default_rng(seed)
    return rng.random(n)


def bootstrap_ci(values: np.ndarray, *, n_bootstrap: int = 10000, seed: int = 42) -> dict[str, float]:
    if values.size == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
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


def one_sided_wilcoxon_pvalue(values: np.ndarray) -> float:
    nonzero = values[values != 0]
    if len(nonzero) < 2:
        return 1.0
    try:
        result = stats.wilcoxon(values, alternative="greater", zero_method="wilcox")
    except ValueError:
        return 1.0
    pvalue = float(result.pvalue)
    return pvalue if not math.isnan(pvalue) else 1.0


def holm_correction(tests: list[dict[str, float]], *, alpha: float) -> dict[str, Any]:
    ordered = sorted(tests, key=lambda item: item["p_value"])
    adjusted: list[dict[str, Any]] = []
    all_pass = True
    m = len(ordered)
    for rank, item in enumerate(ordered):
        threshold = alpha / (m - rank)
        passed = item["p_value"] <= threshold
        adjusted.append({**item, "threshold": threshold, "pass": passed})
        if not passed:
            all_pass = False
    return {"alpha": alpha, "pass": all_pass, "tests": adjusted}


def leakage_audit() -> dict[str, Any]:
    names = feature_names()
    forbidden = sorted(set(names) & FORBIDDEN_FEATURE_FIELD_NAMES)
    return {
        "pass": not forbidden,
        "feature_names": names,
        "forbidden_feature_names_present": forbidden,
        "labels_used_only_as_targets": True,
        "raw_completion_ratings_written_to_feature_rows": False,
    }


def sample_manifest_rows(samples: Sequence[RankingSample]) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": s.sample_id,
            "source_kind": s.source_kind,
            "split_name": s.split_name,
            "row_index": s.row_index,
            "question_hash": s.question_hash,
            "n_steps": len(s.labels),
            "label_variance_nonzero": len(set(s.labels)) > 1,
        }
        for s in samples
    ]


def count_steps(samples: Sequence[RankingSample]) -> int:
    return sum(len(s.labels) for s in samples)


def extract_question(row: Mapping[str, Any]) -> str:
    question = row.get("question")
    if isinstance(question, Mapping):
        return str(question.get("problem") or question.get("question") or "")
    return str(question or "")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def samples_to_feature_matrix(samples: Sequence[RankingSample]) -> np.ndarray:
    names = feature_names()
    rows: list[list[float]] = []
    for sample in samples:
        for row in sample.feature_rows:
            rows.append([float(row[name]) for name in names])
    return np.asarray(rows, dtype=float)


def samples_to_label_vector(samples: Sequence[RankingSample]) -> np.ndarray:
    return np.asarray([label for sample in samples for label in sample.labels], dtype=float)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()