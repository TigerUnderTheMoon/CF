"""Parallel Phase 6 graph intervention engine."""

from __future__ import annotations

import copy
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from tqdm.auto import tqdm

from fma.eval.structural_attribution import (
    StructuralEdgeNecessity,
    StructuralNodeNecessity,
    StructuralSubgraphNecessity,
    compute_edge_necessity,
    compute_node_necessity,
    compute_structural_influence,
    compute_structural_metrics,
    compute_subgraph_necessity,
    default_subgraphs,
)
from fma.graph.reflection_graph import RemovalMode, ReflectionGraph


@dataclass(frozen=True)
class GraphInterventionBatch:
    """Phase 6 intervention rows for one removal mode."""

    mode: str
    node_necessity: list[StructuralNodeNecessity]
    edge_necessity: list[StructuralEdgeNecessity]
    subgraph_necessity: list[StructuralSubgraphNecessity]
    structural_metrics: list[dict[str, float]]


@dataclass(frozen=True)
class GraphInterventionReport:
    """All parallel graph intervention outputs grouped by removal mode."""

    by_mode: dict[str, GraphInterventionBatch]


class ParallelGraphInterventionEngine:
    """Run PRUNE/CASCADE/BYPASS graph interventions with process workers.

    Determinism is preserved by setting the same random seed in the parent
    process before submission and in every worker before computation.
    Graph objects are deep-copied in the parent process before pickling to
    avoid mutating shared state across workers.
    """

    def __init__(
        self,
        max_workers: int | None = None,
        seed: int = 42,
        show_progress: bool = True,
    ) -> None:
        self.max_workers = max_workers
        self.seed = int(seed)
        self.show_progress = bool(show_progress)

    def run(
        self,
        graphs: Sequence[ReflectionGraph],
        modes: Sequence[RemovalMode | str] = (
            RemovalMode.PRUNE,
            RemovalMode.CASCADE,
            RemovalMode.BYPASS,
        ),
    ) -> GraphInterventionReport:
        """Submit one deep-copied graph per mode to process workers."""
        _set_seed(self.seed)
        mode_values = tuple(_mode_value(mode) for mode in modes)
        graph_list = list(graphs)
        # Deep-copy each graph in the parent process before passing to workers.
        # This guarantees immutability of the original sequence and avoids
        # shared-state mutations inside process workers.
        tasks = [
            (mode_index, graph_index, mode, copy.deepcopy(graph), self.seed)
            for mode_index, mode in enumerate(mode_values)
            for graph_index, graph in enumerate(graph_list)
        ]
        if not tasks:
            return GraphInterventionReport(by_mode={})

        completed: list[tuple[int, int, str, dict[str, Any]]] = []
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(_run_graph_intervention_worker, mode, graph, seed): (
                    mode_index,
                    graph_index,
                    mode,
                )
                for mode_index, graph_index, mode, graph, seed in tasks
            }
            progress = tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Phase 6 graph interventions",
                disable=not self.show_progress,
            )
            for future in progress:
                mode_index, graph_index, mode = futures[future]
                completed.append((mode_index, graph_index, mode, future.result()))

        completed.sort(key=lambda item: (item[0], item[1]))
        by_mode: dict[str, GraphInterventionBatch] = {}
        for _mode_index, _graph_index, mode, payload in completed:
            batch = by_mode.setdefault(
                mode,
                GraphInterventionBatch(
                    mode=mode,
                    node_necessity=[],
                    edge_necessity=[],
                    subgraph_necessity=[],
                    structural_metrics=[],
                ),
            )
            batch.node_necessity.extend(payload["node_necessity"])
            batch.edge_necessity.extend(payload["edge_necessity"])
            batch.subgraph_necessity.extend(payload["subgraph_necessity"])
            batch.structural_metrics.append(payload["structural_metrics"])
        return GraphInterventionReport(by_mode=by_mode)


def _run_graph_intervention_worker(
    mode: str, graph: ReflectionGraph, seed: int
) -> dict[str, Any]:
    """Re-initialize the same random seed in every worker for determinism."""
    _set_seed(seed)
    # The graph is already deep-copied by the parent; no need to copy again.
    compute_structural_influence(graph)
    subgraphs = default_subgraphs(graph)
    return {
        "graph_id": graph.graph_id,
        "node_necessity": compute_node_necessity(graph, removal_mode=mode),
        "edge_necessity": compute_edge_necessity(graph),
        "subgraph_necessity": compute_subgraph_necessity(graph, subgraphs),
        "structural_metrics": compute_structural_metrics(graph),
    }


def _set_seed(seed: int) -> None:
    """Set Python and NumPy random state deterministically."""
    random.seed(seed)
    np.random.seed(seed)


def _mode_value(mode: RemovalMode | str) -> str:
    return mode.value if isinstance(mode, RemovalMode) else RemovalMode(str(mode).upper()).value


__all__ = [
    "GraphInterventionBatch",
    "GraphInterventionReport",
    "ParallelGraphInterventionEngine",
]
