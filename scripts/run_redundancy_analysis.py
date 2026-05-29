"""Run Phase 7 redundancy and compensation analysis from Phase 6 outputs."""

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

from fma.eval.redundancy import (
    MODE_ORDER,
    compute_bottlenecks,
    compute_compensation_records,
    compute_redundancy,
    compute_rerouting_records,
    profiles_from_graphs,
    reconstruct_intervention_deltas,
    summarize_compensation,
    summarize_distributedness,
    summarize_rerouting,
    summarize_resilience,
)
from fma.eval.structural_attribution import compute_node_necessity, dataclass_to_dict
from fma.graph.reflection_graph import ReflectionGraph, RemovalMode
from fma.io import load_records


DEFAULT_STRUCTURAL_DIAGNOSTICS = PROJECT_ROOT / "outputs" / "structural_diagnostics.json"
DEFAULT_PHASE6_SENSITIVITY = PROJECT_ROOT / "outputs" / "phase6_sensitivity.json"
DEFAULT_GRAPH_PATH = PROJECT_ROOT / "outputs" / "reflection_graph.json"
DEFAULT_NECESSITY_SCORES = PROJECT_ROOT / "outputs" / "necessity_scores.jsonl"
DEFAULT_NODE_NECESSITY = PROJECT_ROOT / "outputs" / "structural_node_necessity.jsonl"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "outputs" / "redundancy_analysis.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "outputs" / "redundancy_analysis.md"
DEFAULT_FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic Phase 7 redundancy and compensation analysis.",
    )
    parser.add_argument("--structural-diagnostics", type=Path, default=DEFAULT_STRUCTURAL_DIAGNOSTICS)
    parser.add_argument("--phase6-sensitivity", type=Path, default=DEFAULT_PHASE6_SENSITIVITY)
    parser.add_argument("--reflection-graph", type=Path, default=DEFAULT_GRAPH_PATH)
    parser.add_argument("--necessity-scores", type=Path, default=DEFAULT_NECESSITY_SCORES)
    parser.add_argument("--node-necessity", type=Path, default=DEFAULT_NODE_NECESSITY)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--redundancy-threshold", type=float, default=0.75)
    parser.add_argument("--bottleneck-threshold", type=float, default=0.25)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    structural_diagnostics = _read_json(args.structural_diagnostics)
    phase6_sensitivity = _read_json(args.phase6_sensitivity)
    graphs = _load_graphs(args.reflection_graph)
    attribution_records = load_records(args.necessity_scores)
    node_necessity_records, adapter_notes = _node_necessity_records(
        graphs,
        args.node_necessity,
    )

    profiles = profiles_from_graphs(
        graphs,
        attribution_records=attribution_records,
        node_necessity_records=node_necessity_records,
    )
    deltas = reconstruct_intervention_deltas(graphs, modes=MODE_ORDER)
    compensation_records = compute_compensation_records(profiles, deltas)
    rerouting_records = compute_rerouting_records(profiles, deltas)
    redundancy = compute_redundancy(
        profiles,
        similarity_threshold=args.redundancy_threshold,
    )
    bottleneck = compute_bottlenecks(
        profiles,
        redundancy["redundancy_degree_by_node"],
        threshold=args.bottleneck_threshold,
    )
    resilience = summarize_resilience(profiles)
    distributedness = summarize_distributedness(profiles)

    report = {
        "meta": {
            "phase": 7,
            "input_source": "structural_diagnostics.json",
            "node_count": len(profiles),
            "edge_count": sum(len(graph.edges) for graph in graphs),
            "graph_count": len(graphs),
            "adapter_notes": adapter_notes,
            "phase6_alignment": _phase6_alignment(structural_diagnostics),
            "phase6_sensitivity_summary": _phase6_sensitivity_summary(phase6_sensitivity),
        },
        "compensation": summarize_compensation(compensation_records),
        "rerouting": summarize_rerouting(rerouting_records),
        "redundancy": {
            "density": redundancy["density"],
            "cluster_sizes": redundancy["cluster_sizes"],
            "mean_cluster_size": redundancy["mean_cluster_size"],
            "average_redundancy_degree": redundancy["average_redundancy_degree"],
            "cluster_density": redundancy["cluster_density"],
            "per_trajectory": redundancy["per_trajectory"],
            "similarity_threshold": redundancy["similarity_threshold"],
        },
        "bottleneck": bottleneck,
        "resilience": resilience,
        "distributedness": distributedness,
    }

    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    write_plots(
        args.figures_dir,
        compensation_records,
        rerouting_records,
        redundancy,
        bottleneck,
        resilience,
        distributedness,
    )
    return report


