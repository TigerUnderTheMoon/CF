# Final Information Sciences Package Manifest

Purpose: define the clean upload boundary for the Information Sciences transfer package and process-annotation-distribution audit-record package.

This package must be described as an Information Sciences-oriented information and knowledge representation upload package. The stratified audit-record diagnostic gate remains `moderate`, so title, abstract, cover letter, and manifest language must stay within moderate process-annotation-distribution audit-record support. The current manuscript revision foregrounds knowledge objects, knowledge representation, fidelity tracking, maintenance-oriented knowledge analysis, graph-aware audit records, and fixed-budget curation.

## Final upload files

The portal-shaped package is `final_package/` and contains the core manuscript files plus the separate Elsevier declaration file:

- `cover_letter.docx` -- Word cover letter with named authors and Information Sciences information/knowledge-representation positioning.
- `Highlights.docx` -- Word highlights file with five concise Elsevier-style highlights.
- `manuscript.pdf` -- manuscript PDF compiled from `final_source/manuscript.tex`.
- `supplementary.pdf` -- compiled supplementary material generated from `final_source/supplementary.tex`.
- `latex_source.zip` -- source bundle containing `manuscript.tex`, `supplementary.tex`, `references.bib`, CAS style files, and referenced artwork under `figures/`.
- `declaration_of_competing_interests.docx` -- Word declaration prepared for Elsevier's competing-interest upload field.

## Author and statement metadata

- Authors: Haoran Ma; Ningning Wang.
- Affiliations:
  - College of Management Science and Engineering, Beijing Information Science and Technology University, Beijing 102200, China.
  - Institute of Information Systems, ESG Intelligent Application Innovation Research Center, Beijing 102200, China.
- Emails: `mahaoran0000@foxmail.com`; `wangningning@bistu.edu.cn`.
- Funding: National Social Science Fund of China Project (24BSH018); Beijing Natural Science Foundation Project (L252145).
- Declaration of Competing Interest: The authors declared that they have no conflicts of interest to this work.
- Data Availability: The PRM800K process-annotation dataset, MuSiQue, and WebQSP are publicly available from their original sources. Derived locked-split reports, audit-record artifacts, trace-audit diagnostics, validation configurations, and reproduction scripts will be made available through an anonymous review repository during submission and released with the final article where permitted.

## Source boundary

`latex_source.zip` intentionally excludes local build artifacts:

- `*.aux`, `*.bbl`, `*.blg`, `*.fdb_latexmk`, `*.fls`, `*.log`, `*.out`, `*.abs`, `*.synctex.gz`
- temporary `_tmp_*` files
- build directories and render QA directories

## Verification

- `manuscript.tex` compiled with TeX Live/latexmk after the Information Sciences evidence update: exit code 0, output `manuscript.pdf` within the configured 20--30 page package-validation range.
- `Highlights.docx` contains five Information Sciences-oriented highlights, each within the 85-character limit.
- `supplementary.pdf` contains the compiled supplementary material from `supplementary.tex`.
- Supplementary data map includes the same-supervision structure-only control, direct graph-necessity diagnostic, and windowed long-trace diagnostic, alongside `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` and its summary as audit-record coverage context only. The window sweep is labeled post hoc locked-split failure analysis, the knowledge-based audit-card interpretation remains a workflow illustration rather than a deployment experiment, and `outputs/webqsp_trace_audit_v1_test/diagnostics/separability_report.json` remains supplementary diagnostic evidence only.
- Manuscript PDF pages were rendered to current PNG contact sheets and visually checked for page count, footer consistency, figure placement, and obvious clipping.
- `cover_letter.docx`, `Highlights.docx`, and `declaration_of_competing_interests.docx` were structurally checked for required DOCX parts and required text after the Information Sciences transfer revision. The supplementary material is provided as `supplementary.pdf`, compiled directly from the LaTeX source bundle.
- `python scripts\check_claim_boundaries.py --active-only --check-dois` passes after the checker excludes inactive `.omo/` planning files and treats claim-registry blocked-wording cells as boundary-contract text.
- Direct package validation against `paper\information_sciences_submission\final_package` passes for required files, readable PDFs, source-zip contents, figure-path coverage, and exclusion of local build artifacts.
- Claim-boundary tests and direct package validation pass after the Information Sciences package refresh.

## Scope and evidence summary

The package supports an information and knowledge representation contribution centered on structured audit records: SC-FMA calibration, process-annotation-dataset signal tracking with `w_struct` as the primary real-data fidelity field, Ridge as a fidelity-tracking decomposition representation on that route, a same-supervision structure-only control, direct graph-necessity diagnostics, post hoc windowed analysis of the long-trace QP failure, fixed-budget audit context, rule-derived audit-record construction, a Countries-KG diagnostic graph showing typed ontology-edge sensitivity, controlled synthetic calibration evidence, structural stress-test evidence that redundancy and bottleneck fields matter in their designed regime, a MuSiQue constructed-label feasibility demonstration, and a WebQSP fixed-schema trace-audit diagnostic. The package contains no human-rater experiment and keeps downstream training, task transfer, field studies of maintenance-oriented review, human outcomes, and formal causal claims outside the reported evidence.
