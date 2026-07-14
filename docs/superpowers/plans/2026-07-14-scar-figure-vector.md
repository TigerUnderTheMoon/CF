# SCAR Figure 1 Vector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce publication-ready, editable SVG and PDF versions of the approved SCAR framework figure.

**Architecture:** Build one self-contained SVG as the source of truth using native text, shape, path, marker, and group elements. Convert that SVG directly to a one-page vector PDF, then inspect both formats structurally and through high-resolution renders.

**Tech Stack:** SVG 1.1/XML, DejaVu Sans, Inkscape or CairoSVG, Poppler, PowerShell validation.

---

### Task 1: Create the native SVG artwork

**Files:**
- Create: `paper/JIIS_submission/source/figures/fig_scar_framework.svg`

- [ ] **Step 1: Define the publication canvas and reusable styles**

Use a `1600 x 900` view box with a white background, DejaVu Sans text, native arrow markers, and named color classes. Set normal labels to at least 27 SVG units so that text remains at least 8 pt when placed at 170 mm width.

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc">
  <title id="title">SCAR framework for budget-aware knowledge-graph maintenance</title>
  <desc id="desc">Information-system artifacts are extracted into a dependency graph, serialized as SCAR records, and consumed by several policies.</desc>
  <style>
    text { font-family: "DejaVu Sans", Arial, sans-serif; fill: #172033; }
    .label { font-size: 27px; }
    .small { font-size: 26px; }
    .section-title { font-size: 31px; font-weight: 700; }
  </style>
</svg>
```

- [ ] **Step 2: Build the five-stage hierarchy**

Create named groups `system-inputs`, `graph-extraction`, `scar-contract`, `policy-consumers`, and `illustrative-uses`. Use blue for extraction and SCAR, green for consumers, and orange for illustrative uses. Keep SCAR as the largest central region and place the five design requirements in a connected side panel.

- [ ] **Step 3: Add exact SCAR 1.0 terminology**

Use these labels without adding unimplemented fields:

```text
Artifact ID; Auditable Status; Graph Snapshot; Snapshot Digest;
Bottleneck Status; Redundancy Status; Redundancy Group ID;
Downstream Impact Count; Sink Drop Count; Raw Risk Score;
At-risk Terminals; Candidate Rule; Protocol Version; Source Unit;
Replicate; Candidate-set Digest.
```

Label the final band `Illustrative Downstream Maintenance Uses`. Do not include a figure number or caption in the SVG.

- [ ] **Step 4: Validate SVG structure**

Run:

```powershell
[xml](Get-Content -Raw paper/JIIS_submission/source/figures/fig_scar_framework.svg) | Out-Null
rg -n '<image|data:image|Fig\. 1' paper/JIIS_submission/source/figures/fig_scar_framework.svg
```

Expected: XML parsing succeeds and `rg` returns no matches.

### Task 2: Export the vector PDF

**Files:**
- Create: `paper/JIIS_submission/source/figures/fig_scar_framework.pdf`

- [ ] **Step 1: Detect a vector conversion tool**

Run:

```powershell
Get-Command inkscape,rsvg-convert -ErrorAction SilentlyContinue
```

If neither is available, use bundled Python with CairoSVG and keep the SVG-to-PDF conversion vector-native.

- [ ] **Step 2: Export and crop the PDF**

Preferred command:

```powershell
inkscape paper/JIIS_submission/source/figures/fig_scar_framework.svg --export-type=pdf --export-filename=paper/JIIS_submission/source/figures/fig_scar_framework.pdf --export-area-drawing
```

Expected: a one-page PDF cropped to the SVG artwork.

- [ ] **Step 3: Verify PDF structure and fonts**

Run:

```powershell
pdfinfo paper/JIIS_submission/source/figures/fig_scar_framework.pdf
pdffonts paper/JIIS_submission/source/figures/fig_scar_framework.pdf
```

Expected: one page; DejaVu Sans is embedded or subset; no bitmap-only font representation.

### Task 3: Render and visually verify both outputs

**Files:**
- Create temporarily: `tmp/pdfs/scar_framework_svg.png`
- Create temporarily: `tmp/pdfs/scar_framework_pdf.png`

- [ ] **Step 1: Render the SVG and PDF at high resolution**

Use Inkscape or CairoSVG for the SVG render and Poppler for the PDF render. Render each at approximately 1800 pixels wide.

- [ ] **Step 2: Inspect the rendered images**

Check all five bands, the design-requirement panel, arrow direction, label wrapping, minimum text size, clipping, and alignment. Confirm that the image has no embedded caption.

- [ ] **Step 3: Correct and rerender until clean**

Apply only targeted SVG edits for observed defects. Repeat structural checks and both renders after every meaningful correction.

- [ ] **Step 4: Run final artifact checks**

Run:

```powershell
Get-FileHash paper/JIIS_submission/source/figures/fig_scar_framework.svg, paper/JIIS_submission/source/figures/fig_scar_framework.pdf -Algorithm SHA256
git diff --check -- paper/JIIS_submission/source/figures/fig_scar_framework.svg
```

Expected: two non-empty hashes and no whitespace errors.
