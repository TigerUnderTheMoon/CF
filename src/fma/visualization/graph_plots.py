"""Plots for Phase 6 structural reflection attribution."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from fma.eval.reflection_compression import CompressionResult
from fma.graph.reflection_graph import ReflectionGraph


def plot_graph_size_distribution(
    graphs: Sequence[ReflectionGraph],
    save_path: str | Path,
) -> None:
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 4))
    sizes = [len(graph.nodes) for graph in graphs]
    if sizes:
        bins = range(1, max(sizes) + 2)
        ax.hist(sizes, bins=bins, color="#4C78A8", edgecolor="white", align="left")
        ax.set_xlabel("Nodes per trace graph")
        ax.set_ylabel("Graph count")
    else:
        _empty(ax, "No graph samples")
    ax.set_title("Reflection Graph Sizes")
    fig.tight_layout()
    _save(fig, save_path)


def plot_node_necessity_distribution(
    node_necessity: Sequence[Mapping[str, Any] | Any],
    save_path: str | Path,
) -> None:
    _histogram(
        [_number(_field(row, "necessity")) for row in node_necessity],
        "Structural node necessity",
        "Count",
        "Node Necessity Distribution",
        save_path,
        "#54A24B",
    )


def plot_edge_necessity_distribution(
    edge_necessity: Sequence[Mapping[str, Any] | Any],
    save_path: str | Path,
) -> None:
    _histogram(
        [_number(_field(row, "necessity")) for row in edge_necessity],
        "Structural edge necessity",
        "Count",
        "Edge Necessity Distribution",
        save_path,
        "#F58518",
    )


def plot_structural_faithfulness_scatter(
    node_necessity: Sequence[Mapping[str, Any] | Any],
    phase5_scores: Sequence[Mapping[str, Any]],
    save_path: str | Path,
) -> None:
    score_by_key = {
        (str(row.get("trace_id")), int(row.get("step_idx"))): float(row.get("attribution_score", 0.0))
        for row in phase5_scores
        if "trace_id" in row and "step_idx" in row
    }
    xs: list[float] = []
    ys: list[float] = []
    for row in node_necessity:
        key = (str(_field(row, "trace_id")), int(_field(row, "step_idx")))
        if key not in score_by_key:
            continue
        xs.append(score_by_key[key])
        ys.append(_number(_field(row, "necessity")))

    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    if xs:
        ax.scatter(xs, ys, color="#4C78A8", alpha=0.65, s=24)
        ax.set_xlabel("Phase 5 attribution score")
        ax.set_ylabel("Structural node necessity")
    else:
        _empty(ax, "No paired faithfulness samples")
    ax.set_title("Structural Faithfulness")
    fig.tight_layout()
    _save(fig, save_path)


def plot_motif_frequency(
    motif_report: Mapping[str, Any],
    save_path: str | Path,
) -> None:
    counts = dict(motif_report.get("motif_counts", {}))
    labels = sorted(counts)
    values = [int(counts[label]) for label in labels]
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))
    if labels:
        x_values = np.arange(len(labels))
        ax.bar(x_values, values, color="#72B7B2")
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.set_ylabel("Matches")
    else:
        _empty(ax, "No motif matches")
    ax.set_title("Motif Frequency")
    fig.tight_layout()
    _save(fig, save_path)


def plot_compression_curve(
    compression_results: Sequence[CompressionResult | Mapping[str, Any]],
    save_path: str | Path,
) -> None:
    grouped: dict[int, list[float]] = defaultdict(list)
    for result in compression_results:
        for point in _field(result, "curve", []):
            grouped[int(point.get("iteration", 0))].append(float(point.get("utility_ratio", 0.0)))

    labels = sorted(grouped)
    means = [float(np.mean(grouped[label])) for label in labels]
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    if labels:
        ax.plot(labels, means, marker="o", color="#E45756")
        ax.set_xlabel("Accepted deletion iteration")
        ax.set_ylabel("Mean retained structural utility")
        ax.set_ylim(0.0, max(1.05, max(means) + 0.05))
    else:
        _empty(ax, "No compression curve")
    ax.set_title("Structural Compression Curve")
    fig.tight_layout()
    _save(fig, save_path)


def plot_structural_influence_distribution(
    node_necessity: Sequence[Mapping[str, Any] | Any],
    save_path: str | Path,
) -> None:
    _histogram(
        [_number(_field(row, "structural_influence")) for row in node_necessity],
        "Structural influence",
        "Count",
        "Structural Influence Distribution",
        save_path,
        "#B279A2",
    )


def plot_structural_suite(
    graphs: Sequence[ReflectionGraph],
    node_necessity: Sequence[Mapping[str, Any] | Any],
    edge_necessity: Sequence[Mapping[str, Any] | Any],
    phase5_scores: Sequence[Mapping[str, Any]],
    motif_report: Mapping[str, Any],
    compression_results: Sequence[CompressionResult | Mapping[str, Any]],
    output_dir: str | Path,
) -> None:
    figure_dir = Path(output_dir)
    plot_graph_size_distribution(graphs, figure_dir / "graph_size_distribution.png")
    plot_node_necessity_distribution(node_necessity, figure_dir / "node_necessity_distribution.png")
    plot_edge_necessity_distribution(edge_necessity, figure_dir / "edge_necessity_distribution.png")
    plot_structural_faithfulness_scatter(
        node_necessity,
        phase5_scores,
        figure_dir / "structural_faithfulness_scatter.png",
    )
    plot_motif_frequency(motif_report, figure_dir / "motif_frequency.png")
    plot_compression_curve(compression_results, figure_dir / "compression_curve.png")
    plot_structural_influence_distribution(
        node_necessity,
        figure_dir / "structural_influence_distribution.png",
    )


def _histogram(
    values: Sequence[float],
    xlabel: str,
    ylabel: str,
    title: str,
    save_path: str | Path,
    color: str,
) -> None:
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 4))
    if values:
        bins = min(24, max(5, len(values) // 40 or 5))
        ax.hist(values, bins=bins, color=color, edgecolor="white")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
    else:
        _empty(ax, "No samples")
    ax.set_title(title)
    fig.tight_layout()
    _save(fig, save_path)


def _field(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def _number(value: Any) -> float:
    return float(value) if value is not None else 0.0


def _empty(ax: plt.Axes, message: str) -> None:
    ax.text(0.5, 0.5, message, ha="center", va="center")
    ax.set_axis_off()


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )


def _save(fig: plt.Figure, save_path: str | Path) -> None:
    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    plt.close(fig)


__all__ = [
    "plot_compression_curve",
    "plot_edge_necessity_distribution",
    "plot_graph_size_distribution",
    "plot_motif_frequency",
    "plot_node_necessity_distribution",
    "plot_structural_faithfulness_scatter",
    "plot_structural_influence_distribution",
    "plot_structural_suite",
]
