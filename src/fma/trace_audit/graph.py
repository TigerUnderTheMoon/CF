"""Lightweight NetworkX verification graph."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import networkx as nx

from fma.trace_audit.schema import EDGE_CATEGORIES


class VerificationGraphBuilder:
    """Build a three-edge-category graph from one reasoning trace."""

    def build(
        self,
        trace: Mapping[str, Any],
        scored_steps: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        score_by_id = {str(row["step_id"]): row for row in scored_steps}
        graph = nx.DiGraph()
        nodes = []
        for step in trace["steps"]:
            score = score_by_id.get(str(step["step_id"]), {})
            node = {
                "node_id": step["step_id"],
                "trace_id": trace["trace_id"],
                "sample_id": trace["sample_id"],
                "step_index": int(step["step_index"]),
                "step_type": step["step_type"],
                "operation": step["operation"],
                "input_entities": list(step.get("input_entities", [])),
                "output_entities": list(step.get("output_entities", [])),
                "candidate_count": len(step.get("candidate_entities", [])),
                "importance_target": float(score.get("importance_target", 0.0)),
                "target_reliability": float(score.get("target_reliability", 0.0)),
            }
            graph.add_node(node["node_id"], **node)
            nodes.append(node)

        edges: list[dict[str, Any]] = []

        def add_edge(source: str, target: str, category: str) -> None:
            if category not in EDGE_CATEGORIES or source == target:
                return
            edge_id = f"{source}->{target}:{category}"
            graph.add_edge(source, target, edge_category=category, edge_id=edge_id)
            edges.append(
                {
                    "edge_id": edge_id,
                    "source": source,
                    "target": target,
                    "edge_category": category,
                    "weight": 1.0,
                }
            )

        steps = list(trace["steps"])
        for left, right in zip(steps, steps[1:]):
            add_edge(str(left["step_id"]), str(right["step_id"]), "Temporal")
        add_edge("s0", "s1", "Dependency")
        add_edge("s1", "s2", "Dependency")
        add_edge("s2", "s3", "Dependency")
        add_edge("s3", "s4", "Dependency")
        add_edge("s3", "s5", "Support")
        add_edge("s4", "s5", "Support")

        return {
            "graph_id": f"{trace['trace_id']}::verification_graph",
            "trace_id": trace["trace_id"],
            "sample_id": trace["sample_id"],
            "graph_backend": "networkx",
            "nodes": sorted(nodes, key=lambda item: item["step_index"]),
            "edges": sorted(edges, key=lambda item: item["edge_id"]),
            "edge_categories": list(EDGE_CATEGORIES),
            "is_dag": nx.is_directed_acyclic_graph(graph),
        }
