# Final KBS Submission Manifest

Purpose: define the clean upload boundary for the Knowledge-Based Systems submission package.

## Final upload files

The portal-facing package is `final_package/` and contains exactly five files:

- `cover_letter.docx` -- Word cover letter with named authors and bounded KBS positioning.
- `Highlights.pdf` -- standalone Highlights PDF extracted from page 1 of the full compiled `main.pdf`.
- `manuscript.pdf` -- manuscript PDF compiled from `final_source/manuscript.tex`.
- `supplementary.pdf` -- supplementary PDF compiled from `final_source/supplementary.tex`.
- `latex_source.zip` -- source bundle containing `manuscript.tex`, `supplementary.tex`, `references.bib`, CAS style files, and all PNG artwork under `figures/`.

## Author and statement metadata

- Authors: Haoran Ma; Ningning Wang.
- Affiliations:
  - College of Management Science and Engineering, Beijing Information Science and Technology University, Beijing 102200, China.
  - Institute of Information Systems, ESG Intelligent Application Innovation Research Center, Beijing 102200, China.
- Emails: `mahaoran0000@foamail.com`; `wangningning@bistu.edu.cn`.
- Funding: National Social Science Fund of China Project (24BSH018); Beijing Natural Science Foundation Project (L252145).
- Declaration of Competing Interest: The authors declared that they have no conflicts of interest to this work.
- Data Availability: PRM800K is publicly available from its original source. Derived locked-split reports, audit-prioritization artifacts, and reproduction scripts will be made available by the authors on request.

## Source boundary

`latex_source.zip` intentionally excludes local build artifacts:

- `*.aux`, `*.bbl`, `*.blg`, `*.fdb_latexmk`, `*.fls`, `*.log`, `*.out`, `*.abs`, `*.synctex.gz`
- temporary `_tmp_*` files
- build directories and render QA directories

## Verification

- The full compiled `main.pdf` has 8 pages and is used only as the source for extracting the standalone Highlights page.
- `Highlights.pdf` has 1 page.
- `manuscript.tex` compiled with TeX Live/latexmk: exit code 0, output `manuscript.pdf` with 7 pages.
- `supplementary.tex` compiled with TeX Live/latexmk: exit code 0, output `supplementary.pdf` with 6 pages.
- Supplementary data map now includes `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` and `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md` as audit-prioritization context only.
- PDF pages were rendered to PNG contact sheets and visually checked for page count, footer consistency, figure placement, and obvious clipping.
- `cover_letter.docx` was structurally checked for required DOCX parts and required text. Visual DOCX rendering could not be completed because `soffice.exe`/LibreOffice is not installed on this machine.
- `python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission\final_package --require-author-metadata --require-pdf-text` passes.
- `pytest -q tests/test_kbs_submission_package_verifier.py` passes.

## Claim boundary

The package supports a methodological KBS submission: SC-FMA calibration, controlled synthetic proxy-label ranking evidence, PRM800K step-label ranking with `w_struct` as the primary real-data result, Ridge as the closest SC-FMA approximation on that route, offline PRM800K audit-prioritization context, and a fixture-level ontology-aware edge pilot as diagnostic context. It does not claim downstream PRM/filtering gains, GSM8K/HotpotQA replay-pass evidence, deployed knowledge-base workflow validation, or formal causal identification.
