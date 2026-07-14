"""Static figures for the Wikidata scientist controlled-audit experiment."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from fma.eval.wikidata_controlled_audit import METHODS, MotifBundle


DISPLAY_NAMES = {
    "life_saving_first": "Life-Saving First",
    "life_saving_clustered": "LSF-Clustered",
    "greedy_maximum_coverage": "Greedy Maximum Coverage",
    "flat_top_k": "Flat Top-K",
    "degree_centrality": "Degree",
    "centrality": "Degree",
    "random_stratified": "Random Stratified",
    "position": "Position",
    "random": "Random",
    "no_fallback": "No-Fallback",
    "no_fallback_ablation": "No-Fallback",
    "lsf_minus_bottleneck": "LSF minus bottleneck",
    "lsf_minus_redundancy": "LSF minus redundancy",
    "lsf_minus_unique_layer": "LSF minus unique layer",
}

OVERALL_WORKFLOW_STAGES = (
    "Intelligent Information System",
    "Dependency Graph Construction",
    "Structural Audit Representation",
    "Budget-Aware Audit Decision",
    "Knowledge Maintenance",
)


def plot_overall_workflow(path: Path) -> None:
    labels = [
        "Intelligent\nInformation\nSystem",
        "Dependency\nGraph\nConstruction",
        "Structural\nAudit\nRepresentation",
        "Budget-Aware\nAudit\nDecision",
        "Knowledge\nMaintenance",
    ]
    colors = ["#2f6f4e", "#4178a8", "#7b5ea7", "#b65d3a", "#58636d"]
    fig, ax = plt.subplots(figsize=(7.2, 1.5))
    ax.set_xlim(-0.65, len(labels) - 0.35)
    ax.set_ylim(-0.65, 0.65)
    ax.axis("off")
    for index, (label, color) in enumerate(zip(labels, colors, strict=True)):
        ax.text(
            index,
            0,
            label,
            ha="center",
            va="center",
            color="white",
            fontsize=7.5,
            fontweight="bold",
            bbox={"boxstyle": "round,pad=0.45", "facecolor": color, "edgecolor": "none"},
        )
        if index < len(labels) - 1:
            ax.annotate(
                "",
                xy=(index + 0.62, 0),
                xytext=(index + 0.38, 0),
                arrowprops={"arrowstyle": "->", "color": "#3c444b", "lw": 1.6},
            )
    ax.set_title("Maintenance Workflow for Structural Audit Records", fontsize=9.5)
    _save(fig, path)


def plot_core_structure(bundle: MotifBundle, path: Path) -> None:
    bottlenecks = sorted(bundle.manifest.bottleneck_nodes)[:2]
    group = next(iter(sorted(bundle.manifest.redundancy_groups.items())), ("", ()))
    redundant = list(group[1])
    controls = sorted(bundle.manifest.control_nodes)[:1]
    records = bottlenecks + redundant + controls
    nodes = set(records)
    for node in records:
        nodes.update(map(str, bundle.graph.predecessors(node)))
        nodes.update(
            target
            for target in nx.descendants(bundle.graph, node)
            if int(bundle.graph.nodes[target].get("layer", 0)) == 3
        )
    graph = bundle.graph.subgraph(nodes).copy()
    position = nx.multipartite_layout(graph, subset_key="layer", align="vertical")
    colors = []
    for node in graph:
        if node in bundle.manifest.bottleneck_nodes:
            colors.append("#c7473f")
        elif node in bundle.manifest.redundant_nodes:
            colors.append("#3d79b7")
        elif node in bundle.manifest.control_nodes:
            colors.append("#7d858c")
        elif int(graph.nodes[node].get("layer", 0)) == 3:
            colors.append("#d8a33f")
        else:
            colors.append("#4f8a63")
    labels = {
        node: (
            "B" if node in bundle.manifest.bottleneck_nodes else
            "R" if node in bundle.manifest.redundant_nodes else
            "C" if node in bundle.manifest.control_nodes else
            "T" if int(graph.nodes[node].get("layer", 0)) == 3 else
            "W"
        )
        for node in graph
    }
    fig, ax = plt.subplots(figsize=(10, 5.5))
    nx.draw_networkx_edges(graph, position, ax=ax, edge_color="#9aa1a7", arrows=True, arrowsize=12)
    nx.draw_networkx_nodes(
        graph,
        position,
        ax=ax,
        node_color=colors,
        node_size=650,
        edgecolors="white",
    )
    nx.draw_networkx_labels(graph, position, labels=labels, ax=ax, font_size=8, font_color="white")
    ax.set_title("Controlled Audit Motifs on the Wikidata DAG Overlay")
    ax.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Wikidata anchor",
                markerfacecolor="#4f8a63",
                markersize=9,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Controlled bottleneck (B)",
                markerfacecolor="#c7473f",
                markersize=9,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Controlled redundancy (R)",
                markerfacecolor="#3d79b7",
                markersize=9,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Matched control (C)",
                markerfacecolor="#7d858c",
                markersize=9,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Maintenance terminal (T)",
                markerfacecolor="#d8a33f",
                markersize=9,
            ),
        ],
        loc="upper left",
        frameon=False,
        fontsize=8,
    )
    ax.axis("off")
    _save(fig, path)


def plot_impact_comparison(
    countries_report: Mapping[str, Any],
    wikidata_summary: Sequence[Mapping[str, Any]],
    *,
    budget_fraction: float,
    path: Path,
) -> None:
    countries_keys = {
        "life_saving_first": "life_saving_first",
        "greedy_maximum_coverage": "greedy_max_coverage",
        "flat_top_k": "flat_top_k",
        "degree_centrality": "centrality",
        "random_stratified": "random_stratified",
        "position": "position",
        "random": "random",
        "no_fallback": "no_fallback_ablation",
        "lsf_minus_bottleneck": "lsf_minus_bottleneck",
        "lsf_minus_redundancy": "lsf_minus_redundancy",
        "lsf_minus_unique_layer": "lsf_minus_unique_layer",
    }
    wiki_by_method = {
        str(row["method"]): float(row["mean"])
        for row in wikidata_summary
        if float(row["budget_fraction"]) == float(budget_fraction)
    }
    methods = [
        method
        for method in METHODS
        if method not in {"life_saving_clustered", "no_fallback"}
        and countries_keys.get(method) in countries_report["methods"]
        and method in wiki_by_method
    ]
    countries = []
    for method in methods:
        key = countries_keys[method]
        countries.append(float(countries_report["methods"][key]["impact_coverage_at_k"]["mean"]))
    wikidata = [wiki_by_method[method] for method in methods]
    x = np.arange(len(methods))
    width = 0.38
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.bar(x - width / 2, countries, width, label="Countries-KG", color="#7b858e")
    ax.bar(x + width / 2, wikidata, width, label="Wikidata scientist KG", color="#357a68")
    ax.set_ylabel("Impact Coverage@K")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x, [DISPLAY_NAMES[method] for method in methods], rotation=25, ha="right")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    _save(fig, path)


def plot_sweep(
    summary: Sequence[Mapping[str, Any]],
    *,
    condition_name: str,
    title: str,
    x_label: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    palette = [
        "#357a68",
        "#2f9e9e",
        "#b45b3e",
        "#5279a8",
        "#8d6aa8",
        "#d09a32",
        "#68727a",
        "#bf4f75",
        "#7a6f55",
        "#5f8f4e",
        "#995f7a",
        "#4d8795",
    ]
    available = {str(row["method"]) for row in summary}
    methods = [
        method
        for method in METHODS
        if method != "no_fallback" and method in available
    ]
    for method, color in zip(methods, palette[: len(methods)]):
        rows = sorted(
            (row for row in summary if row["method"] == method),
            key=lambda row: float(row[condition_name]),
        )
        x = [100.0 * float(row[condition_name]) for row in rows]
        y = [float(row["mean"]) for row in rows]
        error = [float(row["std"]) for row in rows]
        ax.errorbar(
            x,
            y,
            yerr=error,
            marker="o",
            linewidth=1.5,
            capsize=2,
            label=DISPLAY_NAMES[method],
            color=color,
        )
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel("Impact Coverage@K (mean +/- SD)")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.25)
    ax.legend(ncol=2, frameon=False, fontsize=8)
    fig.tight_layout()
    _save(fig, path)


def plot_efficiency(summary: Sequence[Mapping[str, Any]], path: Path) -> None:
    sizes = [int(row["target_nodes"]) for row in summary]
    runtime = [float(row["mean_total_seconds"]) for row in summary]
    memory = [float(row["mean_peak_python_mb"]) for row in summary]
    fig, ax_runtime = plt.subplots(figsize=(8.5, 5.2))
    ax_memory = ax_runtime.twinx()
    line_runtime = ax_runtime.plot(sizes, runtime, marker="o", color="#357a68", label="Runtime")
    line_memory = ax_memory.plot(
        sizes,
        memory,
        marker="s",
        color="#b45b3e",
        label="Peak Python memory",
    )
    ax_runtime.set_xlabel("Raw graph nodes")
    ax_runtime.set_ylabel("Runtime (seconds)", color="#357a68")
    ax_memory.set_ylabel("Peak Python memory (MB)", color="#b45b3e")
    ax_runtime.grid(alpha=0.25)
    lines = line_runtime + line_memory
    ax_runtime.legend(lines, [line.get_label() for line in lines], frameon=False)
    fig.tight_layout()
    _save(fig, path)


def plot_anchor_cluster_confirmation(
    summary: Sequence[Mapping[str, Any]],
    path: Path,
) -> None:
    by_method = {str(row["method"]): row for row in summary}
    preferred_order = [
        "life_saving_first",
        "life_saving_clustered",
        "greedy_maximum_coverage",
        "flat_top_k",
        "degree_centrality",
    ]
    methods = [method for method in preferred_order if method in by_method]
    means = [float(by_method[method]["mean"]) for method in methods]
    errors = [float(by_method[method]["std"]) for method in methods]
    colors = ["#357a68", "#2f9e9e", "#8d6aa8", "#b45b3e", "#5279a8"]
    x = np.arange(len(methods))
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.bar(x, means, yerr=errors, capsize=3, color=colors)
    ax.set_title("Anchor-Cluster Confirmation at K=5%")
    ax.set_ylabel("Impact Coverage@K (mean +/- SD)")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x, [DISPLAY_NAMES[method] for method in methods], rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    _save(fig, path)


def plot_structural_sweep(
    summary: Sequence[Mapping[str, Any]],
    *,
    condition_name: str,
    title: str,
    x_label: str,
    path: Path,
) -> None:
    available = {str(row["method"]) for row in summary}
    methods = [
        method
        for method in (
            "life_saving_first",
            "life_saving_clustered",
            "greedy_maximum_coverage",
            "flat_top_k",
            "degree_centrality",
        )
        if method in available
    ]
    metrics = [
        (
            "mean_protected_at_risk_coverage",
            "std_protected_at_risk_coverage",
            "Protected at-risk coverage",
        ),
        ("mean_sink_drop_mass", "std_sink_drop_mass", "Sink-drop mass"),
    ]
    colors = ["#357a68", "#2f9e9e", "#8d6aa8", "#b45b3e", "#5279a8"]
    markers = ["o", "s", "P", "^", "D"]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), sharey=True)
    for ax, (mean_key, std_key, metric_label) in zip(axes, metrics, strict=True):
        for method, color, marker in zip(methods, colors, markers):
            method_rows = sorted(
                (row for row in summary if row["method"] == method),
                key=lambda row: float(row[condition_name]),
            )
            x = [100.0 * float(row[condition_name]) for row in method_rows]
            y = [float(row[mean_key]) for row in method_rows]
            errors = [float(row[std_key]) for row in method_rows]
            ax.errorbar(
                x,
                y,
                yerr=errors,
                color=color,
                marker=marker,
                linewidth=1.5,
                capsize=2,
                label=DISPLAY_NAMES[method],
            )
        ax.set_title(metric_label)
        ax.set_xlabel(x_label)
        ax.set_ylim(0, 1.05)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Structural protection (mean +/- SD)")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle(title)
    fig.tight_layout()
    _save(fig, path)


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
