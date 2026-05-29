from __future__ import annotations

from fma.graph.motif_analysis import MOTIF_TEMPLATES, detect_motifs, motif_subgraphs, summarize_motifs
from fma.graph.reflection_graph import ReflectionGraph, ReflectionNode


def add_node(graph: ReflectionGraph, node_id: str, step: int, label: str) -> None:
    graph.add_node(ReflectionNode(node_id, "t1", step, label, 1.0, 0.0, node_id))


def motif_names(graph: ReflectionGraph) -> set[str]:
    return {match.motif_type for match in detect_motifs(graph)}


def test_verify_correct_template_matches_explicit_pair() -> None:
    graph = ReflectionGraph("t1")
    add_node(graph, "v", 0, "VERIFICATION")
    add_node(graph, "c", 1, "ERROR_CORRECTION")
    graph.add_edge("v", "c", "corrects")
    graph.freeze_sources(["v"])

    assert "verify_correct" in motif_names(graph)


def test_retry_verify_and_decompose_retry_templates_match() -> None:
    graph = ReflectionGraph("t1")
    add_node(graph, "d", 0, "DECOMPOSITION")
    add_node(graph, "r", 1, "BACKTRACKING")
    add_node(graph, "v", 2, "VERIFICATION")
    graph.add_edge("d", "r", "retries")
    graph.add_edge("r", "v", "verifies")
    graph.freeze_sources(["d"])

    names = motif_names(graph)

    assert "decompose_retry" in names
    assert "retry_verify" in names


def test_convergent_and_divergent_templates_match_branching_graph() -> None:
    graph = ReflectionGraph("t1")
    add_node(graph, "d", 0, "DECOMPOSITION")
    add_node(graph, "x", 1, "PLANNING")
    add_node(graph, "y", 2, "ERROR_CORRECTION")
    add_node(graph, "v", 3, "VERIFICATION")
    graph.add_edge("d", "x", "decomposes")
    graph.add_edge("d", "y", "decomposes")
    graph.add_edge("x", "v", "verifies")
    graph.add_edge("y", "v", "verifies")
    graph.freeze_sources(["d"])

    names = motif_names(graph)

    assert "divergent_decompose" in names
    assert "convergent_verify" in names


def test_full_correction_and_critique_revision_templates_match_path() -> None:
    graph = ReflectionGraph("t1")
    add_node(graph, "q", 0, "STRATEGY_CRITIQUE")
    add_node(graph, "c", 1, "ERROR_CORRECTION")
    add_node(graph, "v", 2, "VERIFICATION")
    graph.add_edge("q", "c", "critiques")
    graph.add_edge("c", "v", "verifies")
    graph.freeze_sources(["q"])

    names = motif_names(graph)

    assert "critique_revision" in names
    assert "full_correction" in names


def test_elaborate_chain_template_matches_two_step_path() -> None:
    graph = ReflectionGraph("t1")
    add_node(graph, "a", 0, "OTHER")
    add_node(graph, "b", 1, "OTHER")
    add_node(graph, "c", 2, "OTHER")
    graph.add_edge("a", "b", "elaborates")
    graph.add_edge("b", "c", "summarizes")
    graph.freeze_sources(["a"])

    assert "elaborate_chain" in motif_names(graph)


def test_motif_summary_has_all_templates_and_subgraph_inputs() -> None:
    graph = ReflectionGraph("t1")
    add_node(graph, "v", 0, "VERIFICATION")
    add_node(graph, "c", 1, "ERROR_CORRECTION")
    graph.add_edge("v", "c", "corrects")
    graph.freeze_sources(["v"])
    matches = detect_motifs(graph)

    summary = summarize_motifs(matches)
    subgraphs = motif_subgraphs(matches)

    assert set(summary["motif_counts"]) == set(MOTIF_TEMPLATES)
    assert summary["num_matches"] == len(matches)
    assert subgraphs[0]["node_ids"] == matches[0].node_ids
