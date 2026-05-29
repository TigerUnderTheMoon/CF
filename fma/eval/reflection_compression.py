"""Greedy topology-sensitive reflection graph compression."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from fma.eval.structural_attribution import compute_graph_utility, compute_node_necessity
from fma.graph.reflection_graph import RemovalMode, ReflectionGraph


@dataclass(frozen=True)
class CompressionStep:
    trace_id: str
    iteration: int
    removed_node_id: str | None
    retained_node_count: int
    utility_ratio: float
    accepted: bool


@dataclass(frozen=True)
class CompressionResult:
    trace_id: str
    original_node_count: int
    retained_node_count: int
    compression_ratio: float
    removed_node_ids: list[str]
    retained_node_ids: list[str]
    utility_retained: float
    utility_threshold: float
    curve: list[dict[str, Any]]


def compute_subgraph_utility_ratio(
    graph: ReflectionGraph,
    original_graph: ReflectionGraph,
    lambda_propagation: float = 0.5,
    gamma_decay: float = 0.8,
) -> float:
    """Return reachable structural utility retained by ``graph``."""
    original_utility = compute_graph_utility(original_graph, lambda_propagation, gamma_decay)
    current_utility = compute_graph_utility(graph, lambda_propagation, gamma_decay)
    if original_utility <= 0.0:
        return 1.0 if current_utility >= 0.0 else 0.0
    return float(current_utility / original_utility)


def compress_reflection_graph(
    graph: ReflectionGraph,
    utility_threshold: float = 0.9,
    removal_mode: RemovalMode | str = RemovalMode.PRUNE,
    lambda_propagation: float = 0.5,
    gamma_decay: float = 0.8,
) -> CompressionResult:
    """Greedily delete the lowest-necessity node while utility is preserved."""
    if not 0.0 <= utility_threshold <= 1.0:
        raise ValueError("utility_threshold must be in [0, 1].")

    mode = removal_mode if isinstance(removal_mode, RemovalMode) else RemovalMode(str(removal_mode).upper())
    original = graph.copy()
    current = graph.copy()
    original_count = len(original.nodes)
    removed: list[str] = []
    curve: list[dict[str, Any]] = [
        asdict(
            CompressionStep(
                trace_id=graph.graph_id,
                iteration=0,
                removed_node_id=None,
                retained_node_count=len(current.nodes),
                utility_ratio=compute_subgraph_utility_ratio(
                    current,
                    original,
                    lambda_propagation,
                    gamma_decay,
                ),
                accepted=True,
            )
        )
    ]

    iteration = 0
    while len(current.nodes) > 1:
        necessities = compute_node_necessity(
            current,
            removal_mode=mode,
            lambda_propagation=lambda_propagation,
            gamma_decay=gamma_decay,
        )
        if not necessities:
            break
        candidate = min(
            necessities,
            key=lambda row: (
                row.necessity,
                row.utility_score,
                row.step_idx,
                row.node_id,
            ),
        )
        proposed = current.remove_node(candidate.node_id, mode)
        ratio = compute_subgraph_utility_ratio(
            proposed,
            original,
            lambda_propagation,
            gamma_decay,
        )
        if ratio < utility_threshold:
            break
        iteration += 1
        current = proposed
        removed.append(candidate.node_id)
        curve.append(
            asdict(
                CompressionStep(
                    trace_id=graph.graph_id,
                    iteration=iteration,
                    removed_node_id=candidate.node_id,
                    retained_node_count=len(current.nodes),
                    utility_ratio=ratio,
                    accepted=True,
                )
            )
        )

    retained = sorted(current.nodes)
    utility_retained = compute_subgraph_utility_ratio(
        current,
        original,
        lambda_propagation,
        gamma_decay,
    )
    return CompressionResult(
        trace_id=graph.graph_id,
        original_node_count=original_count,
        retained_node_count=len(retained),
        compression_ratio=1.0 - (len(retained) / original_count) if original_count else 0.0,
        removed_node_ids=removed,
        retained_node_ids=retained,
        utility_retained=utility_retained,
        utility_threshold=utility_threshold,
        curve=curve,
    )


def compress_graphs(
    graphs: list[ReflectionGraph],
    utility_threshold: float = 0.9,
    removal_mode: RemovalMode | str = RemovalMode.PRUNE,
) -> list[CompressionResult]:
    """Compress a deterministic list of trace graphs."""
    return [
        compress_reflection_graph(
            graph,
            utility_threshold=utility_threshold,
            removal_mode=removal_mode,
        )
        for graph in sorted(graphs, key=lambda item: item.graph_id)
    ]


def compression_summary(results: list[CompressionResult]) -> dict[str, float]:
    """Aggregate compression results for reporting."""
    if not results:
        return {
            "num_graphs": 0.0,
            "mean_compression_ratio": 0.0,
            "mean_utility_retained": 0.0,
        }
    return {
        "num_graphs": float(len(results)),
        "mean_compression_ratio": sum(result.compression_ratio for result in results) / len(results),
        "mean_utility_retained": sum(result.utility_retained for result in results) / len(results),
    }


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def result_from_mapping(payload: Mapping[str, Any]) -> CompressionResult:
    return CompressionResult(
        trace_id=str(payload["trace_id"]),
        original_node_count=int(payload["original_node_count"]),
        retained_node_count=int(payload["retained_node_count"]),
        compression_ratio=float(payload["compression_ratio"]),
        removed_node_ids=[str(node_id) for node_id in payload.get("removed_node_ids", [])],
        retained_node_ids=[str(node_id) for node_id in payload.get("retained_node_ids", [])],
        utility_retained=float(payload["utility_retained"]),
        utility_threshold=float(payload["utility_threshold"]),
        curve=[dict(row) for row in payload.get("curve", [])],
    )


__all__ = [
    "CompressionResult",
    "CompressionStep",
    "compress_graphs",
    "compress_reflection_graph",
    "compression_summary",
    "compute_subgraph_utility_ratio",
    "dataclass_to_dict",
    "result_from_mapping",
]
