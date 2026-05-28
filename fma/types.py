"""Shared Phase 2 dataclasses for taxonomy-driven FMA evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional

import numpy as np


class ReflectionCategory(Enum):
    DECOMPOSITION = auto()
    VERIFICATION = auto()
    ERROR_CORRECTION = auto()
    BACKTRACKING = auto()
    UNCERTAINTY_MONITORING = auto()
    PLANNING = auto()
    CONSTRAINT_TRACKING = auto()
    RETRIEVAL = auto()
    OTHER = auto()


@dataclass(frozen=True)
class ReflectionTrace:
    trace_id: str
    reflection_text: str
    task_id: str
    task_difficulty: int
    intervention_magnitude: float
    locality_score: float


@dataclass(frozen=True)
class ReflectionAnnotation:
    category: ReflectionCategory
    confidence: float
    rationale: str


@dataclass(frozen=True)
class AttributionRecord:
    trace_id: str
    attribution_score: float
    utility_delta: float
    intervention_type: str
    is_local: bool


@dataclass(frozen=True)
class StratifiedInput:
    records: List[AttributionRecord]
    annotations: Dict[str, ReflectionAnnotation]
    traces: Optional[Dict[str, ReflectionTrace]] = None


__all__ = [
    "Any",
    "AttributionRecord",
    "Dict",
    "List",
    "Optional",
    "ReflectionAnnotation",
    "ReflectionCategory",
    "ReflectionTrace",
    "StratifiedInput",
    "np",
]
