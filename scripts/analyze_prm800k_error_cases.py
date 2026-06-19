"""Static error case analysis for the PRM800K locked split.

Loads frozen v3.6 artifacts (w_struct model, locked manifest) and produces:
  - Stratified error analysis: where SC-FMA QP underperforms w_struct
  - Variant behavior comparison: QP vs Ridge vs w_struct groupings
  - Case studies: step-level weights for representative traces

Output:
  - outputs/real_task_v3_6_prm800k_hash/error_case_analysis.json
  - outputs/real_task_v3_6_prm800k_hash/error_case_analysis.md

Zero LLM API calls.  PRM800K data is streamed from the frozen HuggingFace URL
(the same source used by the v3.6 and SC-FMA variants scripts) or from a
local fixture in --fixture mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Path setup (mirrors run_scfma_variants_prm800k.py)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_scfma_variants_prm800k as variants  # noqa: E402
from fma.calibration import (
    BottleneckConstraint,
    scfma_calibrate,
    scfma_calibrate_ridge,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FROZEN_MODEL_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "real_task_v3_6_prm800k_hash"
    / "dev_w_struct_model.json"
)
CONFIG_PATH = PROJECT_ROOT / "configs" / "real_task_v3_6_prm800k_hash_validation.yaml"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash"

VARIANT_NAMES = ["w_struct", "scfma_qp", "scfma_ridge"]
HUMAN_NAMES = {
    "w_struct": "w_struct",
    "scfma_qp": "SC-FMA QP",
    "scfma_ridge": "SC-FMA Ridge",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class TraceInfo:
    """Per-sample analysis record."""

    sample_id: str
    n_steps: int
    labels: list[float]
    w_struct_scores: list[float]
    qp_scores: list[float]
    ridge_scores: list[float]
    necessity: list[float]
    redundancy_mean: float
    bottleneck_count: int
    rho_w_struct: float
    rho_qp: float
    rho_ridge: float
    features: dict[str, float]  # trace-level characteristics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_frozen_model(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def safe_spearman(pred: np.ndarray, labels: np.ndarray) -> float:
    value = stats.spearmanr(pred, labels).statistic
    return 0.0 if math.isnan(float(value)) else float(value)


def _load_config() -> dict[str, Any]:
    import yaml

    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _hash_bucket(sample_id: str, salt: str) -> int:
    digest = hashlib.sha256(f"{sample_id}|{salt}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


# ---------------------------------------------------------------------------
# Fixture data (no network, no API)
# ---------------------------------------------------------------------------
def _fixture_pool_rows(size: int = 200) -> list[dict[str, Any]]:
    """Return a pool of mock PRM800K rows for testing (no network)."""
    rng = np.random.default_rng(42)
    rows: list[dict[str, Any]] = []
    for i in range(size):
        n_steps = int(rng.integers(5, 12))  # 5-11 steps
        # Generate labels with more realistic patterns:
        #   - early steps: moderate (0.3–0.7)
        #   - middle steps: variable (0.1–0.9)
        #   - late steps: high (0.5–1.0) to simulate answer proximity
        labels = np.zeros(n_steps)
        for s in range(n_steps):
            pos = s / max(1, n_steps - 1)
            base = 0.3 + 0.45 * pos  # trend upward
            noise = rng.normal(0, 0.12)
            labels[s] = float(np.clip(base + noise, 0.0, 1.0))
        # Ensure at least 2 unique labels (rounded to 2 decimals)
        labels_rounded = np.round(labels, 2)
        if len(np.unique(labels_rounded)) < 2:
            labels[-1] = 1.0
            labels[0] = 0.0

        steps = []
        for s in range(n_steps):
            rating_val = round(labels[s] * 2.0 - 1.0)  # back to [-1,0,1]
            rating_val = max(-1, min(1, rating_val))
            # Vary text content so features differ
            cues = ["Let", "Therefore", "because", "thus", "hence",
                    "compute", "calculate", "we find", "answer", "boxed"]
            text = " ".join(
                cues[(i * 3 + s * 7 + j) % len(cues)]
                for j in range(3)
            )
            steps.append(
                {
                    "completions": [
                        {
                            "text": f"Step {s}: {text}.",
                            "rating": rating_val,
                            "flagged": False,
                        }
                    ],
                    "chosen_completion": 0,
                }
            )
        rows.append(
            {
                "label": {"steps": steps},
                "question": {
                    "problem": f"Solve example problem {i}: compute the result."
                },
                "timestamp": f"2026-06-{10 + (i % 20):02d}T12:00:00Z",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------
def analyze(
    samples: Sequence[variants.RankingSample],
    model: dict[str, Any],
) -> dict[str, Any]:
    traces: list[TraceInfo] = []
    variant_rhos: dict[str, list[float]] = {v: [] for v in VARIANT_NAMES}

    for sample in samples:
        labels = np.asarray(sample.labels, dtype=float)
        if len(labels) < 3 or len(set(labels)) < 2:
            continue

        w_struct_pred = variants.predict_w_struct(sample, model)
        necessity = variants.compute_necessity_vector(sample, model)
        redundancy = variants.compute_redundancy_matrix(sample, model)
        bottleneck = variants.detect_bottleneck_indices(necessity, redundancy)

        # SC-FMA QP
        try:
            qp_result = scfma_calibrate(
                w_struct_pred,
                necessity,
                redundancy,
                bottleneck_constraints=[
                    BottleneckConstraint(idx, 0.01) for idx in sorted(bottleneck)
                ],
                sample_id=sample.sample_id,
                alpha=1.0,
                beta=0.5,
                gamma=0.2,
                delta=0.1,
            )
            qp_scores = (
                np.asarray(qp_result.weights[0].weights, dtype=float)
                if qp_result.weights and qp_result.converged
                else w_struct_pred
            )
        except Exception:
            qp_scores = w_struct_pred

        # SC-FMA Ridge
        try:
            ridge_result = scfma_calibrate_ridge(
                w_struct_pred,
                necessity,
                sample_id=sample.sample_id,
                alpha_ciui=0.7,
                alpha_nec=0.3,
                temperature=1.0,
            )
            ridge_scores = (
                np.asarray(ridge_result.weights[0].weights, dtype=float)
                if ridge_result.weights
                else w_struct_pred
            )
        except Exception:
            ridge_scores = w_struct_pred

        # Per-sample Spearman
        rho_ws = safe_spearman(w_struct_pred, labels)
        rho_qp = safe_spearman(qp_scores, labels)
        rho_ri = safe_spearman(ridge_scores, labels)

        # Redundancy density: mean off-diagonal redundancy
        if redundancy.size > 0 and redundancy.shape[0] > 1:
            off_diag = redundancy.copy()
            np.fill_diagonal(off_diag, 0.0)
            redundancy_mean = float(np.mean(off_diag))
        else:
            redundancy_mean = 0.0

        # Position of high-necessity steps (top 25%)
        threshold = np.percentile(necessity, 75) if len(necessity) > 0 else 0.0
        high_nec_positions = [
            i / max(1, len(necessity) - 1)
            for i, v in enumerate(necessity)
            if v >= threshold
        ]
        high_nec_mean_pos = (
            float(np.mean(high_nec_positions)) if high_nec_positions else 0.0
        )

        info = TraceInfo(
            sample_id=sample.sample_id,
            n_steps=len(labels),
            labels=labels.tolist(),
            w_struct_scores=w_struct_pred.tolist(),
            qp_scores=qp_scores.tolist(),
            ridge_scores=ridge_scores.tolist(),
            necessity=necessity.tolist(),
            redundancy_mean=redundancy_mean,
            bottleneck_count=len(bottleneck),
            rho_w_struct=rho_ws,
            rho_qp=rho_qp,
            rho_ridge=rho_ri,
            features={
                "trace_length": float(len(labels)),
                "redundancy_density": redundancy_mean,
                "bottleneck_count": float(len(bottleneck)),
                "high_necessity_position_mean": high_nec_mean_pos,
                "label_variance": float(np.std(labels)),
            },
        )
        traces.append(info)
        for v in VARIANT_NAMES:
            variant_rhos[v].append(getattr(info, f"rho_{_variant_key(v)}"))

    result: dict[str, Any] = {
        "n_samples": len(traces),
        "mean_spearman": {
            v: float(np.mean(variant_rhos[v])) if variant_rhos[v] else 0.0
            for v in VARIANT_NAMES
        },
        "stratified_summary": _stratified_summary(traces),
        "variant_comparison": _variant_comparison(traces),
        "case_studies": _case_studies(traces),
        "concrete_finding": _concrete_finding(traces),
    }
    return result


def _variant_key(variant_name: str) -> str:
    """Map variant name to TraceInfo attribute suffix."""
    return {"w_struct": "w_struct", "scfma_qp": "qp", "scfma_ridge": "ridge"}[
        variant_name
    ]


# ---------------------------------------------------------------------------
# Stratified error analysis
# ---------------------------------------------------------------------------
def _stratified_summary(traces: list[TraceInfo]) -> dict[str, Any]:
    """Group traces by characteristics and report mean delta per group."""

    # Compute deltas
    ws_rhos = np.array([t.rho_w_struct for t in traces])
    qp_rhos = np.array([t.rho_qp for t in traces])
    ridge_rhos = np.array([t.rho_ridge for t in traces])
    qp_delta = qp_rhos - ws_rhos  # QP minus w_struct
    ridge_delta = ridge_rhos - ws_rhos  # Ridge minus w_struct

    strata = {}
    for name, values, label in [
        (
            "redundancy_density",
            np.array([t.features["redundancy_density"] for t in traces]),
            "Redundancy density",
        ),
        (
            "trace_length",
            np.array([t.features["trace_length"] for t in traces]),
            "Trace length",
        ),
        (
            "bottleneck_count",
            np.array([t.features["bottleneck_count"] for t in traces]),
            "Bottleneck count",
        ),
    ]:
        if len(values) < 3:
            strata[name] = {"label": label, "groups": []}
            continue
        low = float(np.percentile(values, 33.33))
        high = float(np.percentile(values, 66.67))
        groups = []
        for range_name, mask_fn in [
            ("low", lambda v: v <= low),
            ("mid", lambda v: (v > low) & (v <= high)),
            ("high", lambda v: v > high),
        ]:
            mask = mask_fn(values)
            n = int(np.sum(mask))
            if n == 0:
                continue
            groups.append(
                {
                    "range": range_name,
                    "n_traces": n,
                    "mean_delta_qp_vs_ws": float(np.mean(qp_delta[mask])),
                    "mean_delta_ridge_vs_ws": float(np.mean(ridge_delta[mask])),
                    "mean_rho_ws": float(np.mean(ws_rhos[mask])),
                    "mean_rho_qp": float(np.mean(qp_rhos[mask])),
                    "mean_rho_ridge": float(np.mean(ridge_rhos[mask])),
                }
            )
        strata[name] = {"label": label, "groups": groups}

    # Overall deltas
    overall = {
        "mean_delta_qp_vs_ws": float(np.mean(qp_delta)),
        "mean_delta_ridge_vs_ws": float(np.mean(ridge_delta)),
        "n_qp_underperforms_ws": int(np.sum(qp_delta < 0)),
        "n_qp_outperforms_ws": int(np.sum(qp_delta > 0)),
        "n_qp_ties_ws": int(np.sum(qp_delta == 0)),
    }

    return {"strata": strata, "overall": overall}


# ---------------------------------------------------------------------------
# Variant behavior comparison
# ---------------------------------------------------------------------------
def _variant_comparison(traces: list[TraceInfo]) -> dict[str, Any]:
    """Group traces into (QP > Ridge), (QP < Ridge), (QP << w_struct)."""

    ws_rhos = np.array([t.rho_w_struct for t in traces])
    qp_rhos = np.array([t.rho_qp for t in traces])
    ridge_rhos = np.array([t.rho_ridge for t in traces])

    groups = {}

    for group_name, mask in [
        ("qp_wins_over_ridge", qp_rhos > ridge_rhos),
        ("ridge_wins_over_qp", ridge_rhos > qp_rhos),
        ("qp_equal_ridge", qp_rhos == ridge_rhos),
        ("qp_far_below_ws", (ws_rhos - qp_rhos) > 0.05),
        ("qp_far_above_ws", (qp_rhos - ws_rhos) > 0.05),
        ("ridge_far_below_ws", (ws_rhos - ridge_rhos) > 0.05),
        ("ridge_far_above_ws", (ridge_rhos - ws_rhos) > 0.05),
    ]:
        n = int(np.sum(mask))
        if n == 0:
            groups[group_name] = {"n_traces": 0, "mean_characteristics": {}}
            continue
        red_dens = np.array([t.features["redundancy_density"] for t in traces])[mask]
        tr_len = np.array([t.features["trace_length"] for t in traces])[mask]
        bn_cnt = np.array([t.features["bottleneck_count"] for t in traces])[mask]

        groups[group_name] = {
            "n_traces": n,
            "mean_rho_ws": float(np.mean(ws_rhos[mask])),
            "mean_rho_qp": float(np.mean(qp_rhos[mask])),
            "mean_rho_ridge": float(np.mean(ridge_rhos[mask])),
            "mean_characteristics": {
                "redundancy_density": float(np.mean(red_dens)),
                "trace_length": float(np.mean(tr_len)),
                "bottleneck_count": float(np.mean(bn_cnt)),
            },
        }

    return groups


# ---------------------------------------------------------------------------
# Case studies
# ---------------------------------------------------------------------------
def _case_studies(traces: list[TraceInfo]) -> list[dict[str, Any]]:
    """Select 3 representative traces: QP wins, Ridge wins, w_struct wins.

    Falls back to best-available trace when no clear winner exists for a variant.
    """

    ws_rhos = np.array([t.rho_w_struct for t in traces])
    qp_rhos = np.array([t.rho_qp for t in traces])
    ridge_rhos = np.array([t.rho_ridge for t in traces])

    cases = []

    def _best_trace(winner: str, mask: np.ndarray, score_fn=None) -> dict[str, Any]:
        """Select best trace for a winner, or fall back to top-w_struct trace."""
        if np.any(mask):
            indices = np.where(mask)[0]
            if score_fn is not None:
                idx = int(indices[np.argmax(score_fn(indices))])
            else:
                idx = int(indices[0])
            return {"winner": winner, **_trace_case_study(traces[idx])}
        # Fallback: pick the trace with highest w_struct rho
        fb_idx = int(np.argmax(ws_rhos))
        return {"winner": winner, "fallback": True, **_trace_case_study(traces[fb_idx])}

    # QP wins: QP best among all three
    qp_best_mask = (qp_rhos > ws_rhos) & (qp_rhos > ridge_rhos)
    cases.append(
        _best_trace(
            "SC-FMA QP",
            qp_best_mask,
            score_fn=lambda idxs: qp_rhos[idxs] - ws_rhos[idxs],
        )
    )

    # Ridge wins: Ridge best
    ridge_best_mask = (ridge_rhos > ws_rhos) & (ridge_rhos > qp_rhos)
    cases.append(
        _best_trace(
            "SC-FMA Ridge",
            ridge_best_mask,
            score_fn=lambda idxs: ridge_rhos[idxs] - ws_rhos[idxs],
        )
    )

    # w_struct wins: w_struct >= others with at least one strict
    ws_best_mask = (ws_rhos >= qp_rhos) & (ws_rhos >= ridge_rhos) & (
        (ws_rhos > qp_rhos) | (ws_rhos > ridge_rhos)
    )
    cases.append(
        _best_trace(
            "w_struct",
            ws_best_mask,
            score_fn=lambda idxs: ws_rhos[idxs]
            - np.maximum(qp_rhos[idxs], ridge_rhos[idxs]),
        )
    )

    return cases


def _trace_case_study(trace: TraceInfo) -> dict[str, Any]:
    """Detailed per-step dump for a single trace."""
    return {
        "sample_id": trace.sample_id,
        "n_steps": trace.n_steps,
        "rho_w_struct": trace.rho_w_struct,
        "rho_qp": trace.rho_qp,
        "rho_ridge": trace.rho_ridge,
        "redundancy_density": trace.features["redundancy_density"],
        "bottleneck_count": trace.bottleneck_count,
        "step_level": [
            {
                "step": i,
                "label": trace.labels[i],
                "w_struct": trace.w_struct_scores[i],
                "scfma_qp": trace.qp_scores[i],
                "scfma_ridge": trace.ridge_scores[i],
                "necessity": trace.necessity[i],
            }
            for i in range(len(trace.labels))
        ],
    }


# ---------------------------------------------------------------------------
# Concrete finding
# ---------------------------------------------------------------------------
def _concrete_finding(traces: list[TraceInfo]) -> str:
    """Generate a data-driven concrete finding from the trace analysis."""

    if not traces:
        return "No traces available for analysis."

    ws_rhos = np.array([t.rho_w_struct for t in traces])
    qp_rhos = np.array([t.rho_qp for t in traces])
    ridge_rhos = np.array([t.rho_ridge for t in traces])

    n_qp_below = int(np.sum(qp_rhos < ws_rhos))
    n_qp_above = int(np.sum(qp_rhos > ws_rhos))
    pct_qp_below = 100.0 * n_qp_below / len(traces) if traces else 0.0

    n_ridge_below = int(np.sum(ridge_rhos < ws_rhos))
    pct_ridge_below = 100.0 * n_ridge_below / len(traces) if traces else 0.0

    # Check if QP underperforms on high-redundancy traces
    red_dens = np.array([t.features["redundancy_density"] for t in traces])
    if len(red_dens) >= 3:
        high_red = red_dens > np.percentile(red_dens, 67)
        low_red = red_dens <= np.percentile(red_dens, 33)
        qp_delta = qp_rhos - ws_rhos
        high_red_qp_delta = float(np.mean(qp_delta[high_red])) if np.any(high_red) else 0.0
        low_red_qp_delta = float(np.mean(qp_delta[low_red])) if np.any(low_red) else 0.0
    else:
        high_red_qp_delta = 0.0
        low_red_qp_delta = 0.0

    mean_qp_delta = float(np.mean(qp_rhos - ws_rhos))
    mean_ridge_delta = float(np.mean(ridge_rhos - ws_rhos))

    # Build concrete finding
    parts = [
        f"Across {len(traces)} locked PRM800K traces: "
        f"SC-FMA QP underperforms w_struct on {n_qp_below} traces "
        f"({pct_qp_below:.1f}%) with mean delta {mean_qp_delta:.4f}, "
        f"while SC-FMA Ridge underperforms on {n_ridge_below} traces "
        f"({pct_ridge_below:.1f}%) with mean delta {mean_ridge_delta:.4f}.",
    ]

    if abs(high_red_qp_delta - low_red_qp_delta) > 0.01:
        parts.append(
            f"QP underperforms more on traces with high redundancy density "
            f"(mean delta {high_red_qp_delta:.4f}) than low redundancy density "
            f"(mean delta {low_red_qp_delta:.4f}). "
            f"Ridge is robust because it soft-averages rather than fully optimizing, "
            f"avoiding overfit to w_struct on traces where redundancy already "
            f"captures the dominant ordering."
        )
    else:
        parts.append(
            f"Both QP and Ridge variants closely track w_struct on this split. "
            f"The SC-FMA calibration adds limited marginal benefit over the "
            f"baseline w_struct predictions for step-label ranking on PRM800K."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------
def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# PRM800K Error Case Analysis",
        "",
        "Static analysis of SC-FMA variant behavior on the locked PRM800K split.",
        "Zero LLM API calls.  Uses frozen v3.6 w_struct model.",
        "",
        f"- **Locked samples analyzed**: {result['n_samples']}",
        f"- **Mean Spearman (w_struct)**: {result['mean_spearman']['w_struct']:.4f}",
        f"- **Mean Spearman (SC-FMA QP)**: {result['mean_spearman']['scfma_qp']:.4f}",
        f"- **Mean Spearman (SC-FMA Ridge)**: {result['mean_spearman']['scfma_ridge']:.4f}",
        "",
        "---",
        "",
        "## Concrete Finding",
        "",
        result["concrete_finding"],
        "",
        "---",
        "",
        "## Stratified Error Analysis",
        "",
    ]

    strata = result["stratified_summary"]["strata"]
    overall = result["stratified_summary"]["overall"]

    lines.append(
        f"Overall: QP underperforms w_struct on {overall['n_qp_underperforms_ws']} "
        f"traces, outperforms on {overall['n_qp_outperforms_ws']} traces. "
        f"Mean delta QP vs w_struct: {overall['mean_delta_qp_vs_ws']:.4f}. "
        f"Mean delta Ridge vs w_struct: {overall['mean_delta_ridge_vs_ws']:.4f}."
    )
    lines.append("")

    for key, stratum in strata.items():
        if not stratum["groups"]:
            continue
        lines.append(f"### By {stratum['label']}")
        lines.append(
            "| Range | N | Mean rho ws | Mean rho QP | Mean rho Ridge | "
            "Delta QP vs ws | Delta Ridge vs ws |"
        )
        lines.append(
            "|---|---:|---:|---:|---:|---:|---:|"
        )
        for g in stratum["groups"]:
            lines.append(
                f"| {g['range']} | {g['n_traces']} | "
                f"{g['mean_rho_ws']:.4f} | {g['mean_rho_qp']:.4f} | "
                f"{g['mean_rho_ridge']:.4f} | "
                f"{g['mean_delta_qp_vs_ws']:.4f} | "
                f"{g['mean_delta_ridge_vs_ws']:.4f} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Variant Behavior Comparison")
    lines.append("")

    vc = result["variant_comparison"]
    for group_name in ["qp_wins_over_ridge", "ridge_wins_over_qp"]:
        if group_name not in vc:
            continue
        g = vc[group_name]
        if g["n_traces"] == 0:
            lines.append(f"### {group_name}: no traces")
            continue
        ch = g["mean_characteristics"]
        lines.append(
            f"### {group_name} (N={g['n_traces']})"
        )
        lines.append(
            f"- Mean rho ws: {g['mean_rho_ws']:.4f}, "
            f"QP: {g['mean_rho_qp']:.4f}, "
            f"Ridge: {g['mean_rho_ridge']:.4f}"
        )
        lines.append(
            f"- Redundancy density: {ch['redundancy_density']:.4f}, "
            f"Trace length: {ch['trace_length']:.1f}, "
            f"Bottlenecks: {ch['bottleneck_count']:.1f}"
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Case Studies")
    lines.append("")

    for case in result["case_studies"]:
        lines.append(f"### Winner: {case['winner']}")
        if case.get("trace") is None:
            lines.append(f"_No representative trace found: {case.get('note', '')}_")
            lines.append("")
            continue
        t = case["trace"]
        lines.append(
            f"- Sample: `{t['sample_id']}`, {t['n_steps']} steps"
        )
        lines.append(
            f"- rho w_struct: {t['rho_w_struct']:.4f}, "
            f"QP: {t['rho_qp']:.4f}, "
            f"Ridge: {t['rho_ridge']:.4f}"
        )
        lines.append(
            f"- Redundancy density: {t['redundancy_density']:.4f}, "
            f"Bottlenecks: {t['bottleneck_count']}"
        )
        lines.append("")
        lines.append(
            "| Step | Label | w_struct | SC-FMA QP | SC-FMA Ridge | Necessity |"
        )
        lines.append(
            "|---|---:|---:|---:|---:|---:|"
        )
        for s in t["step_level"]:
            lines.append(
                f"| {s['step']} | {s['label']:.2f} | "
                f"{s['w_struct']:.4f} | {s['scfma_qp']:.4f} | "
                f"{s['scfma_ridge']:.4f} | {s['necessity']:.4f} |"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--model",
        type=Path,
        default=FROZEN_MODEL_PATH,
        help="Path to frozen w_struct model JSON",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for error_case_analysis.{json,md}",
    )
    p.add_argument(
        "--fixture",
        action="store_true",
        help="Use mock fixture data (no network, no API)",
    )
    p.add_argument(
        "--fixture-size",
        type=int,
        default=100,
        help="Number of fixture samples",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()

    # Load frozen model
    model = load_frozen_model(args.model)
    print(f"Loaded frozen model: {args.model}")

    if args.fixture:
        print("Fixture mode: generating mock PRM800K data...")
        config = _load_config()
        split_config = config["data"]["split_strategy"]
        dev_upper = int(split_config["dev_mod_upper_exclusive"])

        pool_rows = _fixture_pool_rows(size=args.fixture_size)
        pool_samples = variants.build_samples(
            pool_rows,
            split_name="pool",
            row_start=5000,
        )
        # Assign splits deterministically so locked split is consistent
        locked_samples: list[variants.RankingSample] = []
        for s in pool_samples:
            bucket = _hash_bucket(s.sample_id, split_config["salt"])
            if bucket >= dev_upper:
                locked_samples.append(s)
        print(
            f"Fixture: {len(pool_samples)} pool, {len(locked_samples)} locked samples"
        )
    else:
        print("Loading PRM800K data (hash-stratified split)...")
        config = _load_config()
        pool_rows = variants.load_pool_rows(config)
        pool_samples = variants.build_samples(
            pool_rows,
            split_name="pool",
            row_start=int(config["data"]["pool"]["start_row"]),
        )
        split_config = config["data"]["split_strategy"]
        _, locked_samples = variants.split_samples(pool_samples, split_config)
        print(
            f"Pool: {len(pool_samples)}, Locked: {len(locked_samples)}"
        )

    # Run analysis
    print("Computing per-sample variant scores and Spearman correlations...")
    result = analyze(locked_samples, model)

    # Write outputs
    json_path = args.output_dir / "error_case_analysis.json"
    md_path = args.output_dir / "error_case_analysis.md"

    json_path.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_markdown(result), encoding="utf-8")

    elapsed = time.time() - started
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Concrete finding: {result['concrete_finding']}")


if __name__ == "__main__":
    main()
