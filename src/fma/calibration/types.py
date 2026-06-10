"""Type definitions for the Structural Calibration Module (SC-FMA)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BottleneckConstraint:
    node_index: int
    floor_weight: float = 0.01


@dataclass(frozen=True)
class CalibratedWeights:
    weights: tuple[float, ...]
    sample_id: str
    method: str = "scfma_qp"
    metadata: dict[str, Any] | None = None

    def to_list(self) -> list[float]:
        return list(self.weights)


@dataclass(frozen=True)
class CalibrationResult:
    weights: list[CalibratedWeights]
    loss_fidelity: float
    loss_structure: float
    loss_redundancy: float
    loss_total: float
    alpha: float
    beta: float
    gamma: float
    iteration_count: int
    converged: bool
    metadata: dict[str, Any] | None = None
