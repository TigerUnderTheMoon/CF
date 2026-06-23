# Final IPM Package Manifest

Purpose: define the clean upload boundary for the claim-bounded knowledge-intensive information processing methodology and PRM800K-like audit-prioritization package.

This package must be described only as a claim-bounded IPM upload package. The PRM800K stratified audit-prioritization gate remains `moderate`, so title, abstract, cover letter, and manifest language must stay within moderate preliminary PRM800K-like audit-prioritization support.

## Final upload files

The portal-shaped package is `final_package/` and contains exactly five files:

- `cover_letter.docx` -- Word cover letter with named authors and bounded knowledge-intensive positioning.
- `Highlights.docx` -- Word highlights file converted from the standalone highlights content.
- `manuscript.pdf` -- manuscript PDF compiled from `final_source/manuscript.tex`.
- `supplementary.docx` -- Word supplementary file converted from the supplementary content.
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

- `manuscript.tex` compiled with TeX Live/latexmk after the moderate-title revision: exit code 0, output `manuscript.pdf` (includes Section 6 Audit Prioritization Demonstration).
- `Highlights.docx` contains the final highlights text and current title, with no KBS residual wording.
- `supplementary.docx` contains the supplementary title, author names, and supplementary content converted from the split supplementary material.
- Supplementary data map now includes `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` and `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md` as audit-prioritization context only, and `outputs/kbs_audit_demo/audit_demo_report.json` as the audit demonstration artifact (Section 6).
- Manuscript PDF pages were rendered to current PNG contact sheets and visually checked for page count, footer consistency, figure placement, and obvious clipping.
- `cover_letter.docx`, `Highlights.docx`, and `supplementary.docx` were structurally checked for required DOCX parts and required text after the moderate-title revision. Visual DOCX rendering could not be completed because `soffice.exe`/LibreOffice is not installed on this machine.
- `python scripts/verify_ipm_submission_package.py --package-dir paper/ipm_submission/final_package --require-author-metadata --require-pdf-text --min-manuscript-pages 12 --max-manuscript-pages 20` passes.
- `pytest -q tests/test_ipm_submission_package_verifier.py` passes.

## Claim boundary

The package supports a bounded knowledge-intensive diagnostic and audit-prioritization contribution: SC-FMA calibration, controlled synthetic proxy-label ranking evidence, PRM800K step-label ranking with `w_struct` as the primary real-data result, Ridge as the closest SC-FMA approximation on that route, moderate preliminary PRM800K audit-prioritization context, a preliminary audit demonstration (Section 6, claim `M_KBS_AUDIT_DEMONSTRATION`) applying SC-FMA to knowledge-intensive process-annotation audit prioritization, and a fixture-level ontology-aware edge pilot as diagnostic context. It does not claim downstream PRM/filtering gains, GSM8K/HotpotQA replay-pass evidence, production deployment validation, or formal causal identification.
