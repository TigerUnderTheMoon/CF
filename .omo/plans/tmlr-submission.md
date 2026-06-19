# TMLR Submission Conversion Plan

## TL;DR

> Convert existing KBS submission to TMLR format: reframe for ML audience, anonymize, expand references, regenerate figures, add verifier test, prepare anonymous GitHub package. No new experiments.

---

## Context

- Existing KBS manuscript at `paper/kbs_submission/final_source/manuscript.tex` (433 lines, 14 pages)
- TMLR style file uploaded to `paper/tmlr-style-file/tmlr-style-file-main/`
- User chose: reframe scope, compress KBS sections, ML-focused title, expand refs+regenerate figures, anonymous GitHub, no new experiments, add TMLR verifier test

## Work Objectives

### Must Have
- TMLR style (tmlr.sty), US Letter, authoryear citations
- Double-blind anonymization
- Claim boundary preservation per `paper/claim_registry.md`
- KBS sections compressed to single Discussion subsection
- References expanded 28 to 40-60
- Figures regenerated at 6.5-inch width
- Anonymous GitHub reproducibility link
- TMLR package verifier test passing

### Must NOT Have
- Do not modify `paper/kbs_submission/`
- Do not modify `paper/claim_registry.md`
- Do not modify `src/fma/` core implementation
- Do not run new experiments or rerun failed routes
- Do not add forbidden wording (true causal effect, average treatment effect, etc.)

## Execution Strategy

### Waves

Wave 1 (scaffolding + parallel prep): Tasks 1-5
Wave 2 (content reframe): Tasks 6-10
Wave 3 (finalize + verify): Tasks 11-15
Wave 4 (integration): Tasks 16-18
Wave FINAL: Tasks F1-F4

## TODOs

### Wave 1: Scaffolding and Parallel Content Prep

- [ ] 1. Scaffold tmlr_submission directory + copy style files

  **What to do**:
  - Create `paper/tmlr_submission/` directory
  - Copy `tmlr.sty`, `tmlr.bst`, `fancyhdr.sty`, `math_commands.tex` from `paper/tmlr-style-file/tmlr-style-file-main/` into `paper/tmlr_submission/`
  - Create `paper/tmlr_submission/figures/` subdirectory
  - Verify no files are deleted from `paper/kbs_submission/`

  **Must NOT do**:
  - Do not modify `paper/tmlr-style-file/` (read-only reference)
  - Do not delete or modify `paper/kbs_submission/`

  **Recommended Agent Profile**:
  - Category: quick
  - Skills: safe-edit
  - Reason: directory scaffolding, file copies, minimal edits

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 1 with Tasks 2-5)
  - Blocks: Task 3, Task 5, Task 11

  **QA Scenarios**:
  - Scenario: Directory structure correct
    Tool: Bash (PowerShell)
    Steps:
      1. Test-Path paper/tmlr_submission/ -> True
      2. Test-Path paper/tmlr_submission/tmlr.sty -> True
      3. Test-Path paper/tmlr_submission/tmlr.bst -> True
      4. Test-Path paper/tmlr_submission/figures/ -> True
      5. Test-Path paper/kbs_submission/ -> True (untouched)
    Expected Result: All paths exist, KBS package preserved
    Evidence: .omo/evidence/task-1-structure.png

- [ ] 2. Expand references.bib from 28 to 40-60 entries

  **What to do**:
  - Read existing `paper/kbs_submission/final_source/references.bib` (28 entries)
  - Add 12-32 new entries focusing on:
    - Process supervision and PRMs (Lightman 2023, Snell 2024, Wang 2024 Math-Shepherd, Zheng 2024 ProcessBench)
    - Attribution methods (Sundararajan 2017 IG, Lundberg 2017 SHAP, Ying 2019 GNNExplainer)
    - Reasoning trace evaluation (Uesato 2022, Cobbe 2021)
    - Recent LLM reasoning interpretability (2024-2025)
  - Ensure all entries are formatted for `tmlr.bst` (authoryear, full author list, consistent fields)
  - Verify no duplicates with existing 28 entries

  **Must NOT do**:
  - Do not remove any existing 28 entries
  - Do not add references without reading them
  - Do not exceed 60 entries total

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: librarian
  - Reason: requires literature research and bib formatting

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 1 with Tasks 1, 3-5)
  - Blocks: Task 11

  **QA Scenarios**:
  - Scenario: Bib count and format correct
    Tool: Bash (Python)
    Steps:
      1. Count entries: len([l for l in open('references.bib') if l.strip().startswith('@')]) -> 40-60
      2. Verify no duplicate keys: all unique
      3. Verify all entries have required fields for tmlr.bst
    Expected Result: 40-60 entries, zero duplicates, all required fields present
    Evidence: .omo/evidence/task-2-bib-count.txt

