from pathlib import Path
import json

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter


report_path = Path("paper/JIIS_submission/reports/jiis_audit_case/jiis_audit_case_report.json")
report = json.loads(report_path.read_text(encoding="utf-8"))

method_order = [
    ("life_saving_first", "Life-Saving First"),
    ("no_fallback_ablation", "No-Fallback Ablation"),
    ("flat_top_k", "Flat Top-K"),
    ("centrality", "Degree Centrality"),
    ("random_stratified", "Random Stratified"),
    ("random", "Random"),
    ("position", "Position"),
]
methods = [label for _key, label in method_order]
coverage = [
    float(report["methods"][key]["impact_coverage_at_k"]["mean"])
    for key, _label in method_order
]
colors = {
    "Life-Saving First": "#2E86AB",
    "No-Fallback Ablation": "#6BAED6",
    "Flat Top-K": "#F28E2B",
    "Degree Centrality": "#7B52AB",
    "Random Stratified": "#59A14F",
    "Random": "#F1CE63",
    "Position": "#B0B0B0",
}

out_dirs = [
    Path("paper/JIIS_submission/figures"),
    Path("paper/JIIS_submission/source/figures"),
    Path("paper/JIIS_submission/submission_package/figures"),
]
for out_dir in out_dirs:
    out_dir.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)

fig, ax = plt.subplots(figsize=(9.0, 5.0))
fig.subplots_adjust(left=0.09, right=0.985, top=0.94, bottom=0.34)

x = list(range(len(methods)))
bars = ax.bar(
    x,
    coverage,
    color=[colors[method] for method in methods],
    edgecolor="#333333",
    linewidth=0.6,
    width=0.66,
)

ax.set_ylabel("Impact Coverage@K")
ax.set_ylim(0, 1.15)
ax.set_xlim(-0.65, len(methods) - 0.35)
ax.set_xticks(x)
ax.set_xticklabels(methods, rotation=30, ha="right")
ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))
ax.axhline(1.0, color="#9A9A9A", linestyle="--", linewidth=1.0, alpha=0.9, zorder=0)
ax.text(
    len(methods) - 0.42,
    1.015,
    "Ideal upper bound",
    ha="right",
    va="bottom",
    fontsize=9,
    color="#666666",
)
ax.grid(axis="y", linestyle="-", linewidth=0.5, color="#D9D9D9", alpha=0.85)
ax.set_axisbelow(True)

for bar, value in zip(bars, coverage):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        value + 0.025,
        f"{value:.3f}",
        ha="center",
        va="bottom",
        fontsize=9,
        color="#222222",
    )


def add_group(x0, x1, label, y=-0.30):
    trans = ax.get_xaxis_transform()
    ax.plot([x0, x1], [y, y], transform=trans, color="#555555", linewidth=0.8, clip_on=False)
    ax.plot([x0, x0], [y, y + 0.035], transform=trans, color="#555555", linewidth=0.8, clip_on=False)
    ax.plot([x1, x1], [y, y + 0.035], transform=trans, color="#555555", linewidth=0.8, clip_on=False)
    ax.text(
        (x0 + x1) / 2,
        y - 0.055,
        label,
        transform=trans,
        ha="center",
        va="top",
        fontsize=11,
        fontweight="bold",
        color="#333333",
        clip_on=False,
    )


add_group(-0.33, 0.33, "Main strategy")
add_group(0.67, 1.33, "Ablation")
add_group(1.67, 6.33, "Baselines")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#555555")
ax.spines["bottom"].set_color("#555555")
ax.tick_params(axis="x", pad=8)

written = []
for out_dir in out_dirs:
    pdf_path = out_dir / "impact_coverage_comparison.pdf"
    png_path = out_dir / "impact_coverage_comparison.png"
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=300, bbox_inches="tight")
    written.extend([pdf_path.resolve(), png_path.resolve()])
plt.close(fig)

for path in written:
    print(path)
