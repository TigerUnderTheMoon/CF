"""Topology-sensitive attribution over reflection DAGs."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from fma.graph.reflection_graph import RemovalMode, ReflectionEdge, ReflectionGraph


@dataclass(frozen=True)
class StructuralNodeNecessity:
    trace_id: str
    node_id: str
    step_idx: int
    taxonomy_label: str
    utility_score: float
    structural_influence: float
    necessity: float
    necessity_normalized: float
    removal_mode: str


@dataclass(frozen=True)
class StructuralEdgeNecessity:
    trace_id: str
    source: str
    target: str
    edge_type: str
    weight: float
    necessity: float
    necessity_normalized: float


@dataclass(frozen=True)
class StructuralSubgraphNecessity:
    trace_id: str
    subgraph_id: str
    node_ids: list[str]
    edge_count: int
    necessity: float
    necessity_normalized: float


def compute_structural_influence(
    graph: ReflectionGraph,
    lambda_propagation: float = 0.5,
    gamma_decay: float = 0.8,
) -> dict[str, float]:
    """Compute propagated influence for every node in a DAG."""
    if lambda_propagation < 0.0:
        raise ValueError("lambda_propagation must be non-negative.")
    if not 0.0 <= gamma_decay <= 1.0:
        raise ValueError("gamma_decay must be in [0, 1].")

    graph.topological_order()
    influence: dict[str, float] = {}
    for node_id in sorted(graph.nodes):
        node = graph.nodes[node_id]
        value = float(node.utility_score)
        distances = graph.shortest_distances_from(node_id)
        for descendant_id, distance in distances.items():
            if descendant_id == node_id:
                continue
            descendant = graph.nodes[descendant_id]
            value += lambda_propagation * (gamma_decay ** distance) * float(
                descendant.utility_score
            )
        influence[node_id] = float(value)

    for node_id, value in influence.items():
        graph.nodes[node_id].structural_influence = value
    return influence


def compute_graph_utility(
    graph: ReflectionGraph,
    lambda_propagation: float = 0.5,
    gamma_decay: float = 0.8,
) -> float:
    """Sum structural influence over nodes reachable from frozen sources."""
    influence = compute_structural_influence(graph, lambda_propagation, gamma_decay)
    reachable = graph.reachable_nodes()
    return float(sum(influence[node_id] for node_id in sorted(reachable)))


def compute_node_necessity(
    graph: ReflectionGraph,
    removal_mode: RemovalMode | str = RemovalMode.PRUNE,
    lambda_propagation: float = 0.5,
    gamma_decay: float = 0.8,
) -> list[StructuralNodeNecessity]:
    """Compute topology-sensitive node necessity for every node."""
    mode = removal_mode if isinstance(removal_mode, RemovalMode) else RemovalMode(str(removal_mode).upper())
    baseline = compute_graph_utility(graph, lambda_propagation, gamma_decay)
    baseline_influence = {
        node_id: graph.nodes[node_id].structural_influence for node_id in graph.nodes
    }
    rows: list[StructuralNodeNecessity] = []
    for node in graph.sorted_nodes():
        ablated = graph.remove_node(node.node_id, mode)
        ablated_utility = compute_graph_utility(ablated, lambda_propagation, gamma_decay)
        necessity = _necessity(baseline, ablated_utility)
        rows.append(
            StructuralNodeNecessity(
                trace_id=node.trace_id,
                node_id=node.node_id,
                step_idx=node.step_index,
                taxonomy_label=node.taxonomy_label,
                utility_score=float(node.utility_score),
                structural_influence=float(baseline_influence.get(node.node_id, 0.0)),
                necessity=necessity,
                necessity_normalized=_clamp(necessity, 0.0, 1.0),
                removal_mode=mode.value,
            )
        )
    return rows


def compute_edge_necessity(
    graph: ReflectionGraph,
    lambda_propagation: float = 0.5,
    gamma_decay: float = 0.8,
) -> list[StructuralEdgeNecessity]:
    """Compute topology-sensitive edge necessity for every edge."""
    baseline = compute_graph_utility(graph, lambda_propagation, gamma_decay)
    rows: list[StructuralEdgeNecessity] = []
    for edge in graph.sorted_edges():
        ablated = graph.remove_edge(edge.source, edge.target)
        ablated_utility = compute_graph_utility(ablated, lambda_propagation, gamma_decay)
        necessity = _necessity(baseline, ablated_utility)
        rows.append(
            StructuralEdgeNecessity(
                trace_id=graph.nodes[edge.source].trace_id,
                source=edge.source,
                target=edge.target,
                edge_type=edge.edge_type,
                weight=float(edge.weight),
                necessity=necessity,
                necessity_normalized=_clamp(necessity, 0.0, 1.0),
            )
        )
    return rows


def compute_subgraph_necessity(
    graph: ReflectionGraph,
    subgraphs: Sequence[Mapping[str, Any]] | None = None,
    lambda_propagation: float = 0.5,
    gamma_decay: float = 0.8,
) -> list[StructuralSubgraphNecessity]:
    """Compute necessity for deterministic local node sets."""
    baseline = compute_graph_utility(graph, lambda_propagation, gamma_decay)
    rows: list[StructuralSubgraphNecessity] = []
    for subgraph in subgraphs or default_subgraphs(graph):
        node_ids = sorted(str(node_id) for node_id in subgraph.get("node_ids", []) if str(node_id) in graph.nodes)
        if not node_ids:
            continue
        ablated = graph.copy()
        ablated._source_ids = graph._source_ids or tuple(graph.source_nodes())
        ablated._drop_nodes(set(node_ids))
        ablated_utility = compute_graph_utility(ablated, lambda_propagation, gamma_decay)
        necessity = _necessity(baseline, ablated_utility)
        rows.append(
            StructuralSubgraphNecessity(
                trace_id=graph.graph_id,
                subgraph_id=str(subgraph.get("subgraph_id") or _subgraph_id(graph.graph_id, node_ids)),
                node_ids=node_ids,
                edge_count=sum(
                    1
                    for edge in graph.sorted_edges()
                    if edge.source in node_ids and edge.target in node_ids
                ),
                necessity=necessity,
                necessity_normalized=_clamp(necessity, 0.0, 1.0),
            )
        )
    return rows


def default_subgraphs(graph: ReflectionGraph, max_size: int = 3) -> list[dict[str, Any]]:
    """Enumerate small local subgraphs without generic graph isomorphism."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for node_id in graph.topological_order():
        children = graph.children(node_id)
        if children:
            nodes = tuple(sorted([node_id, *children[: max_size - 1]]))
        else:
            nodes = (node_id,)
        if nodes in seen:
            continue
        seen.add(nodes)
        rows.append({"subgraph_id": _subgraph_id(graph.graph_id, nodes), "node_ids": list(nodes)})
    return rows


