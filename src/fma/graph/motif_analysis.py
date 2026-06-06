"""Deterministic motif detection for small reflection DAG templates."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from fma.graph.reflection_graph import ReflectionGraph


MOTIF_TEMPLATES: tuple[str, ...] = (
    "critique_revision",
    "verify_correct",
    "decompose_retry",
    "retry_verify",
    "elaborate_chain",
    "convergent_verify",
    "divergent_decompose",
    "full_correction",
)


@dataclass(frozen=True)
class MotifMatch:
    trace_id: str
    motif_type: str
    node_ids: list[str]
    edge_types: list[str]
    motif_utility: float


def detect_motifs(graph: ReflectionGraph) -> list[MotifMatch]:
    """Detect all predefined motifs with explicit local topology checks."""
    matches: list[MotifMatch] = []
    matches.extend(_critique_revision(graph))
    matches.extend(_verify_correct(graph))
    matches.extend(_decompose_retry(graph))
    matches.extend(_retry_verify(graph))
    matches.extend(_elaborate_chain(graph))
    matches.extend(_convergent_verify(graph))
    matches.extend(_divergent_decompose(graph))
    matches.extend(_full_correction(graph))
    return sorted(
        _dedupe(matches),
        key=lambda item: (item.trace_id, item.motif_type, item.node_ids, item.edge_types),
    )


def summarize_motifs(matches: Sequence[MotifMatch]) -> dict[str, Any]:
    """Aggregate motif counts and utility summaries."""
    counts = Counter(match.motif_type for match in matches)
    utility_by_type: dict[str, list[float]] = {template: [] for template in MOTIF_TEMPLATES}
    for match in matches:
        utility_by_type.setdefault(match.motif_type, []).append(match.motif_utility)
    return {
        "motif_counts": {template: counts.get(template, 0) for template in MOTIF_TEMPLATES},
        "motif_mean_utility": {
            template: (sum(values) / len(values) if values else 0.0)
            for template, values in utility_by_type.items()
        },
        "num_matches": len(matches),
        "matches": [asdict(match) for match in matches],
    }


def motif_subgraphs(matches: Sequence[MotifMatch]) -> list[dict[str, Any]]:
    """Convert motif matches to subgraph-necessity inputs."""
    return [
        {
            "subgraph_id": f"{match.trace_id}::{match.motif_type}::{index:03d}",
            "node_ids": match.node_ids,
            "motif_type": match.motif_type,
        }
        for index, match in enumerate(matches)
    ]


def _critique_revision(graph: ReflectionGraph) -> list[MotifMatch]:
    rows: list[MotifMatch] = []
    for edge in graph.sorted_edges():
        source = graph.nodes[edge.source]
        target = graph.nodes[edge.target]
        if edge.edge_type in {"critiques", "revises"} or (
            _is_critique(source.taxonomy_label) and _is_revision(target.taxonomy_label)
        ):
            rows.append(_match(graph, "critique_revision", [edge.source, edge.target], [edge.edge_type]))
    return rows


def _verify_correct(graph: ReflectionGraph) -> list[MotifMatch]:
    rows: list[MotifMatch] = []
    for edge in graph.sorted_edges():
        source = graph.nodes[edge.source]
        target = graph.nodes[edge.target]
        if (_is_verify(source.taxonomy_label) and _is_correction(target.taxonomy_label)) or (
            edge.edge_type == "verifies" and _is_correction(target.taxonomy_label)
        ):
            rows.append(_match(graph, "verify_correct", [edge.source, edge.target], [edge.edge_type]))
    return rows


def _decompose_retry(graph: ReflectionGraph) -> list[MotifMatch]:
    rows: list[MotifMatch] = []
    for edge in graph.sorted_edges():
        source = graph.nodes[edge.source]
        target = graph.nodes[edge.target]
        if _is_decompose(source.taxonomy_label) and (
            edge.edge_type == "retries" or _is_retry(target.taxonomy_label)
        ):
            rows.append(_match(graph, "decompose_retry", [edge.source, edge.target], [edge.edge_type]))
    return rows


def _retry_verify(graph: ReflectionGraph) -> list[MotifMatch]:
    rows: list[MotifMatch] = []
    for edge in graph.sorted_edges():
        source = graph.nodes[edge.source]
        target = graph.nodes[edge.target]
        if (_is_retry(source.taxonomy_label) or edge.edge_type == "retries") and _is_verify(
            target.taxonomy_label
        ):
            rows.append(_match(graph, "retry_verify", [edge.source, edge.target], [edge.edge_type]))
    return rows


def _elaborate_chain(graph: ReflectionGraph) -> list[MotifMatch]:
    rows: list[MotifMatch] = []
    for first in graph.sorted_edges():
        for second in graph.outgoing_edges(first.target):
            edge_types = [first.edge_type, second.edge_type]
            if all(edge_type in {"elaborates", "summarizes", "revises"} for edge_type in edge_types):
                rows.append(
                    _match(
                        graph,
                        "elaborate_chain",
                        [first.source, first.target, second.target],
                        edge_types,
                    )
                )
    return rows


def _convergent_verify(graph: ReflectionGraph) -> list[MotifMatch]:
    rows: list[MotifMatch] = []
    for node_id in sorted(graph.nodes):
        parents = graph.parents(node_id)
        if len(parents) < 2 or not _is_verify(graph.nodes[node_id].taxonomy_label):
            continue
        for left_index in range(len(parents)):
            for right_index in range(left_index + 1, len(parents)):
                left = parents[left_index]
                right = parents[right_index]
                edge_types = [
                    graph.edges[(left, node_id)].edge_type,
                    graph.edges[(right, node_id)].edge_type,
                ]
                rows.append(_match(graph, "convergent_verify", [left, right, node_id], edge_types))
    return rows


def _divergent_decompose(graph: ReflectionGraph) -> list[MotifMatch]:
    rows: list[MotifMatch] = []
    for node_id in sorted(graph.nodes):
        children = graph.children(node_id)
        if len(children) < 2 or not _is_decompose(graph.nodes[node_id].taxonomy_label):
            continue
        for left_index in range(len(children)):
            for right_index in range(left_index + 1, len(children)):
                left = children[left_index]
                right = children[right_index]
                edge_types = [
                    graph.edges[(node_id, left)].edge_type,
                    graph.edges[(node_id, right)].edge_type,
                ]
                rows.append(_match(graph, "divergent_decompose", [node_id, left, right], edge_types))
    return rows


def _full_correction(graph: ReflectionGraph) -> list[MotifMatch]:
    rows: list[MotifMatch] = []
    for first in graph.sorted_edges():
        middle = graph.nodes[first.target]
        if not (_is_critique(graph.nodes[first.source].taxonomy_label) or first.edge_type == "critiques"):
            continue
        if not (_is_correction(middle.taxonomy_label) or first.edge_type in {"corrects", "revises"}):
            continue
        for second in graph.outgoing_edges(first.target):
            if _is_verify(graph.nodes[second.target].taxonomy_label) or second.edge_type == "verifies":
                rows.append(
                    _match(
                        graph,
                        "full_correction",
                        [first.source, first.target, second.target],
                        [first.edge_type, second.edge_type],
                    )
                )
    return rows


def _match(
    graph: ReflectionGraph,
    motif_type: str,
    node_ids: list[str],
    edge_types: list[str],
) -> MotifMatch:
    return MotifMatch(
        trace_id=graph.graph_id,
        motif_type=motif_type,
        node_ids=list(node_ids),
        edge_types=list(edge_types),
        motif_utility=float(sum(graph.nodes[node_id].utility_score for node_id in node_ids)),
    )


def _dedupe(matches: Sequence[MotifMatch]) -> list[MotifMatch]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    rows: list[MotifMatch] = []
    for match in matches:
        key = (match.motif_type, tuple(match.node_ids))
        if key in seen:
            continue
        seen.add(key)
        rows.append(match)
    return rows


def _is_verify(label: str) -> bool:
    return _has(label, "VERIFICATION", "CONSTRAINT", "CONSISTENCY", "VERIFY")


def _is_correction(label: str) -> bool:
    return _has(label, "ERROR", "CORRECTION", "RECOVERY", "CORRECT")


def _is_critique(label: str) -> bool:
    return _has(label, "CRITIQUE", "ERROR", "BACKTRACK", "UNCERTAINTY")


def _is_revision(label: str) -> bool:
    return _has(label, "PLANNING", "REVISION", "ERROR", "CORRECTION", "BACKTRACK")


def _is_decompose(label: str) -> bool:
    return _has(label, "DECOMPOSITION", "DECOMPOSE")


def _is_retry(label: str) -> bool:
    return _has(label, "BACKTRACK", "RETRY", "RECOVERY")


def _has(label: str, *parts: str) -> bool:
    normalized = label.upper()
    return any(part in normalized for part in parts)


__all__ = [
    "MOTIF_TEMPLATES",
    "MotifMatch",
    "detect_motifs",
    "motif_subgraphs",
    "summarize_motifs",
]
