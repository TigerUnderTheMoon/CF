# Final Information Sciences Package Manifest

Purpose: define the clean upload boundary for the Information Sciences transfer package and process-annotation-distribution audit-prioritization package.

This package must be described as an Information Sciences-oriented information and knowledge representation upload package. The stratified audit-prioritization gate remains `moderate`, so title, abstract, cover letter, and manifest language must stay within moderate process-annotation-distribution audit-prioritization support. The current manuscript revision foregrounds knowledge objects, knowledge representation, information preservation, knowledge maintenance, graph-aware audit records, and fixed-budget curation.

## Final upload files

The portal-shaped package is `final_package/` and contains the core manuscript files plus the separate Elsevier declaration file:

- `cover_letter.docx` -- Word cover letter with named authors and Information Sciences information/knowledge-representation positioning.
- `Highlights.docx` -- Word highlights file converted from the standalone highlights content.
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
- Data Availability: The PRM800K process-annotation dataset, MuSiQue, and WebQSP are publicly available from their original sources. Derived locked-split reports, audit-prioritization artifacts, trace-audit diagnostics, and reproduction scripts will be deposited in an anonymous public repository for review and released with the final article.

## Source boundary

`latex_source.zip` intentionally excludes local build artifacts:

- `*.aux`, `*.bbl`, `*.blg`, `*.fdb_latexmk`, `*.fls`, `*.log`, `*.out`, `*.abs`, `*.synctex.gz`
- temporary `_tmp_*` files
- build directories and render QA directories

## Verification

- `manuscript.tex` compiled with TeX Live/latexmk after the Information Sciences transfer revision to journal metadata, abstract, keywords, and Introduction positioning: exit code 0, output `manuscript.pdf` within the project-specific 12--25 page gate.
- `Highlights.docx` contains the final Information Sciences-oriented highlights text and current title.
- `supplementary.pdf` contains the compiled supplementary material from `supplementary.tex`.
- Supplementary data map now includes `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` and `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md` as audit-prioritization context only, the Section 6 knowledge-based audit-card interpretation as a workflow illustration rather than a new deployment experiment, and `outputs/webqsp_trace_audit_v1_test/diagnostics/separability_report.json` as supplementary diagnostic evidence only.
- Manuscript PDF pages were rendered to current PNG contact sheets and visually checked for page count, footer consistency, figure placement, and obvious clipping.
- `cover_letter.docx`, `Highlights.docx`, and `declaration_of_competing_interests.docx` were structurally checked for required DOCX parts and required text after the Information Sciences transfer revision. The supplementary material is provided as `supplementary.pdf`, compiled directly from the LaTeX source bundle.
- `python scripts\check_claim_boundaries.py --active-only --check-dois` passes after the checker excludes inactive `.omo/` planning files and treats claim-registry blocked-wording cells as boundary-contract text.
- Direct package validation against `paper\information_sciences_submission\final_package` passes for required files, readable PDFs, source-zip contents, figure-path coverage, and exclusion of local build artifacts.
- Claim-boundary tests and direct package validation pass after the Information Sciences package refresh.

## Scope and evidence summary

The package supports an information and knowledge representation contribution centered on structured audit records: SC-FMA calibration, process-annotation-dataset signal preservation with `w_struct` as the primary real-data fidelity field, Ridge as a preservation-with-decomposition representation on that route, fixed-budget audit context, rule-derived audit-record construction, a Countries-KG diagnostic graph showing typed ontology-edge sensitivity, controlled synthetic calibration evidence, structural stress-test evidence that redundancy and bottleneck fields matter in their designed regime, a MuSiQue constructed-label feasibility demonstration, and a WebQSP fixed-schema trace-audit diagnostic. The package keeps downstream training, task-transfer, deployed maintenance, human-outcome, and formal causal claims outside the reported evidence.