def compute_structural_faithfulness(
    node_necessity: Sequence[StructuralNodeNecessity | Mapping[str, Any]],
    phase5_scores: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Correlate Phase 5 attribution scores with structural node necessity."""
    attribution_by_key = {
        (str(record.get("trace_id")), int(record.get("step_idx"))): float(
            record.get("attribution_score", 0.0)
        )
        for record in phase5_scores
        if "trace_id" in record and "step_idx" in record
    }
    attribution: list[float] = []
    necessity: list[float] = []
    for row in node_necessity:
        trace_id = str(_field(row, "trace_id"))
        step_idx = int(_field(row, "step_idx"))
        key = (trace_id, step_idx)
        if key not in attribution_by_key:
            continue
        attribution.append(attribution_by_key[key])
        necessity.append(float(_field(row, "necessity")))

    return {
        "pearson": _pearson(attribution, necessity),
        "num_samples": len(necessity),
        "mean_structural_node_necessity": _mean(necessity),
        "mean_phase5_attribution_score": _mean(attribution),
    }


def compute_structural_metrics(graph: ReflectionGraph) -> dict[str, float]:
    """Compute aggregate topology-sensitive graph metrics."""
    influence = compute_structural_influence(graph)
    reachable = graph.reachable_nodes()
    descendant_distances: list[float] = []
    descendant_weights: list[float] = []
    for node_id in sorted(graph.nodes):
        distances = graph.shortest_distances_from(node_id)
        for descendant_id, distance in distances.items():
            if descendant_id == node_id:
                continue
            weight = abs(float(graph.nodes[descendant_id].utility_score))
            descendant_distances.append(float(distance))
            descendant_weights.append(weight)

    return {
        "structural_influence_mean": _mean(list(influence.values())),
        "reachable_ratio": float(len(reachable) / len(graph.nodes)) if graph.nodes else 0.0,
        "influence_depth": _weighted_mean(descendant_distances, descendant_weights),
        "bridge_node_fraction": _bridge_node_fraction(graph),
    }


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def _bridge_node_fraction(graph: ReflectionGraph) -> float:
    if not graph.nodes:
        return 0.0
    before = graph.reachable_nodes()
    bridge_count = 0
    for node_id in sorted(graph.nodes):
        if not graph.children(node_id):
            continue
        ablated = graph.remove_node(node_id, RemovalMode.PRUNE)
        after = ablated.reachable_nodes()
        lost = (before - {node_id}) - after
        if lost:
            bridge_count += 1
    return float(bridge_count / len(graph.nodes))


def _necessity(baseline: float, ablated: float) -> float:
    if baseline == 0.0:
        return 0.0
    value = (baseline - ablated) / baseline
    return float(value) if math.isfinite(value) else 0.0


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    if float(np.std(left_array)) == 0.0 or float(np.std(right_array)) == 0.0:
        return 0.0
    value = float(np.corrcoef(left_array, right_array)[0, 1])
    return value if math.isfinite(value) else 0.0


def _field(row: Any, name: str) -> Any:
    if isinstance(row, Mapping):
        return row[name]
    return getattr(row, name)


def _weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    if not values:
        return 0.0
    total_weight = float(sum(weights))
    if total_weight == 0.0:
        return float(np.mean(values))
    return float(sum(value * weight for value, weight in zip(values, weights)) / total_weight)


def _mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, float(value)))


def _subgraph_id(graph_id: str, node_ids: Iterable[str]) -> str:
    suffix = "__".join(node_id.rsplit("::", 1)[-1] for node_id in node_ids)
    return f"{graph_id}::{suffix}"


__all__ = [
    "StructuralEdgeNecessity",
    "StructuralNodeNecessity",
    "StructuralSubgraphNecessity",
    "compute_edge_necessity",
    "compute_graph_utility",
    "compute_node_necessity",
    "compute_structural_faithfulness",
    "compute_structural_influence",
    "compute_structural_metrics",
    "compute_subgraph_necessity",
    "dataclass_to_dict",
    "default_subgraphs",
]
