# Final KBS Submission Manifest

Purpose: define the intended upload boundary for the Knowledge-Based Systems submission package. This manifest separates submission files from local build/test artifacts and records the remaining user-supplied author metadata required before portal upload.

## Manuscript files

- `main.pdf` -- compiled manuscript PDF generated from the current source.
- `main.tex` -- Elsevier CAS single-column source.
- `references.bib` -- BibTeX database for the manuscript.
- `cas-sc.cls`, `cas-common.sty`, `cas-model2-names.bst` -- local Elsevier CAS template/style files required to compile the source.
- `cover_letter.md` -- cover letter draft synchronized to the current title and claim boundary.
- `format_checklist.md` -- local compliance checklist for the package.
- `submission_author_metadata_template.md` -- local template for author names, affiliations, corresponding-author details, funding, and author-specific statements.

## Required before portal upload

KBS uses a single-anonymized review workflow. The current manuscript source still contains `Anonymous Author(s)` and `Anonymous Institution` placeholders because author metadata has not been supplied in this workspace. Before direct upload, replace those placeholders and the anonymous CRediT wording using `submission_author_metadata_template.md`, then rebuild `main.pdf`.

## Figure assets used by the current manuscript source

The current `main.tex` source does not directly include PNG figures; plots are represented as compiled LaTeX figure boxes. Retained PNG files are historical/source assets and may be supplied only if the editorial system requests separate artwork or supplementary files. The retained PNG files were inspected at 300 DPI.

- `structural_diagnostics_attribution_vs_necessity.png`
- `structural_diagnostics_mode_comparison.png`
- `compensation_distribution.png`
- `redundancy_density_histogram.png`
- `resilience_curves.png`
- `task_comparison.png`
- `position_stratified.png`
- `filtering_accuracy_comparison.png`
- `prm_comparison.png`

## Supplementary files

- `supplementary_materials.md` -- editorial description of supplementary items.
- `supplementary/supplementary_manifest.md` -- artifact-level supplementary manifest.
- `supplementary/Supplementary_Figure_S1_governance_diagnostic_upset.png`
- `supplementary/Supplementary_Data_S1_governance_diagnostic_report.json`

## Evidence artifacts referenced by the supplementary manifest

These artifacts are retained as repository evidence and may be provided as supplementary data if the submission system requests the full reproducibility bundle.

- `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json`
- `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json`
- `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_downstream_filtering_report.json`
- `outputs/archive/real_task_v3/qwen36_delete_hotfix_20260607/smoke_report.json`
- `outputs/archive/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_report.json`
- `outputs/archive/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json`
- `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json`
- `outputs/real_task_v3_6_prm800k_hash/decision_report.json`
- `outputs/real_task_v3_7_prm_baseline_comparison/training_overlap_audit.json`
- `outputs/real_task_v3_8_prm_locked_scoring/locked_prm_baseline_comparison_report.json`
- `outputs/real_task_v3_8_prm_locked_scoring/decision_report.json`

## Excluded local artifacts

Do not upload LaTeX auxiliary files or scratch test files:

- `*.aux`, `*.bbl`, `*.blg`, `*.fdb_latexmk`, `*.fls`, `*.log`, `*.out`, `*.abs`
- `test_title.*`
- temporary build directories such as `build_tmp/`

## Final verification

- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` completed with exit code 0.
- The final `main.pdf` has 38 pages and is 637,944 bytes.
- Final log scan before auxiliary cleanup found no undefined citations, no undefined references, and no remaining rerun request.
- `pdftotext` confirmed the rendered PDF contains the compressed Highlights, competing-interest declaration, generative-AI declaration, data/code availability statement, and CRediT statement.
- Citation audit found 63 citation keys and `missing_citations=[]`.
- Highlights audit found 4 items with lengths 66, 71, 72, and 68 characters.
- Supplementary path audit found no missing referenced artifact paths.
- Package hygiene cleanup removed local LaTeX auxiliary files, scratch `test_title.*` files, and temporary build directories from `paper/kbs_submission/`.
- Cover letter title and method naming are synchronized to the current SC-FMA manuscript title.
- Initial-submission acknowledgments no longer thank anonymous reviewers before peer review.
- `python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission` passes with the expected author-metadata warning.
- `python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission --require-author-metadata` is the final direct-upload gate and currently fails only because author names, affiliations, and corresponding-author details have not been supplied.

## Claim boundary

The package supports a methodological/diagnostic KBS submission: SC-FMA calibration, PRM800K step-label ranking, and overlap-limited frozen PRM baseline context. It does not claim downstream training/filtering gains, GSM8K/HotpotQA replay-pass evidence, deployed-system validation, external baseline generalization, or mechanism recovery.
