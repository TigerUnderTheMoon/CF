# Final DKE Package Manifest

Purpose: define the clean upload boundary for the Data & Knowledge Engineering transfer package and PRM800K-like audit-prioritization package.

This package must be described as a DKE-oriented knowledge-engineering upload package. The PRM800K stratified audit-prioritization gate remains `moderate`, so title, abstract, cover letter, and manifest language must stay within moderate PRM800K-like audit-prioritization support. The current manuscript revision foregrounds knowledge objects, knowledge representation, knowledge maintenance, graph-aware audit records, and fixed-budget curation.

## Final upload files

The portal-shaped package is `final_package/` and contains exactly five files:

- `cover_letter.docx` -- Word cover letter with named authors and DKE knowledge-engineering positioning.
- `Highlights.docx` -- Word highlights file converted from the standalone highlights content.
- `manuscript.pdf` -- manuscript PDF compiled from `final_source/manuscript.tex`.
- `supplementary.pdf` -- compiled supplementary material generated from `final_source/supplementary.tex`.
- `latex_source.zip` -- source bundle containing `manuscript.tex`, `supplementary.tex`, `references.bib`, CAS style files, and referenced artwork under `figures/`.

## Author and statement metadata

- Authors: Haoran Ma; Ningning Wang.
- Affiliations:
  - College of Management Science and Engineering, Beijing Information Science and Technology University, Beijing 102200, China.
  - Institute of Information Systems, ESG Intelligent Application Innovation Research Center, Beijing 102200, China.
- Emails: `mahaoran0000@foxmail.com`; `wangningning@bistu.edu.cn`.
- Funding: National Social Science Fund of China Project (24BSH018); Beijing Natural Science Foundation Project (L252145).
- Declaration of Competing Interest: The authors declared that they have no conflicts of interest to this work.
- Data Availability: PRM800K, MuSiQue, and WebQSP are publicly available from their original sources. Derived locked-split reports, audit-prioritization artifacts, trace-audit diagnostics, and reproduction scripts will be deposited in an anonymous public repository for review and released with the final article.

## Source boundary

`latex_source.zip` intentionally excludes local build artifacts:

- `*.aux`, `*.bbl`, `*.blg`, `*.fdb_latexmk`, `*.fls`, `*.log`, `*.out`, `*.abs`, `*.synctex.gz`
- temporary `_tmp_*` files
- build directories and render QA directories

## Verification

- `manuscript.tex` compiled with TeX Live/latexmk after the DKE transfer revision to journal metadata, abstract, keywords, and Introduction positioning: exit code 0, output `manuscript.pdf` within the project-specific 12--25 page gate.
- `Highlights.docx` contains the final DKE-oriented highlights text and current title.
- `supplementary.pdf` contains the compiled supplementary material from `supplementary.tex`.
- Supplementary data map now includes `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` and `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md` as audit-prioritization context only, the Section 6 knowledge-based audit-card interpretation as a workflow illustration rather than a new deployment experiment, and `outputs/webqsp_trace_audit_v1_test/diagnostics/separability_report.json` as supplementary diagnostic evidence only.
- Manuscript PDF pages were rendered to current PNG contact sheets and visually checked for page count, footer consistency, figure placement, and obvious clipping.
- `cover_letter.docx` and `Highlights.docx` were structurally checked for required DOCX parts and required text after the DKE transfer revision. The supplementary material is provided as `supplementary.pdf`, compiled directly from the LaTeX source bundle.
- `python scripts\check_claim_boundaries.py --active-only --check-dois` passes after the checker excludes inactive `.omo/` planning files and treats claim-registry blocked-wording cells as boundary-contract text.
- `python scripts\verify_dke_submission_package.py --package-dir paper\dke_submission\final_package --require-pdf-text --min-manuscript-pages 12 --max-manuscript-pages 25` passes.
- `python -m pytest tests/test_claim_boundaries.py tests/test_dke_submission_package_verifier.py -q` passes.

## Scope and evidence summary

The package supports a knowledge-engineering contribution centered on structured audit records: SC-FMA calibration, PRM800K annotation-signal preservation with `w_struct` as the primary real-data fidelity field, Ridge as a preservation-with-decomposition representation on that route, fixed-budget PRM800K audit context, rule-derived audit-record construction, a Countries-KG representation study showing typed ontology-edge sensitivity, controlled synthetic calibration evidence, structural stress-test evidence that redundancy and bottleneck fields matter in their designed regime, a MuSiQue constructed-label feasibility demonstration, and a WebQSP fixed-schema trace-audit diagnostic. The package keeps downstream training, task-transfer, deployed maintenance, human-outcome, and formal causal claims outside the reported evidence.
