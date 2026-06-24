"""Reviewer V2 graph-construction ablation.

Compares graph-building variants under the existing structural attribution
machinery. The report is mechanism-ablation evidence only and makes zero API
calls.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from fma.eval.structural_attribution import (  # noqa: E402
    compute_node_necessity,
    compute_structural_faithfulness,
    compute_structural_metrics,
    dataclass_to_dict,
)
from fma.graph.build_reflection_graph import build_reflection_graphs  # noqa: E402
from fma.graph.reflection_graph import ReflectionGraph  # noqa: E402
from fma.io import load_records  # noqa: E402
from reviewer_v2_common import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    SEED_LIST,
    Timer,
    common_metadata,
    fixture_necessity_records,
    fixture_traces,
    mean,
    safe_corr,
    write_json,
    write_markdown,
)


DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "graph_construction_ablation"
DEFAULT_TRACE_PATH = PROJECT_ROOT / "data" / "traces" / "synthetic_100x8.json"
DEFAULT_NECESSITY_PATH = PROJECT_ROOT / "outputs" / "necessity_scores.jsonl"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--necessity-scores", type=Path, default=DEFAULT_NECESSITY_PATH)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--fixture-size", type=int, default=40)
    parser.add_argument("--similarity-threshold", type=float, default=0.15)
    parser.add_argument("--max-long-range", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    timer = Timer.start()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.fixture:
        traces = fixture_traces(args.fixture_size)
        necessity_records = fixture_necessity_records(traces)
        source_artifacts = ["fixture_traces", "fixture_necessity_records"]
    else:
        traces = load_records(args.traces)
        necessity_records = load_records(args.necessity_scores)
        source_artifacts = [str(args.traces), str(args.necessity_scores)]

    variants = {
        "full_tfidf": _build_variant(
            traces,
            necessity_records,
            method="tfidf",
            threshold=args.similarity_threshold,
            max_long_range=args.max_long_range,
        ),
        "temporal_only": _build_variant(
            traces,
            necessity_records,
            method=None,
            threshold=args.similarity_threshold,
            max_long_range=1,
        ),
        "jaccard_topical": _build_variant(
            traces,
            necessity_records,
            method="jaccard",
            threshold=args.similarity_threshold,
            max_long_range=args.max_long_range,
        ),
    }
    variants["shuffled_topical"] = _shuffle_topical_edges(
        variants["full_tfidf"],
        seeds=SEED_LIST,
    )

    variant_metrics = {
        name: _summarize_graphs(graphs, necessity_records)
        for name, graphs in variants.items()
    }
    report = {
        **common_metadata(
            output_dir=args.output_dir,
            evidence_level="mechanism_ablation",
            source_artifacts=source_artifacts,
        ),
        "experiment": "graph_construction_ablation",
        "n_traces": len(traces),
        "n_steps": sum(len(trace.get("reflection_chain", [])) for trace in traces),
        "elapsed_seconds": timer.elapsed(),
        "variants": variant_metrics,
        "interpretation_rule": (
            "Ranking metrics answer whether graph construction changes ordering; "
            "structural diagnostics answer how necessity, redundancy, and "
            "bottleneck structure change."
        ),
    }

    write_json(args.output_dir / "graph_construction_ablation.json", report)
    write_markdown(
        args.output_dir / "graph_construction_ablation.md",
        _render_markdown(report),
    )
    print(f"Wrote {args.output_dir / 'graph_construction_ablation.json'}")
    print(f"Wrote {args.output_dir / 'graph_construction_ablation.md'}")


def _build_variant(
    traces: Sequence[Mapping[str, Any]],
    necessity_records: Sequence[Mapping[str, Any]],
    *,
    method: str | None,
    threshold: float,
    max_long_range: int,
) -> list[ReflectionGraph]:
    return build_reflection_graphs(
        traces,
        necessity_records,
        similarity_method=method,
        similarity_threshold=threshold,
        max_long_range=max_long_range,
    )


def _shuffle_topical_edges(graphs: Sequence[ReflectionGraph], *, seeds: Sequence[int]) -> list[ReflectionGraph]:
    shuffled: list[ReflectionGraph] = []
    for graph_index, graph in enumerate(graphs):
        new_graph = graph.copy()
        temporal_edges = {
            (edge.source, edge.target)
            for edge in graph.sorted_edges()
            if _step_index(graph, edge.target) == _step_index(graph, edge.source) + 1
        }
        topical_edges = [
            edge for edge in graph.sorted_edges() if (edge.source, edge.target) not in temporal_edges
        ]
        for edge in topical_edges:
            new_graph.edges.pop((edge.source, edge.target), None)

        node_ids = [node.node_id for node in graph.sorted_nodes()]
        candidates = [
            (left, right)
            for left in node_ids
            for right in node_ids
            if _step_index(graph, left) + 1 < _step_index(graph, right)
            and (left, right) not in temporal_edges
        ]
        rng = random.Random(seeds[graph_index % len(seeds)])
        rng.shuffle(candidates)
        added = 0
        for left, right in candidates:
            if added >= len(topical_edges):
                break
            if new_graph.has_edge(left, right):
                continue
            try:
                new_graph.add_edge(left, right, "elaborates", 0.5, 0.5)
            except ValueError:
                continue
            added += 1
        shuffled.append(new_graph)
    return shuffled


def _step_index(graph: ReflectionGraph, node_id: str) -> int:
    return int(graph.nodes[node_id].step_index)


def _summarize_graphs(
    graphs: Sequence[ReflectionGraph],
    necessity_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    node_rows = []
    structural_metrics = []
    labels = []
    scores = []
    for graph in graphs:
        rows = compute_node_necessity(graph)
        node_rows.extend(rows)
        structural_metrics.append(compute_structural_metrics(graph))
        for row in rows:
            label = _phase5_score(necessity_records, row.trace_id, row.step_idx)
            labels.append(label)
            scores.append(float(row.necessity))

    row_dicts = [dataclass_to_dict(row) for row in node_rows]
    necessity_values = [float(row["necessity"]) for row in row_dicts]
    faithfulness = compute_structural_faithfulness(node_rows, necessity_records)
    return {
        "spearman": safe_corr(scores, labels, "spearman"),
        "kendall": safe_corr(scores, labels, "kendall"),
        "structural_faithfulness_pearson": float(faithfulness.get("pearson", 0.0)),
        "mean_necessity": mean(necessity_values),
        "max_necessity": max(necessity_values) if necessity_values else 0.0,
        "redundancy_density": _edge_density(graphs),
        "bottleneck_count": _bottleneck_count(row_dicts),
        "reachable_ratio": mean([metric["reachable_ratio"] for metric in structural_metrics]),
        "bridge_node_fraction": mean(
            [metric["bridge_node_fraction"] for metric in structural_metrics]
        ),
        "influence_depth": mean([metric["influence_depth"] for metric in structural_metrics]),
        "n_graphs": len(graphs),
        "n_nodes": sum(len(graph.nodes) for graph in graphs),
        "n_edges": sum(len(graph.edges) for graph in graphs),
    }


def _phase5_score(
    necessity_records: Sequence[Mapping[str, Any]],
    trace_id: str,
    step_idx: int,
) -> float:
    for record in necessity_records:
        if str(record.get("trace_id")) == trace_id and int(record.get("step_idx", -1)) == step_idx:
            return float(record.get("attribution_score", record.get("necessity", 0.0)))
    return 0.0


def _edge_density(graphs: Sequence[ReflectionGraph]) -> float:
    values = []
    for graph in graphs:
        n = len(graph.nodes)
        possible = n * (n - 1) / 2
        values.append(float(len(graph.edges) / possible) if possible else 0.0)
    return mean(values)


def _bottleneck_count(rows: Sequence[Mapping[str, Any]]) -> int:
    if not rows:
        return 0
    values = [float(row.get("necessity", 0.0)) for row in rows]
    threshold = float(np.percentile(values, 75))
    return int(sum(value >= threshold and value > 0.0 for value in values))


def _render_markdown(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "# Graph Construction Ablation",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Evidence level: `{report['evidence_level']}`",
        f"- Zero API calls: `{report['zero_api_calls']}`",
        "",
        "| Variant | Spearman | Kendall | Faithfulness | Mean Necessity | Redundancy Density | Bottlenecks |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in report["variants"].items():
        lines.append(
            f"| `{name}` | {metrics['spearman']:.4f} | {metrics['kendall']:.4f} | "
            f"{metrics['structural_faithfulness_pearson']:.4f} | "
            f"{metrics['mean_necessity']:.4f} | {metrics['redundancy_density']:.4f} | "
            f"{metrics['bottleneck_count']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            str(report["interpretation_rule"]),
            "These results must not be described as external validation or production KBS evidence.",
        ]
    )
    return lines


if __name__ == "__main__":
    main()