- [ ] 3. Create TMLR main.tex skeleton from template

  **What to do**:
  - Start from `paper/tmlr-style-file/tmlr-style-file-main/main.tex` template
  - Replace template content with manuscript structure:
    - documentclass[10pt]{article} + usepackage{tmlr}
    - Title placeholder (final title decided in Task 6)
    - Abstract placeholder (final abstract decided in Task 6)
    - Section skeleton: Introduction, Related Work, Methodology, Evaluation, Discussion, Conclusion
    - Appendix command at end
    - bibliography{references} + bibliographystyle{tmlr}
  - Include math_commands.tex (optional but recommended for consistency)
  - Set up natbib authoryear citation commands
  - Define figure/table environments compatible with tmlr.sty

  **Must NOT do**:
  - Do not include author names, affiliations, or acknowledgments in this skeleton (anonymization in Task 13)
  - Do not modify tmlr.sty parameters

  **Recommended Agent Profile**:
  - Category: quick
  - Skills: safe-edit
  - Reason: LaTeX skeleton creation from template

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 1 with Tasks 1-2, 4-5)
  - Blocks: Tasks 6-10, Task 11
  - Blocked By: Task 1 (needs style files in place)

  **QA Scenarios**:
  - Scenario: Skeleton compiles without content
    Tool: Bash (PowerShell)
    Steps:
      1. cd paper/tmlr_submission; pdflatex -interaction=nonstopmode main.tex
      2. Check exit code: 0
    Expected Result: Compiles successfully (may have empty sections but no errors)
    Evidence: .omo/evidence/task-3-skeleton-compile.log

- [ ] 4. Regenerate figures at 6.5-inch width

  **What to do**:
  - Copy `scripts/generate_paper_figures.py` and `scripts/generate_scfma_figures.py` to `paper/tmlr_submission/scripts/`
  - Modify the COPIES (not originals) to fit TMLR 6.5-inch width:
    - In `generate_scfma_figures.py` copy: change `TWO_COL = 7.0` to `6.5`, keep `SINGLE_COL = 3.5`, change `FIGURES_DIR` to `paper/tmlr_submission/figures`
    - In `generate_paper_figures.py` copy: scale hardcoded figsize widths proportionally (7.2→6.7, 6.6→6.5, 9.0→8.1) to fit 6.5-inch text width, change output paths to `paper/tmlr_submission/figures/`
  - Run both copied scripts to regenerate all figures into `paper/tmlr_submission/figures/`
  - For figures not generated by these two scripts (compensation_distribution.png, filtering_accuracy_comparison.png, position_stratified.png, prm_comparison.png, redundancy_density_histogram.png, resilience_curves.png, structural_diagnostics_attribution_vs_necessity.png, structural_diagnostics_mode_comparison.png, task_comparison.png), check `scripts/` for additional generators; if none found, copy from `paper/kbs_submission/figures/` and resize with PIL to width <= 1950px at 300 DPI
  - Use SAME seed 42 and SAME data as KBS version to ensure determinism
  - Verify all 15 figures are generated:
    - fig_ciu_necessity.png, fig_mode_comparison.png, fig_redundancy_comp.png, fig_resilience.png, fig_scaling.png, fig_sensitivity.png
    - compensation_distribution.png, filtering_accuracy_comparison.png, position_stratified.png, prm_comparison.png, redundancy_density_histogram.png, resilience_curves.png, structural_diagnostics_attribution_vs_necessity.png, structural_diagnostics_mode_comparison.png, task_comparison.png

  **Must NOT do**:
  - Do not modify original scripts in `scripts/` (preserve KBS reproducibility)
  - Do not change figure content or data (only resize)
  - Do not delete original figures in `paper/kbs_submission/figures/`

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: python-debug
  - Reason: requires running Python figure generation scripts and debugging any size issues

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 1 with Tasks 1-3, 5)
  - Blocks: Task 11

  **QA Scenarios**:
  - Scenario: All figures fit 6.5-inch width
    Tool: Bash (Python with PIL)
    Steps:
      1. For each PNG in paper/tmlr_submission/figures/:
      2. Open with PIL, check width at 300 DPI <= 6.5 inches (1950 pixels)
      3. Verify all 15 figures exist
    Expected Result: All 15 figures present, width <= 1950px at 300 DPI
    Evidence: .omo/evidence/task-4-figure-dims.txt

