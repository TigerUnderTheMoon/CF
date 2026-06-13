"""Diagnostic ontology-aware edge construction pilot for KBS positioning.

This module deliberately does not integrate a rule engine, ontology reasoner,
knowledge-graph query engine, or deployed KBS workflow. It maps small fixture
metadata to the existing functional edge types accepted by ``ReflectionGraph``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from fma.eval.diagnostics.correlation_metrics import spearman, top_k_overlap
from fma.eval.structural_attribution import compute_node_necessity
from fma.graph.build_reflection_graph import build_reflection_graphs, node_id_for
from fma.graph.reflection_graph import ReflectionGraph, ReflectionNode
from fma.io import load_records

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "kbs_ontology_edge_pilot"
DEFAULT_OUTPUT_JSON = DEFAULT_OUTPUT_DIR / "diagnostic_report.json"
DEFAULT_OUTPUT_MD = DEFAULT_OUTPUT_DIR / "diagnostic_report.md"

DEFAULT_FIXTURE_TRACES: tuple[dict[str, Any], ...] = (
    {
        "trace_id": "kbs_toy_medical",
        "domain": "toy_medical",
        "reflection_chain": [
            {
                "category": "DECOMPOSITION",
                "text": "Identify the patient safety constraint before checking therapy options.",
                "concept_id": "patient_case",
                "constraint_id": "drug_safety",
                "operation_type": "decompose",
                "utility_score": 0.20,
            },
            {
                "category": "VERIFICATION",
                "text": "Check the allergy constraint for the candidate medication.",
                "concept_id": "allergy",
                "constraint_id": "drug_safety",
                "operation_type": "verify",
                "depends_on_concept_ids": ["patient_case"],
                "utility_score": 0.80,
            },
            {
                "category": "ERROR_CORRECTION",
                "text": "Correct the recommendation because the medication conflicts with safety constraints.",
                "concept_id": "medication",
                "constraint_id": "drug_safety",
                "operation_type": "correct",
                "depends_on_concept_ids": ["allergy"],
                "contradicts_constraint_id": "drug_safety",
                "utility_score": 0.90,
            },
            {
                "category": "VERIFICATION",
                "text": "Validate the final recommendation against the same drug safety constraint.",
                "concept_id": "recommendation",
                "constraint_id": "drug_safety",
                "operation_type": "verify",
                "depends_on_concept_ids": ["medication"],
                "utility_score": 0.70,
            },
        ],
    },
    {
        "trace_id": "kbs_toy_finance",
        "domain": "toy_finance",
        "reflection_chain": [
            {
                "category": "DECOMPOSITION",
                "text": "Separate exposure, collateral, and covenant checks before scoring risk.",
                "concept_id": "loan_case",
                "constraint_id": "credit_risk",
                "operation_type": "decompose",
                "utility_score": 0.30,
            },
            {
                "category": "VERIFICATION",
                "text": "Verify collateral coverage under the credit risk constraint.",
                "concept_id": "collateral",
                "constraint_id": "credit_risk",
                "operation_type": "verify",
                "depends_on_concept_ids": ["loan_case"],
                "utility_score": 0.75,
            },
            {
                "category": "PLANNING",
                "text": "Revise the risk plan after covenant and collateral checks.",
                "concept_id": "risk_plan",
                "constraint_id": "credit_risk",
                "operation_type": "revise",
                "depends_on_concept_ids": ["collateral"],
                "utility_score": 0.60,
            },
            {
                "category": "VERIFICATION",
                "text": "Validate the final risk decision under the same credit risk constraint.",
                "concept_id": "risk_decision",
                "constraint_id": "credit_risk",
                "operation_type": "verify",
                "depends_on_concept_ids": ["risk_plan"],
                "utility_score": 0.65,
            },
        ],
    },
)

OPERATION_EDGE_TYPES: dict[str, str] = {
    "verify": "verifies",
    "decompose": "decomposes",
    "correct": "corrects",
    "revise": "revises",
    "plan": "revises",
    "critique": "critiques",
    "retry": "retries",
    "summarize": "summarizes",
}


def build_ontology_edge_graph(
    trace: Mapping[str, Any],
    index: int = 0,
) -> tuple[ReflectionGraph, list[dict[str, Any]]]:
    """Build a temporal graph augmented with fixture-level ontology edges."""
    trace_id = _trace_id(trace, index)
    steps = _reflection_steps(trace)
    graph = ReflectionGraph(trace_id)
    node_ids: list[str] = []

    for step_index, step in enumerate(steps):
        node_id = node_id_for(trace_id, step_index)
        graph.add_node(
            ReflectionNode(
                node_id=node_id,
                trace_id=trace_id,
                step_index=step_index,
                taxonomy_label=_taxonomy_label(step),
                utility_score=_utility_score(step),
                structural_influence=0.0,
                content=_step_content(step),
            )
        )
        node_ids.append(node_id)

    for position in range(len(node_ids) - 1):
        graph.add_edge(
            node_ids[position],
            node_ids[position + 1],
            _functional_edge_type(steps[position + 1]),
            weight=1.0,
            quality=1.0,
        )

    ontology_edges: list[dict[str, Any]] = []
    for left_index, left_step in enumerate(steps):
        for right_index in range(left_index + 1, len(steps)):
            right_step = steps[right_index]
            relation = _ontology_relation(left_step, right_step)
            if relation is None:
                continue
            edge_type = _functional_edge_type(right_step, relation=relation)
            source = node_ids[left_index]
            target = node_ids[right_index]
            added = False
            if not graph.has_edge(source, target):
                graph.add_edge(source, target, edge_type, weight=0.9, quality=1.0)
                added = True
            ontology_edges.append(
                {
                    "trace_id": trace_id,
                    "source_step_idx": left_index,
                    "target_step_idx": right_index,
                    "source_concept_id": _string_field(left_step, "concept_id"),
                    "target_concept_id": _string_field(right_step, "concept_id"),
                    "constraint_id": _string_field(right_step, "constraint_id"),
                    "ontology_relation": relation,
                    "edge_type": edge_type,
                    "added_to_graph": added,
                }
            )

    if node_ids:
        graph.freeze_sources([node_ids[0]])
    return graph, ontology_edges


def run_ontology_edge_pilot(
    *,
    traces: Sequence[Mapping[str, Any]] | None = None,
    output_json: str | Path = DEFAULT_OUTPUT_JSON,
    output_md: str | Path = DEFAULT_OUTPUT_MD,
) -> dict[str, Any]:
    """Run the fixture-level ontology-edge diagnostic and write artifacts."""
    selected_traces = [dict(trace) for trace in (traces or DEFAULT_FIXTURE_TRACES)]
    baseline_graphs = build_reflection_graphs(
        selected_traces,
        similarity_method="tfidf",
        similarity_threshold=0.15,
    )

    ontology_graphs: list[ReflectionGraph] = []
    ontology_edges: list[dict[str, Any]] = []
    for index, trace in enumerate(selected_traces):
        graph, edges = build_ontology_edge_graph(trace, index=index)
        ontology_graphs.append(graph)
        ontology_edges.extend(edges)

    comparison = _compare_graph_sets(baseline_graphs, ontology_graphs)
    report: dict[str, Any] = {
        "evidence_level": "diagnostic",
        "validated_kbs_workflow": False,
        "claim_boundary": (
            "Fixture-level ontology-aware edge construction pilot only; not a deployed "
            "KBS validation and not evidence for rule-engine, ontology-reasoner, "
            "KG-query, PRM-training, replay, or downstream-filtering claims."
        ),
        "integration_scope": {
            "uses_real_ontology": False,
            "uses_rule_engine": False,
            "uses_ontology_reasoner": False,
            "uses_kg_query_engine": False,
            "uses_deployed_kbs_workflow": False,
            "uses_prm_training": False,
            "uses_gsm8k_hotpotqa_replay": False,
        },
        "summary": {
            "num_traces": len(selected_traces),
            "baseline_edge_count": sum(len(graph.edges) for graph in baseline_graphs),
            "ontology_graph_edge_count": sum(len(graph.edges) for graph in ontology_graphs),
            "ontology_candidate_edge_count": len(ontology_edges),
            "ontology_added_edge_count": sum(
                1 for edge in ontology_edges if edge["added_to_graph"]
            ),
            "ontology_relation_counts": dict(
                sorted(Counter(edge["ontology_relation"] for edge in ontology_edges).items())
            ),
            "functional_edge_type_counts": dict(
                sorted(Counter(edge["edge_type"] for edge in ontology_edges).items())
            ),
        },
        "comparison": comparison,
        "ontology_edges": ontology_edges,
    }
    _write_json(Path(output_json), report)
    write_markdown(Path(output_md), report)
    return report


def write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    """Write a claim-safe Markdown summary for the pilot report."""
    summary = report["summary"]
    comparison = report["comparison"]
    lines = [
        "# KBS Ontology-Aware Edge Pilot",
        "",
        "This is a deterministic fixture-level diagnostic, not a deployed KBS validation.",
        "",
        "validated_kbs_workflow: false",
        f"evidence_level: {report['evidence_level']}",
        "",
        "## Scope Boundary",
        "",
        str(report["claim_boundary"]),
        "",
        "## Edge Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Traces | {summary['num_traces']} |",
        f"| Baseline TF-IDF/topical edges | {summary['baseline_edge_count']} |",
        f"| Ontology-aware graph edges | {summary['ontology_graph_edge_count']} |",
        f"| Ontology candidate edges | {summary['ontology_candidate_edge_count']} |",
        f"| Ontology-added edges | {summary['ontology_added_edge_count']} |",
        "",
        "## Structural Comparison",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| All ontology graphs are DAGs | {comparison['all_ontology_graphs_are_dags']} |",
        f"| Mean abs structural necessity delta | {comparison['mean_abs_structural_necessity_delta']:.6f} |",
        f"| Necessity Spearman | {comparison['structural_necessity_spearman']:.6f} |",
        f"| Bottleneck top-1 overlap | {comparison['bottleneck_top1_overlap']:.6f} |",
        "",
        "## Interpretation",
        "",
        "- Ontology relations are recorded as diagnostic metadata and mapped to existing SC-FMA functional edge types.",
        "- The graph API is unchanged: ontology relation labels such as `is_a` or `part_of` are not added as core edge types.",
        "- This artifact demonstrates edge-construction interface feasibility only.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixture-level ontology-aware edge diagnostic pilot.",
    )
    parser.add_argument("--traces", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    traces = load_records(args.traces) if args.traces else None
    report = run_ontology_edge_pilot(
        traces=traces,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def _compare_graph_sets(
    baseline_graphs: Sequence[ReflectionGraph],
    ontology_graphs: Sequence[ReflectionGraph],
) -> dict[str, Any]:
    baseline_scores = _node_necessity_by_key(baseline_graphs)
    ontology_scores = _node_necessity_by_key(ontology_graphs)
    keys = sorted(set(baseline_scores) & set(ontology_scores))
    baseline_values = [baseline_scores[key] for key in keys]
    ontology_values = [ontology_scores[key] for key in keys]
    deltas = [
        abs(ontology_scores[key] - baseline_scores[key])
        for key in keys
    ]
    return {
        "matched_node_count": len(keys),
        "all_ontology_graphs_are_dags": all(_is_dag(graph) for graph in ontology_graphs),
        "mean_abs_structural_necessity_delta": (
            float(sum(deltas) / len(deltas)) if deltas else 0.0
        ),
        "structural_necessity_spearman": spearman(baseline_values, ontology_values),
        "bottleneck_top1_overlap": top_k_overlap(
            baseline_values,
            ontology_values,
            1,
            keys=keys,
        )
        if keys
        else 0.0,
    }


def _node_necessity_by_key(
    graphs: Sequence[ReflectionGraph],
) -> dict[tuple[str, int], float]:
    rows: dict[tuple[str, int], float] = {}
    for graph in graphs:
        for row in compute_node_necessity(graph):
            rows[(row.trace_id, row.step_idx)] = float(row.necessity_normalized)
    return rows


def _is_dag(graph: ReflectionGraph) -> bool:
    try:
        graph.topological_order()
    except ValueError:
        return False
    return True


def _trace_id(trace: Mapping[str, Any], index: int) -> str:
    return str(
        trace.get("trace_id")
        or trace.get("sample_id")
        or trace.get("task_id")
        or f"ontology_trace_{index:05d}"
    )


def _reflection_steps(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    chain = trace.get("reflection_chain")
    if isinstance(chain, list):
        return [dict(step) for step in chain if isinstance(step, Mapping)]
    return []


def _taxonomy_label(step: Mapping[str, Any]) -> str:
    label = step.get("category") or step.get("reflection_type") or step.get("type") or "OTHER"
    return str(label).strip().upper().replace("-", "_") or "OTHER"


def _step_content(step: Mapping[str, Any]) -> str:
    return str(step.get("text") or step.get("content") or "").strip()


def _utility_score(step: Mapping[str, Any]) -> float:
    return float(step.get("utility_score", 0.0))


def _ontology_relation(
    left_step: Mapping[str, Any],
    right_step: Mapping[str, Any],
) -> str | None:
    left_constraint = _string_field(left_step, "constraint_id")
    right_constraint = _string_field(right_step, "constraint_id")
    if right_step.get("contradicts_constraint_id") == left_constraint and left_constraint:
        return "contradicts_constraint"
    if _string_field(left_step, "concept_id") in _string_list(
        right_step.get("depends_on_concept_ids")
    ):
        return "depends_on_concept"
    if left_constraint and left_constraint == right_constraint:
        return "same_constraint"
    if _string_field(left_step, "concept_id") == _string_field(right_step, "concept_id"):
        return "same_concept"
    return None


def _functional_edge_type(step: Mapping[str, Any], relation: str | None = None) -> str:
    if relation == "contradicts_constraint":
        return "corrects"
    operation = str(step.get("operation_type") or "").strip().lower()
    if operation in OPERATION_EDGE_TYPES:
        return OPERATION_EDGE_TYPES[operation]
    label = _taxonomy_label(step)
    if "ERROR" in label or "CORRECTION" in label:
        return "corrects"
    if "VERIFICATION" in label or "CONSTRAINT" in label:
        return "verifies"
    if "DECOMPOSITION" in label:
        return "decomposes"
    if "PLANNING" in label:
        return "revises"
    return "elaborates"


def _string_field(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    return str(value).strip() if value is not None else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "DEFAULT_FIXTURE_TRACES",
    "DEFAULT_OUTPUT_JSON",
    "DEFAULT_OUTPUT_MD",
    "DEFAULT_OUTPUT_DIR",
    "build_ontology_edge_graph",
    "main",
    "parse_args",
    "run_ontology_edge_pilot",
    "write_markdown",
]


if __name__ == "__main__":
    main()
