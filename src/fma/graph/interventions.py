"""Phase 6 graph intervention interfaces."""

from __future__ import annotations

from dataclasses import dataclass

from fma.graph.reflection_graph import ReflectionGraph, RemovalMode


@dataclass(frozen=True)
class GraphIntervention:
    """Apply a PRUNE, CASCADE, or BYPASS intervention to a reflection graph."""

    target_node_id: str
    mode: RemovalMode = RemovalMode.PRUNE

    def apply(self, graph: ReflectionGraph) -> ReflectionGraph:
        """Return an intervened graph using the existing graph removal contract."""
        return graph.remove_node(self.target_node_id, mode=self.mode)


__all__ = ["GraphIntervention"]
