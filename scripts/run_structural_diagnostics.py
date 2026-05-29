"""Run interpretation diagnostics for structural reflection attribution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.eval.diagnostics.topology_statistics import (
    StructuralDiagnosticRecord,
    join_phase5_structural_records,
    mode_diagnostics,
)
from fma.eval.structural_attribution import compute_node_necessity
from fma.graph.build_reflection_graph import build_reflection_graphs
from fma.graph.reflection_graph import RemovalMode
from fma.io import load_records


DEFAULT_TRACE_PATH = PROJECT_ROOT / "data" / "traces" / "synthetic_100x8.json"
DEFAULT_NECESSITY_PATH = PROJECT_ROOT / "outputs" / "necessity_scores.jsonl"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "outputs" / "structural_diagnostics.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "outputs" / "structural_diagnostics.md"
DEFAULT_FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"
TOP_K_VALUES = (3, 5, 10)
MODE_ORDER = tuple(mode.value for mode in RemovalMode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic diagnostics for weak structural alignment.",
    )
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--necessity-scores", type=Path, default=DEFAULT_NECESSITY_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    traces = load_records(args.traces)
    phase5_scores = load_records(args.necessity_scores)
    graphs = build_reflection_graphs(traces, phase5_scores)
    source_node_ids = {
        node_id
        for graph in graphs
        for node_id in graph.source_nodes()
    }

    records_by_mode: dict[str, list[StructuralDiagnosticRecord]] = {}
    report: dict[str, Any] = {
        "inputs": {
            "traces": str(args.traces),
            "phase5_scores": str(args.necessity_scores),
        },
        "summary": {
            "num_graphs": len(graphs),
            "num_phase5_scores": len(phase5_scores),
            "num_source_nodes": len(source_node_ids),
            "top_k_values": list(TOP_K_VALUES),
        },
        "interpretation": {
            "primary_reading": "weak structural alignment",
            "boundary": "local attribution and topology-sensitive necessity are different signals",
            "causal_scope": "Phase 6 studies topology-mediated functional influence, not true causal identification",
        },
        "modes": {},
    }

    for removal_mode in RemovalMode:
        node_rows = []
        for graph in graphs:
            node_rows.extend(compute_node_necessity(graph, removal_mode=removal_mode))
        records = join_phase5_structural_records(
            node_rows,
            phase5_scores,
            source_node_ids=source_node_ids,
            removal_mode=removal_mode.value,
        )
        records_by_mode[removal_mode.value] = records
        report["modes"][removal_mode.value] = {
            "num_node_rows": len(node_rows),
            **mode_diagnostics(records, top_k_values=TOP_K_VALUES),
        }

    report["cross_mode"] = _cross_mode_summary(report["modes"])
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    write_plots(records_by_mode, report, args.figures_dir)
    return report


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Structural Diagnostics",
        "",
        "This report compares Phase 5 `attribution_score` with Phase 6 topology-sensitive necessity. It is an interpretation diagnostic, not a new attribution algorithm.",
        "",
        "The expected reading is weak structural alignment: local reflective attribution and structural reflective necessity are related but distinct signals.",
        "",
        "## Overall Correlation",
        "",
        "| Mode | Pearson | Spearman | Kendall Tau | Top-10 overlap | Zero necessity | Attribution > 0 and necessity = 0 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for mode in MODE_ORDER:
        mode_report = report["modes"][mode]
        corr = mode_report["correlation"]
        zero = mode_report["zero_inflation"]
        lines.append(
            "| {mode} | {pearson:.4f} | {spearman:.4f} | {kendall:.4f} | {top10:.4f} | {zero_frac:.2%} | {mismatch:.2%} |".format(
                mode=mode,
                pearson=corr["pearson"],
                spearman=corr["spearman"],
                kendall=corr["kendall_tau"],
                top10=corr["top_k_overlap"]["10"],
                zero_frac=zero["zero_structural_necessity_fraction"],
                mismatch=zero["positive_attribution_zero_necessity_fraction"],
            )
        )

    lines.extend(
        [
            "",
            "## Scatter Summaries",
            "",
            "| Mode | Samples | Mean attribution | Mean necessity | Median necessity | Positive necessity |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for mode in MODE_ORDER:
        mode_report = report["modes"][mode]
        scatter = mode_report["scatter"]
        zero = mode_report["zero_inflation"]
        lines.append(
            "| {mode} | {n} | {attr_mean:.4f} | {nec_mean:.4f} | {nec_median:.4f} | {pos_nec:.2%} |".format(
                mode=mode,
                n=scatter["num_samples"],
                attr_mean=scatter["attribution_score"]["mean"],
                nec_mean=scatter["structural_necessity"]["mean"],
                nec_median=scatter["structural_necessity"]["median"],
                pos_nec=zero["positive_structural_necessity_fraction"],
            )
        )

    lines.extend(
        [
            "",
            "## Stratified Diagnostics",
            "",
            "Per-group correlations help identify local-to-structural mismatch rather than masking it with one global linear statistic.",
        ]
    )
    for mode in MODE_ORDER:
        lines.extend(["", f"### {mode}", ""])
        lines.extend(_stratified_lines(report["modes"][mode]["stratified"]))

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Low Pearson values indicate weak structural alignment; they do not confirm Phase 5 scores or prove attribution correctness.",
            "- Structural necessity is topology-sensitive: bridge nodes, source reachability, and downstream dependencies can dominate local scalar scores.",
            "- Zero-inflated necessity distributions make linear correlation conservative because many positive local scores have no structural removal effect.",
            "- CASCADE is especially sensitive to propagation because it removes descendants as well as the selected node.",
            "- The framework does not claim true causal identification; Phase 6 studies topology-mediated functional influence under deterministic graph interventions.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plots(
    records_by_mode: Mapping[str, Sequence[StructuralDiagnosticRecord]],
    report: Mapping[str, Any],
    figure_dir: Path,
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    _plot_attribution_vs_necessity(
        records_by_mode,
        report,
        figure_dir / "structural_diagnostics_attribution_vs_necessity.png",
    )
    _plot_mode_comparison(
        report,
        figure_dir / "structural_diagnostics_mode_comparison.png",
    )


def _plot_attribution_vs_necessity(
    records_by_mode: Mapping[str, Sequence[StructuralDiagnosticRecord]],
    report: Mapping[str, Any],
    save_path: Path,
) -> None:
    _apply_style()
    fig, axes = plt.subplots(1, len(MODE_ORDER), figsize=(13.5, 4.2), sharex=True, sharey=True)
    colors = {"PRUNE": "#4C78A8", "CASCADE": "#E45756", "BYPASS": "#54A24B"}
    for axis, mode in zip(axes, MODE_ORDER):
        records = records_by_mode[mode]
        xs = [record.attribution_score for record in records]
        ys = [record.structural_necessity for record in records]
        if xs:
            axis.scatter(xs, ys, s=14, alpha=0.35, color=colors[mode], edgecolors="none")
        else:
            axis.text(0.5, 0.5, "No samples", ha="center", va="center")
        pearson = report["modes"][mode]["correlation"]["pearson"]
        axis.set_title(f"{mode} (Pearson {pearson:.3f})")
        axis.set_xlabel("Phase 5 attribution_score")
        axis.set_xlim(-0.03, 0.93)
        axis.set_ylim(-0.03, 1.03)
    axes[0].set_ylabel("Phase 6 structural necessity")
    fig.suptitle("Local Attribution vs Topology-Sensitive Necessity", y=1.03)
    fig.tight_layout()
    _save(fig, save_path)


def _plot_mode_comparison(report: Mapping[str, Any], save_path: Path) -> None:
    _apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    x_values = np.arange(len(MODE_ORDER))
    width = 0.24

    metric_specs = (
        ("pearson", "Pearson", "#4C78A8"),
        ("spearman", "Spearman", "#F58518"),
        ("kendall_tau", "Kendall Tau", "#72B7B2"),
    )
    for offset, (key, label, color) in enumerate(metric_specs):
        values = [report["modes"][mode]["correlation"][key] for mode in MODE_ORDER]
        axes[0].bar(x_values + (offset - 1) * width, values, width=width, label=label, color=color)
    axes[0].axhline(0.0, color="#333333", linewidth=0.8)
    axes[0].set_xticks(x_values)
    axes[0].set_xticklabels(MODE_ORDER)
    axes[0].set_ylabel("Correlation")
    axes[0].set_title("Alignment Metrics")
    axes[0].legend(frameon=False)

    zero_values = [
        report["modes"][mode]["zero_inflation"]["zero_structural_necessity_fraction"]
        for mode in MODE_ORDER
    ]
    mismatch_values = [
        report["modes"][mode]["zero_inflation"]["positive_attribution_zero_necessity_fraction"]
        for mode in MODE_ORDER
    ]
    axes[1].bar(x_values - width / 2, zero_values, width=width, label="Necessity = 0", color="#B279A2")
    axes[1].bar(x_values + width / 2, mismatch_values, width=width, label="Attr > 0, necessity = 0", color="#FF9DA6")
    axes[1].set_xticks(x_values)
    axes[1].set_xticklabels(MODE_ORDER)
    axes[1].set_ylim(0.0, 1.0)
    axes[1].set_ylabel("Fraction")
    axes[1].set_title("Zero-Inflation")
    axes[1].legend(frameon=False)

    fig.suptitle("PRUNE / CASCADE / BYPASS Diagnostic Comparison", y=1.03)
    fig.tight_layout()
    _save(fig, save_path)


def _stratified_lines(stratified: Mapping[str, Mapping[str, Mapping[str, float]]]) -> list[str]:
    lines: list[str] = []
    for group_name in ("taxonomy", "step_idx", "source_role"):
        lines.extend(
            [
                f"#### {group_name}",
                "",
                "| Group | Samples | Pearson | Spearman |",
                "|---|---:|---:|---:|",
            ]
        )
        for group_key, summary in stratified[group_name].items():
            lines.append(
                "| {group} | {n} | {pearson:.4f} | {spearman:.4f} |".format(
                    group=group_key,
                    n=int(summary["num_samples"]),
                    pearson=summary["pearson"],
                    spearman=summary["spearman"],
                )
            )
        lines.append("")
    return lines


def _cross_mode_summary(modes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "lowest_pearson_mode": min(
            MODE_ORDER,
            key=lambda mode: modes[mode]["correlation"]["pearson"],
        ),
        "highest_pearson_mode": max(
            MODE_ORDER,
            key=lambda mode: modes[mode]["correlation"]["pearson"],
        ),
        "mean_zero_structural_necessity_fraction": float(
            np.mean(
                [
                    modes[mode]["zero_inflation"]["zero_structural_necessity_fraction"]
                    for mode in MODE_ORDER
                ]
            )
        ),
    }


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
        }
    )


def _save(fig: plt.Figure, save_path: Path) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
