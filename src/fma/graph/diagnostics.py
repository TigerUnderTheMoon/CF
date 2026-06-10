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

from fma.utils.logging_config import get_logger

logger = get_logger("fma.graph.diagnostics")

PROJECT_ROOT = Path(__file__).resolve().parents[3]

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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic diagnostics for weak structural alignment.",
    )
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--necessity-scores", type=Path, default=DEFAULT_NECESSITY_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--similarity-method", choices=["none", "tfidf", "jaccard"], default="tfidf")
    parser.add_argument("--similarity-threshold", type=float, default=0.15)
    parser.add_argument("--prune-threshold", type=float, default=0.0)
    parser.add_argument("--max-long-range", type=int, default=5)
    parser.add_argument("--interactive", action="store_true", default=False)
    return parser.parse_args(argv)


def run_from_config(
    *,
    config_name: str = "phase6/graph",
    overrides: Sequence[str] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Compose a Hydra-style config and adapt it to the legacy diagnostics args."""
    from fma.utils.config import load_config

    config = load_config(
        config_name,
        overrides=overrides or [],
        create_run_dir=True,
        timestamp=timestamp,
    )
    phase6 = config.get("phase6", {})
    inputs = phase6.get("inputs", {}) if isinstance(phase6, dict) else {}
    outputs = phase6.get("outputs", {}) if isinstance(phase6, dict) else {}
    run_dir = Path(config["paths"]["run_dir"])
    figures_dir = Path(outputs.get("figures_dir", "figures"))
    if not figures_dir.is_absolute():
        figures_dir = run_dir / figures_dir
    removal_mode = str(
        config.get("intervention_mode")
        or phase6.get("default_intervention_mode", "PRUNE")
    )
    args = argparse.Namespace(
        traces=_project_path(inputs.get("traces", "data/traces/synthetic_100x8.json")),
        necessity_scores=_project_path(
            inputs.get("necessity_scores", "outputs/necessity_scores.jsonl")
        ),
        output_json=run_dir / outputs.get(
            "structural_diagnostics_json", "structural_diagnostics.json"
        ),
        output_md=run_dir / outputs.get(
            "structural_diagnostics_md", "structural_diagnostics.md"
        ),
        figures_dir=figures_dir,
        removal_mode=removal_mode,
        similarity_method=phase6.get("similarity", {}).get("method", "tfidf") if isinstance(phase6, dict) else "tfidf",
        similarity_threshold=float(phase6.get("similarity", {}).get("long_range_threshold", 0.15)) if isinstance(phase6, dict) else 0.15,
        prune_threshold=float(phase6.get("pruning", {}).get("threshold", 0.0)) if isinstance(phase6, dict) else 0.0,
        max_long_range=int(phase6.get("similarity", {}).get("long_range_max_distance", 5)) if isinstance(phase6, dict) else 5,
        interactive=bool(phase6.get("interactive", False)),
    )
    return run_structural_diagnostics(args)


def _uses_hydra_config(argv: Sequence[str]) -> bool:
    return any(
        token == "--config-name"
        or token.startswith("--config-name=")
        or token.startswith("+")
        or ("=" in token and not token.startswith("--"))
        for token in argv
    )


def _none_if_none_str(value: str | None) -> str | None:
    return None if value in (None, "none") else value


def _project_path(value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(str(value))
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def run_structural_diagnostics(args: argparse.Namespace) -> dict[str, Any]:
    """Run Phase 6 structural diagnostics and write configured artifacts."""
    logger.info("diagnostics_start", traces=str(args.traces), scores=str(args.necessity_scores))
    traces = load_records(args.traces)
    phase5_scores = load_records(args.necessity_scores)
    logger.debug("data_loaded", trace_count=len(traces), score_count=len(phase5_scores))
    graphs = build_reflection_graphs(
        traces,
        phase5_scores,
        similarity_method=_none_if_none_str(getattr(args, "similarity_method", None)),
        similarity_threshold=getattr(args, "similarity_threshold", 0.15),
        prune_threshold=getattr(args, "prune_threshold", 0.0),
        max_long_range=getattr(args, "max_long_range", 5),
    )
    source_node_ids = {
        node_id
        for graph in graphs
        for node_id in graph.source_nodes()
    }
    logger.info("graphs_built", graph_count=len(graphs), source_node_count=len(source_node_ids))

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
        logger.debug("processing_mode", mode=removal_mode.value)
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
        logger.debug("mode_complete", mode=removal_mode.value, record_count=len(records))

    report["cross_mode"] = _cross_mode_summary(report["modes"])
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    write_plots(records_by_mode, report, args.figures_dir)
    logger.info(
        "diagnostics_complete",
        output_json=str(args.output_json),
        output_md=str(args.output_md),
        figures_dir=str(args.figures_dir),
    )
    if getattr(args, "interactive", False):
        write_interactive_plots(records_by_mode, report, args.figures_dir)
        logger.debug("interactive_plots_written", figures_dir=str(args.figures_dir))
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
            "- The current evidence does not support true causal identification; Phase 6 studies topology-mediated functional influence under deterministic graph interventions.",
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
    fig, axes = plt.subplots(2, 2, figsize=(8.2, 7.0), sharex=True, sharey=True)
    flat_axes = list(axes.ravel())
    colors = {"PRUNE": "#0072B2", "CASCADE": "#D55E00", "BYPASS": "#009E73"}
    for axis, mode in zip(flat_axes[:3], MODE_ORDER):
        records = records_by_mode[mode]
        xs = [record.attribution_score for record in records]
        ys = [record.structural_necessity for record in records]
        if xs:
            axis.scatter(xs, ys, s=10, alpha=0.28, color=colors[mode], edgecolors="none")
        else:
            axis.text(0.5, 0.5, "No samples", ha="center", va="center")
        pearson = report["modes"][mode]["correlation"]["pearson"]
        zero_rate = report["modes"][mode]["zero_inflation"][
            "zero_structural_necessity_fraction"
        ]
        axis.plot([0.0, 1.0], [0.0, 1.0], color="#333333", linewidth=0.9, linestyle="--")
        axis.set_title(f"{mode}: r={pearson:.3f}, zero={zero_rate:.1%}")
        axis.set_xlim(-0.03, 1.03)
        axis.set_ylim(-0.03, 1.03)

    pooled_axis = flat_axes[3]
    pooled_xs = [
        record.attribution_score
        for mode in MODE_ORDER
        for record in records_by_mode[mode]
    ]
    pooled_ys = [
        record.structural_necessity
        for mode in MODE_ORDER
        for record in records_by_mode[mode]
    ]
    if pooled_xs:
        density = pooled_axis.hexbin(
            pooled_xs,
            pooled_ys,
            gridsize=28,
            mincnt=1,
            cmap="viridis",
            linewidths=0.0,
        )
        fig.colorbar(density, ax=pooled_axis, fraction=0.046, pad=0.04).set_label("Count")
    else:
        pooled_axis.text(0.5, 0.5, "No samples", ha="center", va="center")
    pooled_axis.plot([0.0, 1.0], [0.0, 1.0], color="#333333", linewidth=0.9, linestyle="--")
    pooled_axis.set_title("Mode-pooled density")

    for axis in flat_axes:
        axis.set_xlabel("Phase 5 attribution_score")
        axis.grid(alpha=0.25, linewidth=0.6)
    flat_axes[0].set_ylabel("Phase 6 structural necessity")
    flat_axes[2].set_ylabel("Phase 6 structural necessity")
    sample_n = report["modes"][MODE_ORDER[0]]["correlation"]["num_samples"]
    zero_fraction = report["cross_mode"]["mean_zero_structural_necessity_fraction"]
    fig.suptitle(
        f"Local Attribution vs Topology-Sensitive Necessity (n={sample_n}, zero={zero_fraction:.1%})",
        y=0.995,
    )
    fig.tight_layout()
    _save(fig, save_path)


def _plot_mode_comparison(report: Mapping[str, Any], save_path: Path) -> None:
    _apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    x_values = np.arange(len(MODE_ORDER))
    width = 0.24

    metric_specs = (
        ("pearson", "Pearson", "#0072B2"),
        ("spearman", "Spearman", "#E69F00"),
        ("kendall_tau", "Kendall Tau", "#009E73"),
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
    axes[1].bar(x_values - width / 2, zero_values, width=width, label="Necessity = 0", color="#CC79A7")
    axes[1].bar(x_values + width / 2, mismatch_values, width=width, label="Attr > 0, necessity = 0", color="#D55E00")
    axes[1].set_xticks(x_values)
    axes[1].set_xticklabels(MODE_ORDER)
    axes[1].set_ylim(0.0, 1.0)
    axes[1].set_ylabel("Fraction")
    axes[1].set_title("Zero-Inflation")
    axes[1].legend(frameon=False)

    fig.suptitle("PRUNE / CASCADE / BYPASS Diagnostic Comparison", y=1.03)
    fig.tight_layout()
    _save(fig, save_path)


def write_interactive_plots(
    records_by_mode: Mapping[str, Sequence[StructuralDiagnosticRecord]],
    report: Mapping[str, Any],
    figure_dir: Path,
) -> None:
    """Generate interactive Plotly HTML charts. Gracefully skips if plotly is missing."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return

    figure_dir.mkdir(parents=True, exist_ok=True)
    _interactive_scatter(records_by_mode, report, figure_dir, go, make_subplots)
    _interactive_mode_comparison(report, figure_dir, go, make_subplots)


def _interactive_scatter(
    records_by_mode: Mapping[str, Sequence[StructuralDiagnosticRecord]],
    report: Mapping[str, Any],
    figure_dir: Path,
    go: Any,
    make_subplots: Any,
) -> None:
    colors = {"PRUNE": "#0072B2", "CASCADE": "#D55E00", "BYPASS": "#009E73"}
    fig = go.Figure()
    for mode in MODE_ORDER:
        records = records_by_mode[mode]
        if not records:
            continue
        hover_texts = [
            f"trace_id: {r.trace_id}<br>node_id: {r.node_id}<br>taxonomy: {r.taxonomy_label}"
            for r in records
        ]
        fig.add_trace(
            go.Scatter(
                x=[r.attribution_score for r in records],
                y=[r.structural_necessity for r in records],
                mode="markers",
                name=mode,
                marker=dict(color=colors.get(mode, "#999"), size=6, opacity=0.5),
                text=hover_texts,
                hoverinfo="text",
            )
        )
    pearson_vals = " / ".join(
        f"{m}: {report['modes'][m]['correlation']['pearson']:.3f}" for m in MODE_ORDER
    )
    fig.update_layout(
        title=f"Attribution vs Necessity ({pearson_vals})",
        xaxis_title="Phase 5 attribution_score",
        yaxis_title="Phase 6 structural necessity",
        template="plotly_white",
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80),
    )
    fig.write_html(
        str(figure_dir / "structural_diagnostics_attribution_vs_necessity.html"),
        include_plotlyjs="cdn",
        full_html=True,
    )


