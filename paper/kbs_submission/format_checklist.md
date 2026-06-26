# KBS Format Compliance Checklist

Repository-level submission status is currently `methodological_submission_possible_with_claim_boundaries`; this checklist records package-format checks for the claim-bounded KBS upload package.

- [x] Final upload boundary is isolated under `final_package/`.
- [x] Required upload files are present: `cover_letter.docx`, `Highlights.docx`, `manuscript.pdf`, `supplementary.docx`, `latex_source.zip`.
- [x] Author metadata is filled in manuscript, supplementary source, and cover letter.
- [x] Funding statement is present.
- [x] Declaration of Competing Interest is present with the user-supplied wording.
- [x] Data Availability is present and distinguishes public datasets from derived artifacts to be deposited in an anonymous public repository for review and released with the final article.
- [x] Declaration of generative AI and AI-assisted technologies is present.
- [x] CRediT authorship contribution statement uses named authors.
- [x] Manuscript PDF compiled from `final_source/manuscript.tex` after the PRM800K auditability revision, including `Why Calibration Beyond Direct Ranking`, fixed Audit Cards, and the Complexity Summary Table.
- [x] Supplementary content was converted to `supplementary.docx`; reproducible source remains in `final_source/supplementary.tex` and `latex_source.zip`.
- [x] Highlights content was converted to `Highlights.docx`.
- [x] Manuscript page count is content-faithful to the cleanly compiled source after the current evidence-boundary revision and remains within the project-specific 12--25 page quality gate, not a journal rule; KBS imposes no hard page limit.
- [x] Supplementary data map includes the PRM800K audit-prioritization report and summary as context-only artifacts.
- [x] Supplementary diagnostic map includes WebQSP trace-audit outputs as fixed-schema separability and metric-artifact evidence only, with no KGQA performance claim.
- [x] KBS audit demonstration section (Section 6) present in manuscript with a fixed-budget audit comparison and a rule/RAG/KG-style audit-card interpretation paragraph.
- [x] Explainable Audit Prioritization is promoted consistently across Abstract, Introduction/contributions, PRM800K interpretation, Audit Cards, and Conclusion.
- [x] KBS audit demo artifact exists at `outputs/kbs_audit_demo/audit_demo_report.json`.
- [x] Manuscript PDF was compiled and page-count checked after the current evidence-boundary revision.
- [x] Source zip includes manuscript/supplementary LaTeX sources, bibliography, CAS files, and PNG artwork.
- [x] Source zip excludes LaTeX auxiliary/build artifacts.
- [x] Package verifier passes with author metadata, PDF text, and DOCX text gates after the package refresh:
  `python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission\final_package --require-author-metadata --require-pdf-text --min-manuscript-pages 12 --max-manuscript-pages 25`
- [x] Verifier unit tests pass:
  `python -m pytest tests/test_claim_boundaries.py tests/test_kbs_submission_package_verifier.py -q`
- [x] Claim-boundary/DOI gate passes:
  `python scripts\check_claim_boundaries.py --active-only --check-dois`
- [x] Manual drift scan checked manuscript source, packaged source zip, and rendered PDF text for `outperform`, `improve PRM training`, `generalize to reasoning tasks`, and `better than w_struct`; remaining PRM-training, causal-identification, and external-generalization mentions are negative boundary statements only.
- [x] DOCX visual rendering: `cover_letter.docx`, `Highlights.docx`, and `supplementary.docx` rendered to PDF/PNG via LibreOffice and visually/textually checked; cover letter, highlights, supplementary tables, and edited MuSiQue paragraphs render without clipping, overlap, or table overflow.
