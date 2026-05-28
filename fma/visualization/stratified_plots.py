"""Matplotlib plots for stratified FMA reports."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from fma.generation import ReflectionStyle
from fma.types import ReflectionAnnotation, ReflectionCategory


LOGGER = logging.getLogger(__name__)
STYLE_COLORS: dict[str, str] = {
    ReflectionStyle.DECOMPOSITION.name: "#4C78A8",
    ReflectionStyle.VERIFICATION.name: "#F58518",
    ReflectionStyle.ERROR_CORRECTION.name: "#E45756",
    ReflectionStyle.BACKTRACKING.name: "#72B7B2",
    ReflectionStyle.PLANNING.name: "#54A24B",
    ReflectionStyle.CONSTRAINT_TRACKING.name: "#B279A2",
    ReflectionStyle.UNCERTAINTY_MONITORING.name: "#FF9DA6",
    ReflectionStyle.RETRIEVAL.name: "#9D755D",
    ReflectionCategory.OTHER.name: "#BAB0AC",
    "CONTRADICTION": "#D62728",
}


def plot_category_distribution(
    annotations: List[ReflectionAnnotation],
    save_path: str = "outputs/figures/category_dist.png",
) -> None:
    """Horizontal bar chart of category frequencies."""
    counts = Counter(annotation.category.name for annotation in annotations)
    for category in ReflectionCategory:
        if counts.get(category.name, 0) == 0:
            LOGGER.warning("Omitting category %s from plot because it has 0 samples.", category.name)

    labels = [name for name, count in sorted(counts.items()) if count > 0]
    values = [counts[name] for name in labels]
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if labels:
        colors = _colors_for_labels(labels)
        ax.barh(labels, values, color=colors)
        ax.set_xlabel("Frequency")
        ax.set_ylabel("Reflection category")
    else:
        ax.text(0.5, 0.5, "No category samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Reflection Category Distribution")
    fig.tight_layout()
    _save(fig, save_path)


def plot_utility_by_category(
    report: Dict[str, Any],
    save_path: str = "outputs/figures/utility_by_category.png",
) -> None:
    """Grouped bar chart: mean utility delta +- std error per category."""
    categories = _non_empty_categories(report)
    labels = [name for name, _ in categories]
    means = [_number(metrics.get("mean_utility_delta")) for _, metrics in categories]
    errors = [
        _std_error(metrics.get("utility_variance"), metrics.get("frequency"))
        for _, metrics in categories
    ]

    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if labels:
        x_values = np.arange(len(labels))
        ax.bar(x_values, means, yerr=errors, color=_colors_for_labels(labels), capsize=4)
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=35, ha="right")
        ax.set_ylabel("Mean utility delta")
    else:
        ax.text(0.5, 0.5, "No category samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Utility by Reflection Category")
    fig.tight_layout()
    _save(fig, save_path)


def plot_stability_scatter(
    report: Dict[str, Any],
    save_path: str = "outputs/figures/stability_scatter.png",
) -> None:
    """Scatter: attribution stability (x) vs. mean utility delta (y), colored by category, with jitter to avoid overlap."""
    categories = [
        (name, metrics)
        for name, metrics in _non_empty_categories(report)
        if metrics.get("attribution_consistency") is not None
        and metrics.get("mean_utility_delta") is not None
    ]

    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if categories:
        rng = np.random.default_rng(42)
        for idx, (name, metrics) in enumerate(categories):
            x_value = _number(metrics.get("attribution_consistency")) + float(rng.normal(0.0, 0.005))
            y_value = _number(metrics.get("mean_utility_delta")) + float(rng.normal(0.0, 0.005))
            ax.scatter(x_value, y_value, color=_color_for_label(name), label=name, s=80)
        ax.set_xlabel("Attribution stability")
        ax.set_ylabel("Mean utility delta")
        ax.legend(fontsize=8, loc="best")
    else:
        ax.text(0.5, 0.5, "No stability samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Attribution Stability and Utility")
    fig.tight_layout()
    _save(fig, save_path)


def plot_locality_sensitivity(
    report: Dict[str, Any],
    save_path: str = "outputs/figures/locality_sensitivity.png",
) -> None:
    """Dot plot: categories sorted by locality sensitivity score."""
    categories = [
        (name, metrics)
        for name, metrics in _non_empty_categories(report)
        if metrics.get("locality_sensitivity") is not None
    ]
    categories.sort(key=lambda item: _number(item[1].get("locality_sensitivity")))

    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if categories:
        labels = [name for name, _ in categories]
        values = [_number(metrics.get("locality_sensitivity")) for _, metrics in categories]
        y_values = np.arange(len(labels))
        ax.scatter(values, y_values, color=_colors_for_labels(labels), s=90)
        ax.set_yticks(y_values)
        ax.set_yticklabels(labels)
        ax.set_xlabel("Locality sensitivity")
    else:
        ax.text(0.5, 0.5, "No locality sensitivity samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Locality Sensitivity by Category")
    fig.tight_layout()
    _save(fig, save_path)


def plot_taxonomy_distribution(
    taxonomy_report: Dict[str, Any],
    save_path: str = "outputs/figures/taxonomy_distribution.png",
) -> None:
    """Vertical bar chart of taxonomy category counts."""
    counts = taxonomy_report.get("taxonomy_distribution", taxonomy_report)
    labels = [name for name, count in sorted(counts.items()) if int(count) > 0]
    values = [int(counts[name]) for name in labels]

    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if labels:
        x_values = np.arange(len(labels))
        ax.bar(x_values, values, color=_colors_for_labels(labels))
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=35, ha="right")
        ax.set_ylabel("Category count")
    else:
        ax.text(0.5, 0.5, "No taxonomy samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Taxonomy Distribution")
    fig.tight_layout()
    _save(fig, save_path)


def plot_intervention_type_comparison(
    records: List[Any],
    save_path: str = "outputs/figures/intervention_type_comparison.png",
) -> None:
    """Grouped bar chart comparing utility before and after by intervention type."""
    grouped: dict[str, dict[str, list[float]]] = {}
    for record in records:
        intervention = str(_field(record, "intervention_type", "unknown"))
        grouped.setdefault(intervention, {"before": [], "after": []})
        grouped[intervention]["before"].append(float(_field(record, "utility_before", 0.0)))
        grouped[intervention]["after"].append(float(_field(record, "utility_after", 0.0)))

    labels = sorted(grouped)
    before = [float(np.mean(grouped[label]["before"])) for label in labels]
    after = [float(np.mean(grouped[label]["after"])) for label in labels]

    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if labels:
        x_values = np.arange(len(labels))
        width = 0.38
        ax.bar(x_values - width / 2, before, width, label="utility_before", color="#4C78A8")
        ax.bar(x_values + width / 2, after, width, label="utility_after", color="#F58518")
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.set_ylabel("Mean utility")
        ax.legend()
    else:
        ax.text(0.5, 0.5, "No intervention samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Intervention Utility Comparison")
    fig.tight_layout()
    _save(fig, save_path)


def plot_locality_stress_scatter(
    results: List[Any],
    save_path: str = "outputs/figures/locality_stress_scatter.png",
) -> None:
    """Scatter plot of edit distance versus utility shift."""
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if results:
        intervention_types = sorted({str(_field(result, "intervention_type", "unknown")) for result in results})
        for intervention_type in intervention_types:
            subset = [
                result
                for result in results
                if str(_field(result, "intervention_type", "unknown")) == intervention_type
            ]
            x_values = [float(_field(result, "edit_distance", 0.0)) for result in subset]
            y_values = [float(_field(result, "utility_shift", 0.0)) for result in subset]
            ax.scatter(
                x_values,
                y_values,
                color=_color_for_label(intervention_type.upper()),
                label=intervention_type,
                alpha=0.8,
                s=60,
            )
        ax.set_xlabel("Edit distance")
        ax.set_ylabel("Utility shift")
        ax.legend(fontsize=8, loc="best")
    else:
        ax.text(0.5, 0.5, "No locality stress samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Locality Stress Response")
    fig.tight_layout()
    _save(fig, save_path)


def plot_stability_histogram(
    stability_scores: List[float],
    save_path: str = "outputs/figures/stability_histogram.png",
) -> None:
    """Histogram of bounded stability scores across trace batches."""
    scores = [float(score) for score in stability_scores if np.isfinite(float(score))]

    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if scores:
        ax.hist(scores, bins=min(12, max(3, len(scores))), color="#54A24B", edgecolor="white")
        ax.set_xlabel("Stability score")
        ax.set_ylabel("Batch count")
        ax.set_xlim(0.0, 1.0)
    else:
        ax.text(0.5, 0.5, "No stability scores", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Stability Score Distribution")
    fig.tight_layout()
    _save(fig, save_path)


def _non_empty_categories(report: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    per_category = report.get("per_category") or {}
    categories: list[tuple[str, dict[str, Any]]] = []
    for name, metrics in per_category.items():
        if not isinstance(metrics, dict):
            continue
        if int(metrics.get("frequency") or 0) == 0:
            LOGGER.warning("Omitting category %s from plot because it has 0 samples.", name)
            continue
        categories.append((name, metrics))
    return categories


def _std_error(variance: Any, frequency: Any) -> float:
    if variance is None or frequency is None or int(frequency) <= 0:
        return 0.0
    return float(np.sqrt(max(0.0, float(variance)) / int(frequency)))


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _colors(count: int) -> list[Any]:
    palette = plt.get_cmap("Set2", max(1, count))
    return [palette(index) for index in range(count)]


def _colors_for_labels(labels: list[str]) -> list[str]:
    return [_color_for_label(label) for label in labels]


def _color_for_label(label: str) -> str:
    normalized = str(label).strip().upper().replace("-", "_")
    return STYLE_COLORS.get(normalized, "#6B7280")


def _field(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )


def _save(fig: plt.Figure, save_path: str) -> None:
    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    plt.close(fig)