def _interactive_mode_comparison(
    report: Mapping[str, Any],
    figure_dir: Path,
    go: Any,
    make_subplots: Any,
) -> None:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Alignment Metrics", "Zero-Inflation"))
    metric_specs = (
        ("pearson", "Pearson", "#0072B2"),
        ("spearman", "Spearman", "#E69F00"),
        ("kendall_tau", "Kendall Tau", "#009E73"),
    )
    for key, label, color in metric_specs:
        fig.add_trace(
            go.Bar(
                name=label,
                x=list(MODE_ORDER),
                y=[report["modes"][m]["correlation"][key] for m in MODE_ORDER],
                marker_color=color,
            ),
            row=1,
            col=1,
        )
    fig.add_trace(
        go.Bar(
            name="Necessity = 0",
            x=list(MODE_ORDER),
            y=[
                report["modes"][m]["zero_inflation"]["zero_structural_necessity_fraction"]
                for m in MODE_ORDER
            ],
            marker_color="#CC79A7",
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(
            name="Attr > 0, necessity = 0",
            x=list(MODE_ORDER),
            y=[
                report["modes"][m]["zero_inflation"][
                    "positive_attribution_zero_necessity_fraction"
                ]
                for m in MODE_ORDER
            ],
            marker_color="#D55E00",
        ),
        row=1,
        col=2,
    )
    fig.update_layout(
        title="PRUNE / CASCADE / BYPASS Diagnostic Comparison",
        template="plotly_white",
        barmode="group",
        margin=dict(t=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.write_html(
        str(figure_dir / "structural_diagnostics_mode_comparison.html"),
        include_plotlyjs="cdn",
        full_html=True,
    )


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
            "figure.titlesize": 12,
        }
    )


def _save(fig: plt.Figure, save_path: Path) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> dict[str, Any] | None:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if _uses_hydra_config(raw_args):
        parser = argparse.ArgumentParser(
            description="Run structural diagnostics from a Hydra-style config.",
        )
        parser.add_argument("--config-name", default="phase6/graph")
        args, overrides = parser.parse_known_args(raw_args)
        return run_from_config(config_name=args.config_name, overrides=overrides)
    return run_structural_diagnostics(parse_args(raw_args))


if __name__ == "__main__":
    main()


__all__ = [
    "DEFAULT_FIGURE_DIR",
    "DEFAULT_NECESSITY_PATH",
    "DEFAULT_OUTPUT_JSON",
    "DEFAULT_OUTPUT_MD",
    "DEFAULT_TRACE_PATH",
    "MODE_ORDER",
    "TOP_K_VALUES",
    "main",
    "parse_args",
    "run_from_config",
    "run_structural_diagnostics",
    "write_interactive_plots",
    "write_json",
    "write_markdown",
    "write_plots",
]
