"""Long-trace recovery analysis for the windowed SC-FMA QP variant on PRM800K.

Companion to ``run_prm800k_audit_prioritization.py``. It reuses the same locked
hash split and the same stratified Spearman machinery, but focuses on the
trace-length stratum where the plain QP degrades, reporting a window-size sweep
for ``scfma_qp_windowed`` next to the ``w_struct`` / Ridge / plain-QP baselines.

It is written as a *separate* artifact so the canonical
``audit_prioritization_report.json`` (which carries the frozen-PRM row that
requires the v3.8 locked-scoring file) is left untouched.

Usage:
    python scripts/run_windowed_calibration_analysis.py \
        [--config CONFIG] [--output-dir DIR] [--pool-cache POOL.jsonl] \
        [--canonical-window 4] [--window-sizes 2,3,4,5,6,8]
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
from fma.calibration import (  # noqa: E402
    BottleneckConstraint,
    scfma_calibrate,
    scfma_calibrate_ridge,
    scfma_calibrate_windowed,
)
from fma.eval.prm800k_audit_prioritization import (  # noqa: E402
    assign_error_uncertainty_stratum,
    assign_label_entropy_stratum,
    assign_trace_length_stratum,
    label_entropy,
    summarize_audit_prioritization_by_stratum,
    tertile_cutpoints,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash"
SCU = dict(alpha=1.0, beta=0.5, gamma=0.2, delta=0.1)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=variants.DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pool-cache", type=Path, default=None,
                        help="Optional local JSONL cache of pool rows (dev speed).")
    parser.add_argument("--canonical-window", type=int, default=4)
    parser.add_argument("--stitch", type=str, default="mass", choices=["mass", "ridge"])
    parser.add_argument("--window-sizes", type=str, default="2,3,4,5,6,8")
    return parser.parse_args(argv)


def load_pool_rows(config: Mapping[str, Any], cache: Path | None) -> list[dict[str, Any]]:
    if cache is not None and cache.exists():
        print(f"[cache] loading pool rows from {cache}", flush=True)
        return [json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines() if line.strip()]
    print("[stream] downloading pool rows from source URL...", flush=True)
    rows = variants.load_pool_rows(config)
    if cache is not None:
        cache.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        print(f"[cache] wrote {len(rows)} pool rows to {cache}", flush=True)
    return rows


def compute_scores(sample, model, window_sizes: list[int], stitch: str) -> dict[str, np.ndarray]:
    w_struct_pred = variants.predict_w_struct(sample, model)
    necessity = variants.compute_necessity_vector(sample, model)
    redundancy = variants.compute_redundancy_matrix(sample, model)
    bottleneck = variants.detect_bottleneck_indices(necessity, redundancy)
    bcs = [BottleneckConstraint(i, 0.01) for i in sorted(bottleneck)]

    scores: dict[str, np.ndarray] = {"w_struct": w_struct_pred}
    try:
        r = scfma_calibrate(w_struct_pred, necessity, redundancy, bottleneck_constraints=bcs,
                            sample_id=sample.sample_id, **SCU)
        scores["scfma_qp"] = np.asarray(r.weights[0].weights, float) if (r.weights and r.converged) else w_struct_pred
    except Exception:
        scores["scfma_qp"] = w_struct_pred
    try:
        r = scfma_calibrate_ridge(w_struct_pred, necessity, sample_id=sample.sample_id,
                                  alpha_ciui=0.7, alpha_nec=0.3, temperature=1.0)
        scores["scfma_ridge"] = np.asarray(r.weights[0].weights, float) if r.weights else w_struct_pred
    except Exception:
        scores["scfma_ridge"] = w_struct_pred
    for ws in window_sizes:
        key = f"scfma_qp_win{ws}"
        try:
            r = scfma_calibrate_windowed(w_struct_pred, necessity, redundancy, bottleneck_constraints=bcs,
                                         sample_id=sample.sample_id, window_size=ws, stitch=stitch, **SCU)
            scores[key] = np.asarray(r.weights[0].weights, float) if (r.weights and r.converged) else w_struct_pred
        except Exception:
            scores[key] = w_struct_pred
    return scores


def build_rows(locked, model, window_sizes: list[int], stitch: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = len(locked)
    for idx, sample in enumerate(locked):
        labels = np.asarray(sample.labels, dtype=float)
        scores = compute_scores(sample, model, window_sizes, stitch)
        rows.append({
            "sample_id": sample.sample_id,
            "n_steps": len(labels),
            "label_entropy": label_entropy(labels),
            "error_uncertainty_stratum": assign_error_uncertainty_stratum(sample.feature_rows),
            "labels": labels.tolist(),
            "scores_by_method": {m: np.asarray(v, dtype=float).tolist() for m, v in scores.items()},
        })
        if (idx + 1) % 1000 == 0:
            print(f"  scored {idx + 1}/{n} locked samples...", flush=True)
    return rows


def assign_trace_strata(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trace_cut = tertile_cutpoints([float(r["n_steps"]) for r in rows])
    entropy_cut = tertile_cutpoints([float(r["label_entropy"]) for r in rows])
    for r in rows:
        r["strata"] = {
            "trace_length": assign_trace_length_stratum(int(r["n_steps"]), trace_cut),
            "label_entropy": assign_label_entropy_stratum(float(r["label_entropy"]), entropy_cut),
            "error_uncertainty": str(r["error_uncertainty_stratum"]),
        }
    return rows


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    window_sizes = [int(x) for x in str(args.window_sizes).split(",") if x.strip()]
    t0 = time.time()

    config = variants.load_config(args.config)
    rows_raw = load_pool_rows(config, args.pool_cache)
    pool = variants.build_samples(rows_raw, split_name="pool",
                                  row_start=int(config["data"]["pool"]["start_row"]))
    dev, locked = variants.split_samples(pool, config["data"]["split_strategy"])
    print(f"pool={len(pool)} dev={len(dev)} locked={len(locked)}", flush=True)
    model = variants.fit_w_struct_model(dev, ridge_lambda=float(config["model"]["ridge_lambda"]))

    rows = assign_trace_strata(build_rows(locked, model, window_sizes, args.stitch))
    baselines = ["w_struct", "scfma_ridge", "scfma_qp"]
    windowed = [f"scfma_qp_win{ws}" for ws in window_sizes]
    strat = summarize_audit_prioritization_by_stratum(
        rows, methods=baselines + windowed, strata=["trace_length"])
    by = {(s["stratum"], s["method"]): s for s in strat}
    order = ["trace_length_low", "trace_length_mid", "trace_length_high"]

    def rho(method: str, stratum: str) -> float | None:
        s = by.get((stratum, method))
        return round(s["mean_spearman"], 4) if s else None

    canonical_key = f"scfma_qp_win{args.canonical_window}"
    try:
        config_ref = str(Path(args.config).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        config_ref = str(args.config)
    report = {
        "route_id": str(config["route"]["id"]),
        "analysis": "windowed_qp_long_trace_recovery",
        "claim_permission": "audit_prioritization_context_only",
        "source": {
            "config": config_ref,
            "dataset": config["data"]["source"]["dataset"],
            "split_strategy": dict(config["data"]["split_strategy"]),
            "deterministic": True,
        },
        "n_locked_samples": len(locked),
        "canonical_window": args.canonical_window,
        "stitch": args.stitch,
        "scu_hyperparameters": SCU,
        "strata": {
            stratum: {
                "n_samples": (by.get((stratum, "w_struct")) or {}).get("n_samples"),
                "n_steps": (by.get((stratum, "w_struct")) or {}).get("n_steps"),
                "w_struct": rho("w_struct", stratum),
                "scfma_ridge": rho("scfma_ridge", stratum),
                "scfma_qp": rho("scfma_qp", stratum),
                "scfma_qp_windowed_canonical": rho(canonical_key, stratum),
                "windowed_sweep": {str(ws): rho(f"scfma_qp_win{ws}", stratum) for ws in window_sizes},
            }
            for stratum in order
        },
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    out_json = args.output_dir / "windowed_stratified_analysis.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Markdown summary
    lines = ["# Windowed SC-FMA QP — long-trace recovery (PRM800K locked split)", "",
             f"Canonical window = {args.canonical_window}, stitch = {args.stitch}. "
             f"mean Spearman by trace-length stratum (n_locked={len(locked)}).", "",
             "| method | short | mid | long |", "|---|---|---|---|"]
    for m in baselines + [canonical_key]:
        cells = " | ".join("" if rho(m, o) is None else f"{rho(m, o):.3f}" for o in order)
        lines.append(f"| {m} | {cells} |")
    lines += ["", "## Window-size sweep (long stratum)", "", "| window | " +
              " | ".join(str(ws) for ws in window_sizes) + " |",
              "|---|" + "---|" * len(window_sizes)]
    lines.append("| long-trace ρ | " +
                 " | ".join(f"{rho(f'scfma_qp_win{ws}', 'trace_length_high'):.3f}" for ws in window_sizes) + " |")
    out_md = args.output_dir / "windowed_stratified_analysis.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines), flush=True)
    print(f"\nwrote {out_json}\nwrote {out_md}\nelapsed {report['elapsed_seconds']}s", flush=True)


if __name__ == "__main__":
    main()
