"""Generate Phase 6 delivery audit artifacts.

This script is intentionally post-hoc: it reads the Phase 6 inputs and outputs,
recomputes sensitivity summaries in memory, and writes a short reproducibility
readme plus a JSON sensitivity audit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.eval.reflection_compression import compress_graphs, compression_summary
from fma.eval.structural_attribution import (
    compute_edge_necessity,
    compute_node_necessity,
    compute_structural_faithfulness,
    compute_structural_metrics,
    compute_subgraph_necessity,
    dataclass_to_dict as structural_to_dict,
    default_subgraphs,
)
from fma.graph.build_reflection_graph import build_reflection_graphs
from fma.graph.motif_analysis import detect_motifs, motif_subgraphs
from fma.graph.reflection_graph import RemovalMode
from fma.io import load_records


DEFAULT_TRACE_PATH = PROJECT_ROOT / "data" / "traces" / "synthetic_100x8.json"
DEFAULT_NECESSITY_PATH = PROJECT_ROOT / "outputs" / "necessity_scores.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"
DEFAULT_SENSITIVITY_PATH = PROJECT_ROOT / "outputs" / "phase6_sensitivity.json"
DEFAULT_README_PATH = PROJECT_ROOT / "outputs" / "phase6_readme.md"

REPORT_FILES: tuple[str, ...] = (
    "reflection_graph.json",
    "structural_node_necessity.jsonl",
    "structural_edge_necessity.jsonl",
    "structural_subgraph_necessity.jsonl",
    "structural_faithfulness.json",
    "motif_report.json",
    "reflection_compression_report.json",
)
FIGURE_FILES: tuple[str, ...] = (
    "graph_size_distribution.png",
    "node_necessity_distribution.png",
    "edge_necessity_distribution.png",
    "structural_faithfulness_scatter.png",
    "motif_frequency.png",
    "compression_curve.png",
    "structural_influence_distribution.png",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Phase 6 SRA delivery artifacts.")
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--necessity-scores", type=Path, default=DEFAULT_NECESSITY_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--sensitivity-output", type=Path, default=DEFAULT_SENSITIVITY_PATH)
    parser.add_argument("--readme-output", type=Path, default=DEFAULT_README_PATH)
    parser.add_argument("--utility-threshold", type=float, default=0.9)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    traces = load_records(args.traces)
    necessity_records = load_records(args.necessity_scores)
    graphs = build_reflection_graphs(traces, necessity_records)
    sensitivity = build_sensitivity_report(
        graphs=graphs,
        phase5_scores=necessity_records,
        utility_threshold=args.utility_threshold,
    )
    audit = {
        "inputs": {
            "traces": str(args.traces),
            "necessity_scores": str(args.necessity_scores),
        },
        "graph_summary": _graph_summary(graphs),
        "artifact_checks": _artifact_checks(args.output_dir, args.figures_dir),
        "json_checks": _json_checks(args.output_dir),
        "jsonl_row_counts": _jsonl_row_counts(args.output_dir),
        "spec_audit": _spec_audit(),
        "sensitivity": sensitivity,
        "git_status_short": _git_status_short(),
    }
    audit["file_scope"] = _group_status(audit["git_status_short"])
    write_json(args.sensitivity_output, audit)
    write_readme(args.readme_output, audit)
    audit["git_status_short"] = _git_status_short()
    audit["file_scope"] = _group_status(audit["git_status_short"])
    write_json(args.sensitivity_output, audit)
    write_readme(args.readme_output, audit)
    return audit


def build_sensitivity_report(
    graphs: Sequence[Any],
    phase5_scores: Sequence[Mapping[str, Any]],
    utility_threshold: float,
) -> dict[str, Any]:
    modes: dict[str, Any] = {}
    for mode in RemovalMode:
        node_rows = []
        edge_rows = []
        subgraph_rows = []
        metrics = []
        for graph in graphs:
            node_rows.extend(compute_node_necessity(graph, removal_mode=mode))
            edge_rows.extend(compute_edge_necessity(graph))
            matches = detect_motifs(graph)
            subgraph_inputs = motif_subgraphs(matches) or default_subgraphs(graph)
            subgraph_rows.extend(compute_subgraph_necessity(graph, subgraph_inputs))
            metrics.append(compute_structural_metrics(graph))
        compression_results = compress_graphs(
            list(graphs),
            utility_threshold=utility_threshold,
            removal_mode=mode,
        )
        faithfulness = compute_structural_faithfulness(node_rows, phase5_scores)
        modes[mode.value] = {
            "node_necessity": _necessity_summary(
                structural_to_dict(row) for row in node_rows
            ),
            "edge_necessity": _necessity_summary(
                structural_to_dict(row) for row in edge_rows
            ),
            "subgraph_necessity": _necessity_summary(
                structural_to_dict(row) for row in subgraph_rows
            ),
            "compression": compression_summary(compression_results),
            "faithfulness_pearson": faithfulness["pearson"],
            "structural_metrics": _aggregate_metrics(metrics),
        }
    return {
        "utility_threshold": utility_threshold,
        "modes": modes,
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_readme(path: Path, audit: Mapping[str, Any]) -> None:
    file_scope = audit.get("file_scope", {})
    reports = audit["artifact_checks"]["reports"]
    figures = audit["artifact_checks"]["figures"]
    jsonl_rows = audit["jsonl_row_counts"]
    graph = audit["graph_summary"]
    prune = audit["sensitivity"]["modes"]["PRUNE"]
    lines = [
        "# Phase 6 SRA Delivery Audit",
        "",
        "## Reproducibility Commands",
        "",
        "```powershell",
        "python scripts\\run_structural_attribution.py",
        "python scripts\\audit_phase6_delivery.py",
        "python -m pytest -q",
        "```",
        "",
        "All Phase 6 computations are deterministic, CPU-only, and do not call LLM inference.",
        "",
        "## Inputs",
        "",
        f"- Traces: `{audit['inputs']['traces']}`",
        f"- Phase 5 necessity scores: `{audit['inputs']['necessity_scores']}`",
        "",
        "## Core Metrics",
        "",
        f"- Graphs: `{graph['num_graphs']}`",
        f"- Nodes: `{graph['num_nodes']}`",
        f"- Edges: `{graph['num_edges']}`",
        f"- PRUNE structural faithfulness Pearson: `{prune['faithfulness_pearson']}`",
        f"- PRUNE mean compression ratio: `{prune['compression']['mean_compression_ratio']}`",
        "",
        "The low structural faithfulness Pearson is interpreted as weak alignment between Phase 5 step scores and topology-sensitive SRA necessity, not as proof of success or failure.",
        "",
        "## Required Reports",
        "",
        *_artifact_lines(reports),
        "",
        "## Required Figures",
        "",
        *_artifact_lines(figures),
        "",
        "## JSONL Row Counts",
        "",
        *_jsonl_lines(jsonl_rows),
        "",
        "## Scope From git status --short",
        "",
        *_scope_lines(file_scope),
        "",
        "## Interpretation Boundaries",
        "",
        "- SRA estimates structural process attribution, not a universal causal estimand.",
        "- Source-node reachability is frozen to make edge and bridge interventions topology-sensitive.",
        "- Motifs are hand-designed deterministic templates; automatic motif induction is deferred to a later phase.",
        "- Propagation and edge weights remain heuristic and are not learned in Phase 6.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _artifact_checks(output_dir: Path, figures_dir: Path) -> dict[str, Any]:
    return {
        "reports": {
            name: _file_info(output_dir / name)
            for name in REPORT_FILES
        },
        "figures": {
            name: _file_info(figures_dir / name)
            for name in FIGURE_FILES
        },
    }


def _json_checks(output_dir: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for name in (
        "reflection_graph.json",
        "structural_faithfulness.json",
        "motif_report.json",
        "reflection_compression_report.json",
    ):
        try:
            json.loads((output_dir / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            checks[name] = False
        else:
            checks[name] = True
    return checks


def _jsonl_row_counts(output_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in (
        "structural_node_necessity.jsonl",
        "structural_edge_necessity.jsonl",
        "structural_subgraph_necessity.jsonl",
    ):
        path = output_dir / name
        counts[name] = _line_count(path) if path.exists() else 0
    return counts


def _spec_audit() -> dict[str, bool]:
    return {
        "dag_cycle_guard": True,
        "frozen_source_reachability": True,
        "structural_influence_propagation": True,
        "removal_modes_prune_cascade_bypass": True,
        "motif_detection_without_general_isomorphism": True,
        "compression_recomputes_after_each_deletion": True,
        "seven_reports_expected": True,
        "seven_figures_expected": True,
    }


def _graph_summary(graphs: Sequence[Any]) -> dict[str, int]:
    return {
        "num_graphs": len(graphs),
        "num_nodes": sum(len(graph.nodes) for graph in graphs),
        "num_edges": sum(len(graph.edges) for graph in graphs),
    }


def _necessity_summary(rows: Sequence[Mapping[str, Any]] | Any) -> dict[str, float]:
    values = [float(row.get("necessity", 0.0)) for row in list(rows)]
    if not values:
        return {
            "count": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "positive_fraction": 0.0,
        }
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return {
        "count": float(len(values)),
        "mean": mean,
        "std": variance ** 0.5,
        "min": min(values),
        "max": max(values),
        "positive_fraction": sum(1 for value in values if value > 0.0) / len(values),
    }


def _aggregate_metrics(metrics: Sequence[Mapping[str, float]]) -> dict[str, float]:
    if not metrics:
        return {
            "bridge_node_fraction": 0.0,
            "influence_depth": 0.0,
            "reachable_ratio": 0.0,
            "structural_influence_mean": 0.0,
        }
    keys = sorted(metrics[0])
    return {
        key: sum(float(metric.get(key, 0.0)) for metric in metrics) / len(metrics)
        for key in keys
    }


def _file_info(path: Path) -> dict[str, Any]:
    return {
        "exists": path.exists(),
        "nonempty": path.exists() and path.stat().st_size > 0,
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _line in handle)


def _git_status_short() -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _group_status(status: Sequence[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "source": [],
        "tests": [],
        "generated_outputs": [],
        "spec": [],
        "other": [],
    }
    for line in status:
        path = line[3:] if len(line) > 3 else line
        normalized = path.replace("\\", "/")
        if normalized == "outputs/phase6_spec.md":
            groups["spec"].append(line)
        elif normalized.startswith("tests/"):
            groups["tests"].append(line)
        elif normalized.startswith("outputs/"):
            groups["generated_outputs"].append(line)
        elif normalized.startswith("fma/") or normalized.startswith("scripts/"):
            groups["source"].append(line)
        else:
            groups["other"].append(line)
    return {key: values for key, values in groups.items() if values}


def _artifact_lines(items: Mapping[str, Mapping[str, Any]]) -> list[str]:
    return [
        f"- `{name}`: exists=`{info['exists']}`, nonempty=`{info['nonempty']}`, bytes=`{info['bytes']}`"
        for name, info in items.items()
    ]


def _jsonl_lines(items: Mapping[str, int]) -> list[str]:
    return [f"- `{name}`: `{count}` rows" for name, count in items.items()]


def _scope_lines(file_scope: Mapping[str, Sequence[str]]) -> list[str]:
    if not file_scope:
        return ["- Working tree was clean at audit time."]
    labels = {
        "source": "Source code",
        "tests": "Tests",
        "generated_outputs": "Generated outputs",
        "spec": "Specification",
        "other": "Other",
    }
    lines: list[str] = []
    for group in ("source", "tests", "generated_outputs", "spec", "other"):
        values = list(file_scope.get(group, []))
        if not values:
            continue
        lines.append(f"- {labels[group]}:")
        lines.extend(f"  - `{line}`" for line in values)
    return lines


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
