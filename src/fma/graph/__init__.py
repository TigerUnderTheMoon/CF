"""Graph utilities for structural reflection attribution."""

from __future__ import annotations

from typing import Any

from fma.graph.interventions import GraphIntervention
from fma.graph.reflection_graph import (
    RemovalMode,
    ReflectionEdge,
    ReflectionGraph,
    ReflectionNode,
)


def __getattr__(name: str) -> Any:
    """Lazy-load engine exports to avoid circular imports with structural_attribution."""
    if name in {"GraphInterventionBatch", "GraphInterventionReport", "ParallelGraphInterventionEngine"}:
        from fma.graph import engine as _engine

        return getattr(_engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def run_structural_diagnostics(*args, **kwargs):
    """Lazy wrapper for Phase 6 structural diagnostics."""
    from fma.graph.diagnostics import run_structural_diagnostics as _run

    return _run(*args, **kwargs)


__all__ = [
    "GraphIntervention",
    "GraphInterventionBatch",
    "GraphInterventionReport",
    "ParallelGraphInterventionEngine",
    "RemovalMode",
    "ReflectionEdge",
    "ReflectionGraph",
    "ReflectionNode",
    "run_structural_diagnostics",
]
