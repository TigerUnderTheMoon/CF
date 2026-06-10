"""Phase 7 diagnostic interfaces for redundancy, compensation, bottlenecks, and resilience."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class DiagnosticResult:
    """Container for a Phase 7 diagnostic summary."""

    name: str
    value: float | None = None
    status: str = "planned"
    metadata: Mapping[str, Any] = field(default_factory=dict)


__all__ = ["DiagnosticResult"]
