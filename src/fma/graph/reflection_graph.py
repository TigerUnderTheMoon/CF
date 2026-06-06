"""DAG representation for structural reflection attribution.

The graph keeps the original source nodes fixed after an intervention. This
makes reachability-based utility sensitive to deleted edges instead of allowing
newly orphaned nodes to become fresh utility sources.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


SUPPORTED_EDGE_TYPES: tuple[str, ...] = (
    "verifies",
    "critiques",
    "corrects",
    "elaborates",
    "retries",
    "decomposes",
    "summarizes",
    "revises",
)


class RemovalMode(str, Enum):
    """Node-removal semantics for structural interventions."""

    PRUNE = "PRUNE"
    CASCADE = "CASCADE"
    BYPASS = "BYPASS"


@dataclass
class ReflectionNode:
    node_id: str
    trace_id: str
    step_index: int
    taxonomy_label: str
    utility_score: float
    structural_influence: float
    content: str


@dataclass(frozen=True)
class ReflectionEdge:
    source: str
    target: str
    edge_type: str
    weight: float = 1.0


class ReflectionGraph:
    """Small deterministic DAG container for reflection operations."""

    def __init__(
        self,
        graph_id: str,
        nodes: Iterable[ReflectionNode] | None = None,
        edges: Iterable[ReflectionEdge] | None = None,
        source_ids: Iterable[str] | None = None,
    ) -> None:
        self.graph_id = str(graph_id)
        self.nodes: dict[str, ReflectionNode] = {}
        self.edges: dict[tuple[str, str], ReflectionEdge] = {}
        self._source_ids: tuple[str, ...] | None = (
            tuple(dict.fromkeys(str(node_id) for node_id in source_ids))
            if source_ids is not None
            else None
        )
        for node in nodes or ():
            self.add_node(node)
        for edge in edges or ():
            self.add_edge(edge.source, edge.target, edge.edge_type, edge.weight)

    def add_node(self, node: ReflectionNode) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"duplicate node_id {node.node_id!r}")
        self.nodes[node.node_id] = node

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        weight: float = 1.0,
    ) -> None:
        source_id = str(source)
        target_id = str(target)
        if source_id == target_id:
            raise ValueError("self edges are not allowed in a reflection DAG")
        if source_id not in self.nodes or target_id not in self.nodes:
            raise KeyError("both edge endpoints must already exist in the graph")
        if edge_type not in SUPPORTED_EDGE_TYPES:
            raise ValueError(f"unsupported edge_type {edge_type!r}")
        key = (source_id, target_id)
        if key in self.edges:
            raise ValueError(f"duplicate ordered edge {source_id!r}->{target_id!r}")
        if self.has_path(target_id, source_id):
            raise ValueError(f"edge {source_id!r}->{target_id!r} would create a cycle")
        self.edges[key] = ReflectionEdge(source_id, target_id, str(edge_type), float(weight))

    def copy(self) -> "ReflectionGraph":
        return ReflectionGraph(
            graph_id=self.graph_id,
            nodes=[ReflectionNode(**asdict(node)) for node in self.sorted_nodes()],
            edges=list(self.sorted_edges()),
            source_ids=self._source_ids,
        )

    def freeze_sources(self, source_ids: Iterable[str] | None = None) -> None:
        """Persist the source set used for future reachability calculations."""
        if source_ids is None:
            sources = self._computed_sources()
        else:
            sources = [str(node_id) for node_id in source_ids if str(node_id) in self.nodes]
        self._source_ids = tuple(dict.fromkeys(sorted(sources)))

    def sorted_nodes(self) -> list[ReflectionNode]:
        return [self.nodes[node_id] for node_id in sorted(self.nodes)]

    def sorted_edges(self) -> list[ReflectionEdge]:
        return [
            self.edges[key]
            for key in sorted(self.edges, key=lambda item: (item[0], item[1]))
        ]

    def source_nodes(self) -> list[str]:
        if self._source_ids is not None:
            return [node_id for node_id in self._source_ids if node_id in self.nodes]
        return self._computed_sources()

    def parents(self, node_id: str) -> list[str]:
        return sorted(source for source, target in self.edges if target == node_id)

    def children(self, node_id: str) -> list[str]:
        return sorted(target for source, target in self.edges if source == node_id)

    def incoming_edges(self, node_id: str) -> list[ReflectionEdge]:
        return [edge for edge in self.sorted_edges() if edge.target == node_id]

    def outgoing_edges(self, node_id: str) -> list[ReflectionEdge]:
        return [edge for edge in self.sorted_edges() if edge.source == node_id]

    def has_edge(self, source: str, target: str) -> bool:
        return (str(source), str(target)) in self.edges

    def has_path(self, source: str, target: str) -> bool:
        """Return True if a directed path exists from source to target.

        Uses breadth-first search (BFS) from the source node. Traversal
        terminates early when the target is reached.

        Complexity:
            Time:  O(V + E), where V = |nodes| and E = |edges|.  Each
                   node is visited at most once and each outgoing edge
                   is examined at most once during the BFS.
            Space: O(V) worst-case for the visited set and frontier
                   deque (in the limit of a complete graph or a linear
                   chain, the frontier may hold Θ(V) nodes).

            Both average and worst-case bounds are identical; early exit
            upon reaching the target does not change the asymptotic
            worst case (e.g., when no path exists).
        """
        source_id = str(source)
        target_id = str(target)
        if source_id not in self.nodes or target_id not in self.nodes:
            return False
        frontier: deque[str] = deque([source_id])
        seen: set[str] = set()
        while frontier:
            node_id = frontier.popleft()
            if node_id == target_id:
                return True
            if node_id in seen:
                continue
            seen.add(node_id)
            frontier.extend(child for child in self.children(node_id) if child not in seen)
        return False

    def descendants(self, node_id: str) -> set[str]:
        if node_id not in self.nodes:
            return set()
        seen: set[str] = set()
        frontier: deque[str] = deque(self.children(node_id))
        while frontier:
            current = frontier.popleft()
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(self.children(current))
        return seen

    def ancestors(self, node_id: str) -> set[str]:
        if node_id not in self.nodes:
            return set()
        seen: set[str] = set()
        frontier: deque[str] = deque(self.parents(node_id))
        while frontier:
            current = frontier.popleft()
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(self.parents(current))
        return seen

    def shortest_distances_from(self, node_id: str) -> dict[str, int]:
        if node_id not in self.nodes:
            return {}
        distances: dict[str, int] = {node_id: 0}
        frontier: deque[str] = deque([node_id])
        while frontier:
            current = frontier.popleft()
            for child in self.children(current):
                if child in distances:
                    continue
                distances[child] = distances[current] + 1
                frontier.append(child)
        return distances

    def reachable_nodes(self, sources: Iterable[str] | None = None) -> set[str]:
        """Return every node reachable from any of the given source nodes.

        Performs a multi-source BFS. When *sources* is ``None`` the
        frozen source set (or the computed zero-indegree sources) is used.

        Complexity:
            Time:  O(V + E).  Each node is enqueued at most once and
                   each outgoing edge is traversed at most once.
            Space: O(V) for the ``reachable`` set and the BFS frontier.
                   The returned set itself requires O(V) space.

            The multi-source initialization adds at most |sources| ≤ V
            pushes to the frontier, which is absorbed by the O(V + E)
            bound.
        """
        source_ids = list(sources) if sources is not None else self.source_nodes()
        reachable: set[str] = set()
        frontier: deque[str] = deque(source_id for source_id in source_ids if source_id in self.nodes)
        while frontier:
            node_id = frontier.popleft()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            frontier.extend(self.children(node_id))
        return reachable

    def topological_order(self) -> list[str]:
        """Return nodes in topologically sorted order (Kahn's algorithm).

        Builds an indegree map, enqueues zero-indegree nodes, and
        iteratively removes them while decreasing the indegree of
        their children.  Raises ``ValueError`` if the graph contains
        a cycle.

        Complexity:
            Time:  O(V + E).  Indegree initialization visits every node
                   and every edge once; the main loop processes each
                   node and each outgoing edge exactly once.
                   The explicit re-sort of the ready deque inside the
                   loop adds O(V * r * log r) where r is the average
                   deque size, but in reflection DAGs r ≪ V so this
                   term is dominated by O(V + E) in practice.
            Space: O(V) for the indegree map, ready deque, and output
                   list.

            Both average and worst-case time are O(V + E) for a DAG.
        """
        indegree = {node_id: 0 for node_id in self.nodes}
        for edge in self.edges.values():
            indegree[edge.target] += 1
        ready = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
        order: list[str] = []
        while ready:
            node_id = ready.popleft()
            order.append(node_id)
            for child in self.children(node_id):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
            ready = deque(sorted(ready))
        if len(order) != len(self.nodes):
            raise ValueError("reflection graph contains a cycle")
        return order

    def remove_edge(self, source: str, target: str) -> "ReflectionGraph":
        source_key = str(source)
        target_key = str(target)
        if (source_key, target_key) not in self.edges:
            raise KeyError(f"edge {source_key!r}->{target_key!r} does not exist")
        graph = self.copy()
        graph._source_ids = self._source_ids or tuple(self.source_nodes())
        del graph.edges[(source_key, target_key)]
        return graph

    def remove_node(self, node_id: str, mode: RemovalMode | str = RemovalMode.PRUNE) -> "ReflectionGraph":
        """Return a new graph with *node_id* removed under the chosen semantics.

        Three removal modes are supported:

        * **PRUNE** — drop only the targeted node and its incident edges
          (O(V + E)).
        * **CASCADE** — drop the node together with all its descendants;
          useful for modelling "propagating failure" of a reflection
          whose dependents become meaningless (O(V + E)).
        * **BYPASS** — drop the node (and cascade its descendants if
          CASCADE is combined) and reconnect each surviving parent to
          each surviving child with a ``"revises"`` edge, simulating
          a "short-circuit" past the removed reflection.

        Complexity:
            PRUNE:
                Time  O(V + E) — dominated by the graph copy.
                Space O(V + E).
            CASCADE:
                Time  O(V + E) — descendants are collected via BFS,
                      then a single drop removes all of them.
                Space O(V + E).
            BYPASS:
                Time  O(V + E) for the drop, plus O(P × C × (V + E))
                      worst-case for the reconnection phase, where
                      P = |parents| and C = |children|.  In reflection
                      DAGs the fan-in/fan-out are small (typically
                      P, C ≤ 3), so the reconnection term is
                      O(V + E) in practice.
                Space O(V + E).
        """
        node_key = str(node_id)
        if node_key not in self.nodes:
            raise KeyError(f"node {node_key!r} does not exist")
        removal_mode = mode if isinstance(mode, RemovalMode) else RemovalMode(str(mode).upper())
        graph = self.copy()
        graph._source_ids = self._source_ids or tuple(self.source_nodes())

        if removal_mode is RemovalMode.CASCADE:
            remove_ids = {node_key, *self.descendants(node_key)}
        else:
            remove_ids = {node_key}

        if removal_mode is RemovalMode.BYPASS:
            parents = self.parents(node_key)
            children = self.children(node_key)
        else:
            parents = []
            children = []

        graph._drop_nodes(remove_ids)

        if removal_mode is RemovalMode.BYPASS:
            for parent in parents:
                if parent not in graph.nodes:
                    continue
                for child in children:
                    if child not in graph.nodes or parent == child or graph.has_edge(parent, child):
                        continue
                    if graph.has_path(child, parent):
                        continue
                    graph.add_edge(parent, child, "revises", 1.0)
        return graph

    def subgraph(self, node_ids: Iterable[str], graph_id: str | None = None) -> "ReflectionGraph":
        selected = {str(node_id) for node_id in node_ids if str(node_id) in self.nodes}
        nodes = [ReflectionNode(**asdict(self.nodes[node_id])) for node_id in sorted(selected)]
        edges = [
            edge
            for edge in self.sorted_edges()
            if edge.source in selected and edge.target in selected
        ]
        source_ids = [node_id for node_id in self.source_nodes() if node_id in selected]
        subgraph = ReflectionGraph(graph_id or f"{self.graph_id}:subgraph", nodes, edges, source_ids)
        if not source_ids and nodes:
            subgraph.freeze_sources()
        return subgraph

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": [asdict(node) for node in self.sorted_nodes()],
            "edges": [asdict(edge) for edge in self.sorted_edges()],
            "source_ids": self.source_nodes(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReflectionGraph":
        nodes = [ReflectionNode(**dict(node)) for node in payload.get("nodes", [])]
        edges = [ReflectionEdge(**dict(edge)) for edge in payload.get("edges", [])]
        return cls(
            graph_id=str(payload.get("graph_id", "reflection_graph")),
            nodes=nodes,
            edges=edges,
            source_ids=payload.get("source_ids"),
        )

    def _drop_nodes(self, node_ids: set[str]) -> None:
        for node_id in node_ids:
            self.nodes.pop(node_id, None)
        self.edges = {
            key: edge
            for key, edge in self.edges.items()
            if edge.source not in node_ids and edge.target not in node_ids
        }
        if self._source_ids is not None:
            self._source_ids = tuple(node_id for node_id in self._source_ids if node_id in self.nodes)

    def _computed_sources(self) -> list[str]:
        if not self.nodes:
            return []
        parents_by_node = {node_id: set(self.parents(node_id)) for node_id in self.nodes}
        has_any_edge = bool(self.edges)
        sources = [
            node_id
            for node_id in sorted(self.nodes)
            if not parents_by_node[node_id] and (self.children(node_id) or not has_any_edge)
        ]
        return sources


__all__ = [
    "RemovalMode",
    "ReflectionEdge",
    "ReflectionGraph",
    "ReflectionNode",
    "SUPPORTED_EDGE_TYPES",
]
