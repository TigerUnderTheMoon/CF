"""Structural Calibration Module — SC-FMA core methodological contribution.

Transforms raw CIU estimates into structurally-calibrated supervision weights
via convex constrained optimization.
"""

from .optimizer import (
    SCULoss,
    scfma_calibrate,
    scfma_calibrate_ridge,
    scfma_calibrate_windowed,
)
from .projection import TopologyProjection, project_weights
from .types import BottleneckConstraint, CalibratedWeights, CalibrationResult

__all__ = [
    "BottleneckConstraint",
    "CalibratedWeights",
    "CalibrationResult",
    "SCULoss",
    "TopologyProjection",
    "project_weights",
    "scfma_calibrate",
    "scfma_calibrate_ridge",
    "scfma_calibrate_windowed",
]
