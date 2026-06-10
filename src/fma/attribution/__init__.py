"""Phase 5 attribution computation interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from fma.attribution.engine import IncrementalAttributionEngine, ParallelAttributionEngine


@dataclass(frozen=True)
class AttributionResult:
    """Result container for a local functional attribution score."""

    target_id: str
    score: float
    phase: str = "phase5"
    metadata: Mapping[str, Any] = field(default_factory=dict)


__all__ = [
    "AttributionResult",
    "IncrementalAttributionEngine",
    "ParallelAttributionEngine",
]
