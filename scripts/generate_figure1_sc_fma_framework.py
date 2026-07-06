"""Generate a journal-style Fig. 1 workflow for the DKE submission.

Outputs:
  - paper/dke_submission/final_source/figures/fig_overall_framework.drawio
  - paper/dke_submission/final_source/figures/fig_overall_framework.svg
  - paper/dke_submission/final_source/figures/fig_overall_framework.pdf

The design is deliberately sparse: native draw.io shapes, editable SVG text,
thin rules, no decorative icons, no gradients, no shadows, and no external
assets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import cairosvg


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "paper" / "dke_submission" / "final_source" / "figures"
DRAWIO_PATH = OUT_DIR / "fig_overall_framework.drawio"
SVG_PATH = OUT_DIR / "fig_overall_framework.svg"
PDF_PATH = OUT_DIR / "fig_overall_framework.pdf"

W = 1400
H = 540

BLUE = "#1F4E79"
BLUE_PALE = "#F2F7FB"
INK = "#222222"
LINE = "#333333"
MID = "#7C8792"
LIGHT = "#D8DDE3"
FAINT = "#F7F8FA"
MUTED = "#646B73"
GREEN = "#2F7D4F"
RED = "#B23A2E"


def esc(value: str) -> str:
    return escape(value, {'"': "&quot;"})


class Drawio:
    def __init__(self) -> None:
        self.cells: list[str] = [
            '        <mxCell id="0" />',
            '        <mxCell id="1" parent="0" />',
        ]

    def vertex(self, id_: str, value: str, style: str, x: float, y: float, w: float, h: float) -> None:
        self.cells.append(
            f'        <mxCell id="{id_}" value="{esc(value)}" style="{style}" vertex="1" parent="1">'
        )
        self.cells.append(f'          <mxGeometry x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" as="geometry" />')
        self.cells.append("        </mxCell>")

    def edge(
        self,
        id_: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        color: str = LINE,
        width: float = 1.5,
        dashed: bool = False,
        arrow: bool = True,
    ) -> None:
        style = (
            "edgeStyle=none;html=1;rounded=0;shadow=0;"
            f"strokeColor={color};strokeWidth={width:g};dashed={1 if dashed else 0};"
            f"endArrow={'block' if arrow else 'none'};endFill=1;"
        )
        self.cells.append(f'        <mxCell id="{id_}" value="" style="{style}" edge="1" parent="1">')
        self.cells.append(
            f'          <mxGeometry relative="1" as="geometry">'
            f'<mxPoint x="{x1:g}" y="{y1:g}" as="sourcePoint" />'
            f'<mxPoint x="{x2:g}" y="{y2:g}" as="targetPoint" />'
            f"</mxGeometry>"
        )
        self.cells.append("        </mxCell>")

    def xml(self) -> str:
        modified = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="{modified}" agent="Codex" version="30.0.4" type="device">
  <diagram id="sc-fma-framework" name="Page-1">
    <mxGraphModel dx="1400" dy="760" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{W}" pageHeight="{H}" math="0" shadow="0" background="#FFFFFF">
      <root>
{chr(10).join(self.cells)}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
'''


def text_style(size: int, color: str = INK, *, bold: bool = False, align: str = "center", italic: bool = False) -> str:
    font_style = (1 if bold else 0) + (2 if italic else 0)
    return (
        "text;html=1;strokeColor=none;fillColor=none;whiteSpace=wrap;rounded=0;shadow=0;"
        f"fontFamily=Arial;fontSize={size};fontColor={color};fontStyle={font_style};"
        f"align={align};verticalAlign=middle;spacing=0;"
    )


def rect_style(fill: str, stroke: str, width: float = 1.0, *, dashed: bool = False, radius: int = 3) -> str:
    return (
        "rounded=1;whiteSpace=wrap;html=1;shadow=0;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth={width:g};arcSize={radius};"
        f"dashed={1 if dashed else 0};"
        "fontFamily=Arial;fontSize=12;fontColor=#222222;align=center;verticalAlign=middle;spacing=4;"
    )


def line_rect_style(stroke: str = MID, width: float = 1.0) -> str:
    return rect_style("none", stroke, width)


def ellipse_style(stroke: str = LINE, width: float = 1.2, *, dashed: bool = False) -> str:
    return (
        "ellipse;whiteSpace=wrap;html=1;fillColor=#FFFFFF;shadow=0;"
        f"strokeColor={stroke};strokeWidth={width:g};dashed={1 if dashed else 0};"
        "fontFamily=Arial;fontSize=12;fontColor=#222222;fontStyle=1;align=center;verticalAlign=middle;"
    )


def add_cells(d: Drawio) -> None:
    # Hairline frame and section rules.
    d.vertex("top_rule", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), 50, 54, 1300, 1)
    d.vertex("bottom_rule", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), 50, 490, 1300, 1)
    d.vertex("v_rule_1", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), 345, 86, 1, 365)
    d.vertex("v_rule_2", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), 1015, 86, 1, 365)

    d.vertex("input_header", "Knowledge artifacts", text_style(16, BLUE, bold=True), 80, 76, 230, 22)
    d.vertex("scfma_header", "SC-FMA: representation layer", text_style(17, BLUE, bold=True), 410, 76, 545, 22)
    d.vertex("out_header", "Knowledge maintenance", text_style(16, BLUE, bold=True), 1055, 76, 260, 22)

    # Input block, text-only.
    d.vertex("input_box", "", line_rect_style(MID, 1.0), 85, 126, 225, 226)
    d.vertex("input_a", "<b>knowledge artifacts</b><br>retrieval, entity, rule", text_style(14), 110, 160, 175, 46)
    d.vertex("input_line", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), 118, 230, 160, 1)
    d.vertex("input_b", "<b>knowledge representation</b><br>A = (a<sub>1</sub>, ..., a<sub>n</sub>)", text_style(14), 105, 252, 185, 64)
    d.vertex("input_note", "Observable artifacts only.", text_style(11, MUTED), 105, 326, 185, 20)

    d.edge("input_to_graph", 310, 238, 390, 238, color=BLUE, width=1.9)
    d.vertex("input_to_graph_label", "representation", text_style(11, MUTED, italic=True), 318, 212, 70, 18)

    # SC-FMA audit graph.
    d.vertex("graph_panel", "", line_rect_style(MID, 1.0), 390, 126, 260, 226)
    d.vertex("graph_label", "Dependency graph", text_style(14, INK, bold=True), 416, 145, 210, 20)
    nodes = {
        "s1": (432, 244, "a<sub>1</sub>", False, False),
        "s2": (508, 203, "a<sub>2</sub>", False, False),
        "s4": (508, 289, "a<sub>4</sub>", True, False),
        "s3": (585, 246, "a<sub>3</sub>", False, True),
    }
    for src, dst, dashed in [
        ("s1", "s2", False),
        ("s1", "s4", False),
        ("s2", "s3", False),
        ("s4", "s3", False),
        ("s2", "s4", True),
    ]:
        x1, y1, *_ = nodes[src]
        x2, y2, *_ = nodes[dst]
        d.edge(f"graph_{src}_{dst}", x1, y1, x2, y2, color=LINE, width=1.35, dashed=dashed)
    for key, (cx, cy, label, dashed, strong) in nodes.items():
        d.vertex(
            f"node_{key}",
            label,
            ellipse_style(BLUE if strong else LINE, 2.1 if strong else 1.15, dashed=dashed),
            cx - 17,
            cy - 17,
            34,
            34,
        )
    d.vertex("graph_note", "artifact dependencies", text_style(11, MUTED), 420, 320, 200, 18)

    d.edge("graph_to_cal", 650, 238, 724, 238, color=BLUE, width=1.9)
    d.vertex("graph_to_cal_label", "annotation signal + structure", text_style(11, MUTED, italic=True), 654, 212, 72, 28)

    # SCU calibration block.
    d.vertex("cal_panel", "", line_rect_style(MID, 1.0), 724, 126, 255, 226)
    d.vertex("cal_label", "SCU calibration", text_style(14, INK, bold=True), 746, 145, 210, 20)
    d.vertex("cal_vec", "artifact roles", rect_style("#FFFFFF", BLUE, 1.1), 765, 178, 170, 34)
    d.edge("cal_vec_to_mid", 850, 212, 850, 238, color=BLUE, width=1.5)
    d.vertex(
        "cal_mid",
        "calibrate priority<br>under fixed budget",
        rect_style(BLUE_PALE, BLUE, 1.1),
        765,
        238,
        170,
        58,
    )
    d.edge("cal_mid_to_out", 850, 296, 850, 320, color=BLUE, width=1.5)
    d.vertex("cal_weight", "audit record schema", rect_style("#FFFFFF", BLUE, 1.1), 765, 320, 170, 30)

    d.edge("cal_to_out", 979, 238, 1055, 238, color=BLUE, width=1.9)
    d.vertex("budget_label", "audit budget", text_style(11, MUTED, italic=True), 987, 212, 62, 18)

    # Decomposition strip across the SC-FMA layer.
    d.vertex("strip_title", "knowledge audit record fields", text_style(13, BLUE, bold=True), 490, 383, 395, 18)
    d.vertex("strip_frame", "", line_rect_style("#A9B1BA", 0.9), 390, 408, 589, 44)
    for i, label in enumerate(["annotation fidelity", "structural role", "redundancy", "bottleneck", "maintenance action"]):
        x = 402 + i * 115
        if i > 0:
            d.vertex(f"strip_sep_{i}", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), x - 12, 416, 1, 28)
        d.vertex(f"strip_field_{i}", label, text_style(11, INK, bold=True), x, 419, 100, 20)

    # Output as one compact matrix, not a UI card.
    d.vertex("queue_panel", "", line_rect_style(MID, 1.0), 1055, 126, 260, 226)
    d.vertex("queue_title", "Knowledge audit records", text_style(14, INK, bold=True), 1080, 145, 210, 20)
    d.vertex("q_frame", "", rect_style("#FFFFFF", "#9BA4AD", 1.0, radius=2), 1080, 184, 210, 132)
    d.vertex("q_h_artifact", "artifact", text_style(9, MUTED, bold=True), 1090, 200, 42, 14)
    d.vertex("q_h_role", "role", text_style(9, MUTED, bold=True), 1135, 200, 40, 14)
    d.vertex("q_h_reason", "audit reason", text_style(9, MUTED, bold=True), 1175, 200, 68, 14)
    d.vertex("q_h_action", "action", text_style(9, MUTED, bold=True), 1244, 200, 42, 14)
    d.vertex("q_h_rule", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), 1088, 218, 194, 1)
    rows = [
        ("a<sub>3</sub>", "gate", "bottleneck", "retain"),
        ("a<sub>2</sub>", "link", "dependency", "verify"),
        ("a<sub>5</sub>", "cluster", "redundant", "merge"),
    ]
    for i, (artifact, role, reason, action) in enumerate(rows):
        y = 239 + i * 28
        d.vertex(f"q_artifact_{i}", artifact, text_style(10, INK), 1093, y, 36, 14)
        d.vertex(f"q_role_{i}", role, text_style(10, INK), 1138, y, 34, 14)
        d.vertex(f"q_reason_{i}", reason, text_style(10, INK), 1174, y, 72, 14)
        d.vertex(f"q_action_{i}", action, text_style(10, INK), 1250, y, 36, 14)
    d.vertex("q_note", "record = artifact + role + maintenance action", text_style(11, MUTED), 1078, 330, 214, 18)

    # Bottom interpretation, intentionally understated.
    d.vertex("bottom_left", "Knowledge Artifacts", text_style(12, MUTED), 104, 468, 180, 18)
    d.vertex("bottom_right", "Knowledge Maintenance", text_style(12, MUTED), 1035, 468, 290, 18)
    d.edge("bottom_arrow", 292, 477, 1028, 477, color="#9BA4AD", width=1.1)


def svg_text(
    x: float,
    y: float,
    text: str,
    *,
    size: int = 13,
    color: str = INK,
    weight: int = 400,
    anchor: str = "middle",
    italic: bool = False,
) -> str:
    style = (
        "font-family:Arial, Helvetica, sans-serif;"
        f"font-size:{size}px;fill:{color};font-weight:{weight};"
        f"font-style:{'italic' if italic else 'normal'};"
    )
    return f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}" dominant-baseline="middle" style="{style}">{escape(text)}</text>'


def svg_multiline(
    x: float,
    y: float,
    lines: list[str],
    *,
    size: int = 13,
    color: str = INK,
    weight: int = 400,
    anchor: str = "middle",
    line_gap: int = 18,
) -> str:
    style = f"font-family:Arial, Helvetica, sans-serif;font-size:{size}px;fill:{color};font-weight:{weight};"
    tspans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_gap
        tspans.append(f'<tspan x="{x:g}" dy="{dy:g}">{escape(line)}</tspan>')
    return f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}" dominant-baseline="middle" style="{style}">{"".join(tspans)}</text>'


def svg_rect(x: float, y: float, w: float, h: float, fill: str, stroke: str, sw: float = 1.0, rx: float = 3) -> str:
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx:g}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:g}"/>'


def svg_line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = LINE,
    sw: float = 1.4,
    dashed: bool = False,
    arrow: bool = True,
) -> str:
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    marker = ""
    if arrow:
        marker = ' marker-end="url(#arrow-blue)"' if color == BLUE else ' marker-end="url(#arrow)"'
    return f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{color}" stroke-width="{sw:g}"{dash}{marker}/>'


def svg_circle(cx: float, cy: float, r: float, label: str, *, stroke: str = LINE, sw: float = 1.2, dashed: bool = False) -> str:
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    return (
        f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="#FFFFFF" stroke="{stroke}" stroke-width="{sw:g}"{dash}/>'
        f'{svg_text(cx, cy + 0.5, label, size=12, weight=700)}'
    )


def generate_svg() -> str:
    p: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<defs>",
        '<marker id="arrow" markerWidth="9" markerHeight="8" refX="8" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="#333333"/></marker>',
        '<marker id="arrow-blue" markerWidth="9" markerHeight="8" refX="8" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="#1F4E79"/></marker>',
        "</defs>",
        '<rect width="1400" height="540" fill="#FFFFFF"/>',
        '<line x1="50" y1="54" x2="1350" y2="54" stroke="#D8DDE3" stroke-width="1"/>',
        '<line x1="50" y1="490" x2="1350" y2="490" stroke="#D8DDE3" stroke-width="1"/>',
        '<line x1="345" y1="86" x2="345" y2="451" stroke="#D8DDE3" stroke-width="1"/>',
        '<line x1="1015" y1="86" x2="1015" y2="451" stroke="#D8DDE3" stroke-width="1"/>',
        svg_text(195, 88, "Knowledge artifacts", size=16, color=BLUE, weight=700),
        svg_text(682.5, 88, "SC-FMA: representation layer", size=17, color=BLUE, weight=700),
        svg_text(1185, 88, "Knowledge maintenance", size=16, color=BLUE, weight=700),
        svg_rect(85, 126, 225, 226, "none", MID, 1.0, 3),
        svg_multiline(197.5, 171, ["knowledge artifacts", "retrieval, entity, rule"], size=14, weight=700, line_gap=22),
        '<line x1="118" y1="230" x2="278" y2="230" stroke="#D8DDE3" stroke-width="1"/>',
        svg_multiline(197.5, 269, ["knowledge representation", "A = (a1, ..., an)"], size=14, weight=700, line_gap=22),
        svg_text(197.5, 336, "Observable artifacts only.", size=11, color=MUTED),
        svg_line(310, 238, 390, 238, color=BLUE, sw=1.9),
        svg_text(353, 219, "representation", size=11, color=MUTED, italic=True),
        svg_rect(390, 126, 260, 226, "none", MID, 1.0, 3),
        svg_text(520, 155, "Dependency graph", size=14, weight=700),
    ]

    nodes = {"s1": (432, 244), "s2": (508, 203), "s4": (508, 289), "s3": (585, 246)}
    for src, dst, dashed in [
        ("s1", "s2", False),
        ("s1", "s4", False),
        ("s2", "s3", False),
        ("s4", "s3", False),
        ("s2", "s4", True),
    ]:
        x1, y1 = nodes[src]
        x2, y2 = nodes[dst]
        p.append(svg_line(x1, y1, x2, y2, sw=1.35, dashed=dashed))
    p.extend(
        [
            svg_circle(432, 244, 17, "a1"),
            svg_circle(508, 203, 17, "a2"),
            svg_circle(508, 289, 17, "a4", dashed=True),
            svg_circle(585, 246, 17, "a3", stroke=BLUE, sw=2.1),
            svg_text(520, 329, "artifact dependencies", size=11, color=MUTED),
            svg_line(650, 238, 724, 238, color=BLUE, sw=1.9),
            svg_multiline(687, 215, ["annotation signal", "+ structure"], size=11, color=MUTED, line_gap=13),
            svg_rect(724, 126, 255, 226, "none", MID, 1.0, 3),
            svg_text(851.5, 155, "SCU calibration", size=14, weight=700),
            svg_rect(765, 178, 170, 34, "#FFFFFF", BLUE, 1.1, 3),
            svg_text(850, 196, "artifact roles", size=13, weight=700),
            svg_line(850, 212, 850, 238, color=BLUE, sw=1.5),
            svg_rect(765, 238, 170, 58, BLUE_PALE, BLUE, 1.1, 3),
            svg_multiline(850, 254, ["calibrate priority", "under fixed budget"], size=13, weight=700, line_gap=20),
            svg_line(850, 296, 850, 320, color=BLUE, sw=1.5),
            svg_rect(765, 320, 170, 30, "#FFFFFF", BLUE, 1.1, 3),
            svg_text(850, 336, "audit record schema", size=13, weight=700),
            svg_line(979, 238, 1055, 238, color=BLUE, sw=1.9),
            svg_text(1018, 219, "audit budget", size=11, color=MUTED, italic=True),
            svg_text(687.5, 392, "knowledge audit record fields", size=13, color=BLUE, weight=700),
            svg_rect(390, 408, 589, 44, "none", "#A9B1BA", 0.9, 2),
        ]
    )

    for i, label in enumerate(["annotation fidelity", "structural role", "redundancy", "bottleneck", "maintenance action"]):
        x = 402 + i * 115
        if i > 0:
            p.append(f'<line x1="{x - 12:g}" y1="416" x2="{x - 12:g}" y2="444" stroke="#D8DDE3" stroke-width="1"/>')
        p.append(svg_text(x + 50, 430, label, size=11, weight=700))

    p.extend(
        [
            svg_rect(1055, 126, 260, 226, "none", MID, 1.0, 3),
            svg_text(1185, 155, "Knowledge audit records", size=14, weight=700),
            svg_rect(1080, 184, 210, 132, "#FFFFFF", "#9BA4AD", 1.0, 2),
            svg_text(1111, 204, "artifact", size=9, color=MUTED, weight=700),
            svg_text(1155, 204, "role", size=9, color=MUTED, weight=700),
            svg_text(1209, 204, "audit reason", size=9, color=MUTED, weight=700),
            svg_text(1267, 204, "action", size=9, color=MUTED, weight=700),
            '<line x1="1088" y1="218" x2="1282" y2="218" stroke="#D8DDE3" stroke-width="1"/>',
            svg_text(1111, 243, "a3", size=10),
            svg_text(1155, 243, "gate", size=10),
            svg_text(1209, 243, "bottleneck", size=10),
            svg_text(1267, 243, "retain", size=10),
            svg_text(1111, 271, "a2", size=10),
            svg_text(1155, 271, "link", size=10),
            svg_text(1209, 271, "dependency", size=10),
            svg_text(1267, 271, "verify", size=10),
            svg_text(1111, 299, "a5", size=10),
            svg_text(1155, 299, "cluster", size=10),
            svg_text(1209, 299, "redundant", size=10),
            svg_text(1267, 299, "merge", size=10),
            svg_text(1185, 339, "record = artifact + role + maintenance action", size=11, color=MUTED),
            svg_text(194, 475, "Knowledge Artifacts", size=12, color=MUTED),
            svg_line(292, 477, 1028, 477, color="#9BA4AD", sw=1.1),
            svg_text(1180, 475, "Knowledge Maintenance", size=12, color=MUTED),
        ]
    )
    p.append("</svg>")
    return "\n".join(p) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    d = Drawio()
    add_cells(d)
    DRAWIO_PATH.write_text(d.xml(), encoding="utf-8", newline="\n")
    SVG_PATH.write_text(generate_svg(), encoding="utf-8", newline="\n")
    cairosvg.svg2pdf(url=str(SVG_PATH), write_to=str(PDF_PATH), output_width=W, output_height=H)
    print(DRAWIO_PATH)
    print(SVG_PATH)
    print(PDF_PATH)


if __name__ == "__main__":
    main()
