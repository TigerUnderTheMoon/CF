"""Mathematical variable-dependency DAG construction for structural attribution.

This backend is an alternative to the TF-IDF topical-similarity edge construction
in :mod:`fma.graph.build_reflection_graph`. Instead of scoring generic lexical
overlap between step texts, it parses the mathematical variables *introduced* and
*referenced* in each reasoning step (from LaTeX-style math regions such as
``$...$`` and ``\\begin{align*}...\\end{align*}``) and connects a step to the
nearest earlier step that supplies a variable it uses. A step that introduces a
quantity many later steps depend on therefore becomes a structural hub.

The parser is deliberately a regular-expression heuristic (no computer algebra
system): it reads variable-like tokens from math regions only, so natural-language
words are not mistaken for variables. The resulting graph is a standard
:class:`~fma.graph.reflection_graph.ReflectionGraph` whose node necessity can be
scored unchanged by :func:`fma.eval.structural_attribution.compute_node_necessity`.

Dependency edges run from the earlier (defining) step to the later (using) step,
so the graph is acyclic by construction. A sequential temporal backbone keeps the
graph connected and reachable from the frozen source (step 0).
"""
from __future__ import annotations

import re
from typing import Sequence

from fma.graph.build_reflection_graph import node_id_for
from fma.graph.reflection_graph import ReflectionGraph, ReflectionNode

__all__ = [
    "parse_step_symbols",
    "build_math_dependency_graph",
    "math_dependency_edges",
]

# Greek letter command names treated as variables (drop LaTeX operators/formatting).
_GREEK = {
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta",
    "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi", "pi",
    "varpi", "rho", "varrho", "sigma", "varsigma", "tau", "upsilon", "phi",
    "varphi", "chi", "psi", "omega",
}

# Environments and inline delimiters that wrap mathematical content.
_MATH_PATTERNS = (
    re.compile(r"\$\$(.+?)\$\$", re.DOTALL),
    re.compile(r"\$(.+?)\$", re.DOTALL),
    re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
    re.compile(r"\\\((.+?)\\\)", re.DOTALL),
    re.compile(r"\\begin\{[a-zA-Z]+\*?\}(.+?)\\end\{[a-zA-Z]+\*?\}", re.DOTALL),
)

# Textual LaTeX wrappers whose braced content is prose, not variables.
_TEXT_WRAPPER = re.compile(
    r"\\(?:text|mathrm|mbox|operatorname|mathbf|mathcal|mathsf|textbf|textit)\s*\{[^}]*\}"
)
_COMMAND = re.compile(r"\\[A-Za-z]+")
_SUBSCRIPT = re.compile(r"([A-Za-z])_\{?([A-Za-z0-9]+)\}?")
_LETTER = re.compile(r"[A-Za-z]")
# A single variable (possibly Greek command or subscripted) used as the LHS of "=".
_ASSIGN = re.compile(
    r"(\\[A-Za-z]+|[A-Za-z](?:_\{?[A-Za-z0-9]+\}?)?)\s*&?\s*="
)


def _math_regions(text: str) -> list[str]:
    """Return the mathematical sub-strings of ``text`` (inline + display + envs)."""
    regions: list[str] = []
    for pattern in _MATH_PATTERNS:
        for match in pattern.finditer(text):
            regions.append(next(g for g in match.groups() if g is not None))
    return regions


def _greek_symbols(fragment: str) -> set[str]:
    return {
        m.group(0)[1:].lower()
        for m in _COMMAND.finditer(fragment)
        if m.group(0)[1:].lower() in _GREEK
    }


def _clean(fragment: str) -> str:
    """Strip textual wrappers, environment markers, and remaining LaTeX commands."""
    fragment = _TEXT_WRAPPER.sub(" ", fragment)
    fragment = re.sub(r"\\(?:begin|end)\{[^}]*\}", " ", fragment)
    fragment = _COMMAND.sub(" ", fragment)
    return fragment


def _symbols(fragment: str) -> set[str]:
    """All variable-like symbols in a single math fragment."""
    symbols = _greek_symbols(fragment)
    cleaned = _clean(fragment)

    def _record_subscript(match: re.Match[str]) -> str:
        symbols.add(f"{match.group(1)}_{match.group(2)}")
        return " "

    cleaned = _SUBSCRIPT.sub(_record_subscript, cleaned)
    symbols.update(m.group(0) for m in _LETTER.finditer(cleaned))
    return symbols