def _load_graphs(path: Path) -> list[ReflectionGraph]:
    payload = _read_json(path)
    graphs = payload.get("graphs", []) if isinstance(payload, Mapping) else []
    return [ReflectionGraph.from_dict(graph) for graph in graphs]


def _node_necessity_records(
    graphs: Sequence[ReflectionGraph],
    node_necessity_path: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    expected_rows = sum(len(graph.nodes) for graph in graphs)
    records = load_records(node_necessity_path) if node_necessity_path.exists() else []
    notes: list[str] = []
    completed: list[dict[str, Any]] = []

    for mode in MODE_ORDER:
        mode_records = [
            record for record in records if str(record.get("removal_mode", "")).upper() == mode
        ]
        if len(mode_records) == expected_rows:
            completed.extend(mode_records)
            continue
        reconstructed: list[dict[str, Any]] = []
        for graph in graphs:
            reconstructed.extend(
                dataclass_to_dict(row)
                for row in compute_node_necessity(
                    graph,
                    removal_mode=RemovalMode(mode),
                )
            )
        completed.extend(reconstructed)
        notes.append(
            f"{mode} node rows reconstructed from stored reflection_graph.json because raw per-node rows were absent or incomplete."
        )
    return completed, notes


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = report["meta"]
    comp = report["compensation"]
    rerouting = report["rerouting"]
    redundancy = report["redundancy"]
    bottleneck = report["bottleneck"]
    resilience = report["resilience"]
    distributedness = report["distributedness"]

    lines = [
        "# Phase 7 Redundancy and Compensation Analysis",
        "",
        "This report explains why local reflective utility and topology-sensitive structural necessity can weakly align. It is descriptive and structural; it does not introduce new attribution experiments, learned models, or score tuning.",
        "",
        "Weak necessity alignment does not imply attribution invalidity. Instead, it suggests distributed and compensatory reflective organization.",
        "",
        "Observed redistribution patterns should not be interpreted as intentional or agentic adaptation.",
        "",
        "## Methodology",
        "",
        "- Loaded Phase 6 structural diagnostics, sensitivity summaries, stored reflection graphs, and per-step attribution records.",
        "- Joined graph nodes to PRUNE, CASCADE, and BYPASS structural necessity rows. Missing per-node mode rows were reconstructed from stored graph traces only.",
        "- Estimated compensation ratios from post-removal downstream necessity deltas over the stored topology.",
        "- Estimated redundancy using hybrid similarity: half scalar profile cosine similarity and half downstream-influence Jaccard overlap.",
        "- Estimated bottlenecks as high normalized attribution, high normalized necessity, and low normalized redundancy degree.",
        "- Estimated resilience from cumulative removal curves with normalized removal progress before AUC computation.",
        "",
        "## Core Results",
        "",
        f"- Nodes: `{meta['node_count']}` across `{meta['graph_count']}` graphs and `{meta['edge_count']}` edges.",
        f"- Mean rerouting entropy: `{rerouting['mean_entropy']:.4f}`.",
        f"- Mean rerouting depth: `{rerouting['mean_depth']:.4f}`.",
        f"- Redundancy density: `{redundancy['density']:.4f}`.",
        f"- Mean redundancy cluster size: `{redundancy['mean_cluster_size']:.4f}`.",
        f"- Bottleneck count: `{bottleneck['bottleneck_count']}`; rarity: `{bottleneck['rarity']:.4f}`.",
        f"- Distributedness index: `{distributedness['global_index']:.4f}`.",
        "",
        "## Compensation by Mode",
        "",
        "| Mode | Mean compensation ratio |",
        "|---|---:|",
    ]
    for mode in ("prune", "cascade", "bypass"):
        lines.append(f"| {mode.upper()} | {comp[mode]['mean_ratio']:.4f} |")

    lines.extend(
        [
            "",
            "## Resilience AUC",
            "",
            "| Removal sequence | AUC |",
            "|---|---:|",
            f"| Sequential | {resilience['sequential_removal_auc']:.4f} |",
            f"| Deterministic random | {resilience['random_removal_auc']:.4f} |",
            f"| Attribution-first | {resilience['attribution_first_auc']:.4f} |",
            f"| Necessity-first | {resilience['necessity_first_auc']:.4f} |",
            "",
            "## Interpretation Guidance",
            "",
        "- High compensation ratios indicate measured structural redistribution after a node is removed. They do not imply deliberate replanning.",
            "- Here, compensatory behavior means non-agentic functional redistribution in the measured graph, with possible reflective substitution among downstream steps.",
            "- High redundancy density indicates substitutable reflective structure under the stored graph and score profiles.",
            "- High distributedness indicates diffuse necessity rather than a single dominant reflective anchor.",
            "- Sparse bottlenecks identify candidate structural anchors that combine local attribution, topology-sensitive necessity, and low redundancy.",
            "- The analysis should be read as evidence about topology-level robustness and functional displacement, not mechanistic self-repair.",
            "",
            "## Assumptions",
            "",
            "- Graph edges are deterministic approximations from Phase 6 graph construction.",
            "- Necessity is nonnegative-clipped for redundancy, bottleneck, and resilience summaries.",
            "- Post-removal deltas are adapter-level graph-state summaries when explicit Phase 6 delta records are unavailable.",
            "- Deterministic random removal uses stable node-id hashing, not runtime randomness.",
            "",
            "## Limitations",
            "",
            "- The framework conditions only on observable reflection traces and stored graph topology.",
            "- Compensation and rerouting are descriptive redistribution metrics, not evidence of agentic recovery.",
            "- Similarity clusters depend on the fixed hybrid-similarity threshold.",
            "- Resilience curves use stored node necessity profiles and do not rerun intervention experiments.",
            "- Bottleneck scores are candidate diagnostics, not proof of irreplaceability.",
            "",
            "## Redundancy Hypothesis",
            "",
            "The Phase 7 results operationalize the hypothesis that reflective reasoning is redundant, compensatory, and structurally distributed. The weak Phase 6 alignment is therefore informative: many locally useful steps can be replaceable in the topology, while rare high-attribution and high-necessity steps appear as candidate bottlenecks.",
        ]
    )
    if meta["adapter_notes"]:
        lines.extend(["", "## Adapter Notes", ""])
        lines.extend(f"- {note}" for note in meta["adapter_notes"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plots(
    figure_dir: Path,
    compensation_records: Sequence[Any],
    rerouting_records: Sequence[Any],
    redundancy: Mapping[str, Any],
    bottleneck: Mapping[str, Any],
    resilience: Mapping[str, Any],
    distributedness: Mapping[str, Any],
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    _plot_compensation(compensation_records, figure_dir / "compensation_distribution.png")
    _plot_rerouting(rerouting_records, figure_dir / "rerouting_entropy_vs_attribution.png")
    _plot_redundancy(redundancy, figure_dir / "redundancy_density_histogram.png")
    _plot_bottlenecks(bottleneck, figure_dir / "bottleneck_examples.png")
    _plot_resilience(resilience, figure_dir / "resilience_curves.png")
    _plot_distributedness(distributedness, figure_dir / "distributedness_distribution.png")


def _plot_compensation(records: Sequence[Any], save_path: Path) -> None:
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = {"PRUNE": "#4C78A8", "CASCADE": "#E45756", "BYPASS": "#54A24B"}
    plotted = False
    for mode in MODE_ORDER:
        values = [
            min(5.0, record.compensation_ratio)
            for record in records
            if record.mode == mode
        ]
        if values:
            ax.hist(values, bins=20, alpha=0.55, label=mode, color=colors[mode])
            plotted = True
    if plotted:
        ax.set_xlabel("Compensation ratio (clipped at 5 for display)")
        ax.set_ylabel("Node removals")
        ax.legend(frameon=False)
    else:
        _empty(ax, "No compensation samples")
    ax.set_title("Compensation Distribution")
    fig.tight_layout()
    _save(fig, save_path)


def _plot_rerouting(records: Sequence[Any], save_path: Path) -> None:
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    xs = [record.attribution_score for record in records]
    ys = [record.rerouting_entropy for record in records]
    if xs:
        ax.scatter(xs, ys, s=16, alpha=0.35, color="#4C78A8", edgecolors="none")
        ax.set_xlabel("Attribution score")
        ax.set_ylabel("Rerouting entropy")
    else:
        _empty(ax, "No rerouting samples")
    ax.set_title("Rerouting Entropy vs Attribution")
    fig.tight_layout()
    _save(fig, save_path)


def _plot_redundancy(redundancy: Mapping[str, Any], save_path: Path) -> None:
    values = [
        float(payload["density"])
        for payload in redundancy.get("per_trajectory", {}).values()
    ]
    _histogram(
        values,
        "Trajectory redundancy density",
        "Trajectories",
        "Redundancy Density Histogram",
        save_path,
        "#72B7B2",
    )


def _plot_bottlenecks(bottleneck: Mapping[str, Any], save_path: Path) -> None:
    _apply_style()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    examples = list(bottleneck.get("examples", []))[:8]
    if examples:
        labels = [str(item["node_id"]).rsplit("::", 1)[-1] for item in examples]
        values = [float(item["bottleneck_score"]) for item in examples]
        x_values = np.arange(len(labels))
        ax.bar(x_values, values, color="#F58518")
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.set_ylabel("Bottleneck score")
    else:
        _empty(ax, "No bottleneck candidates")
    ax.set_title("Top Bottleneck Examples")
    fig.tight_layout()
    _save(fig, save_path)


def _plot_resilience(resilience: Mapping[str, Any], save_path: Path) -> None:
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = {
        "sequential": "Sequential",
        "random": "Deterministic random",
        "attribution_first": "Attribution first",
        "necessity_first": "Necessity first",
    }
    for strategy, curve in resilience.get("curves", {}).items():
        xs = [point["normalized_removal_step"] for point in curve]
        ys = [point["remaining_total_necessity"] for point in curve]
        ax.plot(xs, ys, label=labels.get(strategy, strategy))
    ax.set_xlabel("Removed nodes / total nodes")
    ax.set_ylabel("Normalized remaining total necessity")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Topology Resilience Curves")
    ax.legend(frameon=False)
    fig.tight_layout()
    _save(fig, save_path)


def _plot_distributedness(distributedness: Mapping[str, Any], save_path: Path) -> None:
    values = list(distributedness.get("per_trajectory", {}).values())
    _histogram(
        [float(value) for value in values],
        "Distributedness index",
        "Trajectories",
        "Distributedness Distribution",
        save_path,
        "#B279A2",
    )


def _histogram(
    values: Sequence[float],
    xlabel: str,
    ylabel: str,
    title: str,
    save_path: Path,
    color: str,
) -> None:
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if values:
        ax.hist(values, bins=min(24, max(5, len(values) // 40 or 5)), color=color, edgecolor="white")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
    else:
        _empty(ax, "No samples")
    ax.set_title(title)
    fig.tight_layout()
    _save(fig, save_path)


def _phase6_alignment(payload: Mapping[str, Any]) -> dict[str, float]:
    modes = payload.get("modes", {}) if isinstance(payload, Mapping) else {}
    return {
        str(mode).lower(): float(mode_payload.get("correlation", {}).get("pearson", 0.0))
        for mode, mode_payload in modes.items()
        if isinstance(mode_payload, Mapping)
    }


def _phase6_sensitivity_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    modes = payload.get("sensitivity", {}).get("modes", {}) if isinstance(payload, Mapping) else {}
    return {
        str(mode).lower(): {
            "node_mean": float(mode_payload.get("node_necessity", {}).get("mean", 0.0)),
            "positive_fraction": float(
                mode_payload.get("node_necessity", {}).get("positive_fraction", 0.0)
            ),
            "faithfulness_pearson": float(mode_payload.get("faithfulness_pearson", 0.0)),
        }
        for mode, mode_payload in modes.items()
        if isinstance(mode_payload, Mapping)
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "axes.titlesize": 13,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
        }
    )


def _empty(ax: plt.Axes, message: str) -> None:
    ax.text(0.5, 0.5, message, ha="center", va="center")
    ax.set_axis_off()


def _save(fig: plt.Figure, save_path: Path) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
