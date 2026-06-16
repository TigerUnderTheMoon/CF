"""P1-7: Extended statistical tests for PRM800K variant comparison.

Adds:
  - Per-variant paired Wilcoxon tests vs w_struct (Holm-corrected)
  - Friedman test across all variants
  - Nemenyi post-hoc test (critical difference diagram data)
  - Effect sizes (Cohen's d) for key comparisons
  - Bootstrapped CI for each variant

Reuses data from v3.6 and v3.8 runs plus P1-6 variant scores.
No API calls. CPU only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.run_scfma_variants_prm800k import (
    RankingSample,
    build_samples,
    count_steps,
    leakage_audit,
    load_config,
    fit_w_struct_model,
    predict_w_struct,
    safe_kendall,
    safe_spearman,
    feature_names,
    compute_necessity_vector,
    compute_redundancy_matrix,
    detect_bottleneck_indices,
    stream_prm800k_rows,
)

from fma.calibration import (
    BottleneckConstraint,
    scfma_calibrate,
    scfma_calibrate_ridge,
)
from fma.calibration.projection import project_weights

DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "real_task_v3_6_prm800k_hash_validation.yaml"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "p1_7_statistical_tests"
V3_8_SCORES = PROJECT_ROOT / "outputs" / "real_task_v3_8_prm_locked_scoring" / "locked_prm_scores.jsonl"


def _split_start(config: Mapping[str, Any], split_key: str) -> int:
    split = config["data"].get(split_key, {})
    if "start_row" in split:
        return int(split["start_row"])
    pool = config["data"].get("pool", {})
    return int(pool.get("start_row", 0))


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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--prm-scores", type=Path, default=V3_8_SCORES)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args()
    output_dir = args.output_dir or DEFAULT_OUTPUT_ROOT
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(args.config)
    started = time.time()

    print("Loading PRM800K data (hash-stratified split)...")
    config = load_config(args.config)
    started = time.time()

    pool_rows = load_pool_rows(config)
    pool_samples = build_samples(
        pool_rows, split_name="pool",
        row_start=int(config["data"]["pool"]["start_row"]),
    )
    print(f"Pool: {len(pool_samples)} samples")

    split_config = config["data"]["split_strategy"]
    dev_samples, locked_samples = split_samples(pool_samples, split_config)
    print(f"Dev: {len(dev_samples)} samples, Locked: {len(locked_samples)} samples")

    dev_model = fit_w_struct_model(dev_samples, ridge_lambda=float(config["model"]["ridge_lambda"]))

    print("Loading PRM scores from v3.8...")
    prm_scores_by_hash = load_prm_scores_by_hash(args.prm_scores)
    print(f"Loaded PRM scores for {len(prm_scores_by_hash)} samples")

    print("Computing per-sample Spearman for all methods...")
    all_variant_names = [
        "w_struct", "scfma_qp", "scfma_ridge", "scfma_projection",
        "raw_local_utility", "relative_position", "span_length", "random", "prm",
    ]
    per_sample_spearman: dict[str, list[float]] = {v: [] for v in all_variant_names}
    per_sample_kendall: dict[str, list[float]] = {v: [] for v in all_variant_names}
    convergence_qp = {"converged": 0, "failed": 0}
    matched_prm = 0
    unmatched_prm = 0

    for sample in locked_samples:
        labels = np.asarray(sample.labels, dtype=float)
        raw_ciu = np.asarray(sample.raw_local_utility, dtype=float)
        w_struct_pred = predict_w_struct(sample, dev_model)
        necessity = compute_necessity_vector(sample, dev_model)
        redundancy = compute_redundancy_matrix(sample, dev_model)
        bottleneck = detect_bottleneck_indices(necessity, redundancy)
        n = len(labels)

        scores: dict[str, np.ndarray] = {}
        scores["w_struct"] = w_struct_pred
        scores["raw_local_utility"] = raw_ciu
        scores["relative_position"] = np.arange(n, dtype=float)
        scores["span_length"] = np.asarray(
            [len(text.split()) for text in sample.step_texts], dtype=float
        )
        scores["random"] = random_scores(sample.sample_id, n)

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
                convergence_qp["converged"] += 1
            else:
                scores["scfma_qp"] = w_struct_pred
                convergence_qp["failed"] += 1
        except Exception:
            scores["scfma_qp"] = w_struct_pred
            convergence_qp["failed"] += 1

        try:
            ridge_result = scfma_calibrate_ridge(
                w_struct_pred, necessity,
                sample_id=sample.sample_id,
                alpha_ciui=0.7, alpha_nec=0.3, temperature=1.0,
            )
            scores["scfma_ridge"] = np.array(ridge_result.weights[0].weights) if ridge_result.weights else w_struct_pred
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

        question_hash = getattr(sample, "question_hash", "") or ""
        if question_hash in prm_scores_by_hash:
            prm_vec = prm_scores_by_hash[question_hash]
            if len(prm_vec) == n:
                scores["prm"] = np.asarray(prm_vec, dtype=float)
                matched_prm += 1
            else:
                scores["prm"] = w_struct_pred
                unmatched_prm += 1
        else:
            scores["prm"] = w_struct_pred
            unmatched_prm += 1

        for variant in all_variant_names:
            per_sample_spearman[variant].append(
                safe_spearman(scores[variant], labels)
            )
            per_sample_kendall[variant].append(
                safe_kendall(scores[variant], labels)
            )

    print(f"PRM matched: {matched_prm}, unmatched: {unmatched_prm}")

    mean_spearman = {v: float(np.mean(per_sample_spearman[v])) for v in all_variant_names}
    mean_kendall = {v: float(np.mean(per_sample_kendall[v])) for v in all_variant_names}

    print("\n=== Mean Spearman ===")
    for v in all_variant_names:
        print(f"  {v}: {mean_spearman[v]:.4f}")

    per_variant_ci = {}
    for v in all_variant_names:
        arr = np.asarray(per_sample_spearman[v], dtype=float)
        per_variant_ci[v] = bootstrap_ci(arr, n_bootstrap=args.bootstrap_samples, seed=args.bootstrap_seed)

    variant_differences = {}
    comparison_pairs = [
        ("scfma_ridge_vs_w_struct", "scfma_ridge", "w_struct"),
        ("scfma_qp_vs_w_struct", "scfma_qp", "w_struct"),
        ("scfma_projection_vs_w_struct", "scfma_projection", "w_struct"),
        ("w_struct_vs_raw", "w_struct", "raw_local_utility"),
        ("w_struct_vs_prm", "w_struct", "prm"),
        ("scfma_ridge_vs_prm", "scfma_ridge", "prm"),
        ("w_struct_vs_best_heuristic", "w_struct", "_best_heuristic"),
    ]
    for diff_name, variant_a, variant_b in comparison_pairs:
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
        ci = bootstrap_ci(diff, n_bootstrap=args.bootstrap_samples, seed=args.bootstrap_seed)
        p_val = one_sided_wilcoxon_pvalue(diff)
        d = cohens_d(arr_a, arr_b)
        variant_differences[diff_name] = {
            "mean": float(np.mean(diff)),
            "bootstrap_ci": ci,
            "wilcoxon_one_sided_p": p_val,
            "cohens_d": d,
        }

    friedman_results = friedman_test(per_sample_spearman, all_variant_names)

    nemenyi_results = nemenyi_posthoc(
        per_sample_spearman, all_variant_names,
        nemenyi_alpha=0.05,
    )

    holm_tests = []
    for diff_name in comparison_pairs:
        holm_tests.append({
            "name": diff_name[0],
            "p_value": variant_differences[diff_name[0]]["wilcoxon_one_sided_p"],
        })
    holm = holm_correction(holm_tests, alpha=0.05)

    wilk_pairs = all_pairwise_wilcoxon(per_sample_spearman, all_variant_names)
    holm_all = holm_correction(
        [{"name": n, "p_value": p} for n, p in wilk_pairs],
        alpha=0.05,
    )

    report = {
        "n_samples": len(locked_samples),
        "n_steps": count_steps(locked_samples),
        "n_prm_matched": matched_prm,
        "n_prm_unmatched": unmatched_prm,
        "mean_spearman": mean_spearman,
        "mean_kendall": mean_kendall,
        "per_variant_ci": per_variant_ci,
        "variant_differences": variant_differences,
        "convergence_stats": convergence_qp,
        "friedman_test": friedman_results,
        "nemenyi_posthoc": nemenyi_results,
        "holm_correction_key_comparisons": holm,
        "all_pairwise_wilcoxon": wilk_pairs,
        "holm_all_pairwise": holm_all,
        "leakage_audit": leakage_audit(),
        "elapsed_seconds": round(time.time() - started, 2),
        "claim_boundary": "M_STEP_RANKING_REAL_PRM800K_statistical_tests",
    }

    write_json(output_dir / "p1_7_statistical_report.json", report)
    print(f"\nResults written to {output_dir}")
    print_summary(report)


def print_summary(report: dict[str, Any]) -> None:
    mean_sp = report["mean_spearman"]
    print("\n=== Mean Spearman ===")
    for v in sorted(mean_sp, key=lambda k: mean_sp[k], reverse=True):
        ci = report["per_variant_ci"].get(v, {})
        print(f"  {v:30s}: rho={mean_sp[v]:.4f}  [{ci.get('ci_lower',0):.4f}, {ci.get('ci_upper',0):.4f}]")

    friedman = report["friedman_test"]
    print(f"\n=== Friedman Test ===")
    print(f"  statistic={friedman['statistic']:.2f}, p={friedman['p_value']:.2e}, n={friedman['n_samples']}")

    print(f"\n=== Key Pairwise Comparisons ===")
    for name, data in report["variant_differences"].items():
        ci = data["bootstrap_ci"]
        print(f"  {name:40s}: mean={data['mean']:+.4f}  [{ci['ci_lower']:+.4f}, {ci['ci_upper']:+.4f}]  p={data['wilcoxon_one_sided_p']:.2e}  d={data['cohens_d']:.3f}")

    nemenyi = report["nemenyi_posthoc"]
    print(f"\n=== Nemenyi Post-hoc (CD={nemenyi['critical_difference']:.4f}) ===")
    for item in nemenyi["mean_ranks"]:
        print(f"  {item['method']:30s}: rank={item['mean_rank']:.2f}")


def random_scores(sample_id: str, n: int) -> np.ndarray:
    digest = hashlib.sha256(sample_id.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big") % (2**32)
    rng = np.random.default_rng(seed)
    return rng.random(n)


def load_prm_scores_by_hash(path: Path) -> dict[str, list[float]]:
    scores: dict[str, list[float]] = {}
    if not path.exists():
        print(f"WARNING: PRM scores file not found: {path}")
        return scores
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            qhash = record.get("question_hash", "")
            if qhash and "scores" in record:
                scores[qhash] = record["scores"]
    return scores


def bootstrap_ci(
    values: np.ndarray, *, n_bootstrap: int = 10000, seed: int = 42,
) -> dict[str, float]:
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
        result = stats.wilcoxon(values, alternative="less", zero_method="wilcox")
    except ValueError:
        return 1.0
    pvalue = float(result.pvalue)
    return pvalue if not math.isnan(pvalue) else 1.0


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    diff = a - b
    if len(diff) < 2:
        return 0.0
    std = float(np.std(diff, ddof=1))
    if std < 1e-10:
        return 0.0
    return float(np.mean(diff)) / std


def friedman_test(
    per_sample: dict[str, list[float]], variant_names: list[str],
) -> dict[str, Any]:
    matrix = np.column_stack([
        np.asarray(per_sample[v], dtype=float) for v in variant_names
    ])
    n_samples, k = matrix.shape
    try:
        stat, p = stats.friedmanchisquare(
            *[matrix[:, i] for i in range(k)]
        )
    except Exception:
        return {"statistic": 0.0, "p_value": 1.0, "n_samples": n_samples, "k": k}
    return {
        "statistic": float(stat),
        "p_value": float(p),
        "n_samples": n_samples,
        "k": k,
    }


def nemenyi_posthoc(
    per_sample: dict[str, list[float]], variant_names: list[str],
    *, nemenyi_alpha: float = 0.05,
) -> dict[str, Any]:
    matrix = np.column_stack([
        np.asarray(per_sample[v], dtype=float) for v in variant_names
    ])
    n, k = matrix.shape
    ranks = np.zeros_like(matrix)
    for i in range(n):
        ranks[i] = stats.rankdata(-matrix[i])

    mean_ranks = np.mean(ranks, axis=0)
    q_alpha = 2.343  # q(0.05) for infinite df from studentized range
    cd = q_alpha * np.sqrt(k * (k + 1) / (6 * n))

    rank_list = [
        {"method": v, "mean_rank": float(mean_ranks[j])}
        for j, v in enumerate(variant_names)
    ]
    rank_list.sort(key=lambda x: x["mean_rank"])

    n_significant = 0
    for i in range(k):
        for j in range(i + 1, k):
            if abs(mean_ranks[i] - mean_ranks[j]) > cd:
                n_significant += 1

    return {
        "critical_difference": float(cd),
        "alpha": nemenyi_alpha,
        "q_alpha": float(q_alpha),
        "mean_ranks": rank_list,
        "n_significant_pairs": n_significant,
        "total_pairs": k * (k - 1) // 2,
    }


def all_pairwise_wilcoxon(
    per_sample: dict[str, list[float]], variant_names: list[str],
) -> list[tuple[str, float]]:
    results: list[tuple[str, float]] = []
    for i, v_a in enumerate(variant_names):
        for j, v_b in enumerate(variant_names):
            if j <= i:
                continue
            arr_a = np.asarray(per_sample[v_a], dtype=float)
            arr_b = np.asarray(per_sample[v_b], dtype=float)
            diff = arr_a - arr_b
            nonzero = diff[diff != 0]
            if len(nonzero) < 2:
                p = 1.0
            else:
                try:
                    result = stats.wilcoxon(diff, alternative="two-sided", zero_method="wilcox")
                    p = float(result.pvalue)
                    if math.isnan(p):
                        p = 1.0
                except ValueError:
                    p = 1.0
            name = f"{v_a}_vs_{v_b}"
            results.append((name, p))
    return results


def holm_correction(
    tests: list[dict[str, Any]], *, alpha: float,
) -> dict[str, Any]:
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


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()