def _introduced(fragment: str) -> set[str]:
    """Variables that appear as the simple left-hand side of an assignment."""
    introduced: set[str] = set()
    for match in _ASSIGN.finditer(fragment):
        token = match.group(1)
        if token.startswith("\\"):
            name = token[1:].lower()
            if name in _GREEK:
                introduced.add(name)
        else:
            sub = _SUBSCRIPT.match(token)
            introduced.add(f"{sub.group(1)}_{sub.group(2)}" if sub else token)
    return introduced


def parse_step_symbols(text: str) -> tuple[set[str], set[str]]:
    """Parse ``(introduced, referenced)`` mathematical symbols from one step.

    ``referenced`` is every variable appearing in a math region; ``introduced`` is
    the subset that is defined via an assignment (the left-hand side of ``=``).
    """
    referenced: set[str] = set()
    introduced: set[str] = set()
    for region in _math_regions(text):
        referenced |= _symbols(region)
        introduced |= _introduced(region)
    # An assignment LHS is only "introduced" if it is also a recognised symbol.
    introduced &= referenced
    return introduced, referenced


def math_dependency_edges(
    steps: Sequence[str],
) -> list[tuple[int, int, str]]:
    """Return dependency edges ``(source_step, target_step, shared_symbol)``.

    For every symbol referenced in step ``j``, link the nearest earlier step that
    supplies it: preferring the most recent step that *introduced* the symbol, and
    otherwise the most recent step that *referenced* it. Only the nearest
    antecedent per symbol is linked, keeping the DAG sparse.
    """
    parsed = [parse_step_symbols(text) for text in steps]
    edges: list[tuple[int, int, str]] = []
    for j in range(len(steps)):
        _, referenced_j = parsed[j]
        for symbol in sorted(referenced_j):
            source = _nearest_antecedent(parsed, j, symbol)
            if source is not None:
                edges.append((source, j, symbol))
    return edges


def _nearest_antecedent(
    parsed: Sequence[tuple[set[str], set[str]]],
    j: int,
    symbol: str,
) -> int | None:
    introduced_source: int | None = None
    referenced_source: int | None = None
    for i in range(j - 1, -1, -1):
        introduced_i, referenced_i = parsed[i]
        if introduced_source is None and symbol in introduced_i:
            introduced_source = i
        if referenced_source is None and symbol in referenced_i:
            referenced_source = i
        if introduced_source is not None:
            break
    return introduced_source if introduced_source is not None else referenced_source


def build_math_dependency_graph(
    steps: Sequence[str],
    trace_id: str = "trace",
    *,
    edge_type: str = "elaborates",
    include_dependency_edges: bool = True,
) -> ReflectionGraph:
    """Build a variable-dependency :class:`ReflectionGraph` from step texts.

    Node ``utility_score`` is uniform (``1.0``) so that node necessity is a pure
    dependency-topology signal with no label leakage. A sequential temporal
    backbone (step ``i`` to ``i+1``) guarantees connectivity; math-dependency
    edges are added on top, and step 0 is frozen as the graph source.

    Setting ``include_dependency_edges=False`` yields the temporal backbone alone,
    which serves as the positional control when evaluating whether the
    variable-dependency edges add signal beyond step order.
    """
    graph = ReflectionGraph(trace_id)
    node_ids: list[str] = []
    for index, text in enumerate(steps):
        node_id = node_id_for(trace_id, index)
        graph.add_node(
            ReflectionNode(
                node_id=node_id,
                trace_id=trace_id,
                step_index=index,
                taxonomy_label="MATH_STEP",
                utility_score=1.0,
                structural_influence=0.0,
                content=text,
            )
        )
        node_ids.append(node_id)

    for position in range(len(node_ids) - 1):
        graph.add_edge(
            node_ids[position], node_ids[position + 1], edge_type, weight=1.0, quality=1.0
        )

    if include_dependency_edges:
        for source, target, _symbol in math_dependency_edges(steps):
            source_id, target_id = node_ids[source], node_ids[target]
            if not graph.has_edge(source_id, target_id):
                graph.add_edge(source_id, target_id, edge_type, weight=1.0, quality=1.0)

    if node_ids:
        graph.freeze_sources([node_ids[0]])
    return graph
