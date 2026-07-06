# DKE Format Compliance Checklist

Repository-level submission status remains bounded to audit-prioritization evidence; this checklist records package-format checks for the DKE upload package.

- [x] Final upload boundary is isolated under `final_package/`.
- [x] Required upload files are present: `cover_letter.docx`, `Highlights.docx`, `manuscript.pdf`, `supplementary.pdf`, `latex_source.zip`.
- [x] Author metadata is filled in manuscript, supplementary source, and cover letter.
- [x] Funding statement is present.
- [x] Declaration of Competing Interest is present with the user-supplied wording.
- [x] Data Availability is present and distinguishes public datasets from derived artifacts to be deposited in an anonymous public repository for review and released with the final article.
- [x] Declaration of generative AI and AI-assisted technologies is present.
- [x] CRediT authorship contribution statement uses named authors.
- [x] Manuscript PDF compiled from `final_source/manuscript.tex` after the DKE transfer revision, including the knowledge-engineering abstract, Introduction, experiment order, Figure 1 workflow, and Scope and Limitations section.
- [x] Supplementary material was compiled as `supplementary.pdf` from `final_source/supplementary.tex`; authoritative equations, algorithms, tables, figures, and captions remain in `final_source/supplementary.tex` and `latex_source.zip`.
- [x] Highlights content was converted to `Highlights.docx`.
- [x] Manuscript page count is content-faithful to the cleanly compiled source after the DKE transfer revision and remains within the project-specific 12--25 page quality gate.
- [x] Supplementary data map includes the PRM800K audit-prioritization report and summary as context-only artifacts.
- [x] Supplementary diagnostic map includes WebQSP trace-audit outputs as fixed-schema separability and metric-artifact evidence only, with no KGQA task-success claim.
- [x] DKE knowledge-audit material is positioned as graph-aware audit records for fixed-budget curation, not as deployment validation.
- [x] Audit prioritization is promoted consistently across Abstract, Introduction/contributions, PRM800K interpretation, audit cards, and Conclusion.
- [x] Audit demonstration artifacts are treated as workflow illustrations or diagnostics, not production knowledge-base validation.
- [x] Manuscript PDF was compiled and page-count checked after the current evidence-boundary revision.
- [x] Source zip includes manuscript/supplementary LaTeX sources, bibliography, CAS files, and PNG artwork.
- [x] Source zip excludes LaTeX auxiliary/build artifacts.
- [x] Package verifier passes with PDF text and DOCX text gates after the package refresh:
  `python scripts\verify_dke_submission_package.py --package-dir paper\dke_submission\final_package --require-pdf-text --min-manuscript-pages 12 --max-manuscript-pages 25`
- [x] Verifier unit tests pass:
  `python -m pytest tests/test_claim_boundaries.py tests/test_dke_submission_package_verifier.py -q`
- [x] Claim-boundary/DOI gate passes:
  `python scripts\check_claim_boundaries.py --active-only --check-dois`
- [x] Manual drift scan checked manuscript source, packaged source zip, and rendered PDF text for `outperform`, `improve PRM training`, `generalize to reasoning tasks`, and `better than w_struct`; remaining PRM-training, causal-identification, and external-generalization mentions are negative boundary statements only.
- [x] DOCX visual rendering: `cover_letter.docx` and `Highlights.docx` rendered to PDF/PNG via LibreOffice and visually/textually checked; supplementary material is provided as compiled `supplementary.pdf`.