- [ ] 5. Convert supplementary.tex to TMLR format

  **What to do**:
  - Read `paper/kbs_submission/final_source/supplementary.tex` (441 lines)
  - Replace `documentclass{cas-sc}` with `documentclass[10pt]{article}` + usepackage{tmlr}
  - Remove author info, affiliations, acknowledgments (anonymization)
  - Convert section numbering from Appendix A.1, A.2 style to standard appendix numbering
  - Update bibliography style to tmlr.bst
  - Keep all mathematical content, proofs, tables, figures intact
  - Ensure supplementary compiles standalone with main.bib or its own bib file

  **Must NOT do**:
  - Do not remove any proofs, derivations, or extended results
  - Do not modify mathematical content

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: safe-edit
  - Reason: LaTeX format conversion, preserving content

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 1 with Tasks 1-4)
  - Blocks: Task 11
  - Blocked By: Task 1 (needs style files)

  **QA Scenarios**:
  - Scenario: Supplementary compiles standalone
    Tool: Bash (PowerShell)
    Steps:
      1. cd paper/tmlr_submission; pdflatex -interaction=nonstopmode supplementary.tex
      2. Check exit code: 0
    Expected Result: Zero compilation errors
    Evidence: .omo/evidence/task-5-supplementary-compile.log

---

### Wave 2: Manuscript Content Reframe (After Wave 1)

- [ ] 6. Reframe Introduction + Abstract for ML audience

  **What to do**:
  - Read KBS manuscript abstract (lines 51-53) and introduction (lines 61-72)
  - Rewrite abstract to de-emphasize KBS framing, emphasize ML methodology:
    - Lead with SC-FMA as calibration methodology for step-level weights in reasoning traces
    - Mention convex SCU objective, structural necessity, redundancy, bottleneck
    - Evidence: synthetic benchmark (Spearman 0.608) + PRM800K locked split (Spearman 0.611 w_struct, 0.604 Ridge)
    - Boundary: explicitly state what is NOT claimed
  - Rewrite introduction for ML audience:
    - Open with process supervision in LLM reasoning traces
    - Cite recent PRM literature (Lightman 2023, Uesato 2022, Wang 2024)
    - Position SC-FMA as calibration layer between raw utility and process supervision targets
    - State 4 numbered contributions (same as KBS but reframed)
    - Move KBS-specific paragraphs to Discussion
  - Decide final title: "Structurally-Calibrated Functional Attribution for Process Supervision in Reasoning Traces"

  **Must NOT do**:
  - Do not upgrade any claims
  - Do not add causal identification language
  - Do not remove the 4 numbered contributions

  **Recommended Agent Profile**:
  - Category: deep
  - Skills: writing

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 2 with Tasks 7-10)
  - Blocks: Task 11
  - Blocked By: Task 3

  **QA Scenarios**:
  - Scenario: Abstract length and content check
    Tool: Bash (Python)
    Steps:
      1. Extract abstract text from main.tex
      2. Word count: 150-250 words
      3. Check forbidden phrases: "true causal effect", "average treatment effect", "downstream PRM training"
      4. Check KBS-specific language count
    Expected Result: 150-250 words, zero forbidden phrases, minimal KBS jargon
    Evidence: .omo/evidence/task-6-abstract-check.txt

