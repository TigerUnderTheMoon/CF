# IPM SC-FA Reframing Design

## Objective

Reframe the active Information Sciences submission toward an Information
Processing & Management audience by presenting the method as an information
organization and audit representation framework rather than a metacognitive or
reasoning-centered mechanism.

## Naming

- Manuscript title:
  `Structurally-Calibrated Functional Attribution for Information Audit Prioritization in Knowledge-Intensive Systems`
- Method name:
  `Structurally-Calibrated Functional Attribution`
- Method abbreviation:
  `SC-FA`
- All reader-facing uses of `SC-FMA` and the previous full method name are
  replaced across the manuscript, figures, supplementary material, and
  submission documents.
- Archived experiment paths, output identifiers, and reproducibility filenames
  containing lowercase `scfma` remain unchanged because they identify existing
  artifacts and are not reader-facing method labels.

## Manuscript Changes

### Abstract

- Open with the growth of intermediate information artifacts and the resulting
  inspection and information-quality-management burden.
- Define the gap in scalar scoring approaches: they do not organize review
  priorities by dependency, redundancy, bottleneck, and maintenance roles.
- Introduce SC-FA as an information organization and audit representation
  framework.
- Use `information artifacts` instead of `knowledge artifacts` where the
  replacement is semantically valid.
- Compress the correlation reporting while preserving the evidence boundary
  that the strongest supervised fidelity field remains the best ranking signal
  and structural fields are diagnostic rather than independently validated
  ranking improvements.

### Introduction

- Paragraph 1: establish information overload from retrieval evidence,
  verification signals, reasoning steps, provenance records, and related
  intermediate information objects.
- Paragraph 2: define the fixed-budget information audit problem as organizing
  artifacts by inspection role, not merely identifying scalar importance.
- Paragraph 3: define SC-FA as an information organization and audit
  representation layer.
- Remove the operational explanation of `metacognitive`.
- Replace the contribution paragraph with:
  1. a fixed-budget information audit representation problem for heterogeneous
     intermediate artifacts;
  2. SC-FA as a structurally calibrated framework that transforms scalar
     importance signals into decomposed audit records;
  3. evaluation through information coverage, representation consistency, and
     audit-target organization analyses.

### Remaining Sections

- Replace reader-facing `SC-FMA` labels with `SC-FA`.
- Remove residual reader-facing uses of the previous full method name.
- Preserve formulas, symbols, numerical results, datasets, experimental
  settings, tables, citations, labels, references, and claim boundaries.
- Revise knowledge-engineering wording only where needed for terminology
  consistency with the approved information-organization framing.

## Figure Changes

- Update Figure 1 embedded label to
  `SC-FA: information organization layer`.
- Reframe the workflow from knowledge-artifact transformation toward
  information-artifact organization and audit decision support.
- Update the generator, editable figure source, SVG, PDF, caption, and any
  linked package copies consistently.

## Submission Materials

- Update the title and method name in the cover letter and competing-interest
  declaration.
- Revise the cover letter toward information overload, information
  organization, review cost, and audit decision support.
- Revise Highlights to use information-artifact and information-audit framing.
- Update author metadata, package manifests, revision notes, and active
  consistency documents that contain the previous title or reader-facing
  method name.
- Do not rewrite unrelated administrative or empirical content.

## Output Synchronization

- Compile `final_source/manuscript.tex`.
- Compile `final_source/supplementary.tex`.
- Regenerate the updated Figure 1 assets.
- Rebuild `final_package/latex_source.zip`.
- Synchronize the compiled manuscript and supplementary PDFs into
  `final_package`.
- Regenerate edited DOCX files while preserving their existing layout.

## Verification

- No reader-facing `SC-FMA`, previous full method title, or operational
  `metacognitive` explanation remains in active submission artifacts.
- Internal lowercase reproducibility identifiers such as `scfma_variants` are
  allowed and must remain stable.
- Main and supplementary LaTeX builds exit successfully with no fatal errors.
- Submission PDFs match their compiled source PDFs by SHA-256.
- DOCX title and method-name checks pass.
- Empirical numbers, formulas, labels, references, sample sizes, and evidence
  boundaries remain unchanged.
