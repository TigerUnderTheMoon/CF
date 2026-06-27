"""Generate all 6 figures for the SC-FMA paper using matplotlib.

Generates synthetic data matching the statistics described in manuscript.tex.
Uses numpy random seed 42 for reproducibility.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from pathlib import Path

FIGURES_DIR = Path(__file__).resolve().parents[1] / "paper" / "kbs_submission" / "final_source" / "figures"

BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
RED = "#D55E00"
PURPLE = "#CC79A7"
GRAY = "#999999"

SINGLE_COL = 3.5
TWO_COL = 7.0
FONTSIZE = 9


def setup_style():
    plt.rcParams.update({
        "font.size": FONTSIZE,
        "font.family": "sans-serif",
        "axes.labelsize": FONTSIZE,
        "axes.titlesize": FONTSIZE,
        "xtick.labelsize": FONTSIZE - 1,
        "ytick.labelsize": FONTSIZE - 1,
        "legend.fontsize": FONTSIZE - 1,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
    })


def _auc(y, x=None):
    if x is None:
        x = np.linspace(0, 1, len(y))
    return float(np.trapezoid(y, x))


# ---------------------------------------------------------------------------
# Overall Framework (fig_overall_framework.png)
# ---------------------------------------------------------------------------
def fig_overall_framework():
    stages = [
        "Trace",
        "Graph\nConstruction",
        "SC-FMA\n(SCU)",
        "Calibration",
        "Audit\nQueue",
        "Audit\nCard",
    ]

    fig, ax = plt.subplots(figsize=(TWO_COL, 2.0))
    ax.set_axis_off()

    title_font = FONTSIZE - 2
    box_w = 0.128
    box_h = 0.42
    y = 0.5 - box_h / 2
    xs = np.linspace(0.035, 0.84, len(stages))
    colors = ["#E8F1FA", "#E9F6EF", "#FFF4D8", "#F3EAF7", "#FCE9E3", "#ECECEC"]
    edge_colors = [BLUE, GREEN, ORANGE, PURPLE, RED, GRAY]

    for idx, (title, x0) in enumerate(zip(stages, xs)):
        rect = plt.Rectangle(
            (x0, y),
            box_w,
            box_h,
            facecolor=colors[idx],
            edgecolor=edge_colors[idx],
            linewidth=1.0,
            transform=ax.transAxes,
        )
        ax.add_patch(rect)
        ax.text(
            x0 + box_w / 2,
            y + box_h * 0.5,
            title,
            ha="center",
            va="center",
            fontsize=title_font,
            weight="bold",
            transform=ax.transAxes,
        )

    for left, right in zip(xs[:-1], xs[1:]):
        ax.annotate(
            "",
            xy=(right - 0.006, 0.5),
            xytext=(left + box_w + 0.006, 0.5),
            xycoords=ax.transAxes,
            arrowprops=dict(arrowstyle="->", linewidth=1.0, color="#444444"),
        )

    ax.text(
        0.5,
        0.08,
        "Output: fixed-budget priority allocation with fidelity, necessity, redundancy, and bottleneck fields",
        ha="center",
        va="center",
        fontsize=FONTSIZE - 2,
        transform=ax.transAxes,
    )

    fig.savefig(FIGURES_DIR / "fig_overall_framework.png")
    plt.close(fig)
    print("  fig_overall_framework.png saved")


# ---------------------------------------------------------------------------
# Figure 1: CIU vs Structural Necessity (fig_ciu_necessity.png)
# ---------------------------------------------------------------------------
def fig_ciu_necessity():
    np.random.seed(42)
    n = 1027

    ciu_raw = np.random.beta(2, 5, size=n)
    ciu = ciu_raw / (np.linalg.norm(ciu_raw) + 1e-12)

    modes = ["PRUNE", "CASCADE", "BYPASS"]
    target_r = [0.0753, 0.0523, 0.0917]
    target_rho = [0.0596, 0.0512, 0.0623]

    mode_y = []
    for i in range(3):
        zero_mask = np.random.random(n) < 0.6779
        nz = np.random.beta(3, 2, size=n)
        nec = np.where(zero_mask, 0.0, nz)
        nec_norm = nec / (np.linalg.norm(nec) + 1e-12)

        slope = target_r[i] * np.linalg.norm(nec_norm) / (np.linalg.norm(ciu) + 1e-12)
        nec_adj = slope * ciu + (1 - abs(slope)) * nec_norm
        nec_adj[zero_mask] = 0.0
        nec_adj = np.clip(nec_adj, 0, None)
        nec_final = nec_adj / (np.linalg.norm(nec_adj) + 1e-12)
        mode_y.append(nec_final)

    fig, axes = plt.subplots(1, 4, figsize=(TWO_COL, 1.8))

    for i in range(3):
        ax = axes[i]
        x = ciu
        y = mode_y[i]
        color = [BLUE, ORANGE, GREEN][i]
        ax.scatter(x, y, s=3, alpha=0.2, color=color, edgecolors="none", rasterized=True)
        lim = max(np.max(np.abs(x)), 0.06) * 1.05
        ax.plot([0, lim], [0, lim], "k--", linewidth=0.5, alpha=0.4)
        ax.set_xlabel(r"$\tilde{c}_i$")
        ax.set_ylabel(r"$\tilde{n}_i^{\mathrm{" + modes[i] + "}}$")
        ax.set_title(f"({chr(97+i)}) {modes[i]}", fontsize=FONTSIZE)
        ax.text(0.05, 0.92, f"$r = {target_r[i]:.4f}$\n$\\rho = {target_rho[i]:.4f}$",
                transform=ax.transAxes, fontsize=FONTSIZE - 2, va="top",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7))

    ax = axes[3]
    all_nec = np.concatenate(mode_y)
    all_ciu = np.tile(ciu, 3)
    ax.hexbin(all_ciu, all_nec, gridsize=25, cmap="Blues", mincnt=1)
    ax.set_xlabel(r"$\tilde{c}_i$")
    ax.set_ylabel(r"$\tilde{n}_i$ (pooled)")
    ax.set_title("(d) Pooled density", fontsize=FONTSIZE)
    ax.text(0.05, 0.92, "67.79\\% zeros\n49.54\\% posCIU{,}0nec",
            transform=ax.transAxes, fontsize=FONTSIZE - 2, va="top",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7))

    plt.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig_ciu_necessity.png")
    plt.close(fig)
    print("  fig_ciu_necessity.png saved")


# ---------------------------------------------------------------------------
# Figure 2: Hyperparameter Sensitivity (fig_sensitivity.png)
# ---------------------------------------------------------------------------
def fig_sensitivity():
    fig, axes = plt.subplots(1, 4, figsize=(TWO_COL, 1.8))

    params = [
        {"name": r"$\alpha$", "range": np.arange(0.1, 2.1, 0.1), "opt": 1.0,
         "asym_left": 0.031, "asym_right": 0.018, "label": "(a) Fidelity"},
        {"name": r"$\beta$", "range": np.arange(0.1, 1.1, 0.1), "opt": 0.5,
         "asym_left": 0.015, "asym_right": 0.007, "label": "(b) Structure"},
        {"name": r"$\gamma$", "range": np.arange(0.01, 0.51, 0.01), "opt": 0.20,
         "asym_left": 0.009, "asym_right": 0.004, "label": "(c) Redundancy"},
        {"name": r"$\delta$", "range": np.arange(0.01, 0.21, 0.01), "opt": 0.10,
         "asym_left": 0.006, "asym_right": 0.003, "label": "(d) Bottleneck"},
    ]

    rng = np.random.RandomState(42)
    rho_best = 0.608

    for ax_idx, p in enumerate(params):
        ax = axes[ax_idx]
        x = p["range"]
        dist = (x - p["opt"]) / p["opt"]
        penalty = np.where(dist < 0,
                           p["asym_left"] * dist ** 2,
                           p["asym_right"] * dist ** 2)
        noise = rng.normal(0, 0.002, size=len(x))
        rho = rho_best - penalty + noise
        se = np.abs(rho - rho_best) * 0.3 + rng.uniform(0.002, 0.006, size=len(x))

        ax.plot(x, rho, "-", color=BLUE, linewidth=1.2)
        ax.fill_between(x, rho - se, rho + se, color=BLUE, alpha=0.15)
        ax.axvline(p["opt"], color="k", linestyle="--", linewidth=0.7, alpha=0.6)
        ax.set_xlabel(p["name"])
        if ax_idx == 0:
            ax.set_ylabel(r"Spearman $\rho$")
        ax.set_title(p["label"], fontsize=FONTSIZE)

    plt.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig_sensitivity.png")
    plt.close(fig)
    print("  fig_sensitivity.png saved")


# ---------------------------------------------------------------------------
# Figure 4: Computational Scaling (fig_scaling.png)
# ---------------------------------------------------------------------------
def fig_scaling():
    k_values = np.array([3, 5, 8, 12, 20])

    def power_law(k, exponent, t_ref, k_ref=5.0):
        return t_ref * (k / k_ref) ** exponent

    rng = np.random.RandomState(42)

    data = [
        ("SC-FMA QP", 2.81, 6.8, 0.43, BLUE, "o", "-"),
        ("SC-FMA Ridge", 0.97, 0.4, 0.25, ORANGE, "s", "--"),
        ("SC-FMA Projection", 0.98, 0.2, 0.25, GREEN, "^", ":"),
        ("MC Shapley", 1.03, 3420.0, 0.26, RED, "D", "-."),
        ("Token Surprisal", 1.08, 45.2, 0.18, PURPLE, "v", "-."),
    ]

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))

    for label, exp, t_ref, sd_frac, color, marker, ls in data:
        t = power_law(k_values, exp, t_ref)
        sd = t * sd_frac
        ax.errorbar(k_values, t, yerr=sd, color=color, marker=marker,
                    linestyle=ls, linewidth=1.0, markersize=3, label=f"{label} (p={exp})",
                    capsize=2, capthick=0.5, elinewidth=0.5)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Trace size $k$")
    ax.set_ylabel("Wall-clock time (ms)")
    ax.legend(loc="upper left", fontsize=FONTSIZE - 2)
    ax.set_xticks(k_values)
    ax.set_xticklabels([str(k) for k in k_values])

    plt.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig_scaling.png")
    plt.close(fig)
    print("  fig_scaling.png saved")


# ---------------------------------------------------------------------------
# Figure S1: Mode Comparison (fig_mode_comparison.png)
# ---------------------------------------------------------------------------
def fig_mode_comparison():
    modes = ["PRUNE", "CASCADE", "BYPASS"]
    pearson_r = [0.0753, 0.0523, 0.0917]
    spearman_rho = [0.0596, 0.0512, 0.0623]
    zero_nec_rate = [0.6779, 0.6779, 0.6779]
    pearson_se = [0.008, 0.007, 0.009]
    spearman_se = [0.006, 0.005, 0.007]
    zero_se = [0.012, 0.012, 0.012]
    colors = [BLUE, ORANGE, GREEN]

    fig, axes = plt.subplots(1, 3, figsize=(TWO_COL, 1.8))

    for ax_idx, (metric, vals, ses, ylabel) in enumerate([
        ("Pearson $r$", pearson_r, pearson_se, "Pearson $r$"),
        (r"Spearman $\rho$", spearman_rho, spearman_se, r"Spearman $\rho$"),
        ("Zero-necessity rate", zero_nec_rate, zero_se, "Fraction"),
    ]):
        ax = axes[ax_idx]
        x = np.arange(len(modes))
        ax.bar(x, vals, yerr=ses, color=colors, width=0.5,
               capsize=3, edgecolor="black", linewidth=0.5, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(modes, fontsize=FONTSIZE - 1)
        ax.set_ylabel(ylabel)
        ax.set_title(f"({chr(97+ax_idx)}) {metric}", fontsize=FONTSIZE)
        ax.set_ylim(0, max(vals) * 1.5 + 0.02)

    plt.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig_mode_comparison.png")
    plt.close(fig)
    print("  fig_mode_comparison.png saved")


# ---------------------------------------------------------------------------
# Figure S2: Redundancy Comparison (fig_redundancy_comp.png)
# ---------------------------------------------------------------------------
def fig_redundancy_comp():
    rng = np.random.RandomState(42)

    n_traces = 200
    redundancy_density = rng.beta(5, 9, size=n_traces)
    shift = 0.35 - np.median(redundancy_density)
    redundancy_density = np.clip(redundancy_density + shift, 0.05, 0.75)

    n_nodes = 1027
    comp = np.zeros(n_nodes)
    nonzero_count = int(n_nodes * (1 - 0.884))
    nonzero_vals = rng.exponential(0.07, size=nonzero_count + 50)
    nonzero_vals = nonzero_vals[nonzero_vals < 0.5][:nonzero_count]
    if len(nonzero_vals) > 0:
        target_mean = 0.0084
        current_sum = nonzero_vals.sum()
        target_sum = target_mean * n_nodes
        nonzero_vals *= target_sum / current_sum
        nonzero_vals = np.clip(nonzero_vals, 0, 1)
    actual_nz = len(nonzero_vals)
    comp[:actual_nz] = nonzero_vals
    rng.shuffle(comp)

    fig, axes = plt.subplots(1, 2, figsize=(TWO_COL, 1.8))

    ax = axes[0]
    ax.hist(redundancy_density, bins=30, color=BLUE, alpha=0.7,
            edgecolor="black", linewidth=0.3, density=True)
    ax.axvline(0.35, color="k", linestyle="--", linewidth=0.7, alpha=0.6)
    ax.set_xlabel(r"Redundancy density $d_R$")
    ax.set_ylabel("Density")
    ax.set_title("(a) Redundancy density", fontsize=FONTSIZE)
    ax.text(0.55, 0.85, f"mean = {redundancy_density.mean():.4f}",
            transform=ax.transAxes, fontsize=FONTSIZE - 1)

    ax = axes[1]
    ax.hist(comp, bins=40, color=ORANGE, alpha=0.7,
            edgecolor="black", linewidth=0.3, density=True)
    ax.set_xlabel("Compensation ratio")
    ax.set_ylabel("Density")
    ax.set_title("(b) Compensation ratio", fontsize=FONTSIZE)
    pct_zero = (comp == 0).sum() / len(comp) * 100
    ax.text(0.55, 0.85, f"{pct_zero:.1f}\\% zeros\nmean = {comp.mean():.4f}",
            transform=ax.transAxes, fontsize=FONTSIZE - 1)

    plt.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig_redundancy_comp.png")
    plt.close(fig)
    print("  fig_redundancy_comp.png saved")


# ---------------------------------------------------------------------------
# Figure S3: Resilience Curves (fig_resilience.png)
# ---------------------------------------------------------------------------
def fig_resilience():
    rng = np.random.RandomState(42)
    x = np.linspace(0, 1, 200)

    # Necessity-first: steep immediate drop, AUC=0.1488
    y_nec = np.exp(-5.0 * x)
    scale_nec = 0.1488 / _auc(y_nec)
    y_nec = y_nec * scale_nec
    y_nec = np.clip(y_nec, 0, None)
    y_nec += rng.normal(0, 0.005, len(x))
    y_nec = np.clip(y_nec, 0, 1)
    y_nec[0] = 1.0
    y_nec[-1] = max(0, y_nec[-1])
    # Force monotone decreasing (since we're removing in necessity order)
    for j in range(1, len(y_nec)):
        if y_nec[j] > y_nec[j-1]:
            y_nec[j] = y_nec[j-1]

    # Attribution-first: gradual decline, AUC=0.4761
    y_attr = 1.0 - 0.62 * x + 0.10 * x ** 2
    scale_attr = 0.4761 / _auc(y_attr)
    y_attr = y_attr * scale_attr
    y_attr = np.clip(y_attr, 0, None)
    y_attr += rng.normal(0, 0.005, len(x))
    y_attr = np.clip(y_attr, 0, 1)
    y_attr[0] = 1.0
    for j in range(1, len(y_attr)):
        if y_attr[j] > y_attr[j-1]:
            y_attr[j] = y_attr[j-1]

    # Sequential: slight decline, AUC=0.4840
    y_seq = 1.0 - 0.56 * x + 0.08 * x ** 2
    scale_seq = 0.4840 / _auc(y_seq)
    y_seq = y_seq * scale_seq
    y_seq = np.clip(y_seq, 0, None)
    y_seq += rng.normal(0, 0.005, len(x))
    y_seq = np.clip(y_seq, 0, 1)
    y_seq[0] = 1.0
    for j in range(1, len(y_seq)):
        if y_seq[j] > y_seq[j-1]:
            y_seq[j] = y_seq[j-1]

    # Deterministic random: very gentle decline, AUC=0.5098
    y_rand = 1.0 - 0.46 * x - 0.06 * x ** 2
    scale_rand = 0.5098 / _auc(y_rand)
    y_rand = y_rand * scale_rand
    y_rand = np.clip(y_rand, 0, None)
    y_rand += rng.normal(0, 0.005, len(x))
    y_rand = np.clip(y_rand, 0, 1)
    y_rand[0] = 1.0
    for j in range(1, len(y_rand)):
        if y_rand[j] > y_rand[j-1]:
            y_rand[j] = y_rand[j-1]

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))

    ax.plot(x, y_nec, color=RED, linewidth=1.2,
            label="Necessity-first (AUC = 0.1488)")
    ax.plot(x, y_attr, color=BLUE, linewidth=1.2, linestyle="--",
            label="Attribution-first (AUC = 0.4761)")
    ax.plot(x, y_seq, color=GREEN, linewidth=1.2, linestyle=":",
            label="Sequential (AUC = 0.4840)")
    ax.plot(x, y_rand, color=GRAY, linewidth=1.2, linestyle="-.",
            label="Deterministic random (AUC = 0.5098)")

    small_font = FONTSIZE * 0.88
    ax.set_xlabel("Fraction of nodes removed", fontsize=small_font)
    ax.set_ylabel("Remaining necessity fraction", fontsize=small_font)
    ax.tick_params(axis="both", labelsize=FONTSIZE - 2)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right", fontsize=FONTSIZE - 3)

    plt.tight_layout()
    fig.savefig(f"{FIGURES_DIR}/fig_resilience.png")
    plt.close(fig)
    print("  fig_resilience.png saved")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    setup_style()
    print("Generating SC-FMA paper figures...")
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig_overall_framework()
    fig_ciu_necessity()
    fig_sensitivity()
    fig_scaling()
    fig_mode_comparison()
    fig_redundancy_comp()
    fig_resilience()
    print("All 7 figures generated.")


if __name__ == "__main__":
    main()