- [ ] 7. Reframe Related Work for ML audience

  **What to do**:
  - Read KBS manuscript Section 2 (Related Work, lines 73-97)
  - Keep Subsection 2.1 (Process Supervision and PRMs) -- expand with 2-3 recent PRM citations
  - Keep Subsection 2.2 (Attribution and Explanation) -- emphasize token-level vs step-level
  - Compress Subsection 2.3 (Knowledge-Based Systems) to 2-3 sentences within broader Applications paragraph
  - Keep Subsection 2.4 (Scope and Boundary)
  - Add paragraph on Structural Calibration in ML if literature supports

  **Must NOT do**:
  - Do not delete any original 28 references
  - Do not expand KBS subsection

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: writing

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 2 with Tasks 6, 8-10)
  - Blocks: Task 11
  - Blocked By: Task 3

  **QA Scenarios**:
  - Scenario: Related work section length and focus
    Tool: Bash (Python)
    Steps:
      1. Extract Section 2 text
      2. Word count: 800-1200 words
      3. Check KBS-specific paragraph length: <= 150 words
    Expected Result: Compact, ML-focused, KBS compressed
    Evidence: .omo/evidence/task-7-related-work-stats.txt

- [ ] 8. Convert Methodology section to TMLR format

  **What to do**:
  - Read KBS manuscript Section 3 (Methodology, lines 98-145)
  - Replace theorem environment to TMLR-compatible style
  - Ensure algorithm environments compile with tmlr.sty
  - Convert figure reference to standard figure environment
  - Keep all mathematical notation and SCU objective exactly as-is
  - Keep Theorem 1 verbatim
  - Keep all three variant descriptions
  - Add brief computational complexity paragraph

  **Must NOT do**:
  - Do not modify SCU objective formula
  - Do not modify Theorem 1
  - Do not remove variant descriptions

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: safe-edit

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 2 with Tasks 6-7, 9-10)
  - Blocks: Task 11
  - Blocked By: Task 3

  **QA Scenarios**:
  - Scenario: Methodology compiles with equations and theorem
    Tool: Bash (PowerShell)
    Steps:
      1. Compile main.tex with methodology section
      2. Check for undefined references
      3. Verify Theorem 1 rendered correctly
    Expected Result: Zero errors, theorem correct
    Evidence: .omo/evidence/task-8-methodology-compile.log

- [ ] 9. Convert Evaluation section to TMLR format

  **What to do**:
  - Read KBS manuscript Section 4 (Evaluation, lines 153-304)
  - Convert all 4 tables to TMLR-compatible format for 6.5-inch width
  - Keep all evidence route accounting exactly as-is
  - Keep all numerical results exactly as-is
  - Keep error analysis and reviewer-facing interpretation verbatim
  - Move KBS maintenance workflow paragraphs to Discussion
  - Add brief reproducibility note

  **Must NOT do**:
  - Do not modify any numerical results
  - Do not modify evidence route accounting
  - Do not upgrade any claims

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: safe-edit

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 2 with Tasks 6-8, 10)
  - Blocks: Task 11
  - Blocked By: Task 3

  **QA Scenarios**:
  - Scenario: All tables render within text width
    Tool: Bash (PowerShell) + visual inspection
    Steps:
      1. Compile main.tex
      2. Check each table fits within 6.5-inch margins
      3. Verify no overflow
    Expected Result: All 4 tables legible and within margins
    Evidence: .omo/evidence/task-9-tables.pdf

