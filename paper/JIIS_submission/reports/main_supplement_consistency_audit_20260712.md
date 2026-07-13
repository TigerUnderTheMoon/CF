# Main manuscript and supplementary consistency audit

Date: 2026-07-12

Scope:
- `paper/JIIS_submission/source/manuscript.tex`
- `paper/JIIS_submission/source/supplementary.tex`
- synchronized copies in `paper/JIIS_submission/submission_package/`

## Checks performed

1. Extracted main-text mentions of supplementary material, Appendix A/B, supplementary diagnostics, failure taxonomy, KG backend details, confidence intervals, and reproducibility artifacts.
2. Compared those mentions against supplementary sections, captions, and labels.
3. Checked LaTeX `\ref{...}` labels in the main manuscript for unresolved local references.
4. Compiled both PDFs and scanned logs for undefined references or undefined citations.

## Issues found and fixed

- The main manuscript used the hard-coded phrase `Supplementary Tables C.8 and C.9`. This was fragile after restoring and extending the supplementary file. It was replaced with a stable reference to the supplementary `Process-Annotation Variant Details and Audit Readout` section.
- The main manuscript claimed that full edge lists, the audit report, and degeneracy-handling details were in the supplement, but the restored supplement only contained a high-level Countries-KG paragraph. The main text now refers to edge-list schema and summary counts, audit-report artifacts, and degeneracy-handling rules; the supplement now includes `tab:supp-kg-backend-artifacts` with those details.
- The supplement lacked an explicit map from main-text supplementary references to their locations. A `Main-text and supplementary consistency map` section and `tab:supp-consistency-map` were added.
- The restored supplementary Appendix A/B/C sections and front tables lacked stable labels. Labels were added for the synthetic scalability, necessary-condition diagnosis, cached-label reproducibility, and supporting tables.

## Supplementary content added for reviewer defense

- A main-text/supplementary consistency map showing where each supplementary claim is supported.
- Countries-KG backend artifact and degeneracy-handling details, including edge-list schema, edge counts, relation families, audit-report artifacts, degeneracy rules, and claim boundaries.
- Stable labels for synthetic scalability, synthetic path-length diagnostics, PRM800K necessary-condition context, and cached-label reproducibility.

## Verification status

- Main manuscript compiles to 22 pages.
- Supplementary material compiles to 24 pages.
- LaTeX logs contain no undefined references or undefined citations after recompilation.
- Submission-package manuscript and supplementary PDFs are synchronized with the source PDFs by hash.
