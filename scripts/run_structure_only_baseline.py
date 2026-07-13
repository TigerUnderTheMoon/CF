"""Same-supervision structure-only Ridge baseline on the PRM800K locked split.

Reviewer question answered: *under identical supervision, does graph-derived
structural information carry step-ranking signal?*

This script reuses the EXACT PRM800K hash split, target extraction, Ridge
training procedure, and metrics used by the ``w_struct`` fidelity field
(``run_scfma_variants_prm800k`` / ``run_prm800k_audit_prioritization``). The
only thing that changes is the feature set: instead of the 15 lexical/positional
w_struct features, we fit Ridge on graph-derived structural features
(necessity, redundancy density, bottleneck flag, degree/eigenvector/betweenness
centrality) computed from a per-trace TF-IDF step-similarity graph.

Crucially, the structural features are computed INDEPENDENTLY of the lexical
w_struct model (no w_struct predictions feed the features), so this is a clean
"structure-only" control rather than a re-expression of the lexical model.

Two structural feature sets are reported:
  - structure_graph:          pure topological features (no position, no lexical)
  - structure_graph_position: topological + trace-position features

References reported alongside: w_struct (full lexical Ridge) and
raw_local_utility. Same dev/locked split, same target, same Ridge closed form
(standardized features, unpenalized intercept, ridge_lambda from config).

No API calls. CPU only. Streams PRM800K phase2 rows over HTTP per the config.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for _p in (PROJECT_ROOT, PROJECT_ROOT / "src", SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import run_scfma_variants_prm800k as variants  # noqa: E402
from fma.eval.prm800k_audit_prioritization import (  # noqa: E402
    label_mass_at_budget,
    max_label_hit_at_budget,
    ndcg_at_budget,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "structure_only_baseline"

# Edge threshold for the thresholded topical-similarity graph (matches the
# redundancy>0.1 connectivity rule used by detect_bottleneck_indices).
EDGE_THRESHOLD = 0.1

STRUCTURE_GRAPH_FEATURES = [
    "redundancy_density",
    "max_similarity",
    "degree_centrality",
    "weighted_degree",
    "eigenvector_centrality",
    "betweenness_centrality",
    "bottleneck_flag",
]
POSITION_FEATURES = [
    "relative_position",
    "is_first_step",
    "is_last_step",
    "log_step_count",
]


# --------------------------------------------------------------------------- #
# Structural feature extraction (independent of the lexical w_struct model)
# --------------------------------------------------------------------------- #
def _tfidf_similarity(step_texts: Sequence[str]) -> np.ndarray:
    """Cosine similarity over per-trace TF-IDF vectors of step texts."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    k = len(step_texts)
    if k <= 1:
        return np.zeros((k, k), dtype=float)
    try:
        vectorizer = TfidfVectorizer(lowercase=True, stop_words=None)
        tfidf = vectorizer.fit_transform([t if t.strip() else " " for t in step_texts])
        if tfidf.shape[1] == 0:
            return np.zeros((k, k), dtype=float)
        sim = cosine_similarity(tfidf)
    except ValueError:
        return np.zeros((k, k), dtype=float)
    sim = np.asarray(sim, dtype=float)
    sim = np.maximum(0.0, sim)
    np.fill_diagonal(sim, 0.0)
    return (sim + sim.T) / 2.0