- [ ] 10. Write Discussion section + Broader Impact

  **What to do**:
  - Compress 4 KBS-specific sections into ONE Discussion section:
    - 10.1 Applications (2-3 paragraphs): KBS relevance + modern PRM800K use case + future extensions
    - 10.2 Limitations and Future Work (3-4 paragraphs): synthetic control, PRM800K bound, graph construction, binary CIU, no causal identification
    - 10.3 Broader Impact (1 paragraph, TMLR recommended): positive audit prioritization, negative misuse risk, mitigation via human oversight

  **Must NOT do**:
  - Do not upgrade any claims in Discussion
  - Do not remove limitation statements
  - Do not add speculative future claims without "future work" label

  **Recommended Agent Profile**:
  - Category: deep
  - Skills: writing

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 2 with Tasks 6-9)
  - Blocks: Task 11
  - Blocked By: Task 3

  **QA Scenarios**:
  - Scenario: Discussion length and claim compliance
    Tool: Bash (Python)
    Steps:
      1. Extract Discussion section text
      2. Word count: 800-1200 words
      3. Check forbidden phrases: zero occurrences
      4. Verify all 5 limitation items present
    Expected Result: Comprehensive, all limitations preserved, zero forbidden wording
    Evidence: .omo/evidence/task-10-discussion-check.txt

### Wave 3: Finalize and Verify (After Wave 2)

- [ ] 11. Compile main.tex + supplementary.tex via pdflatex and bibtex

  **What to do**:
  - Run pdflatex on main.tex (Windows: pdflatex.exe -interaction=nonstopmode main.tex)
  - Run bibtex on main.aux (Windows: bibtex.exe main)
  - Run pdflatex again (2 passes to resolve references)
  - Run pdflatex on supplementary.tex
  - Capture all .log files for error checking
  - Fix any compilation errors:
    - Undefined citations: add missing bib entries
    - Missing references: check label consistency
    - Package conflicts: resolve tmlr.sty vs existing packages
  - Generate main.pdf and supplementary.pdf

  **Must NOT do**:
  - Do not ignore compilation warnings (treat as errors for submission quality)
  - Do not modify tmlr.sty to suppress errors

  **Recommended Agent Profile**:
  - Category: quick
  - Skills: python-debug

  **Parallelization**:
  - Can Run In Parallel: NO (depends on all Wave 1-2 tasks)
  - Blocks: Tasks 13, 16, 17, 18

  **QA Scenarios**:
  - Scenario: Clean compilation
    Tool: Bash (PowerShell)
    Steps:
      1. pdflatex -interaction=nonstopmode main.tex; check $LASTEXITCODE -eq 0
      2. bibtex main; check $LASTEXITCODE -eq 0
      3. pdflatex main.tex (second pass)
      4. pdflatex supplementary.tex; check $LASTEXITCODE -eq 0
      5. Check main.log for "Error" or "Undefined" strings
    Expected Result: Zero errors, zero undefined citations/references
    Evidence: .omo/evidence/task-11-compile.log

- [ ] 12. Write TMLR cover letter (anonymized)

  **What to do**:
  - Write new cover letter for TMLR (not KBS):
    - Address to TMLR Editors (not KBS Editorial Office)
    - Remove author names, affiliations, funding numbers
    - Frame contribution as ML methodology for process supervision
    - Mention claim boundary explicitly
    - Mention reproducibility: anonymous GitHub link, deterministic seed 42, locked artifacts
    - Keep length to 1 page (300-500 words)
  - Save as `paper/tmlr_submission/cover_letter.md`

  **Must NOT do**:
  - Do not include author-identifying info
  - Do not mention KBS as target journal

  **Recommended Agent Profile**:
  - Category: quick
  - Skills: writing

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 3 with Tasks 11, 13-15)
  - Blocks: Task 13

  **QA Scenarios**:
  - Scenario: Cover letter anonymization check
    Tool: Bash (Python)
    Steps:
      1. Read cover_letter.md
      2. Search for "Haoran", "Ma", "Ningning", "Wang", "BISTU", "Beijing Information"
      3. Verify word count 300-500
    Expected Result: Zero author-identifying strings, appropriate length
    Evidence: .omo/evidence/task-12-cover-letter-check.txt

