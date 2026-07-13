"""Tests for the mathematical variable-dependency DAG backend."""
from __future__ import annotations

from fma.eval.structural_attribution import compute_node_necessity
from fma.graph.math_dependency_graph import (
    build_math_dependency_graph,
    math_dependency_edges,
    parse_step_symbols,
)


def test_parse_inline_assignment():
    introduced, referenced = parse_step_symbols("So, $c=\\frac{32}{2}=16$.")
    assert "c" in referenced
    assert "c" in introduced
    # LaTeX operator letters (from \frac) must not leak in as variables.
    assert "f" not in referenced and "r" not in referenced


def test_parse_greek_and_display_math():
    introduced, referenced = parse_step_symbols("We set $$\\alpha = \\beta + \\gamma$$.")
    assert {"alpha", "beta", "gamma"} <= referenced
    assert "alpha" in introduced  # left-hand side of the assignment


def test_parse_subscripts_and_bracket_delimiters():
    _, referenced = parse_step_symbols("\\[ x_1 + x_{ij} = 0 \\]")
    assert "x_1" in referenced
    assert "x_ij" in referenced


def test_parse_paren_delimiters_and_align_environment():
    _, referenced = parse_step_symbols(
        "\\(y\\) then \\begin{align*} 3x &= 4 \\end{align*}"
    )
    assert "y" in referenced and "x" in referenced
    # environment name letters must not become variables
    assert "l" not in referenced and "g" not in referenced


def test_parse_text_wrapper_is_stripped():
    _, referenced = parse_step_symbols("$\\text{speed} = v$")
    assert "v" in referenced
    assert not ({"s", "p", "e", "d"} & referenced)


def test_parse_plain_text_has_no_symbols():
    introduced, referenced = parse_step_symbols("First, I read the problem carefully.")
    assert introduced == set() and referenced == set()


def test_dependency_edges_prefer_introduced_antecedent():
    steps = ["$c=2$", "$b=c$", "$a=b$"]
    edges = math_dependency_edges(steps)
    pairs = {(s, t) for s, t, _ in edges}
    assert (0, 1) in pairs  # step 1 uses c introduced at step 0
    assert (1, 2) in pairs  # step 2 uses b introduced at step 1
    # 'a' is introduced only at step 2, so it has no antecedent edge
    assert all(sym != "a" for _, _, sym in edges)


def test_dependency_edges_referenced_fallback_and_nonadjacent():
    steps = ["$x=1$", "a plain sentence", "$y=x$"]
    edges = math_dependency_edges(steps)
    assert (0, 2, "x") in edges  # non-adjacent def->use edge across a text step


def test_build_graph_backbone_and_dependency_edges():
    steps = ["$x=1$", "plain", "$y=x$"]
    graph = build_math_dependency_graph(steps, "t")
    assert len(graph.nodes) == 3
    # temporal backbone (0->1, 1->2) plus the non-adjacent dependency 0->2
    assert len(graph.edges) == 3
    necessity = compute_node_necessity(graph)
    assert len(necessity) == 3


def test_build_graph_backbone_only_control():
    steps = ["$x=1$", "plain", "$y=x$"]
    graph = build_math_dependency_graph(steps, "t", include_dependency_edges=False)
    assert len(graph.edges) == len(steps) - 1  # backbone only


def test_build_graph_is_acyclic():
    steps = ["$c=2$", "$b=c$", "$a=b$", "$a+b+c$"]
    graph = build_math_dependency_graph(steps, "t")
    # topological_order raises if the graph contains a cycle
    order = graph.topological_order()
    assert len(order) == len(steps)


def test_build_graph_empty_and_single():
    assert len(build_math_dependency_graph([], "t").nodes) == 0
    single = build_math_dependency_graph(["$x=1$"], "t")
    assert len(single.nodes) == 1
    assert len(single.edges) == 0
    assert len(compute_node_necessity(single)) == 1
