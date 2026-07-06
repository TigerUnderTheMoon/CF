# Information Sciences Format Compliance Checklist

Repository-level submission status remains bounded to audit-record representation evidence; this checklist records package-format checks for the Information Sciences upload package.

- [x] Final upload boundary is isolated under `final_package/`.
- [x] Required upload files are present: `cover_letter.docx`, `Highlights.docx`, `declaration_of_competing_interests.docx`, `manuscript.pdf`, `supplementary.pdf`, `latex_source.zip`.
- [x] Author metadata is filled in manuscript, supplementary source, and cover letter.
- [x] Funding statement is present.
- [x] Declaration of Competing Interest is present with the user-supplied wording.
- [x] Data Availability is present and distinguishes public datasets from derived artifacts to be deposited in an anonymous public repository for review and released with the final article.
- [x] Declaration of generative AI and AI-assisted technologies is present.
- [x] CRediT authorship contribution statement uses named authors.
- [x] Manuscript PDF compiled from `final_source/manuscript.tex` after the Information Sciences transfer revision, including the information/knowledge-representation abstract, Introduction, experiment order, Figure 1 workflow, and Scope and Limitations section.
- [x] Supplementary material was compiled as `supplementary.pdf` from `final_source/supplementary.tex`; authoritative equations, algorithms, tables, figures, and captions remain in `final_source/supplementary.tex` and `latex_source.zip`.
- [x] Highlights content was converted to `Highlights.docx`.
- [x] Manuscript page count is content-faithful to the cleanly compiled source after the Information Sciences transfer revision and remains within the project-specific 12--25 page quality gate.
- [x] Supplementary data map includes the process-annotation audit-record coverage report and summary as context-only artifacts.
- [x] Supplementary diagnostic map includes WebQSP trace-audit outputs as fixed-schema separability and metric-artifact evidence only, with no KGQA task-success claim.
- [x] Information Sciences knowledge-audit material is positioned as graph-aware audit records for fixed-budget curation, not as deployment validation.
- [x] Audit-record construction is promoted consistently across Abstract, Introduction/contributions, process-annotation interpretation, audit cards, and Conclusion.
- [x] Audit demonstration artifacts are treated as workflow illustrations or diagnostics, not production knowledge-base validation.
- [x] Manuscript PDF was compiled and page-count checked after the current evidence-boundary revision.
- [x] Source zip includes manuscript/supplementary LaTeX sources, bibliography, CAS files, and PNG artwork.
- [x] Source zip excludes LaTeX auxiliary/build artifacts.
- [x] Direct package validation passes after the package refresh against `paper\information_sciences_submission\final_package`: required files are present, PDFs are readable, `latex_source.zip` contains the required LaTeX sources/CAS files/figures, and local build artifacts are excluded.
- [x] Claim-boundary tests and direct package validation pass after the Information Sciences package refresh.
- [x] Claim-boundary/DOI gate passes:
  `python scripts\check_claim_boundaries.py --active-only --check-dois`
- [x] Manual drift scan checked manuscript source, packaged source zip, and rendered PDF text for `outperform`, `improve PRM training`, `generalize to reasoning tasks`, and `better than w_struct`; remaining PRM-training, causal-identification, and external-generalization mentions are negative boundary statements only.
- [x] DOCX visual rendering: `cover_letter.docx` and `Highlights.docx` rendered to PDF/PNG via LibreOffice and visually/textually checked; supplementary material is provided as compiled `supplementary.pdf`.