- [ ] 13. Anonymization pass + verify no author-identifying info

  **What to do**:
  - Search main.tex and supplementary.tex for author-identifying strings:
    - Names: Haoran, Ma, Ningning, Wang
    - Affiliations: BISTU, Beijing Information Science and Technology University
    - Emails: mahaoran0000, wangningning
    - Funding: National Social Science Fund (24BSH018), Beijing NSF (L252145)
    - CRediT authorship contribution statement
    - Acknowledgments section
  - Remove or replace all author-identifying content:
    - Replace \author{...} with Anonymous authors comment
    - Remove \affiliation commands
    - Remove Acknowledgments, Funding, Declaration, CRediT sections
    - Remove email addresses
  - Verify compiled PDF contains zero author-identifying strings
  - Use Python pdfplumber or pypdf to search PDF text

  **Must NOT do**:
  - Do not leave any email address in submission version
  - Do not leave funding numbers in submission version
  - Do not forget PDF metadata (check and clear if needed)

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: safe-edit

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 3 with Tasks 11-12, 14-15)
  - Blocks: Task 16
  - Blocked By: Task 11 (needs compiled PDF)

  **QA Scenarios**:
  - Scenario: Complete anonymization verification
    Tool: Bash (Python with pypdf)
    Steps:
      1. Extract all text from main.pdf
      2. Search for forbidden strings: ["Haoran", "Ma", "Ningning", "Wang", "BISTU", "Beijing Information", "mahaoran", "wangningning", "24BSH018", "L252145"]
      3. Count occurrences: expect 0 for each
    Expected Result: Zero occurrences of all author-identifying strings
    Evidence: .omo/evidence/task-13-anonymization-report.txt

- [ ] 14. Prepare anonymous GitHub reproducibility package

  **What to do**:
  - Create curated reproducibility package (not full repo):
    - INCLUDE: src/fma/ (core implementation), scripts/ (reproducible scripts), configs/ (YAML configs), tests/ (all tests), key outputs/ artifacts (v3.6, v3.8, synthetic benchmark, audit demo), README.md with reproduction instructions
    - EXCLUDE: paper/kbs_submission/ (historical), outputs/archive/ (old failed routes), internal logs, .git/ history with author info, large model checkpoints
  - Ensure total size < 100MB (anonymous.4open.science limit)
  - Create reproduction README:
    - Installation: pip install -e .
    - Tests: python -m pytest -q
    - Synthetic benchmark: scripts/generate_synthetic_traces.py --seed 42
    - PRM800K validation: scripts/run_real_task_v3_6_prm800k_hash_validation.py
    - Audit demo: scripts/run_kbs_audit_demo.py
    - Figure generation: scripts/generate_paper_figures.py --width 6.5
  - Upload to anonymous.4open.science (or equivalent anonymous repo service)
  - Verify link is accessible
  - Add link to manuscript Reproducibility section (placeholder in Task 6/10)

  **Must NOT do**:
  - Do not include author-identifying info in README or code comments
  - Do not include .git history with author commits
  - Do not exceed 100MB total

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: bash-subagent

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 3 with Tasks 11-13, 15)
  - Blocks: Task 16

  **QA Scenarios**:
  - Scenario: Anonymous GitHub link accessible and complete
    Tool: webfetch
    Steps:
      1. Fetch anonymous GitHub URL
      2. Verify HTTP 200
      3. Check directory listing contains src/fma/, scripts/, configs/, tests/, README.md
    Expected Result: Link works, all required directories present
    Evidence: .omo/evidence/task-14-github-check.txt

