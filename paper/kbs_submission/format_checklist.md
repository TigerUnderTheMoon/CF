# KBS Format Compliance Checklist

- [x] Final upload boundary is isolated under `final_package/`.
- [x] Required upload files are present: `cover_letter.docx`, `Highlights.pdf`, `manuscript.pdf`, `supplementary.pdf`, `latex_source.zip`.
- [x] Author metadata is filled in manuscript, supplementary source, and cover letter.
- [x] Funding statement is present.
- [x] Declaration of Competing Interest is present with the user-supplied wording.
- [x] Data Availability is present with the user-supplied wording.
- [x] Declaration of generative AI and AI-assisted technologies is present.
- [x] CRediT authorship contribution statement uses named authors.
- [x] Manuscript PDF compiled from `final_source/manuscript.tex` with exit code 0.
- [x] Supplementary PDF compiled from `final_source/supplementary.tex` with exit code 0.
- [x] Highlights PDF extracted as a standalone 1-page file from the full compiled `main.pdf`.
- [x] Page counts are content-faithful to the cleanly recompiled full PDF: `main.pdf` 7 pages, `Highlights.pdf` 1 page, `manuscript.pdf` 6 pages, `supplementary.pdf` 6 pages.
- [x] Manuscript and supplementary PDFs were rendered to PNG contact sheets and visually checked.
- [x] Source zip includes manuscript/supplementary LaTeX sources, bibliography, CAS files, and PNG artwork.
- [x] Source zip excludes LaTeX auxiliary/build artifacts.
- [x] Package verifier passes with author metadata and PDF text gates:
  `python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission\final_package --require-author-metadata --require-pdf-text`
- [x] Verifier unit tests pass:
  `pytest -q tests/test_kbs_submission_package_verifier.py`
- [ ] DOCX visual rendering: blocked locally because LibreOffice/`soffice.exe` is not installed; DOCX structure and required text were checked directly.
