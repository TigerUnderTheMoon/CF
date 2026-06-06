"""Plots for Phase 4 functional-validity diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from fma.eval.counterfactual_attribution import (
    CounterfactualAblationResult,
    NecessityScore,
    RedundancyAnalysis,
)
from fma.eval.attribution_utility_correlation import utility_quality
from fma.eval.utility_annotation import UtilityAnnotation, UtilityLabel
from fma.types import ReflectionCategory


UTILITY_COLORS: dict[UtilityLabel, str] = {
    UtilityLabel.HELPFUL: "#4C78A8",
    UtilityLabel.HARMFUL: "#E45756",
    UtilityLabel.NEUTRAL: "#72B7B2",
    UtilityLabel.SPURIOUS: "#F58518",
}
INTERVENTION_COLORS: dict[str, str] = {
    "DELETE": "#4C78A8",
    "SHUFFLE": "#F58518",
    "REPLACE": "#E45756",
    "TRUNCATE": "#72B7B2",
    "CONTRADICT": "#54A24B",
    "UNKNOWN": "#6B7280",
}


def plot_utility_distribution(
    annotations: Sequence[UtilityAnnotation],
    save_path: str | Path = Path("outputs") / "figures" / "utility_distribution.png",
) -> None:
    """Stacked bar chart for utility-label proportions."""
    counts = Counter(annotation.utility for annotation in annotations)
    total = len(annotations)
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 4))
    left = 0.0
    if total:
        for label in UtilityLabel:
            width = counts[label] / total
            ax.barh(["utility"], [width], left=left, color=UTILITY_COLORS[label], label=label.value)
            left += width
        ax.set_xlim(0.0, 1.0)
        ax.set_xlabel("Share of annotations")
        ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.35), fontsize=8)
    else:
        ax.text(0.5, 0.5, "No utility annotations", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Utility Distribution")
    fig.tight_layout()
    _save(fig, save_path)


def plot_degradation_heatmap(
    annotations: Sequence[UtilityAnnotation],
    save_path: str | Path = Path("outputs") / "figures" / "degradation_heatmap.png",
) -> None:
    """Heatmap of mean degradation by intervention and reflection category."""
    interventions = sorted({annotation.intervention_type or "unknown" for annotation in annotations})
    categories = sorted({annotation.reflection_category for annotation in annotations})
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for annotation in annotations:
        grouped[(annotation.intervention_type or "unknown", annotation.reflection_category)].append(
            annotation.degradation_score
        )

    matrix = np.zeros((len(interventions), len(categories)), dtype=float)
    for row, intervention in enumerate(interventions):
        for col, category in enumerate(categories):
            values = grouped.get((intervention, category), [])
            matrix[row, col] = float(np.mean(values)) if values else 0.0

    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    if interventions and categories:
        image = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=0.0, vmax=max(1.0, float(np.max(matrix))))
        ax.set_xticks(np.arange(len(categories)))
        ax.set_xticklabels(categories, rotation=35, ha="right")
        ax.set_yticks(np.arange(len(interventions)))
        ax.set_yticklabels(interventions)
        ax.set_xlabel("Reflection category")
        ax.set_ylabel("Intervention type")
        fig.colorbar(image, ax=ax, label="Mean degradation")
    else:
        ax.text(0.5, 0.5, "No degradation samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Degradation Heatmap")
    fig.tight_layout()
    _save(fig, save_path)


def plot_attribution_utility_scatter(
    annotations: Sequence[UtilityAnnotation],
    save_path: str | Path = Path("outputs") / "figures" / "attribution_utility_scatter.png",
) -> None:
    """Scatter plot of annotation confidence against observed utility quality."""
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    if annotations:
        for label in UtilityLabel:
            subset = [annotation for annotation in annotations if annotation.utility is label]
            if not subset:
                continue
            ax.scatter(
                [annotation.annotation_confidence for annotation in subset],
                [utility_quality(annotation) for annotation in subset],
                color=UTILITY_COLORS[label],
                label=label.value,
                alpha=0.75,
                s=36,
            )
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.05, 1.05)
        ax.set_xlabel("Annotation confidence")
        ax.set_ylabel("Observed utility quality")
        ax.legend(fontsize=8, loc="best")
    else:
        ax.text(0.5, 0.5, "No attribution samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Attribution Confidence and Utility")
    fig.tight_layout()
    _save(fig, save_path)


def plot_utility_by_category(
    annotations: Sequence[UtilityAnnotation],
    save_path: str | Path = Path("outputs") / "figures" / "utility_by_category.png",
) -> None:
    """Grouped bar chart of utility-label ratios by category."""
    enum_categories = [category.name for category in ReflectionCategory]
    extra_categories = sorted(
        {
            annotation.reflection_category
            for annotation in annotations
            if annotation.reflection_category not in enum_categories
        }
    )
    categories = [*enum_categories, *extra_categories]
    grouped: dict[str, Counter[UtilityLabel]] = defaultdict(Counter)
    for annotation in annotations:
        grouped[annotation.reflection_category][annotation.utility] += 1

    _apply_style()
    fig, ax = plt.subplots(figsize=(11, 6))
    if categories:
        x_values = np.arange(len(categories))
        width = 0.18
        offsets = np.linspace(-1.5 * width, 1.5 * width, len(UtilityLabel))
        for offset, label in zip(offsets, UtilityLabel, strict=True):
            values = []
            for category in categories:
                total = sum(grouped[category].values())
                values.append(grouped[category][label] / total if total else 0.0)
            ax.bar(x_values + offset, values, width=width, color=UTILITY_COLORS[label], label=label.value)
        ax.set_xticks(x_values)
        ax.set_xticklabels(categories, rotation=35, ha="right")
        ax.set_ylim(0.0, 1.0)
        ax.set_ylabel("Share within category")
        ax.legend(fontsize=8, loc="best")
    else:
        ax.text(0.5, 0.5, "No category utility samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Utility by Category")
    fig.tight_layout()
    _save(fig, save_path)


def plot_validity_suite(
    annotations: Sequence[UtilityAnnotation],
    output_dir: str | Path = Path("outputs") / "figures",
) -> None:
    """Write all Phase 4 validity plots."""
    figure_dir = Path(output_dir)
    plot_utility_distribution(annotations, figure_dir / "utility_distribution.png")
    plot_degradation_heatmap(annotations, figure_dir / "degradation_heatmap.png")
    plot_attribution_utility_scatter(annotations, figure_dir / "attribution_utility_scatter.png")
    plot_utility_by_category(annotations, figure_dir / "utility_by_category.png")


def plot_necessity_distribution(
    necessity_scores: Sequence[NecessityScore | Mapping[str, Any]],
    save_path: str | Path = Path("outputs") / "figures" / "necessity_distribution.png",
) -> None:
    """Histogram of raw necessity scores."""
    scores = [_number(_field(score, "necessity")) for score in necessity_scores]
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 4))
    if scores:
        bins = min(20, max(5, len(scores) // 25 or 5))
        ax.hist(scores, bins=bins, color="#4C78A8", edgecolor="white")
        ax.set_xlabel("Necessity")
        ax.set_ylabel("Count")
    else:
        ax.text(0.5, 0.5, "No necessity samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Necessity Distribution")
    fig.tight_layout()
    _save(fig, save_path)


def plot_faithfulness_scatter(
    necessity_scores: Sequence[NecessityScore | Mapping[str, Any]],
    annotations: Sequence[UtilityAnnotation],
    save_path: str | Path = Path("outputs") / "figures" / "faithfulness_scatter.png",
) -> None:
    """Scatter plot of attribution score vs. necessity, colored by intervention type."""
    annotation_by_key = {
        (annotation.trace_id, annotation.reflection_idx): annotation
        for annotation in annotations
    }
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    if necessity_scores:
        grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for score in necessity_scores:
            trace_id = str(_field(score, "trace_id"))
            step_idx = int(_field(score, "step_idx"))
            annotation = annotation_by_key.get((trace_id, step_idx))
            intervention = annotation.intervention_type if annotation else None
            grouped[intervention or "unknown"].append(
                (
                    _number(_field(score, "attribution_score")),
                    _number(_field(score, "necessity")),
                )
            )
        for intervention, values in sorted(grouped.items()):
            ax.scatter(
                [x for x, _ in values],
                [y for _, y in values],
                color=_color_for_label(intervention),
                label=intervention,
                alpha=0.7,
                s=28,
            )
        ax.set_xlabel("Attribution score")
        ax.set_ylabel("Necessity")
        ax.legend(fontsize=8, loc="best")
    else:
        ax.text(0.5, 0.5, "No faithfulness samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Faithfulness Scatter")
    fig.tight_layout()
    _save(fig, save_path)


def plot_ablation_strategy_comparison(
    ablation_results: Sequence[CounterfactualAblationResult | Mapping[str, Any]],
    save_path: str | Path = Path("outputs") / "figures" / "ablation_strategy_comparison.png",
) -> None:
    """Bar chart of mean delta utility by ablation strategy."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for result in ablation_results:
        grouped[str(_field(result, "strategy", "unknown"))].append(_number(_field(result, "delta_utility")))

    labels = sorted(grouped)
    means = [float(np.mean(grouped[label])) for label in labels]
    errors = [float(np.std(grouped[label])) for label in labels]
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))
    if labels:
        x_values = np.arange(len(labels))
        ax.bar(x_values, means, yerr=errors, color="#F58518", capsize=4)
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.set_ylabel("Mean delta utility")
    else:
        ax.text(0.5, 0.5, "No ablation samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Ablation Strategy Comparison")
    fig.tight_layout()
    _save(fig, save_path)