- [ ] 15. Write test_tmlr_submission_package_verifier.py

  **What to do**:
  - Create new test file `tests/test_tmlr_submission_package_verifier.py`
  - Tests to implement:
    1. test_tmlr_style_used: verify main.tex contains "usepackage{tmlr}" not "documentclass{cas-sc}"
    2. test_anonymization_complete: verify compiled PDF has zero author-identifying strings
    3. test_claim_boundary_compliance: verify compiled PDF has zero forbidden phrases from claim_registry.md
    4. test_figures_fit_width: verify all PNG figures have width <= 6.5 inches at 300 DPI
    5. test_bibliography_format: verify references.bib has 40-60 entries, no duplicates, compatible with tmlr.bst
    6. test_page_count_sane: verify main.pdf has 10-25 pages
    7. test_cover_letter_anonymized: verify cover_letter.md has zero author-identifying strings
    8. test_kbs_package_preserved: verify paper/kbs_submission/ still exists and is untouched
  - Use existing test patterns from test_kbs_submission_package_verifier.py as template
  - For PDF text extraction (tests 2 and 3): use `PyPDF2` if available (often pre-installed), otherwise use `subprocess` with `pdftotext` command-line tool, or install `pypdf` via `pip install pypdf` as a test prerequisite
  - All tests must pass on Windows (PowerShell) and be deterministic

  **Must NOT do**:
  - Do not modify existing test files
  - Do not add tests that require external API calls

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: safe-edit

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 3 with Tasks 11-14)
  - Blocks: Task 16

  **QA Scenarios**:
  - Scenario: All verifier tests pass
    Tool: Bash (PowerShell)
    Steps:
      1. python -m pytest tests/test_tmlr_submission_package_verifier.py -v
      2. Check exit code: 0
      3. Verify all 8 test cases show PASS
    Expected Result: 8/8 tests passing
    Evidence: .omo/evidence/task-15-verifier-test.log

### Wave 4: Integration and Final Verification (After Wave 3)

- [ ] 16. Run TMLR package verifier + fix any failures

  **What to do**:
  - Run `python -m pytest tests/test_tmlr_submission_package_verifier.py -v`
  - For each failing test:
    - If anonymization failure: return to Task 13, fix source
    - If claim boundary failure: search main.tex for forbidden phrase, rewrite offending sentence
    - If figure width failure: return to Task 4, regenerate with correct size
    - If bib format failure: return to Task 2, fix entry formatting
    - If compilation failure: return to Task 11, fix LaTeX errors
  - Re-run verifier after each fix until all 8 tests pass
  - Record all fixes in evidence file

  **Must NOT do**:
  - Do not suppress test failures by modifying test expectations
  - Do not ignore warnings

  **Recommended Agent Profile**:
  - Category: quick
  - Skills: python-debug

  **Parallelization**:
  - Can Run In Parallel: NO (depends on all Wave 3 tasks)
  - Blocks: Tasks F1-F4

  **QA Scenarios**:
  - Scenario: Verifier passes after fixes
    Tool: Bash (PowerShell)
    Steps:
      1. python -m pytest tests/test_tmlr_submission_package_verifier.py -v
      2. Verify exit code 0 and all tests PASS
    Expected Result: 8/8 PASS
    Evidence: .omo/evidence/task-16-final-verifier.log

- [ ] 17. Claim boundary audit on final PDF (forbidden wording scan)

  **What to do**:
  - Use Python to extract all text from compiled main.pdf
  - Search for forbidden phrases from claim_registry.md and AGENTS.md:
    - "true causal effect"
    - "average treatment effect"
    - "globally identifiable causal quantity"
    - "downstream PRM training"
    - "external PRM generalization"
    - "production KBS deployment"
    - "GSM8K validation" (without "failed" or "blocked")
    - "HotpotQA validation" (without "failed" or "blocked")
  - For each match, locate source in main.tex, rewrite to compliant wording per claim_registry.md
  - Recompile and re-verify until zero forbidden phrases

  **Must NOT do**:
  - Do not allow any forbidden phrase in final submission
  - Do not modify claim_registry.md to accommodate forbidden wording

  **Recommended Agent Profile**:
  - Category: unspecified-high
  - Skills: safe-edit

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 4 with Tasks 16, 18)
  - Blocks: Tasks F1-F4
  - Blocked By: Task 11

  **QA Scenarios**:
  - Scenario: Zero forbidden phrases in final PDF
    Tool: Bash (Python with pypdf)
    Steps:
      1. Extract text from main.pdf
      2. Search for each forbidden phrase
      3. Count total matches
    Expected Result: Zero matches for all forbidden phrases
    Evidence: .omo/evidence/task-17-claim-audit.txt