def _centralities(sim: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Eigenvector centrality (weighted) and betweenness (thresholded graph)."""
    import networkx as nx

    k = sim.shape[0]
    eig = np.zeros(k, dtype=float)
    btw = np.zeros(k, dtype=float)
    if k <= 2:
        return eig, btw

    g_weighted = nx.Graph()
    g_weighted.add_nodes_from(range(k))
    g_thresholded = nx.Graph()
    g_thresholded.add_nodes_from(range(k))
    for i in range(k):
        for j in range(i + 1, k):
            w = float(sim[i, j])
            if w > 0.0:
                g_weighted.add_edge(i, j, weight=w)
            if w > EDGE_THRESHOLD:
                g_thresholded.add_edge(i, j)

    try:
        eig_map = nx.eigenvector_centrality_numpy(g_weighted, weight="weight")
        eig = np.asarray([eig_map.get(i, 0.0) for i in range(k)], dtype=float)
    except Exception:
        # Fallback: weighted degree (already structural) normalized.
        wd = sim.sum(axis=1)
        eig = wd / wd.max() if wd.max() > 0 else wd

    try:
        btw_map = nx.betweenness_centrality(g_thresholded, normalized=True)
        btw = np.asarray([btw_map.get(i, 0.0) for i in range(k)], dtype=float)
    except Exception:
        btw = np.zeros(k, dtype=float)
    return eig, btw


def structural_feature_rows(sample: "variants.RankingSample") -> list[dict[str, float]]:
    """Per-step graph-derived structural features. No lexical / no w_struct."""
    texts = list(sample.step_texts)
    k = len(texts)
    sim = _tfidf_similarity(texts)
    eig, btw = _centralities(sim)

    if k > 1:
        redundancy_density = sim.mean(axis=1) * (k / (k - 1))  # mean over off-diagonal
        max_similarity = sim.max(axis=1)
        weighted_degree = sim.sum(axis=1)
        degree_centrality = (sim > EDGE_THRESHOLD).sum(axis=1).astype(float) / (k - 1)
    else:
        redundancy_density = np.zeros(k)
        max_similarity = np.zeros(k)
        weighted_degree = np.zeros(k)
        degree_centrality = np.zeros(k)

    # Bottleneck: connector node in the thresholded graph (pipeline-style rule),
    # here computed purely from the topical graph rather than from w_struct.
    conn = (sim > EDGE_THRESHOLD)
    bottleneck_flag = np.zeros(k, dtype=float)
    if k > 2:
        deg = conn.sum(axis=1)
        med_wd = np.median(weighted_degree)
        for i in range(k):
            if deg[i] > 1 and weighted_degree[i] >= med_wd:
                bottleneck_flag[i] = 1.0

    rows: list[dict[str, float]] = []
    for i in range(k):
        rel = i / max(1, k - 1)
        rows.append(
            {
                "redundancy_density": float(redundancy_density[i]),
                "max_similarity": float(max_similarity[i]),
                "degree_centrality": float(degree_centrality[i]),
                "weighted_degree": float(weighted_degree[i]),
                "eigenvector_centrality": float(eig[i]),
                "betweenness_centrality": float(btw[i]),
                "bottleneck_flag": float(bottleneck_flag[i]),
                "relative_position": float(rel),
                "is_first_step": 1.0 if i == 0 else 0.0,
                "is_last_step": 1.0 if i == k - 1 else 0.0,
                "log_step_count": float(np.log1p(k)),
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# Generic Ridge (identical closed form to fit_w_struct_model)
# --------------------------------------------------------------------------- #
def fit_ridge(
    feature_rows_per_sample: Sequence[Sequence[Mapping[str, float]]],
    labels_per_sample: Sequence[Sequence[float]],
    feature_list: Sequence[str],
    *,
    ridge_lambda: float,
) -> dict[str, Any]:
    X = np.asarray(
        [[float(row[name]) for name in feature_list]
         for rows in feature_rows_per_sample for row in rows],
        dtype=float,
    )
    y = np.asarray([lbl for labels in labels_per_sample for lbl in labels], dtype=float)
    if X.size == 0 or y.size == 0:
        raise ValueError("No training data for structure-only Ridge")
    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds = np.where(stds < 1e-8, 1.0, stds)
    Xs = (X - means) / stds
    design = np.column_stack([np.ones(Xs.shape[0]), Xs])
    penalty = ridge_lambda * np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    coeffs = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return {
        "feature_names": list(feature_list),
        "intercept": float(coeffs[0]),
        "coefficients": [float(v) for v in coeffs[1:]],
        "feature_means": [float(v) for v in means],
        "feature_stds": [float(v) for v in stds],
        "ridge_lambda": ridge_lambda,
    }


def predict_ridge(rows: Sequence[Mapping[str, float]], model: Mapping[str, Any]) -> np.ndarray:
    names = list(model["feature_names"])
    matrix = np.asarray([[float(row[name]) for name in names] for row in rows], dtype=float)
    means = np.asarray(model["feature_means"], dtype=float)
    stds = np.asarray(model["feature_stds"], dtype=float)
    coeffs = np.asarray(model["coefficients"], dtype=float)
    return float(model["intercept"]) + ((matrix - means) / stds) @ coeffs


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def evaluate_predictions(
    per_sample_scores: Sequence[np.ndarray],
    per_sample_labels: Sequence[Sequence[float]],
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    spearman, kendall, ndcg25, mass25, top1 = [], [], [], [], []
    for scores, labels in zip(per_sample_scores, per_sample_labels):
        labels_list = list(labels)
        spearman.append(variants.safe_spearman(scores, np.asarray(labels_list)))
        kendall.append(variants.safe_kendall(scores, np.asarray(labels_list)))
        scores_list = np.asarray(scores, dtype=float).tolist()
        ndcg25.append(ndcg_at_budget(scores_list, labels_list, keep_fraction=0.25))
        mass25.append(label_mass_at_budget(scores_list, labels_list, keep_fraction=0.25))
        top1.append(
            max_label_hit_at_budget(scores_list, labels_list, keep_fraction=1.0 / len(labels_list))
        )
    return {
        "mean_spearman": float(np.mean(spearman)),
        "mean_kendall": float(np.mean(kendall)),
        "mean_ndcg_at_25": float(np.mean(ndcg25)),
        "mean_mass_at_25": float(np.mean(mass25)),
        "mean_top1_hit": float(np.mean(top1)),
        "spearman_ci": variants.bootstrap_ci(
            np.asarray(spearman), n_bootstrap=bootstrap_samples, seed=bootstrap_seed
        ),
        "n_samples": len(spearman),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=variants.DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    parser.add_argument("--limit-samples", type=int, default=0,
                        help="Optional cap on locked samples for a fast smoke run (0 = all).")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()

    config = variants.load_config(args.config)
    ridge_lambda = float(config["model"]["ridge_lambda"])

    print("Loading PRM800K locked split (streaming)...")
    pool_rows = variants.load_pool_rows(config)
    pool_samples = variants.build_samples(
        pool_rows, split_name="pool", row_start=int(config["data"]["pool"]["start_row"])
    )
    dev_samples, locked_samples = variants.split_samples(
        pool_samples, config["data"]["split_strategy"]
    )
    if args.limit_samples > 0:
        locked_samples = locked_samples[: args.limit_samples]
    print(f"Pool: {len(pool_samples)}, Dev: {len(dev_samples)}, Locked: {len(locked_samples)}")

    # --- Structural features (dev + locked) ---
    print("Extracting graph-derived structural features...")
    dev_struct = [structural_feature_rows(s) for s in dev_samples]
    locked_struct = [structural_feature_rows(s) for s in locked_samples]
    dev_labels = [list(s.labels) for s in dev_samples]
    locked_labels = [list(s.labels) for s in locked_samples]

    # --- Reference: full lexical w_struct Ridge (identical to the paper) ---
    print("Fitting reference w_struct (lexical) and structure-only Ridge models...")
    w_struct_model = variants.fit_w_struct_model(dev_samples, ridge_lambda=ridge_lambda)

    # --- Structure-only Ridge models (two feature sets) ---
    struct_graph_model = fit_ridge(
        dev_struct, dev_labels, STRUCTURE_GRAPH_FEATURES, ridge_lambda=ridge_lambda
    )
    struct_pos_model = fit_ridge(
        dev_struct, dev_labels, STRUCTURE_GRAPH_FEATURES + POSITION_FEATURES,
        ridge_lambda=ridge_lambda,
    )

    # --- Predictions on locked ---
    methods_scores: dict[str, list[np.ndarray]] = {
        "structure_graph": [],
        "structure_graph_position": [],
        "w_struct": [],
        "raw_local_utility": [],
    }
    for sample, srows in zip(locked_samples, locked_struct):
        methods_scores["structure_graph"].append(predict_ridge(srows, struct_graph_model))
        methods_scores["structure_graph_position"].append(predict_ridge(srows, struct_pos_model))
        methods_scores["w_struct"].append(variants.predict_w_struct(sample, w_struct_model))
        methods_scores["raw_local_utility"].append(np.asarray(sample.raw_local_utility, dtype=float))

    results = {
        method: evaluate_predictions(
            scores, locked_labels,
            bootstrap_samples=args.bootstrap_samples, bootstrap_seed=args.bootstrap_seed,
        )
        for method, scores in methods_scores.items()
    }

    report = {
        "route_id": "structure_only_baseline_prm800k_hash",
        "purpose": (
            "Same-supervision structure-only Ridge control: does graph-derived "
            "structural information carry step-ranking signal under identical "
            "supervision as w_struct?"
        ),
        "claim_boundary": "real_prm800k_step_ranking_control_only",
        "supervision": {
            "target": "PRM800K completion rating mapped to [0,1] via (rating+1)/2",
            "split": "identical sha256 hash split to w_struct (v3.6)",
            "ridge_lambda": ridge_lambda,
            "fit": "closed-form ridge, standardized features, unpenalized intercept",
        },
        "feature_sets": {
            "structure_graph": STRUCTURE_GRAPH_FEATURES,
            "structure_graph_position": STRUCTURE_GRAPH_FEATURES + POSITION_FEATURES,
            "w_struct": variants.feature_names(),
            "note": (
                "Structural features are computed from a per-trace TF-IDF "
                "step-similarity graph, independent of the lexical w_struct model "
                "(no w_struct predictions enter the structural features)."
            ),
        },
        "n_dev_samples": len(dev_samples),
        "n_locked_samples": len(locked_samples),
        "n_locked_steps": variants.count_steps(locked_samples),
        "results": results,
        "structure_only_ridge_coefficients": {
            "structure_graph": dict(zip(
                struct_graph_model["feature_names"], struct_graph_model["coefficients"]
            )),
            "structure_graph_position": dict(zip(
                struct_pos_model["feature_names"], struct_pos_model["coefficients"]
            )),
        },
        "source": {
            "config": str(args.config),
            "git_revision": _git_revision(),
            "bootstrap_seed": args.bootstrap_seed,
        },
        "elapsed_seconds": round(time.time() - started, 2),
    }

    report_path = args.output_dir / "structure_only_baseline_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (args.output_dir / "structure_only_baseline_summary.md").write_text(
        _render_summary(report), encoding="utf-8"
    )
    print(f"Report written to {report_path}")
    _print_summary(report)


def _render_summary(report: Mapping[str, Any]) -> str:
    lines = [
        "# Same-Supervision Structure-Only Ridge Baseline (PRM800K locked split)",
        "",
        report["purpose"],
        "",
        f"- Dev samples: {report['n_dev_samples']}",
        f"- Locked samples: {report['n_locked_samples']}  |  Locked steps: {report['n_locked_steps']}",
        f"- Supervision target: {report['supervision']['target']}",
        f"- Split: {report['supervision']['split']}  |  ridge_lambda={report['supervision']['ridge_lambda']}",
        "",
        "| Method | Features | Spearman rho | 95% CI | Kendall | NDCG@25% | Mass@25% | Top-1 hit |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    feat_counts = {
        "structure_graph": len(report["feature_sets"]["structure_graph"]),
        "structure_graph_position": len(report["feature_sets"]["structure_graph_position"]),
        "w_struct": len(report["feature_sets"]["w_struct"]),
        "raw_local_utility": 1,
    }
    for method in ["w_struct", "structure_graph_position", "structure_graph", "raw_local_utility"]:
        r = report["results"][method]
        ci = r["spearman_ci"]
        lines.append(
            "| {m} | {f} | {sp:.4f} | [{lo:.4f}, {hi:.4f}] | {kd:.4f} | {nd:.4f} | {ms:.4f} | {t1:.4f} |".format(
                m=method, f=feat_counts[method], sp=r["mean_spearman"],
                lo=ci["ci_lower"], hi=ci["ci_upper"], kd=r["mean_kendall"],
                nd=r["mean_ndcg_at_25"], ms=r["mean_mass_at_25"], t1=r["mean_top1_hit"],
            )
        )
    lines += [
        "",
        "Interpretation guide: if a structure-only Ridge reaches rho ~ 0.3-0.4, "
        "structural information carries signal under fair supervision (the "
        "unsupervised extraction, not the information, was the limitation). If it "
        "is near zero, the structural fields are organizational/interpretive "
        "rather than independently predictive of PRM800K step labels.",
    ]
    return "\n".join(lines)


def _print_summary(report: Mapping[str, Any]) -> None:
    print("\n=== Structure-only baseline: mean Spearman (locked) ===")
    for method in ["w_struct", "structure_graph_position", "structure_graph", "raw_local_utility"]:
        r = report["results"][method]
        ci = r["spearman_ci"]
        print(f"  {method:26s}: {r['mean_spearman']:+.4f}  CI[{ci['ci_lower']:+.4f}, {ci['ci_upper']:+.4f}]")


def _git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