def plot_redundancy_heatmap(
    annotations: Sequence[UtilityAnnotation],
    necessity_scores: Sequence[NecessityScore | Mapping[str, Any]],
    redundancy: Sequence[RedundancyAnalysis | Mapping[str, Any]],
    save_path: str | Path = Path("outputs") / "figures" / "redundancy_heatmap.png",
) -> None:
    """Heatmap of attribution type versus necessity quartile."""
    necessity_by_key = {
        (str(_field(score, "trace_id")), int(_field(score, "step_idx"))): _number(
            _field(score, "necessity_normalized")
        )
        for score in necessity_scores
    }
    redundancy_by_trace = {
        str(_field(result, "trace_id")): _number(_field(result, "redundancy_ratio"))
        for result in redundancy
    }
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for annotation in annotations:
        necessity = necessity_by_key.get((annotation.trace_id, annotation.reflection_idx))
        if necessity is None:
            continue
        grouped[annotation.attribution_type or "none"][_quartile_label(necessity)].append(
            redundancy_by_trace.get(annotation.trace_id, 0.0)
        )

    attribution_types = sorted(grouped)
    quartiles = ["q1", "q2", "q3", "q4"]
    matrix = np.zeros((len(attribution_types), len(quartiles)), dtype=float)
    for row, attribution_type in enumerate(attribution_types):
        for col, quartile in enumerate(quartiles):
            values = grouped[attribution_type].get(quartile, [])
            matrix[row, col] = float(np.mean(values)) if values else 0.0

    _apply_style()
    fig, ax = plt.subplots(figsize=(9, 5))
    if attribution_types:
        image = ax.imshow(matrix, aspect="auto", cmap="Purples", vmin=0.0, vmax=max(1.0, float(np.max(matrix))))
        ax.set_yticks(np.arange(len(attribution_types)))
        ax.set_yticklabels(attribution_types)
        ax.set_xticks(np.arange(len(quartiles)))
        ax.set_xticklabels(quartiles)
        ax.set_xlabel("Necessity quartile")
        ax.set_ylabel("Attribution type")
        fig.colorbar(image, ax=ax, label="Mean redundancy ratio")
    else:
        ax.text(0.5, 0.5, "No redundancy samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Redundancy Heatmap")
    fig.tight_layout()
    _save(fig, save_path)


