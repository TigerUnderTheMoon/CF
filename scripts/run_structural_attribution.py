"""Run Phase 6 structural reflection attribution."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.eval.reflection_compression import (
    compress_graphs,
    compression_summary,
    dataclass_to_dict as compression_to_dict,
)
from fma.eval.structural_attribution import (
    compute_edge_necessity,
    compute_node_necessity,
    compute_structural_faithfulness,
    compute_structural_influence,
    compute_structural_metrics,
    compute_subgraph_necessity,
    dataclass_to_dict as structural_to_dict,
    default_subgraphs,
)
from fma.graph.build_reflection_graph import build_reflection_graphs, graph_records
from fma.graph.motif_analysis import detect_motifs, motif_subgraphs, summarize_motifs
from fma.graph.reflection_graph import RemovalMode
from fma.io import load_records, write_records
from fma.visualization.graph_plots import plot_structural_suite


DEFAULT_TRACE_PATH = PROJECT_ROOT / "data" / "traces" / "synthetic_100x8.json"
DEFAULT_NECESSITY_PATH = PROJECT_ROOT / "outputs" / "necessity_scores.jsonl"
DEFAULT_COUNTERFACTUAL_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "counterfactual_summary.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"
LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6 structural reflection attribution.")
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--necessity-scores", type=Path, default=DEFAULT_NECESSITY_PATH)
    parser.add_argument("--counterfactual-summary", type=Path, default=DEFAULT_COUNTERFACTUAL_SUMMARY_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--utility-threshold", type=float, default=0.9)
    parser.add_argument("--removal-mode", choices=[mode.value for mode in RemovalMode], default=RemovalMode.PRUNE.value)
    parser.add_argument("--similarity-method", choices=["none", "tfidf", "jaccard"], default="tfidf")
    parser.add_argument("--similarity-threshold", type=float, default=0.15)
    parser.add_argument("--prune-threshold", type=float, default=0.0)
    parser.add_argument("--max-long-range", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    traces = load_records(args.traces)
    necessity_records = load_records(args.necessity_scores)
    phase5_summary = _read_json(args.counterfactual_summary)

    graphs = build_reflection_graphs(
        traces,
        necessity_records,
        similarity_method=None if args.similarity_method == "none" else args.similarity_method,
        similarity_threshold=args.similarity_threshold,
        prune_threshold=args.prune_threshold,
        max_long_range=args.max_long_range,
    )
    node_rows = []
    edge_rows = []
    subgraph_rows = []
    motif_matches = []
    structural_metrics = []

    for graph in graphs:
        compute_structural_influence(graph)
        node_rows.extend(compute_node_necessity(graph, removal_mode=args.removal_mode))
        edge_rows.extend(compute_edge_necessity(graph))
        matches = detect_motifs(graph)
        motif_matches.extend(matches)
        subgraph_inputs = motif_subgraphs(matches) or default_subgraphs(graph)
        subgraph_rows.extend(compute_subgraph_necessity(graph, subgraph_inputs))
        structural_metrics.append(compute_structural_metrics(graph))

    motif_report = summarize_motifs(motif_matches)
    compression_results = compress_graphs(
        graphs,
        utility_threshold=args.utility_threshold,
        removal_mode=args.removal_mode,
    )
    faithfulness = compute_structural_faithfulness(node_rows, necessity_records)
    faithfulness_report = {
        **faithfulness,
        "num_graphs": len(graphs),
        "num_nodes": sum(len(graph.nodes) for graph in graphs),
        "num_edges": sum(len(graph.edges) for graph in graphs),
        "removal_mode": args.removal_mode,
        "structural_metrics": _aggregate_metrics(structural_metrics),
        "phase5_summary": phase5_summary,
    }
    graph_report = {
        "summary": {
            "num_graphs": len(graphs),
            "num_nodes": sum(len(graph.nodes) for graph in graphs),
            "num_edges": sum(len(graph.edges) for graph in graphs),
        },
        "graphs": graph_records(graphs),
    }
    compression_report = {
        "summary": compression_summary(compression_results),
        "results": [compression_to_dict(result) for result in compression_results],
    }
    run_summary = {
        "num_graphs": len(graphs),
        "num_node_necessity": len(node_rows),
        "num_edge_necessity": len(edge_rows),
        "num_subgraph_necessity": len(subgraph_rows),
        "num_motif_matches": motif_report["num_matches"],
        "faithfulness_pearson": faithfulness_report["pearson"],
        "mean_compression_ratio": compression_report["summary"]["mean_compression_ratio"],
    }

    if args.dry_run:
        LOGGER.info("%s", json.dumps({"dry_run": True, **run_summary}, indent=2, sort_keys=True))
        return run_summary

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "reflection_graph.json", graph_report)
    write_records(
        [structural_to_dict(row) for row in node_rows],
        args.output_dir / "structural_node_necessity.jsonl",
    )
    write_records(
        [structural_to_dict(row) for row in edge_rows],
        args.output_dir / "structural_edge_necessity.jsonl",
    )
    write_records(
        [structural_to_dict(row) for row in subgraph_rows],
        args.output_dir / "structural_subgraph_necessity.jsonl",
    )
    write_json(args.output_dir / "structural_faithfulness.json", faithfulness_report)
    write_json(args.output_dir / "motif_report.json", motif_report)
    write_json(args.output_dir / "reflection_compression_report.json", compression_report)
    plot_structural_suite(
        graphs=graphs,
        node_necessity=[structural_to_dict(row) for row in node_rows],
        edge_necessity=[structural_to_dict(row) for row in edge_rows],
        phase5_scores=necessity_records,
        motif_report=motif_report,
        compression_results=compression_results,
        output_dir=args.figures_dir,
    )
    LOGGER.info("Wrote Phase 6 structural attribution outputs to %s", args.output_dir)
    return run_summary


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _aggregate_metrics(metrics: list[dict[str, float]]) -> dict[str, float]:
    if not metrics:
        return {
            "structural_influence_mean": 0.0,
            "reachable_ratio": 0.0,
            "influence_depth": 0.0,
            "bridge_node_fraction": 0.0,
        }
    keys = sorted(metrics[0])
    return {
        key: float(sum(metric.get(key, 0.0) for metric in metrics) / len(metrics))
        for key in keys
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(parse_args())


if __name__ == "__main__":
    main()
