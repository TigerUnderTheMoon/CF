# Final KBS Package Manifest

Purpose: define the clean upload boundary for the claim-bounded Knowledge-Based Systems methodology and PRM800K-like audit-prioritization package.

This package must be described only as a claim-bounded KBS upload package. The PRM800K stratified audit-prioritization gate remains `moderate`, so title, abstract, cover letter, and manifest language must stay within moderate preliminary PRM800K-like audit-prioritization support.

## Final upload files

The portal-shaped package is `final_package/` and contains exactly five files:

- `cover_letter.docx` -- Word cover letter with named authors and bounded KBS positioning.
- `Highlights.docx` -- Word highlights file converted from the standalone highlights content.
- `manuscript.pdf` -- manuscript PDF compiled from `final_source/manuscript.tex`.
- `supplementary.docx` -- Word supplementary file converted from the supplementary content.
- `latex_source.zip` -- source bundle containing `manuscript.tex`, `supplementary.tex`, `references.bib`, CAS style files, and all PNG artwork under `figures/`.

## Author and statement metadata

- Authors: Haoran Ma; Ningning Wang.
- Affiliations:
  - College of Management Science and Engineering, Beijing Information Science and Technology University, Beijing 102200, China.
  - Institute of Information Systems, ESG Intelligent Application Innovation Research Center, Beijing 102200, China.
- Emails: `mahaoran0000@foxmail.com`; `wangningning@bistu.edu.cn`.
- Funding: National Social Science Fund of China Project (24BSH018); Beijing Natural Science Foundation Project (L252145).
- Declaration of Competing Interest: The authors declared that they have no conflicts of interest to this work.
- Data Availability: PRM800K is publicly available from its original source. Derived locked-split reports, audit-prioritization artifacts, and reproduction scripts will be made available by the authors on request.

## Source boundary

`latex_source.zip` intentionally excludes local build artifacts:

- `*.aux`, `*.bbl`, `*.blg`, `*.fdb_latexmk`, `*.fls`, `*.log`, `*.out`, `*.abs`, `*.synctex.gz`
- temporary `_tmp_*` files
- build directories and render QA directories

## Verification

- `manuscript.tex` compiled with TeX Live/latexmk after the structural stress-test, Countries-KG pilot, and MuSiQue compression revisions: exit code 0, output `manuscript.pdf` with 20 pages (within the project-specific 12--25 page gate).
- `Highlights.docx` contains the final highlights text and current title.
- `supplementary.docx` contains the supplementary title, author names, and supplementary content converted from the split supplementary material.
- Supplementary data map now includes `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` and `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md` as audit-prioritization context only, and `outputs/kbs_audit_demo/audit_demo_report.json` as the KBS audit demonstration artifact (Section 6).
- Manuscript PDF pages were rendered to current PNG contact sheets and visually checked for page count, footer consistency, figure placement, and obvious clipping.
- `cover_letter.docx`, `Highlights.docx`, and `supplementary.docx` were structurally checked for required DOCX parts and required text after the evidence-boundary revision. They were rendered through LibreOffice to PDF/PNG for visual QA; no page clipping, table overflow, or text overlap was observed. The supplementary DOCX is a readable Word/table conversion, while authoritative mathematical layout remains in the LaTeX source bundle.
- `python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission\final_package --require-author-metadata --require-pdf-text --min-manuscript-pages 12 --max-manuscript-pages 25` passes.
- `pytest -q tests/test_kbs_submission_package_verifier.py` passes.

## Claim boundary

The package supports a bounded KBS-facing diagnostic and audit-prioritization contribution: SC-FMA calibration, controlled synthetic proxy-label ranking evidence, structural stress-test evidence that redundancy and bottleneck terms matter in their designed regime, PRM800K step-label ranking with `w_struct` as the primary real-data result, Ridge as a preservation-with-decomposition approximation on that route, moderate preliminary PRM800K audit-prioritization context, a preliminary KBS audit demonstration (Section 6, claim `M_KBS_AUDIT_DEMONSTRATION`) applying SC-FMA to knowledge-base structured audit prioritization, a MuSiQue constructed-label feasibility demonstration (downgraded; labels and features share a step-type source, so it provides no independent audit-prioritization evidence), and a Countries-KG ontology-edge pilot as diagnostic context (`validated_kbs_workflow=false`). It does not claim downstream PRM/filtering gains, GSM8K/HotpotQA replay-pass evidence, production knowledge-base deployment validation, MuSiQue-derived audit-prioritization evidence, or formal causal identification.
