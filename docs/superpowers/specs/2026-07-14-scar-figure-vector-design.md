# SCAR Figure 1 Vector Design

## Objective

Rebuild the supplied SCAR framework image as publication-ready vector artwork for the JIIS manuscript. Produce editable SVG and PDF outputs without embedding the source PNG or placing a figure number or caption inside the artwork.

## Scope

Create these files:

- `paper/JIIS_submission/source/figures/fig_scar_framework.svg`
- `paper/JIIS_submission/source/figures/fig_scar_framework.pdf`

Do not modify `manuscript.tex` or the submission package in this task. Manuscript insertion and package synchronization are separate follow-up work.

## Visual Structure

Use a wide, approximately 16:9 canvas organized into five vertical stages:

1. Intelligent information-system inputs.
2. Dependency-graph construction and artifact extraction.
3. The SCAR record contract and its design requirements.
4. Policy consumers sharing the same SCAR contract.
5. Illustrative downstream maintenance uses.

The SCAR block remains the visual center. The five design requirements appear beside it and connect bidirectionally to the contract. The palette retains blue for extraction and representation, green for consumers, and orange for illustrative downstream uses.

## Content Contract

The figure uses the current SCAR 1.0 terminology:

- Identity: artifact ID and auditable status.
- Snapshot: graph snapshot identifier and digest.
- Structural fields: bottleneck status, redundancy status, redundancy group ID, downstream impact count, and sink drop count.
- Risk and impact: raw risk score as normalized impact used for tie-breaking, plus at-risk terminal identifiers.
- Source and run metadata: candidate rule, protocol version, source unit, replicate, and candidate-set SHA-256 digest.
- Design requirements: snapshot identity, candidate reproducibility, structural role preservation, dependency consequences, and policy-independent consumption.

The bottom row is explicitly labeled as illustrative downstream maintenance uses. It must not imply validated production capabilities or measured operational outcomes.

## Publication Constraints

- Target placement width: approximately 170 mm.
- Minimum final text size: 8 pt at target width.
- All text remains editable SVG text.
- Icons, arrows, borders, and connectors use native vector paths or shapes.
- No raster `<image>` element is permitted.
- Use an embeddable sans-serif font with a broadly available fallback.
- Do not embed `Fig. 1` or a caption in the artwork.
- Keep the PDF page cropped to the artwork bounds.

## Output and Conversion

The SVG is the source of truth. Export the PDF from the SVG using an available vector conversion tool that preserves text and embeds or subsets fonts. Do not use raster intermediate files for conversion.

## Verification

Verification must confirm:

1. The SVG parses as XML and contains no `<image>` elements.
2. The PDF contains one page and has an artwork-sized media box.
3. PDF font inspection reports embedded or subset fonts where the converter supports them.
4. High-resolution renders of both SVG and PDF show no clipping, overlap, missing glyphs, or broken arrows.
5. A target-width readability check confirms the smallest text is at least 8 pt.
6. The SVG and PDF present the same content and geometry.

## Acceptance Criteria

The task is complete when both vector files exist in the source figure directory, pass the structural checks above, and visually match the approved publication-optimized information hierarchy without reproducing the PNG's embedded caption or excessive text density.
