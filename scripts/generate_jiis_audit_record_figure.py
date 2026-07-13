"""Generate a JIIS-style SC-FMA audit-record figure.

Outputs:
  - paper/JIIS_submission/source/figures/fig_audit_record_information_object.drawio
  - paper/JIIS_submission/source/figures/fig_audit_record_information_object.svg
  - paper/JIIS_submission/source/figures/fig_audit_record_information_object.pdf
  - copies of the same files under paper/JIIS_submission/submission_package/figures

The figure uses editable vector primitives only: text, rounded rectangles,
straight connectors, and thin rules. It intentionally avoids gradients,
shadows, icons, clipart, and neural-network or ML-pipeline styling.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "paper" / "JIIS_submission" / "source" / "figures"
PACKAGE_DIR = ROOT / "paper" / "JIIS_submission" / "submission_package" / "figures"
BASE = "fig_audit_record_information_object"

W = 1800
H = 1000
FIG_WIDTH_IN = 7.5

BLUE = "#4F81BD"
INK = "#222222"
LINE = "#4A4A4A"
MID = "#777777"
LIGHT = "#CFCFCF"
FAINT = "#F7F7F7"
MUTED = "#666666"
WHITE = "#FFFFFF"


def pt(value: float) -> float:
    """Convert point size to viewBox units for a 7.5 in wide figure."""
    return value * W / (FIG_WIDTH_IN * 72.0)


TITLE = pt(14)
SECTION = pt(11)
FIELD = pt(8.2)
CAPTION = pt(8.5)
NOTE = pt(8)


def esc(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def svg_text(
    x: float,
    y: float,
    text: str,
    *,
    size: float = FIELD,
    color: str = INK,
    weight: int = 400,
    anchor: str = "middle",
    italic: bool = False,
) -> str:
    style = (
        "font-family:Arial, Helvetica, sans-serif;"
        f"font-size:{size:g}px;fill:{color};font-weight:{weight};"
        f"font-style:{'italic' if italic else 'normal'};"
    )
    return (
        f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}" '
        f'dominant-baseline="middle" style="{style}">{escape(text)}</text>'
    )


def svg_multiline(
    x: float,
    y: float,
    lines: list[str],
    *,
    size: float = FIELD,
    color: str = INK,
    weight: int = 400,
    anchor: str = "middle",
    line_gap: float | None = None,
    italic: bool = False,
) -> str:
    if line_gap is None:
        line_gap = size * 1.25
    style = (
        "font-family:Arial, Helvetica, sans-serif;"
        f"font-size:{size:g}px;fill:{color};font-weight:{weight};"
        f"font-style:{'italic' if italic else 'normal'};"
    )
    spans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_gap
        spans.append(f'<tspan x="{x:g}" dy="{dy:g}">{escape(line)}</tspan>')
    return (
        f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}" '
        f'dominant-baseline="middle" style="{style}">{"".join(spans)}</text>'
    )


def svg_rect(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = WHITE,
    stroke: str = LINE,
    sw: float = 1.4,
    rx: float = 12,
) -> str:
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx:g}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw:g}"/>'
    )


def svg_line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = LINE,
    sw: float = 1.4,
    arrow: bool = False,
) -> str:
    marker = ' marker-end="url(#arrow)"' if arrow else ""
    return (
        f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" '
        f'stroke="{color}" stroke-width="{sw:g}"{marker}/>'
    )


def svg_path(d: str, *, color: str = LINE, sw: float = 1.4, arrow: bool = False) -> str:
    marker = ' marker-end="url(#arrow)"' if arrow else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw:g}"{marker}/>'


def draw_left_column(parts: list[str]) -> None:
    x, y, w, h = 85, 190, 330, 430
    parts.append(svg_multiline(x + w / 2, 118, ["Observable Knowledge", "Artifact"], size=SECTION, weight=700, line_gap=SECTION * 1.15))
    parts.append(svg_rect(x, y, w, h, fill=WHITE, stroke=MID, sw=1.4, rx=14))

    rows = [
        ("Artifact ID", ["A102"]),
        ("Type", ["Retrieved Evidence"]),
        ("Source", ["Knowledge Base"]),
        ("Content", ["Entity E17 supports", "Relation R5."]),
        ("Status", ["Observed"]),
    ]
    row_tops = [225, 300, 375, 450, 545]
    for i, (field, value_lines) in enumerate(rows):
        ry = row_tops[i]
        parts.append(svg_text(x + 32, ry, field, size=FIELD, weight=700, anchor="start"))
        if len(value_lines) == 1:
            parts.append(svg_text(x + 32, ry + 34, value_lines[0], size=FIELD, anchor="start"))
        else:
            parts.append(
                svg_multiline(x + 32, ry + 28, value_lines, size=FIELD, anchor="start", line_gap=FIELD * 1.12)
            )
        if i < len(rows) - 1:
            sep_y = row_tops[i + 1] - 22
            parts.append(svg_line(x + 24, sep_y, x + w - 24, sep_y, color=LIGHT, sw=1.0))

    parts.append(svg_text(x + w / 2, y + h + 50, "Observable system artifact", size=NOTE, color=MUTED, italic=True))


def draw_audit_record(parts: list[str]) -> None:
    x, y, w, h = 480, 175, 835, 530
    parts.append(svg_text(x + w / 2, 130, "SC-FMA Audit Record", size=SECTION, color=BLUE, weight=700))
    parts.append(svg_rect(x, y, w, h, fill=WHITE, stroke=LINE, sw=1.6, rx=14))

    table_x, table_y, table_w = 520, 220, 755
    field_w = 305
    row_h = 41
    rows = [
        ("Artifact ID", "A102"),
        ("Fidelity", "High"),
        ("Dependency", "Depends on Entity E17"),
        ("Redundancy", "Low"),
        ("Bottleneck", "Yes"),
        ("Audit Reason", "Critical supporting evidence"),
        ("Recommended Action", "Verify linked entity before update"),
        ("Interpretation", "Maintain during knowledge revision"),
        ("Timestamp", "2026-07-12"),
        ("Record Version", "v1.0"),
    ]
    table_h = row_h * len(rows)
    parts.append(svg_rect(table_x, table_y, table_w, table_h, fill=WHITE, stroke=MID, sw=1.1, rx=4))
    parts.append(svg_line(table_x + field_w, table_y, table_x + field_w, table_y + table_h, color=LIGHT, sw=1.1))

    for i, (field, value) in enumerate(rows):
        cy = table_y + row_h * i + row_h / 2
        if i > 0:
            ly = table_y + row_h * i
            parts.append(svg_line(table_x, ly, table_x + table_w, ly, color=LIGHT, sw=1.0))
        parts.append(svg_text(table_x + 24, cy, field, size=FIELD, weight=700, anchor="start"))
        parts.append(svg_text(table_x + field_w + 24, cy, value, size=FIELD, anchor="start"))

    label_w, label_h = 330, 38
    label_x = x + (w - label_w) / 2
    label_y = y + h - 58
    parts.append(svg_rect(label_x, label_y, label_w, label_h, fill=BLUE, stroke=BLUE, sw=1.2, rx=13))
    parts.append(svg_text(label_x + label_w / 2, label_y + label_h / 2, "Persistent Audit Record", size=FIELD, color=WHITE, weight=700))


def draw_operations(parts: list[str]) -> None:
    x, w = 1390, 340
    parts.append(svg_text(x + w / 2, 130, "Maintenance Operations", size=SECTION, weight=700))

    labels = ["Query Records", "Dependency Inspection", "Knowledge Update", "Governance Log"]
    ys = [215, 325, 435, 545]
    box_h = 58
    for i, (label, y) in enumerate(zip(labels, ys, strict=True)):
        parts.append(svg_rect(x, y, w, box_h, fill=WHITE, stroke=MID, sw=1.4, rx=13))
        parts.append(svg_text(x + w / 2, y + box_h / 2, label, size=FIELD, weight=700))
        if i < len(labels) - 1:
            parts.append(svg_line(x + w / 2, y + box_h + 12, x + w / 2, ys[i + 1] - 13, color=LINE, sw=1.5, arrow=True))

    # Lightweight maintenance cycle back to the persistent record label.
    parts.append(svg_path("M 1390 574 L 1342 574 L 1342 666 L 1155 666", color=LINE, sw=1.4, arrow=True))


def draw_lifecycle(parts: list[str]) -> None:
    arrow_y = 810
    parts.append(svg_line(150, arrow_y, 1650, arrow_y, color=LINE, sw=1.5, arrow=True))
    parts.append(svg_text(900, arrow_y - 48, "Knowledge Lifecycle", size=SECTION, weight=700))
    labels = [("Construction", 285), ("Maintenance", 690), ("Governance", 1095), ("Reuse", 1500)]
    for label, x in labels:
        parts.append(svg_line(x, arrow_y - 10, x, arrow_y + 10, color=LINE, sw=1.1))
        parts.append(svg_text(x, arrow_y + 54, label, size=FIELD, weight=700))

    caption = [
        "An SC-FMA audit record preserves artifact identity, dependency context, structural roles, and maintenance rationale,",
        "enabling persistent querying, governance, and knowledge lifecycle management beyond a single ranking decision.",
    ]
    parts.append(svg_multiline(900, 925, caption, size=CAPTION, color=INK, line_gap=CAPTION * 1.25))


def generate_svg() -> str:
    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{FIG_WIDTH_IN:g}in" height="{FIG_WIDTH_IN * H / W:g}in" viewBox="0 0 {W} {H}">',
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L9,4 L0,8 Z" fill="#4A4A4A"/></marker>',
        "</defs>",
        f'<rect width="{W}" height="{H}" fill="{WHITE}"/>',
        svg_text(900, 58, "Example of an SC-FMA Audit Record as a Persistent Information Object", size=TITLE, weight=700),
    ]
    draw_left_column(parts)
    draw_audit_record(parts)
    draw_operations(parts)
    draw_lifecycle(parts)
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


class Drawio:
    def __init__(self) -> None:
        self.cells = ['        <mxCell id="0" />', '        <mxCell id="1" parent="0" />']

    def vertex(self, id_: str, value: str, style: str, x: float, y: float, w: float, h: float) -> None:
        self.cells.append(f'        <mxCell id="{id_}" value="{esc(value)}" style="{style}" vertex="1" parent="1">')
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
        arrow: bool = True,
        points: list[tuple[float, float]] | None = None,
    ) -> None:
        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;shadow=0;"
            "strokeColor=#4A4A4A;strokeWidth=1.4;"
            f"endArrow={'block' if arrow else 'none'};endFill=1;"
        )
        self.cells.append(f'        <mxCell id="{id_}" value="" style="{style}" edge="1" parent="1">')
        self.cells.append('          <mxGeometry relative="1" as="geometry">')
        self.cells.append(f'            <mxPoint x="{x1:g}" y="{y1:g}" as="sourcePoint" />')
        self.cells.append(f'            <mxPoint x="{x2:g}" y="{y2:g}" as="targetPoint" />')
        if points:
            self.cells.append("            <Array as=\"points\">")
            for px, py in points:
                self.cells.append(f'              <mxPoint x="{px:g}" y="{py:g}" />')
            self.cells.append("            </Array>")
        self.cells.append("          </mxGeometry>")
        self.cells.append("        </mxCell>")

    def xml(self) -> str:
        modified = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="{modified}" agent="Codex" version="30.0.4" type="device">
  <diagram id="sc-fma-audit-record-object" name="Page-1">
    <mxGraphModel dx="1600" dy="1000" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{W}" pageHeight="{H}" math="0" shadow="0" background="#FFFFFF">
      <root>
{chr(10).join(self.cells)}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
'''


def text_style(size: int, *, color: str = INK, bold: bool = False, italic: bool = False, align: str = "center") -> str:
    font_style = (1 if bold else 0) + (2 if italic else 0)
    return (
        "text;html=1;strokeColor=none;fillColor=none;whiteSpace=wrap;rounded=0;shadow=0;"
        f"fontFamily=Arial;fontSize={size};fontColor={color};fontStyle={font_style};"
        f"align={align};verticalAlign=middle;spacing=0;"
    )


def rect_style(fill: str = WHITE, stroke: str = LINE, width: float = 1.3, *, radius: int = 8, font_color: str = INK) -> str:
    return (
        "rounded=1;whiteSpace=wrap;html=1;shadow=0;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth={width:g};arcSize={radius};"
        f"fontFamily=Arial;fontSize=9;fontColor={font_color};align=center;verticalAlign=middle;spacing=4;"
    )


def add_drawio_cells(d: Drawio) -> None:
    d.vertex("title", "Example of an SC-FMA Audit Record as a Persistent Information Object", text_style(14, bold=True), 345, 38, 1110, 40)

    d.vertex("left_title", "Observable Knowledge<br>Artifact", text_style(11, bold=True), 85, 100, 330, 60)
    d.vertex("left_box", "", rect_style(WHITE, MID, 1.3, radius=8), 85, 190, 330, 430)
    left_rows = [
        ("Artifact ID", "A102", 225, 1),
        ("Type", "Retrieved Evidence", 300, 1),
        ("Source", "Knowledge Base", 375, 1),
        ("Content", "Entity E17 supports<br>Relation R5.", 450, 2),
        ("Status", "Observed", 545, 1),
    ]
    for idx, (field, value, y, lines) in enumerate(left_rows):
        d.vertex(f"left_field_{idx}", field, text_style(9, bold=True, align="left"), 117, y - 13, 210, 26)
        d.vertex(f"left_value_{idx}", value, text_style(9, align="left"), 117, y + (10 if lines == 2 else 21), 250, 34 if lines == 2 else 26)
        if idx < len(left_rows) - 1:
            d.vertex(f"left_sep_{idx}", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), 109, left_rows[idx + 1][2] - 22, 282, 1)
    d.vertex("left_note", "Observable system artifact", text_style(8, color=MUTED, italic=True), 122, 630, 256, 28)

    d.vertex("middle_title", "SC-FMA Audit Record", text_style(11, color=BLUE, bold=True), 697.5, 112, 400, 32)
    d.vertex("record_box", "", rect_style(WHITE, LINE, 1.5, radius=8), 480, 175, 835, 530)
    table_x, table_y, table_w, field_w, row_h = 520, 220, 755, 305, 41
    rows = [
        ("Artifact ID", "A102"),
        ("Fidelity", "High"),
        ("Dependency", "Depends on Entity E17"),
        ("Redundancy", "Low"),
        ("Bottleneck", "Yes"),
        ("Audit Reason", "Critical supporting evidence"),
        ("Recommended Action", "Verify linked entity before update"),
        ("Interpretation", "Maintain during knowledge revision"),
        ("Timestamp", "2026-07-12"),
        ("Record Version", "v1.0"),
    ]
    d.vertex("record_table", "", rect_style(WHITE, MID, 1.0, radius=2), table_x, table_y, table_w, row_h * len(rows))
    d.vertex("record_table_split", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), table_x + field_w, table_y, 1, row_h * len(rows))
    for idx, (field, value) in enumerate(rows):
        cy = table_y + row_h * idx + row_h / 2
        if idx > 0:
            d.vertex(f"record_sep_{idx}", "", rect_style(LIGHT, LIGHT, 0.1, radius=0), table_x, table_y + row_h * idx, table_w, 1)
        d.vertex(f"record_field_{idx}", field, text_style(9, bold=True, align="left"), table_x + 24, cy - 13, field_w - 38, 26)
        d.vertex(f"record_value_{idx}", value, text_style(9, align="left"), table_x + field_w + 24, cy - 13, table_w - field_w - 40, 26)
    d.vertex("persistent_label", "Persistent Audit Record", rect_style(BLUE, BLUE, 1.0, radius=8, font_color=WHITE), 732.5, 647, 330, 38)

    d.vertex("right_title", "Maintenance Operations", text_style(11, bold=True), 1390, 112, 340, 32)
    operation_labels = ["Query Records", "Dependency Inspection", "Knowledge Update", "Governance Log"]
    operation_ys = [215, 325, 435, 545]
    for idx, (label, y) in enumerate(zip(operation_labels, operation_ys, strict=True)):
        d.vertex(f"op_{idx}", label, rect_style(WHITE, MID, 1.3, radius=8), 1390, y, 340, 58)
        if idx < len(operation_labels) - 1:
            d.edge(f"op_edge_{idx}", 1560, y + 70, 1560, operation_ys[idx + 1] - 13)
    d.edge("maintenance_cycle", 1390, 574, 1155, 666, points=[(1342, 574), (1342, 666)])

    d.edge("lifecycle_arrow", 150, 810, 1650, 810)
    d.vertex("lifecycle_title", "Knowledge Lifecycle", text_style(11, bold=True), 715, 745, 370, 32)
    for idx, (label, x) in enumerate([("Construction", 285), ("Maintenance", 690), ("Governance", 1095), ("Reuse", 1500)]):
        d.vertex(f"tick_{idx}", "", rect_style(LINE, LINE, 0.1, radius=0), x, 800, 1, 20)
        d.vertex(f"life_label_{idx}", label, text_style(9, bold=True), x - 90, 844, 180, 30)
    d.vertex(
        "caption",
        "An SC-FMA audit record preserves artifact identity, dependency context, structural roles, and maintenance rationale,<br>"
        "enabling persistent querying, governance, and knowledge lifecycle management beyond a single ranking decision.",
        text_style(9),
        200,
        892,
        1400,
        70,
    )


def write_outputs() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    svg_path = SOURCE_DIR / f"{BASE}.svg"
    drawio_path = SOURCE_DIR / f"{BASE}.drawio"
    pdf_path = SOURCE_DIR / f"{BASE}.pdf"

    svg_path.write_text(generate_svg(), encoding="utf-8", newline="\n")
    d = Drawio()
    add_drawio_cells(d)
    drawio_path.write_text(d.xml(), encoding="utf-8", newline="\n")

    try:
        import cairosvg  # type: ignore
    except ImportError:
        cairosvg = None

    if cairosvg is not None:
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))

    for path in [svg_path, drawio_path, pdf_path]:
        if path.exists():
            copy2(path, PACKAGE_DIR / path.name)
            print(path)
            print(PACKAGE_DIR / path.name)


if __name__ == "__main__":
    write_outputs()
