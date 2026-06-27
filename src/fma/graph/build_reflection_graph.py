"""Deterministic construction of reflection DAGs from Phase 5 artifacts.

Edge weights and quality scores are derived from text-content similarity.
When similarity is disabled (``similarity_method=None``) the behaviour is
identical to the prior fixed-weight construction.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Mapping, Sequence

from fma.graph.reflection_graph import ReflectionEdge, ReflectionGraph, ReflectionNode
from fma.graph.similarity import TextSimilarity


def build_reflection_graphs(
    traces: Sequence[Mapping[str, Any]],
    necessity_records: Sequence[Mapping[str, Any]] | None = None,
    similarity_method: str | None = None,
    similarity_threshold: float = 0.15,
    prune_threshold: float = 0.0,
    max_long_range: int = 5,
    embedding_backend: str = "sentence-transformers",
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    allow_embedding_download: bool = False,
) -> list[ReflectionGraph]:
    """Build one acyclic reflection graph per trace.

    When *similarity_method* is ``"tfidf"`` or ``"jaccard"``, edge weights
    and quality scores are derived from text-content similarity rather than
    fixed constants.  Long-range edges are also discovered via similarity
    instead of only label-pattern matching.
    """
    necessity_by_key = _necessity_by_key(necessity_records or [])
    similarity = _fit_similarity(
        traces,
        similarity_method,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
        allow_embedding_download=allow_embedding_download,
    )
    graphs: list[ReflectionGraph] = []
    for index, trace in enumerate(traces):
        graph = build_reflection_graph(
            trace,
            index=index,
            necessity_by_key=necessity_by_key,
            similarity=similarity,
            similarity_threshold=similarity_threshold,
            prune_threshold=prune_threshold,
            max_long_range=max_long_range,
        )
        if graph.nodes:
            graphs.append(graph)
    return graphs


def build_reflection_graph(
    trace: Mapping[str, Any],
    index: int = 0,
    necessity_by_key: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
    similarity: TextSimilarity | None = None,
    similarity_threshold: float = 0.15,
    prune_threshold: float = 0.0,
    max_long_range: int = 5,
) -> ReflectionGraph:
    """Build a single trace DAG with deterministic local dependency edges.

    When *similarity* is provided, sequential edge weights are set to the
    content-similarity score and long-range edges are discovered for all
    node pairs whose similarity exceeds *similarity_threshold*.
    """
    trace_id = _trace_id(trace, index)
    steps = _reflection_steps(trace)
    graph = ReflectionGraph(trace_id)
    necessity_lookup = necessity_by_key or {}

    node_ids: list[str] = []
    step_texts: list[str] = []
    for step_index, step in enumerate(steps):
        label = _taxonomy_label(step)
        content = _step_content(step)
        record = necessity_lookup.get((trace_id, step_index), {})
        utility = _node_utility(record)
        node_id = node_id_for(trace_id, step_index)
        graph.add_node(
            ReflectionNode(
                node_id=node_id,
                trace_id=trace_id,
                step_index=step_index,
                taxonomy_label=label,
                utility_score=utility,
                structural_influence=0.0,
                content=content,
            )
        )
        node_ids.append(node_id)
        step_texts.append(content)

    use_similarity = similarity is not None

    for position in range(len(node_ids) - 1):
        edge_type = _infer_edge_type(steps[position], steps[position + 1])
        if use_similarity:
            sim = similarity.pairwise(step_texts[position], step_texts[position + 1])
            _add_edge_if_absent(
                graph,
                node_ids[position],
                node_ids[position + 1],
                edge_type,
                weight=sim,
                quality=sim,
            )
        else:
            _add_edge_if_absent(graph, node_ids[position], node_ids[position + 1], edge_type)

    if use_similarity and max_long_range > 1:
        for left in range(len(node_ids)):
            right_limit = min(len(node_ids), left + max_long_range + 1)
            for right in range(left + 2, right_limit):
                sim = similarity.pairwise(step_texts[left], step_texts[right])
                if sim >= similarity_threshold:
                    label_edge_type = _long_range_edge_type(steps[left], steps[right])
                    edge_type = label_edge_type if label_edge_type is not None else _infer_edge_type(steps[left], steps[right])
                    _add_edge_if_absent(
                        graph,
                        node_ids[left],
                        node_ids[right],
                        edge_type,
                        weight=sim,
                        quality=sim,
                    )
    else:
        for left in range(len(node_ids)):
            for right in range(left + 2, len(node_ids)):
                edge_type = _long_range_edge_type(steps[left], steps[right])
                if edge_type is not None:
                    _add_edge_if_absent(graph, node_ids[left], node_ids[right], edge_type, weight=0.75)

    if node_ids:
        graph.freeze_sources([node_ids[0]])

    if use_similarity and prune_threshold > 0.0:
        graph = graph.prune_edges(prune_threshold)

    return graph


def combine_reflection_graphs(
    graphs: Sequence[ReflectionGraph],
    graph_id: str = "phase6_reflection_graphs",
) -> ReflectionGraph:
    """Combine trace-level DAGs into a disconnected DAG forest."""
    combined = ReflectionGraph(graph_id)
    source_ids: list[str] = []
    for graph in graphs:
        for node in graph.sorted_nodes():
            combined.add_node(ReflectionNode(**node.__dict__))
        for edge in graph.sorted_edges():
            combined.add_edge(edge.source, edge.target, edge.edge_type, edge.weight, edge.quality)
        source_ids.extend(graph.source_nodes())
    combined.freeze_sources(source_ids)
    return combined


def graph_records(graphs: Sequence[ReflectionGraph]) -> list[dict[str, Any]]:
    """Serialize graph objects with deterministic ordering."""
    return [graph.to_dict() for graph in sorted(graphs, key=lambda item: item.graph_id)]


def node_id_for(trace_id: str, step_index: int) -> str:
    return f"{trace_id}::r{step_index:03d}"


def _fit_similarity(
    traces: Sequence[Mapping[str, Any]],
    method: str | None,
    *,
    embedding_backend: str = "sentence-transformers",
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    allow_embedding_download: bool = False,
) -> TextSimilarity | None:
    if method is None:
        return None
    all_texts: list[str] = []
    for trace in traces:
        for step in _reflection_steps(trace):
            text = _step_content(step)
            if text:
                all_texts.append(text)
    sim = TextSimilarity(
        method=method,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
        allow_embedding_download=allow_embedding_download,
    )
    sim.fit_corpus(all_texts)
    return sim


def _necessity_by_key(
    records: Sequence[Mapping[str, Any]],
) -> OrderedDict[tuple[str, int], Mapping[str, Any]]:
    lookup: OrderedDict[tuple[str, int], Mapping[str, Any]] = OrderedDict()
    for record in records:
        if "trace_id" not in record or "step_idx" not in record:
            continue
        lookup[(str(record["trace_id"]), int(record["step_idx"]))] = record
    return lookup


def _trace_id(trace: Mapping[str, Any], index: int) -> str:
    return str(
        trace.get("trace_id")
        or trace.get("sample_id")
        or trace.get("task_id")
        or f"trace_{index:05d}"
    )


def _reflection_steps(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    chain = trace.get("reflection_chain")
    if isinstance(chain, list) and chain:
        return [dict(step) for step in chain if isinstance(step, Mapping)]

    spans = trace.get("reflection_spans")
    if isinstance(spans, list) and spans:
        steps = []
        for span in spans:
            if not isinstance(span, Mapping):
                continue
            steps.append(
                {
                    "category": span.get("reflection_type") or span.get("type") or "OTHER",
                    "text": span.get("content") or span.get("text") or "",
                }
            )
        return steps

    text = trace.get("reflection_text") or trace.get("reasoning_trace")
    if isinstance(text, str) and text.strip():
        return [{"category": trace.get("category", "OTHER"), "text": text.strip()}]
    return []


def _taxonomy_label(step: Mapping[str, Any]) -> str:
    label = step.get("category") or step.get("reflection_type") or step.get("type") or "OTHER"
    return str(label).strip().upper().replace("-", "_") or "OTHER"


def _step_content(step: Mapping[str, Any]) -> str:
    return str(step.get("text") or step.get("content") or "").strip()


def _node_utility(record: Mapping[str, Any]) -> float:
    if "necessity_normalized" in record:
        return float(record["necessity_normalized"])
    if "necessity" in record:
        return max(0.0, float(record["necessity"]))
    if "utility_score" in record:
        return float(record["utility_score"])
    return 0.0


def _infer_edge_type(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    left_label = _taxonomy_label(left)
    right_label = _taxonomy_label(right)
    text = f"{_step_content(left)} {_step_content(right)}".lower()

    if _has_any(right_label, "ERROR", "CORRECTION", "BACKTRACK", "RECOVERY") or _contains(
        text,
        "correct",
        "fix",
        "repair",
    ):
        return "corrects"
    if _has_any(right_label, "VERIFICATION", "CONSTRAINT", "CONSISTENCY") or _contains(
        text,
        "verify",
        "check",
        "validate",
    ):
        return "verifies"
    if _has_any(left_label, "CRITIQUE") or _contains(text, "critique", "flaw"):
        return "critiques"
    if _has_any(right_label, "PLANNING") or _contains(text, "revise", "plan", "strategy"):
        return "revises"
    if left_label == right_label or _contains(text, "retry", "again", "backtrack"):
        return "retries"
    if _has_any(left_label, "DECOMPOSITION") or _has_any(right_label, "DECOMPOSITION"):
        return "decomposes"
    if _contains(text, "summary", "summarize", "therefore"):
        return "summarizes"
    return "elaborates"


def _long_range_edge_type(left: Mapping[str, Any], right: Mapping[str, Any]) -> str | None:
    left_label = _taxonomy_label(left)
    right_label = _taxonomy_label(right)
    if left_label == right_label:
        return "retries"
    if _has_any(left_label, "DECOMPOSITION"):
        return "decomposes"
    if _has_any(right_label, "VERIFICATION", "CONSTRAINT", "CONSISTENCY"):
        return "verifies"
    if _has_any(right_label, "ERROR", "CORRECTION", "BACKTRACK", "RECOVERY"):
        return "corrects"
    return None


def _add_edge_if_absent(
    graph: ReflectionGraph,
    source: str,
    target: str,
    edge_type: str,
    weight: float = 1.0,
    quality: float = 1.0,
) -> None:
    if graph.has_edge(source, target):
        return
    graph.add_edge(source, target, edge_type, weight, quality)


def _has_any(label: str, *needles: str) -> bool:
    return any(needle in label for needle in needles)


def _contains(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


__all__ = [
    "build_reflection_graph",
    "build_reflection_graphs",
    "combine_reflection_graphs",
    "graph_records",
    "node_id_for",
]
