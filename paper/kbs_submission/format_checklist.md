# KBS Format Compliance Checklist

Repository-level submission status is currently `methodological_submission_possible_with_claim_boundaries`; this checklist records package-format checks for the claim-bounded KBS upload package.

- [x] Final upload boundary is isolated under `final_package/`.
- [x] Required upload files are present: `cover_letter.docx`, `Highlights.docx`, `manuscript.pdf`, `supplementary.docx`, `latex_source.zip`.
- [x] Author metadata is filled in manuscript, supplementary source, and cover letter.
- [x] Funding statement is present.
- [x] Declaration of Competing Interest is present with the user-supplied wording.
- [x] Data Availability is present and distinguishes public PRM800K from derived artifacts available on request.
- [x] Declaration of generative AI and AI-assisted technologies is present.
- [x] CRediT authorship contribution statement uses named authors.
- [x] Manuscript PDF compiled from `final_source/manuscript.tex` after the moderate-title revision.
- [x] Supplementary content was converted to `supplementary.docx`; reproducible source remains in `final_source/supplementary.tex` and `latex_source.zip`.
- [x] Highlights content was converted to `Highlights.docx`.
- [x] Manuscript page count is content-faithful to the cleanly compiled compressed source: `manuscript.pdf` 5 pages, within the `<=20` page gate.
- [x] Supplementary data map includes the PRM800K audit-prioritization report and summary as context-only artifacts.
- [x] Manuscript PDF was rendered to current PNG contact sheets and visually checked after the moderate-title revision.
- [x] Source zip includes manuscript/supplementary LaTeX sources, bibliography, CAS files, and PNG artwork.
- [x] Source zip excludes LaTeX auxiliary/build artifacts.
- [x] Package verifier passes with author metadata, PDF text, and DOCX text gates after the package refresh:
  `python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission\final_package --require-author-metadata --require-pdf-text --max-manuscript-pages 20`
- [x] Verifier unit tests pass:
  `pytest -q tests/test_kbs_submission_package_verifier.py`
- [ ] DOCX visual rendering: blocked locally because LibreOffice/`soffice.exe` is not installed; DOCX structure and required text are checked directly.
