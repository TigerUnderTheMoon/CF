"""Phase 5 attribution computation interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from fma.attribution.engine import IncrementalAttributionEngine, ParallelAttributionEngine


@dataclass(frozen=True)
class AttributionResult:
    """Skeleton result for a local functional attribution score."""

    target_id: str
    score: float
    phase: str = "phase5"
    metadata: Mapping[str, Any] = field(default_factory=dict)


def compute_attribution(
    traces: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
) -> list[AttributionResult]:
    """TODO: implement Phase 5 attribution computation."""
    raise NotImplementedError("Phase 5 attribution computation is not implemented yet.")


__all__ = [
    "AttributionResult",
    "IncrementalAttributionEngine",
    "ParallelAttributionEngine",
    "compute_attribution",
]
