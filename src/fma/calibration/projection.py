"""Topology-constrained projection for SC-FMA.

Projects raw CIU vectors into a structurally-consistent subspace
using redundancy and bottleneck constraints from the reflection graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

EPSILON = 1e-10


@dataclass(frozen=True)
class TopologyProjection:
    fidelity_weight: float = 0.6
    structure_weight: float = 0.4
    redundancy_decay: float = 0.9
    bottleneck_amplification: float = 2.0

    def project(
        self,
        ciu: np.ndarray,
        necessity: np.ndarray,
        redundancy_matrix: np.ndarray,
        bottleneck_indices: set[int],
    ) -> np.ndarray:
        redundancy_matrix = np.asarray(redundancy_matrix, dtype=float)
        k = len(ciu)
        if k == 0:
            return np.array([], dtype=float)

        c = ciu / (np.linalg.norm(ciu) + EPSILON) if np.linalg.norm(ciu) > EPSILON else ciu
        n = necessity / (np.linalg.norm(necessity) + EPSILON) if np.linalg.norm(necessity) > EPSILON else necessity

        base = self.fidelity_weight * c + self.structure_weight * n

        if k > 1 and np.any(redundancy_matrix > 0):
            avg_redundancy = np.mean(redundancy_matrix, axis=1)
            avg_redundancy = avg_redundancy / (np.max(avg_redundancy) + EPSILON)
            redundancy_penalty = self.redundancy_decay * avg_redundancy * base
            base = base - redundancy_penalty
            base = np.maximum(base, EPSILON)

        for idx in bottleneck_indices:
            if 0 <= idx < k:
                base[idx] = base[idx] * self.bottleneck_amplification

        total = np.sum(base)
        if total < EPSILON:
            return np.ones(k) / k
        return base / total


def project_weights(
    ciu: np.ndarray,
    necessity: np.ndarray,
    redundancy_matrix: np.ndarray | None = None,
    bottleneck_indices: set[int] | None = None,
    fidelity_weight: float = 0.6,
    structure_weight: float = 0.4,
) -> np.ndarray:
    if redundancy_matrix is None:
        redundancy_matrix = np.zeros((len(ciu), len(ciu)))
    else:
        redundancy_matrix = np.asarray(redundancy_matrix, dtype=float)
    if bottleneck_indices is None:
        bottleneck_indices = set()

    proj = TopologyProjection(fidelity_weight=fidelity_weight, structure_weight=structure_weight)
    return proj.project(ciu, necessity, redundancy_matrix, bottleneck_indices)
