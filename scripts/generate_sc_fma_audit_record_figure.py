"""Generate the SC-FMA persistent audit-record conceptual figure.

The figure is intentionally drawn as an information-system conceptual
illustration, not a software or algorithm flowchart.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib import patches


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "paper" / "information_sciences_submission" / "final_source" / "figures"
OUT_STEM = "fig_sc_fma_audit_record_object"


COLORS = {
    "ink": "#1F2933",
    "muted": "#5B6773",
    "light_ink": "#7A8691",
    "line": "#B8C0CA",
    "line_light": "#D7DDE5",
    "paper": "#F8FAFC",
    "card": "#FFFFFF",
    "soft": "#EEF2F6",
    "soft2": "#F5F7FA",
    "blue": "#2F6FAE",
    "blue_soft": "#E8F1FA",
    "blue_line": "#7CA6D6",
}


def rounded_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fc: str = COLORS["card"],
    ec: str = COLORS["line"],
    lw: float = 1.0,
    radius: float = 0.16,
    z: int = 2,
) -> patches.FancyBboxPatch:
    box = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.018,rounding_size={radius}",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
        zorder=z,
    )
    ax.add_patch(box)
    return box


def add_text(
    ax,
    x: float,
    y: float,
    text: str,
    *,
    size: float = 8.5,
    weight: str = "normal",
    color: str = COLORS["ink"],
    ha: str = "left",
    va: str = "center",
    wrap: int | None = None,
    z: int = 5,
) -> None:
    if wrap:
        text = "\n".join(textwrap.wrap(text, width=wrap))
    ax.text(
        x,
        y,
        text,
        fontsize=size,
        fontweight=weight,
        color=color,
        ha=ha,
        va=va,
        family="DejaVu Sans",
        linespacing=1.22,
        zorder=z,
    )


def arrow(ax, start, end, *, color=COLORS["line"], lw=1.15, rad=0.0, style="-|>", alpha=1.0, z=1):
    arr = patches.FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=9,
        linewidth=lw,
        color=color,
        alpha=alpha,
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=4,
        shrinkB=4,
        zorder=z,
    )
    ax.add_patch(arr)
    return arr


def field_rows(ax, x, y_top, w, rows, *, row_h=0.29, label_w=0.92, size=7.2, wraps=None):
    y = y_top
    wraps = wraps or {}
    for label, value in rows:
        add_text(ax, x, y, label, size=size, weight="normal", color=COLORS["muted"], va="top")
        add_text(
            ax,
            x + label_w,
            y,
            value,
            size=size,
            weight="normal",
            color=COLORS["ink"],
            va="top",
            wrap=wraps.get(label, max(12, int((w - label_w) * 9.5))),
        )
        y -= row_h


def draw_left_artifact(ax):
    x, y, w, h = 0.75, 2.72, 2.42, 3.36
    rounded_box(ax, x, y, w, h, fc=COLORS["card"], ec=COLORS["line"], lw=1.05, radius=0.13)
    rounded_box(ax, x + 0.14, y + h - 0.48, w - 0.28, 0.27, fc=COLORS["soft"], ec=COLORS["soft"], radius=0.06, z=3)
    add_text(ax, x + w / 2, y + h - 0.345, "Observable Knowledge Artifact", size=8.5, weight="bold", ha="center")

    field_rows(
        ax,
        x + 0.23,
        y + h - 0.72,
        w - 0.46,
        [
            ("Artifact ID", "A102"),
            ("Type", "Retrieved Evidence"),
            ("Source", "Knowledge Graph"),
            ("Content", "Entity E17 supports Relation R5"),
            ("Status", "Observed"),
        ],
        row_h=0.43,
        label_w=0.82,
        size=7.2,
    )
    rounded_box(ax, x + 0.49, y - 0.43, w - 0.98, 0.29, fc=COLORS["soft2"], ec=COLORS["line_light"], radius=0.09, z=2)
    add_text(ax, x + w / 2, y - 0.285, "Observable Knowledge Artifact", size=7.3, color=COLORS["muted"], ha="center")
    return x, y, w, h


def draw_center_record(ax):
    x, y, w, h = 3.82, 1.72, 3.86, 4.95
    rounded_box(ax, x, y, w, h, fc=COLORS["card"], ec=COLORS["blue"], lw=1.9, radius=0.16, z=3)
    rounded_box(ax, x + 0.17, y + h - 0.56, w - 0.34, 0.34, fc=COLORS["blue_soft"], ec=COLORS["blue_line"], lw=0.65, radius=0.08, z=4)
    add_text(ax, x + w / 2, y + h - 0.39, "SC-FMA Audit Record", size=10.0, weight="bold", color=COLORS["blue"], ha="center")

    field_rows(
        ax,
        x + 0.28,
        y + h - 0.79,
        w - 0.56,
        [
            ("Artifact ID", "A102"),
            ("Fidelity", "High"),
            ("Dependency", "Depends on Entity E17"),
            ("Redundancy", "Low"),
            ("Bottleneck", "Yes"),
            ("Audit Reason", "Critical supporting evidence"),
            ("Recommended Action", "Verify linked entity before update"),
            ("Interpretation", "Maintain during knowledge revision"),
            ("Timestamp", "2026-07-12"),
            ("Version", "Version 1.0"),
        ],
        row_h=0.335,
        label_w=1.35,
        size=6.75,
        wraps={
            "Dependency": 28,
            "Audit Reason": 30,
            "Recommended Action": 30,
            "Interpretation": 30,
        },
    )
    rounded_box(ax, x + 0.78, y + 0.25, w - 1.56, 0.4, fc=COLORS["blue"], ec=COLORS["blue"], lw=0.7, radius=0.11, z=4)
    add_text(ax, x + w / 2, y + 0.45, "Persistent Audit Record", size=8.1, weight="bold", color="#FFFFFF", ha="center", z=6)
    return x, y, w, h


def draw_repository(ax):
    x, y, w, h = 8.02, 2.92, 2.20, 2.48
    rounded_box(ax, x, y, w, h, fc=COLORS["card"], ec=COLORS["line"], lw=1.05, radius=0.14)
    add_text(ax, x + w / 2, y + h + 0.26, "Audit Record Repository", size=9.0, weight="bold", ha="center")

    # Back plate and stacked audit cards.
    rounded_box(ax, x + 0.24, y + 0.35, w - 0.48, h - 0.72, fc=COLORS["soft2"], ec=COLORS["line_light"], lw=0.8, radius=0.12, z=2)
    offsets = [(0.36, 1.55), (0.47, 1.22), (0.58, 0.89), (0.69, 0.56)]
    for i, (dx, dy) in enumerate(offsets):
        card_ec = COLORS["blue_line"] if i == 1 else COLORS["line"]
        card_fc = COLORS["blue_soft"] if i == 1 else COLORS["card"]
        rounded_box(ax, x + dx, y + dy, w - 1.1, 0.46, fc=card_fc, ec=card_ec, lw=0.75, radius=0.055, z=4 + i)
        add_text(ax, x + dx + 0.13, y + dy + 0.3, f"A10{i + 1}", size=6.4, weight="bold", color=COLORS["muted"], z=7)
        ax.plot(
            [x + dx + 0.13, x + dx + w - 1.38],
            [y + dy + 0.16, y + dy + 0.16],
            color=COLORS["line_light"],
            lw=0.85,
            zorder=7,
        )

    boxes = {
        "Query": (9.04, 6.18),
        "Maintenance": (10.28, 4.72),
        "Governance": (10.28, 3.08),
        "Knowledge Reuse": (8.92, 1.82),
    }
    for label, (bx, by) in boxes.items():
        bw = 1.18 if label != "Knowledge Reuse" else 1.48
        bh = 0.4
        rounded_box(ax, bx, by, bw, bh, fc=COLORS["soft2"], ec=COLORS["line"], lw=0.9, radius=0.12, z=3)
        add_text(ax, bx + bw / 2, by + bh / 2, label, size=7.2, weight="bold", color=COLORS["ink"], ha="center", z=6)

        # Repository to use-case arrows.
        start = (x + w - 0.08, y + h / 2)
        end = (bx, by + bh / 2)
        arrow(ax, start, end, color=COLORS["line"], lw=1.0, rad=0.03, z=2)

        # Subtle return arrows.
        ret_start = (bx + bw / 2, by)
        ret_end = (x + w / 2, y + 0.18)
        rad = -0.26 if by > y + h / 2 else 0.26
        arrow(ax, ret_start, ret_end, color=COLORS["line_light"], lw=0.9, rad=rad, style="->", alpha=0.85, z=1)

    return x, y, w, h


def draw_lifecycle(ax):
    x, y, w, h = 1.0, 0.92, 7.15, 0.28
    rounded_box(ax, x, y, w, h, fc=COLORS["soft"], ec=COLORS["line_light"], lw=0.8, radius=0.11, z=1)
    phases = ["Construction", "Maintenance", "Governance", "Reuse"]
    for i, label in enumerate(phases):
        px = x + (i + 0.5) * w / len(phases)
        if i:
            ax.plot([x + i * w / len(phases), x + i * w / len(phases)], [y + 0.04, y + h - 0.04], color=COLORS["line_light"], lw=0.75)
        add_text(ax, px, y + h / 2, label, size=7.0, color=COLORS["muted"], ha="center")
    arrow(ax, (x - 0.25, y + h / 2), (x + w + 0.25, y + h / 2), color=COLORS["line"], lw=0.9, style="->", z=1)
    add_text(ax, x - 0.02, y + h + 0.22, "Lifecycle", size=7.2, weight="bold", color=COLORS["muted"], ha="left")


def draw_characteristics(ax):
    x, y, w, h = 8.68, 0.46, 2.62, 1.16
    rounded_box(ax, x, y, w, h, fc=COLORS["card"], ec=COLORS["line"], lw=0.9, radius=0.11, z=3)
    add_text(ax, x + 0.16, y + h - 0.22, "Key Characteristics", size=7.5, weight="bold", color=COLORS["ink"], va="center")
    bullets = [
        "Persistent Information Object",
        "Dependency-aware Representation",
        "Traceable Maintenance",
        "Reusable Knowledge Asset",
        "Governance Support",
    ]
    yy = y + h - 0.42
    for b in bullets:
        add_text(ax, x + 0.2, yy, "\u2022", size=7.0, color=COLORS["blue"], va="top")
        add_text(ax, x + 0.34, yy, b, size=6.35, color=COLORS["muted"], va="top")
        yy -= 0.155


def draw_caption(ax):
    caption = (
        "SC-FMA converts observable knowledge artifacts into persistent audit records that preserve dependency context, "
        "maintenance rationale, and governance information, enabling long-term querying, traceability, and knowledge reuse "
        "beyond a single ranking decision."
    )
    add_text(ax, 0.72, 0.13, caption, size=6.25, color=COLORS["muted"], ha="left", va="bottom", wrap=118)


def draw_context_lines(ax, left, center, repo):
    lx, ly, lw, lh = left
    cx, cy, cw, ch = center
    rx, ry, rw, rh = repo

    arrow(ax, (lx + lw + 0.1, ly + lh * 0.56), (cx - 0.12, cy + ch * 0.58), color=COLORS["line"], lw=1.15)
    add_text(ax, 3.38, 4.64, "audit\nencoding", size=6.55, color=COLORS["light_ink"], ha="center")
    arrow(ax, (cx + cw + 0.12, cy + ch * 0.58), (rx - 0.1, ry + rh * 0.56), color=COLORS["line"], lw=1.15)
    add_text(ax, 8.02, 4.64, "persistent\nstorage", size=6.55, color=COLORS["light_ink"], ha="center")


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12.2, 7.2), dpi=300)
    fig.patch.set_facecolor(COLORS["paper"])
    ax.set_facecolor(COLORS["paper"])
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7.2)
    ax.axis("off")

    add_text(
        ax,
        6.0,
        6.94,
        "Example of an SC-FMA Audit Record as a Persistent Information Object",
        size=13.2,
        weight="bold",
        color=COLORS["ink"],
        ha="center",
    )

    left = draw_left_artifact(ax)
    center = draw_center_record(ax)
    repo = draw_repository(ax)
    draw_context_lines(ax, left, center, repo)
    draw_lifecycle(ax)
    draw_characteristics(ax)
    draw_caption(ax)

    for ext in ("svg", "pdf", "png"):
        output = FIGURE_DIR / f"{OUT_STEM}.{ext}"
        fig.savefig(output, bbox_inches="tight", pad_inches=0.08, facecolor=fig.get_facecolor())

    plt.close(fig)


if __name__ == "__main__":
    main()
