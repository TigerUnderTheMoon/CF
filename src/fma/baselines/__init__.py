"""Baseline families for step-level importance scoring.

Provides 6 families of baseline methods for comparison against SC-FMA:
  A. Gradient Attribution — Gradient×Input, Integrated Gradients
  C. Shapley — Monte Carlo Shapley value over reasoning steps
  D. LLM-as-Judge — Heuristic-based step scoring (no API required)
  E. Surprisal — Token probability / entropy-based importance
  F. Oracle — Ground truth step-level labels from annotated data
"""

from .gradient_attribution import (
    GradientAttributionConfig,
    attention_rollout_scores,
    compute_ci_from_attribution,
    gradient_input_scores,
)
from .oracle_baselines import (
    compute_oracle_step_scores,
    linear_oracle_ensemble,
    load_oracle_labels,
)
from .shapley import (
    ShapleyConfig,
    compute_shapley_step_scores,
)
from .surprisal_baselines import (
    entropic_step_scores,
    surprisal_step_scores,
)

__all__ = [
    "GradientAttributionConfig",
    "ShapleyConfig",
    "attention_rollout_scores",
    "compute_ci_from_attribution",
    "compute_oracle_step_scores",
    "compute_shapley_step_scores",
    "entropic_step_scores",
    "gradient_input_scores",
    "linear_oracle_ensemble",
    "load_oracle_labels",
    "surprisal_step_scores",
]
