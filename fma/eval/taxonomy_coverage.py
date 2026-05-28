"""Coverage diagnostics for reflection taxonomy distributions."""

from __future__ import annotations

import math
import warnings as warning_module
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from fma.generation import ReflectionChain, ReflectionStyle


@dataclass(frozen=True)
class TaxonomyReport:
    taxonomy_distribution: dict[str, int]
    taxonomy_normalized: dict[str, float]
    entropy: float
    imbalance_ratio: float
    collapsed: bool
    rare_categories: list[str]
    total_traces: int
    total_reflections: int
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "taxonomy_distribution": self.taxonomy_distribution,
            "taxonomy_normalized": self.taxonomy_normalized,
            "entropy": self.entropy,
            "imbalance_ratio": self.imbalance_ratio,
            "collapsed": self.collapsed,
            "rare_categories": self.rare_categories,
            "total_traces": self.total_traces,
            "total_reflections": self.total_reflections,
            "warnings": self.warnings,
        }


class TaxonomyCoverageAnalyzer:
    """Analyze balance, entropy, and collapse in reflection categories."""

    def analyze(self, traces: Sequence[ReflectionChain]) -> TaxonomyReport:
        counts = Counter()
        for trace in traces:
            counts.update(trace.categories())

        for style in ReflectionStyle:
            counts.setdefault(style.name, 0)

        total_reflections = sum(counts.values())
        normalized = {
            category: (count / total_reflections if total_reflections else 0.0)
            for category, count in sorted(counts.items())
        }
        positive_probs = [value for value in normalized.values() if value > 0.0]
        entropy = -sum(prob * math.log2(prob) for prob in positive_probs)
        dominant_ratio = max(normalized.values(), default=0.0)
        rare_categories = [
            category
            for category, ratio in normalized.items()
            if ratio < 0.05 and category != "CONTRADICTION"
        ]
        warnings: list[str] = []
        if dominant_ratio > 0.8:
            self._warn("taxonomy collapse detected", warnings)
        if entropy < 1.0:
            self._warn("low taxonomy diversity", warnings)

        return TaxonomyReport(
            taxonomy_distribution={category: counts[category] for category in sorted(counts)},
            taxonomy_normalized=normalized,
            entropy=float(entropy),
            imbalance_ratio=float(dominant_ratio),
            collapsed=dominant_ratio > 0.8,
            rare_categories=rare_categories,
            total_traces=len(traces),
            total_reflections=total_reflections,
            warnings=warnings,
        )

    @staticmethod
    def _warn(message: str, warnings: list[str]) -> None:
        warnings.append(message)
        warning_module.warn(message, RuntimeWarning, stacklevel=2)


__all__ = ["TaxonomyCoverageAnalyzer", "TaxonomyReport"]
