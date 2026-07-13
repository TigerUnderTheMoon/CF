"""Graph-based structural-necessity measurement on the PRM800K locked split.

Motivation: the manuscript attributes a strongly negative necessity-vs-label
correlation (Spearman rho = -0.418) to "temporal-edge and TF-IDF graph
construction". In the archived pipeline that number is actually produced by a
position/magnitude *heuristic* (`compute_necessity_vector`) that never builds a
reflection graph. This script measures, for the first time on PRM800K, the
label-correlation of genuine graph-based node necessity under two edge backends
-- TF-IDF topical similarity and a mathematical variable-dependency DAG -- next
to the heuristic baseline, so the misattribution can be corrected and the
alternative backend evaluated.

Usage:
    python scripts/run_prm800k_graph_necessity.py \
        [--config CONFIG] [--output-dir DIR] [--pool-cache POOL.jsonl] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _p in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

import run_scfma_variants_prm800k as variants  # noqa: E402
from fma.eval.prm800k_audit_prioritization import (  # noqa: E402
    assign_trace_length_stratum,
    spearman,
    tertile_cutpoints,
)
from fma.eval.structural_attribution import compute_node_necessity  # noqa: E402
from fma.graph.build_reflection_graph import build_reflection_graphs  # noqa: E402
from fma.graph.math_dependency_graph import build_math_dependency_graph  # noqa: E402

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash"
STRATA = ["trace_length_low", "trace_length_mid", "trace_length_high"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=variants.DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pool-cache", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0, help="Score only the first N locked samples (0 = all).")
    parser.add_argument("--bootstrap", type=int, default=10000,
                        help="Bootstrap resamples for necessity CIs (0 = skip).")
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    return parser.parse_args(argv)


def load_pool_rows(config: Mapping[str, Any], cache: Path | None) -> list[dict[str, Any]]:
    if cache is not None and cache.exists():
        return [json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = variants.load_pool_rows(config)
    if cache is not None:
        cache.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return rows


def _necessity_vector(graph, n_steps: int) -> list[float]:
    vec = [0.0] * n_steps
    for row in compute_node_necessity(graph):
        if 0 <= row.step_idx < n_steps:
            vec[row.step_idx] = float(row.necessity)
    return vec


def tfidf_graph_necessity(steps: Sequence[str], trace_id: str) -> list[float]:
    trace = {"trace_id": trace_id, "reflection_chain": [{"text": t, "category": "STEP"} for t in steps]}
    graphs = build_reflection_graphs([trace], similarity_method="tfidf", similarity_threshold=0.15)
    if not graphs:
        return [0.0] * len(steps)
    return _necessity_vector(graphs[0], len(steps))


def _bootstrap_necessity_cis(
    dag_rhos: Sequence[float],
    pos_rhos: Sequence[float],
    n_resamples: int,
    seed: int,
) -> dict[str, Any]:
    """Paired bootstrap 95% CIs for math-DAG necessity, the reverse-position
    baseline, and their per-sample difference (shared resample indices)."""
    dag = np.asarray(dag_rhos, dtype=float)
    pos = np.asarray(pos_rhos, dtype=float)
    n = len(dag)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    dag_bs = dag[idx].mean(axis=1)
    pos_bs = pos[idx].mean(axis=1)
    diff_bs = (dag[idx] - pos[idx]).mean(axis=1)

    def ci(a: np.ndarray) -> list[float]:
        return [round(float(np.percentile(a, 2.5)), 4), round(float(np.percentile(a, 97.5)), 4)]

    return {
        "dag_necessity": {"point": round(float(dag.mean()), 4), "bootstrap_ci_95": ci(dag_bs)},
        "reverse_position_baseline": {"point": round(float(pos.mean()), 4), "bootstrap_ci_95": ci(pos_bs)},
        "paired_difference": {"point": round(float((dag - pos).mean()), 4), "bootstrap_ci_95": ci(diff_bs)},
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    config = variants.load_config(args.config)
    rows_raw = load_pool_rows(config, args.pool_cache)
    pool = variants.build_samples(rows_raw, split_name="pool",
                                  row_start=int(config["data"]["pool"]["start_row"]))
    dev, locked = variants.split_samples(pool, config["data"]["split_strategy"])
    model = variants.fit_w_struct_model(dev, ridge_lambda=float(config["model"]["ridge_lambda"]))
    if args.limit:
        locked = locked[: args.limit]
    print(f"scoring {len(locked)} locked samples", flush=True)

    cut = tertile_cutpoints([float(len(s.labels)) for s in locked])
    methods = [
        "heuristic_necessity",
        "tfidf_graph_necessity",
        "temporal_only_necessity",
        "position_desc",
        "math_dag_necessity",
    ]
    per = {m: {s: [] for s in STRATA} for m in methods}
    overall = {m: [] for m in methods}

    for idx, sample in enumerate(locked):
        steps = list(sample.step_texts)
        labels = list(sample.labels)
        n = len(steps)
        stratum = assign_trace_length_stratum(len(labels), cut)
        vectors = {
            "heuristic_necessity": variants.compute_necessity_vector(sample, model).tolist(),
            "tfidf_graph_necessity": tfidf_graph_necessity(steps, sample.sample_id),
            "temporal_only_necessity": _necessity_vector(
                build_math_dependency_graph(steps, sample.sample_id, include_dependency_edges=False), n),
            "position_desc": [float(n - 1 - i) for i in range(n)],
            "math_dag_necessity": _necessity_vector(
                build_math_dependency_graph(steps, sample.sample_id), n),
        }
        for m, vec in vectors.items():
            rho = spearman(vec, labels)
            per[m][stratum].append(rho)
            overall[m].append(rho)
        if (idx + 1) % 500 == 0:
            print(f"  {idx + 1}/{len(locked)}  elapsed {time.time()-t0:.0f}s", flush=True)

    def _mean(xs: list[float]) -> float | None:
        return round(float(np.mean(xs)), 4) if xs else None

    try:
        config_ref = str(Path(args.config).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        config_ref = str(args.config)

    source = {
        "config": config_ref,
        "dataset": config["data"]["source"]["dataset"],
        "split_strategy": dict(config["data"]["split_strategy"]),
        "deterministic": True,
    }
    bootstrap_block = None
    if args.bootstrap and args.bootstrap > 0:
        bootstrap_block = _bootstrap_necessity_cis(
            overall["math_dag_necessity"],
            overall["position_desc"],
            int(args.bootstrap),
            int(args.bootstrap_seed),
        )
        source["bootstrap"] = {"n_resamples": int(args.bootstrap), "seed": int(args.bootstrap_seed)}

    report = {
        "route_id": str(config["route"]["id"]),
        "analysis": "graph_structural_necessity_vs_labels",
        "claim_permission": "audit_prioritization_context_only",
        "source": source,
        "n_locked_samples": len(locked),
        "overall": {m: _mean(overall[m]) for m in methods},
        "by_trace_length": {m: {s: _mean(per[m][s]) for s in STRATA} for m in methods},
    }
    if bootstrap_block is not None:
        report["dag_necessity"] = bootstrap_block["dag_necessity"]
        report["reverse_position_baseline"] = bootstrap_block["reverse_position_baseline"]
        report["paired_difference"] = bootstrap_block["paired_difference"]
    report["elapsed_seconds"] = round(time.time() - t0, 1)

    out = args.output_dir / "graph_necessity_analysis.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== mean Spearman(necessity, labels) ===", flush=True)
    print(f"{'method':24s}{'overall':>9s}" + "".join(f"{s.split('_')[-1]:>8s}" for s in STRATA))
    for m in methods:
        row = f"{m:24s}{report['overall'][m]:>9.3f}"
        row += "".join(f"{report['by_trace_length'][m][s]:>8.3f}" for s in STRATA)
        print(row, flush=True)
    if bootstrap_block is not None:
        b = bootstrap_block
        print(f"\nbootstrap (n={args.bootstrap}, seed={args.bootstrap_seed}):", flush=True)
        print(f"  dag_necessity             point={b['dag_necessity']['point']}  95% CI={b['dag_necessity']['bootstrap_ci_95']}", flush=True)
        print(f"  reverse_position_baseline point={b['reverse_position_baseline']['point']}  95% CI={b['reverse_position_baseline']['bootstrap_ci_95']}", flush=True)
        print(f"  paired_difference         point={b['paired_difference']['point']}  95% CI={b['paired_difference']['bootstrap_ci_95']}", flush=True)
    print(f"\nwrote {out}  (elapsed {report['elapsed_seconds']}s)", flush=True)


if __name__ == "__main__":
    main()