- [ ] 18. Final compile + page count check + visual QA of figures

  **What to do**:
  - Final clean compile: delete .aux, .bbl, .blg, .out, .fdb_latexmk, .fls, .log files, then recompile from scratch
  - Verify main.pdf page count: 10-25 pages (TMLR has no hard limit but sanity check)
  - Verify supplementary.pdf page count: reasonable (5-15 pages)
  - Open main.pdf and visually inspect:
    - Title page: centered, readable
    - All 4 tables: within margins, readable font size
    - All figures: clear, labels readable, no pixelation
    - Section headings: sans-serif bold, consistent
    - Equations: properly numbered, not cut off
    - References: authoryear format, no [numbers]
  - Save final PDFs as `paper/tmlr_submission/main.pdf` and `paper/tmlr_submission/supplementary.pdf`

  **Must NOT do**:
  - Do not submit without visual inspection
  - Do not accept figures with unreadable labels

  **Recommended Agent Profile**:
  - Category: quick
  - Skills: safe-edit

  **Parallelization**:
  - Can Run In Parallel: YES (Wave 4 with Tasks 16-17)
  - Blocks: Tasks F1-F4
  - Blocked By: Task 11

  **QA Scenarios**:
  - Scenario: Final PDF quality check
    Tool: Bash (PowerShell) + visual inspection
    Steps:
      1. pdflatex main.tex (clean build)
      2. Check page count: Get-PDFFileInfo or pypdf page count
      3. Verify 10 <= page count <= 25
      4. Open PDF and visually inspect all tables, figures, equations
    Expected Result: Clean build, reasonable page count, all content legible
    Evidence: .omo/evidence/task-18-final-pdf.pdf (copy of main.pdf)

---

## Final Verification Wave (MANDATORY - after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** - `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search `paper/tmlr_submission/` for forbidden patterns - reject with file:line if found. Check evidence files exist in `.omo/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** - `unspecified-high`
  Run: `python -m pytest -q` (all 64+1 tests must pass), `pdflatex main.tex` (zero errors), `bibtex main` (zero errors). Review all changed files in `paper/tmlr_submission/` for: unused LaTeX packages, commented-out code, hardcoded paths, inconsistent citation styles, AI-slop hedging language. Check that `claim_registry.md` was NOT modified.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** - `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task - follow exact steps, capture evidence. Test cross-task integration: does the manuscript compile with all sections together? Does the anonymous GitHub link work? Does the PDF open correctly? Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** - `deep`
  For each task: read "What to do", read actual diff (`git log --stat` for `paper/tmlr_submission/`). Verify 1:1 - everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance: verify `paper/kbs_submission/` untouched, `paper/claim_registry.md` untouched, `outputs/` untouched, `src/fma/` untouched. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- Group commits by wave to keep history organized:
  - Wave 1 commit: `chore(tmlr): scaffold submission directory + style files`
  - Wave 2 commit: `content(tmlr): reframe manuscript for ML audience`
  - Wave 3 commit: `feat(tmlr): add verifier test + anonymous GitHub package`
  - Wave 4 commit: `fix(tmlr): final compile + claim boundary audit`
  - Final commit: `docs(tmlr): cover letter + reproducibility README`
- Pre-commit: run `python -m pytest tests/test_tmlr_submission_package_verifier.py -v` to ensure package passes before each commit
- Do not commit intermediate broken LaTeX states

## Success Criteria

### Verification Commands
```bash
# Compile main manuscript
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex

# Compile supplementary
pdflatex -interaction=nonstopmode supplementary.tex

# Run all tests
python -m pytest -q

# Run TMLR package verifier
python -m pytest tests/test_tmlr_submission_package_verifier.py -v
```

### Final Checklist
- [ ] All "Must Have" present in `paper/tmlr_submission/`
- [ ] All "Must NOT Have" absent from `paper/tmlr_submission/`
- [ ] `paper/kbs_submission/` untouched (git diff shows no changes)
- [ ] `paper/claim_registry.md` untouched
- [ ] `src/fma/` untouched (no implementation changes)
- [ ] All 64 existing tests still pass
- [ ] New TMLR verifier test (8/8) passes
- [ ] main.pdf compiles with zero errors
- [ ] supplementary.pdf compiles with zero errors
- [ ] Anonymous GitHub link accessible and complete
- [ ] Cover letter anonymized and TMLR-appropriate
- [ ] User explicit "okay" on Final Verification Wave results
