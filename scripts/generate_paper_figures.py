"""Generate paper figures for downstream filtering and format-sensitivity analyses."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUTPUT_DIR = Path("outputs/downstream_comparison_v1/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PALETTE = {
    "fma": "#0072B2",
    "position": "#009E73",
    "random": "#999999",
    "span": "#E69F00",
    "taxonomy": "#CC79A7",
    "prm": "#56B4E9",
    "prm_length": "#D55E00",
}

plt.rcParams.update(
    {
        "font.size": 9,
        "font.family": "sans-serif",
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.titlesize": 10,
    }
)


def load_report(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_bootstrap(path: str) -> dict:
    return load_report(path)["bootstrap_ci"]


def with_bootstrap_aliases(bootstrap: dict, aliases: dict[str, str]) -> dict:
    """Expose renamed methods without rewriting historical report artifacts."""
    normalized = dict(bootstrap)
    for current_name, stored_name in aliases.items():
        if current_name not in normalized and stored_name in normalized:
            normalized[current_name] = normalized[stored_name]
    return normalized


def ci_errors(bootstrap: dict, methods: list[str], ratios: list[str]) -> list[list[float]]:
    lows = []
    highs = []
    for method in methods:
        for ratio in ratios:
            payload = bootstrap[method][ratio]
            mean = float(payload["mean"])
            lows.append(max(0.0, mean - float(payload["ci_low"])))
            highs.append(max(0.0, float(payload["ci_high"]) - mean))
    return [lows, highs]


def plot_filtering_comparison() -> None:
    """Bar chart: GSM8K filtering accuracy by method and keep ratio."""
    report = load_report("outputs/downstream_comparison_v1/report/comparison_report.json")
    bootstrap = load_bootstrap("outputs/downstream_comparison_v1/report/statistical_report.json")
    acc = report["accuracy_by_method_and_ratio"]

    methods = ["fma_ciu", "random_trial0", "span_length", "taxonomy_prior"]
    labels = ["FMA (masking)", "Random", "Span Length", "Taxonomy Prior"]
    ratios = ["keep_0.25", "keep_0.50", "keep_0.75"]
    ratio_labels = ["25% kept", "50% kept", "75% kept"]

    x = np.arange(len(ratio_labels))
    width = 0.2

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    colors = [PALETTE["fma"], PALETTE["random"], PALETTE["span"], PALETTE["taxonomy"]]
    for i, (method, label) in enumerate(zip(methods, labels)):
        vals = [acc[method].get(ratio, 0.0) for ratio in ratios]
        bars = ax.bar(
            x + i * width - 1.5 * width,
            vals,
            width,
            label=label,
            color=colors[i],
            yerr=ci_errors(bootstrap, [method], ratios),
            capsize=3,
            error_kw={"elinewidth": 0.9, "capthick": 0.9, "ecolor": "#222222"},
        )
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f"{val:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_ylabel("Filtering accuracy")
    ax.set_title("GSM8K filtering with 95% bootstrap intervals (n=1319)")
    ax.set_xticks(x)
    ax.set_xticklabels(ratio_labels)
    ax.legend(loc="lower right")
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.3)

    path = OUTPUT_DIR / "filtering_accuracy_comparison.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_position_stratified() -> None:
    """Bar chart: accuracy by step position bin."""
    report = json.loads(
        Path("outputs/downstream_comparison_v1/position_stratified_report.json").read_text(
            encoding="utf-8"
        )
    )

    bins = ["early", "middle", "late"]
    bin_labels = ["Early (0-33%)", "Middle (33-67%)", "Late (67-100%)"]
    fma_vals = [report["fma_stratified"][bin_name]["keep_0.50"] for bin_name in bins]
    pos_vals = [report["baseline_position"][bin_name]["keep_0.50"] for bin_name in bins]

    x = np.arange(len(bins))
    width = 0.35

    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    bars1 = ax.bar(
        x - width / 2,
        fma_vals,
        width,
        label="FMA (masking CIU)",
        color=PALETTE["fma"],
    )
    bars2 = ax.bar(
        x + width / 2,
        pos_vals,
        width,
        label="Position oracle",
        color=PALETTE["position"],
    )

    for bars, vals in [(bars1, fma_vals), (bars2, pos_vals)]:
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f"{val:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_ylabel("Accuracy at 50% kept")
    ax.set_title("GSM8K position-stratified filtering (n=1319)")
    ax.set_xticks(x)
    ax.set_xticklabels(bin_labels)
    ax.legend()
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", alpha=0.3)

    path = OUTPUT_DIR / "position_stratified.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_prm_comparison() -> None:
    """Bar chart: FMA vs perplexity PRM proxies and baselines."""
    report = load_report(
        "outputs/downstream_comparison_v1/prm_comparison/report/comparison_report.json"
    )
    bootstrap = load_bootstrap(
        "outputs/downstream_comparison_v1/prm_comparison/report/statistical_report.json"
    )
    bootstrap = with_bootstrap_aliases(
        bootstrap,
        {
            "perplexity_heuristic": "prm_frozen",
            "perplexity_length_calibrated": "prm_length_calibrated",
        },
    )
    acc = report["accuracy_by_method_and_ratio"]

    methods = [
        "relative_position",
        "fma_ciu",
        "perplexity_heuristic",
        "perplexity_length_calibrated",
        "random_trial0",
        "taxonomy_prior",
    ]
    labels = [
        "Position",
        "FMA",
        "Perplexity\nproxy",
        "Perplexity\nlength-cal.",
        "Random",
        "Taxonomy\nprior",
    ]
    ratios = ["keep_0.25", "keep_0.50", "keep_0.75"]
    ratio_labels = ["25% kept", "50% kept", "75% kept"]

    x = np.arange(len(ratio_labels))
    width = 0.13
    colors = [
        PALETTE["position"],
        PALETTE["fma"],
        PALETTE["prm"],
        PALETTE["prm_length"],
        PALETTE["random"],
        PALETTE["taxonomy"],
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (method, label) in enumerate(zip(methods, labels)):
        vals = [acc.get(method, {}).get(ratio, 0.0) for ratio in ratios]
        offset = (i - 2.5) * width
        bars = ax.bar(
            x + offset,
            vals,
            width,
            label=label,
            color=colors[i],
            yerr=ci_errors(bootstrap, [method], ratios),
            capsize=2,
            error_kw={"elinewidth": 0.8, "capthick": 0.8, "ecolor": "#222222"},
        )
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f"{val:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_ylabel("Filtering accuracy")
    ax.set_title("GSM8K: FMA, perplexity proxies, and baselines (n=100)")
    ax.set_xticks(x)
    ax.set_xticklabels(ratio_labels)
    ax.legend(ncol=3, loc="lower right")
    ax.set_ylim(0, 1.15)
    ax.grid(axis="y", alpha=0.3)

    path = OUTPUT_DIR / "prm_comparison.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_task_comparison() -> None:
    """Side-by-side: GSM8K filtering and HotpotQA answer-format sensitivity."""
    gsm8k = load_report("outputs/downstream_comparison_v1/report/comparison_report.json")
    gsm8k_bootstrap = load_bootstrap(
        "outputs/downstream_comparison_v1/report/statistical_report.json"
    )
    hotpotqa = load_report(
        "outputs/downstream_comparison_v1/hotpotqa/report/comparison_report.json"
    )
    hotpotqa_bootstrap = load_bootstrap(
        "outputs/downstream_comparison_v1/hotpotqa/report/statistical_report.json"
    )

    methods = ["fma_ciu", "random_trial0", "span_length", "taxonomy_prior"]
    labels = ["FMA", "Random", "Span Len", "Prior"]
    colors = [PALETTE["fma"], PALETTE["random"], PALETTE["span"], PALETTE["taxonomy"]]
    ratio = "keep_0.50"

    panels = [
        (gsm8k, gsm8k_bootstrap, "GSM8K filtering (n=1319)"),
        (hotpotqa, hotpotqa_bootstrap, "HotpotQA format sensitivity (n=500)"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.0), sharey=True)

    for ax, (report, bootstrap, title) in zip(axes, panels):
        acc = report["accuracy_by_method_and_ratio"]
        vals = [acc.get(method, {}).get(ratio, 0.0) for method in methods]
        bars = ax.bar(
            labels,
            vals,
            color=colors,
            width=0.6,
            yerr=ci_errors(bootstrap, methods, [ratio]),
            capsize=3,
            error_kw={"elinewidth": 0.9, "capthick": 0.9, "ecolor": "#222222"},
        )
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f"{val:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        ax.set_title(title)
        ax.set_ylabel("Accuracy at 50% kept")
        ax.set_ylim(0, 1.1)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Filtering accuracy and answer-format dependency")
    fig.tight_layout()

    path = OUTPUT_DIR / "task_comparison.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


if __name__ == "__main__":
    plot_filtering_comparison()
    plot_position_stratified()
    plot_prm_comparison()
    plot_task_comparison()
    print("All figures generated.")
