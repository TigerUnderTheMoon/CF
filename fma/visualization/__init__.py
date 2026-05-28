"""Visualization helpers for FMA reports."""

from fma.visualization.validity_plots import (
    plot_ablation_strategy_comparison,
    plot_attribution_utility_scatter,
    plot_counterfactual_suite,
    plot_degradation_heatmap,
    plot_faithfulness_scatter,
    plot_minimal_subset_curve,
    plot_necessity_distribution,
    plot_redundancy_heatmap,
    plot_utility_distribution,
    plot_validity_suite,
)
from fma.visualization.stratified_plots import (
    plot_category_distribution,
    plot_intervention_type_comparison,
    plot_locality_sensitivity,
    plot_locality_stress_scatter,
    plot_stability_scatter,
    plot_stability_histogram,
    plot_taxonomy_distribution,
    plot_utility_by_category,
)

__all__ = [
    "plot_ablation_strategy_comparison",
    "plot_category_distribution",
    "plot_attribution_utility_scatter",
    "plot_counterfactual_suite",
    "plot_degradation_heatmap",
    "plot_faithfulness_scatter",
    "plot_intervention_type_comparison",
    "plot_locality_sensitivity",
    "plot_locality_stress_scatter",
    "plot_minimal_subset_curve",
    "plot_necessity_distribution",
    "plot_redundancy_heatmap",
    "plot_stability_scatter",
    "plot_stability_histogram",
    "plot_taxonomy_distribution",
    "plot_utility_distribution",
    "plot_utility_by_category",
    "plot_validity_suite",
]