def plot_minimal_subset_curve(
    curves: Sequence[Mapping[str, Any]],
    save_path: str | Path = Path("outputs") / "figures" / "minimal_subset_curve.png",
) -> None:
    """Plot the average greedy retained-utility curve by steps removed."""
    grouped: dict[int, list[float]] = defaultdict(list)
    for row in curves:
        grouped[int(_field(row, "steps_removed", 0))].append(_number(_field(row, "utility_retained")))

    labels = sorted(grouped)
    means = [float(np.mean(grouped[label])) for label in labels]
    _apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    if labels:
        ax.plot(labels, means, marker="o", color="#54A24B")
        ax.set_xlabel("Steps removed")
        ax.set_ylabel("Mean retained utility")
    else:
        ax.text(0.5, 0.5, "No minimal-subset samples", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Minimal Subset Curve")
    fig.tight_layout()
    _save(fig, save_path)


def plot_counterfactual_suite(
    ablation_results: Sequence[CounterfactualAblationResult | Mapping[str, Any]],
    necessity_scores: Sequence[NecessityScore | Mapping[str, Any]],
    annotations: Sequence[UtilityAnnotation],
    redundancy: Sequence[RedundancyAnalysis | Mapping[str, Any]],
    curves: Sequence[Mapping[str, Any]],
    output_dir: str | Path = Path("outputs") / "figures",
) -> None:
    """Write all Phase 5 counterfactual attribution plots."""
    figure_dir = Path(output_dir)
    plot_necessity_distribution(necessity_scores, figure_dir / "necessity_distribution.png")
    plot_faithfulness_scatter(necessity_scores, annotations, figure_dir / "faithfulness_scatter.png")
    plot_ablation_strategy_comparison(ablation_results, figure_dir / "ablation_strategy_comparison.png")
    plot_redundancy_heatmap(annotations, necessity_scores, redundancy, figure_dir / "redundancy_heatmap.png")
    plot_minimal_subset_curve(curves, figure_dir / "minimal_subset_curve.png")


def _field(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _color_for_label(label: str) -> str:
    normalized = str(label).strip().upper().replace("-", "_")
    return INTERVENTION_COLORS.get(normalized, "#6B7280")


def _quartile_label(value: float) -> str:
    if value < 0.25:
        return "q1"
    if value < 0.5:
        return "q2"
    if value < 0.75:
        return "q3"
    return "q4"


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )


def _save(fig: plt.Figure, save_path: str | Path) -> None:
    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    plt.close(fig)


__all__ = [
    "plot_ablation_strategy_comparison",
    "plot_attribution_utility_scatter",
    "plot_counterfactual_suite",
    "plot_degradation_heatmap",
    "plot_faithfulness_scatter",
    "plot_minimal_subset_curve",
    "plot_necessity_distribution",
    "plot_redundancy_heatmap",
    "plot_utility_by_category",
    "plot_utility_distribution",
    "plot_validity_suite",
]
