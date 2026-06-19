# Draft: TMLR Submission Conversion Plan

## Date
2026-06-19

## Project Context
- Repository: D:\CF (FMA — Functional Metacognitive Attribution)
- Existing submission: KBS (Knowledge-Based Systems) package at `paper/kbs_submission/`
- User uploaded TMLR style file: `paper/tmlr-style-file/tmlr-style-file-main/`
- User goal: Convert KBS submission to TMLR format and submit to TMLR

## Existing KBS Manuscript Inventory (verified by reading)

### manuscript.tex (433 lines, ~12,000 words, 14 pages)
- **Title**: "Structurally-Calibrated Functional Attribution for Audit Prioritization in Knowledge-Intensive Reasoning"
- **Authors (currently NON-anonymous)**: Haoran Ma, Ningning Wang (BISTU, Beijing)
- **Sections**:
  1. Introduction
  2. Related Work (4 subsections: PRMs, Attribution/Explanation, KBS, Scope)
  3. Methodology (SCU objective, trace repr, structural necessity/redundancy/bottlenecks, Theorem 1)
  4. Evaluation (Data/baselines, Evidence routes, Synthetic ranking, PRM800K evidence, Error analysis, Reviewer-facing)
  5. KBS Implications and Limitations
  6. KBS-Relevant Audit Prioritization Demonstration
  7. Conclusion
  - Acknowledgments / Funding / Conflict / AI Declaration / Data Availability / CRediT
- **Tables**: 3 (evidence routes, synthetic ranking, PRM800K audit, audit demo results)
- **Figures**: 1 in main text (fig_ciu_necessity.png)

### supplementary.tex (441 lines)
- Extended Proofs (KKT, variance reduction, bottleneck tightness)
- Controlled-benchmark extended results
- Implementation details
- Reproducibility notes
- Countries-KG fixture pilot

### references.bib
- **28 entries** (potentially thin for TMLR; TMLR papers typically 40-60)

### Cover letter (cover_letter.md)
- Addressed to KBS Editorial Office
- Frames contribution as KBS methodology + audit prioritization
- Cites National Social Science Fund (24BSH018) + Beijing NSF (L252145)

## TMLR vs KBS Format Requirements (verified by reading tmlr.sty + main.tex)

### Style Differences
| Aspect | KBS (current) | TMLR (target) |
|---|---|---|
| Class | cas-sc.cls | article + tmlr.sty |
| Paper | A4 | US Letter (8.5x11) |
| Text width | different | 6.5 inch |
| Text height | different | 9.0 inch |
| Font | Computer Modern | lmodern |
| Citation style | [numbers] natbib | natbib authoryear (\citet, \citep) |
| Bibliography | cas-model2-names.bst | tmlr.bst |
| Author info | visible | ANONYMIZED for submission (anonymous option) |
| Header | none | "Under review as submission to TMLR" |
| Section font | serif | sans-serif bold (sffamily) |

### TMLR-Specific Requirements
- **Double-blind submission**: authors, affiliations, acknowledgments, funding, CRediT MUST be removed/anonymized for submission version
- **Required (optional but recommended) sections**: Broader Impact Statement, Author Contributions (post-acceptance)
- **Reproducibility**: TMLR strongly encourages open code + data
- **Math notation**: math_commands.tex template available (optional)
- **No page limit** (unlike KBS 12-20 page gate)
- **Review criteria**: correctness + usefulness (NOT novelty threshold)

## Code Base & Test Infrastructure (verified)

### Tests (64 files in tests/, 8 archived)
Key tests for paper claims:
- `test_calibration_guarantees.py` (15/15 passing) — SCU convexity, monotonicity, variance reduction, bottleneck protection
- `test_baselines.py` (19/19 passing) — 6 baseline families comparison
- `test_ranking.py` — step ranking validation
- `test_real_task_v3_6_prm800k_hash_validation.py` — PRM800K locked split
- `test_real_task_v3_8_prm_locked_scoring.py` — frozen PRM baseline
- `test_kbs_audit_demo.py` — KBS audit demonstration
- `test_claim_boundaries.py` — claim registry enforcement
- `test_kbs_submission_package_verifier.py` — KBS package verification (TMLR version needs similar)

### Scripts (54 in scripts/)
- All experimental routes have reproducible scripts
- `run_scfma_variants_prm800k.py` — SC-FMA variant comparison
- `run_prm800k_audit_prioritization.py` — audit demo
- `run_kbs_audit_demo.py` — KBS audit demo

### Outputs (16 directories in outputs/)
- `outputs/real_task_v3_6_prm800k_hash/` — PASSED (locked validation)
- `outputs/real_task_v3_8_prm_locked_scoring/` — PASSED (frozen PRM baseline)
- `outputs/kbs_audit_demo/` — KBS audit demo artifacts
- `outputs/scfma_variants_prm800k/` — SC-FMA variant comparison

## Claim Boundary (from paper/claim_registry.md — MUST PRESERVE in TMLR)

### Supported Claims (allowed in TMLR version)
- M_SCFMA_CALIBRATION: SC-FMA convex calibration (15/15 tests passing)
- M_SCU_OBJECTIVE: SCU strict convexity, monotonicity, variance reduction, bottleneck protection
- M_STEP_RANKING: PRM800K step ranking (w_struct ρ=0.611, Ridge ρ=0.604)
- M_ABLATION: each SCU term contributes independently
- M_BASELINE_COMPARISON: 6 baseline families compared
- M_KBS_AUDIT_DEMONSTRATION: preliminary audit demo (methodological analogy only)

### Stratum-Dependent (must use careful wording)
- M_PRM_BASELINE_CONTEXT: v3.8 frozen PRM baseline — context only, NOT external generalization

### Forbidden Claims (MUST NOT appear in TMLR version)
- Downstream PRM training validation
- GSM8K/HotpotQA replay validation
- Production KBS deployment
- External PRM generalization
- Causal effect identification
- "True causal effect", "average treatment effect", "globally identifiable"

## Key Conversion Decisions (NEED USER INPUT)

### Decision 1: Conversion Scope
- Option A: Minimal — pure format conversion, keep all KBS content as-is
- Option B: Reframe — convert format + reframe KBS-specific sections for ML audience
- Option C: Major rewrite — full reframing for TMLR/ML audience

### Decision 2: KBS-Specific Sections
Current manuscript has heavy KBS framing:
- Section 2.3 "Knowledge-Based Systems" related work
- Section 5 "KBS Implications and Limitations"
- Section 6 "KBS-Relevant Audit Prioritization Demonstration"
- Section 6.4 "KBS Methodological Analogy"

Options:
- Keep all (TMLR reviewers may find KBS framing tangential)
- Compress KBS sections to a brief discussion
- Remove KBS-specific sections entirely

### Decision 3: Title Adjustment
- Current: "Structurally-Calibrated Functional Attribution for Audit Prioritization in Knowledge-Intensive Reasoning"
- TMLR audience may prefer ML-focused title (e.g., "...for Process Supervision in Reasoning Traces")

### Decision 4: References Expansion
- 28 entries is thin for TMLR
- Should we expand to 40-60 entries with more ML/PRM/attribution literature?

### Decision 5: Figures Regeneration
- Existing figures were generated for KBS A4 format
- TMLR requires 6.5 inch width
- Regenerate all figures or just resize in LaTeX?

### Decision 6: Test Strategy
- Existing 64 tests already cover all paper claims
- Add new tests for TMLR-specific requirements (e.g., anonymization verifier)?
- Or rely on existing tests + manual QA?

### Decision 7: Reproducibility Package
- TMLR strongly encourages open code
- Should we prepare a public GitHub repo link for submission?
- Or use anonymous GitHub / OpenReview supplementary?

## User Decisions (confirmed 2026-06-19)

### Conversion Scope: REFRAME
- Convert format AND reframe KBS-specific sections for ML audience
- Keep core methodology + empirical evidence intact

### KBS Sections Handling: COMPRESS TO ONE SECTION
- Section 2.3 (KBS related work), Section 5 (KBS Implications), Section 6 (KBS Audit Demo), Section 6.4 (KBS Methodological Analogy)
- Compress all four into a single § Discussion subsection
- Preserve KBS as one application scenario, not as primary framing

### Title Adjustment: ML-METHOD-CONTRIBUTION FOCUS
- New title direction: "Structurally-Calibrated Functional Attribution for Process Supervision in Reasoning Traces" (final wording TBD)
- Remove "KBS" / "Audit Prioritization in Knowledge-Intensive Reasoning" from title
- ML audience focus

### References + Figures: EXPAND + REGENERATE
- Expand references.bib from 28 → 40-60 entries
  - Add recent ML/PRM literature (Lightman 2023, Snell 2024, etc.)
  - Add attribution methods (Integrated Gradients, SHAP variants)
  - Add process supervision recent work
- Regenerate all figures for TMLR 6.5-inch width
  - Use matplotlib with explicit figsize=(6.5, X)
  - Re-run figure generation scripts

### Reproducibility Package: ANONYMOUS GITHUB
- Prepare anonymous.4open.science repository
- Include: src/fma/, scripts/, configs/, outputs/ (key artifacts), tests/
- Exclude: author info, internal logs, archived failed routes (v2/v2.1/v2.2/v3/v3.1)
- Submit link in manuscript (typically in Reproducibility section)

### Experiments: NO NEW EXPERIMENTS
- Use existing evidence only:
  - Synthetic benchmark (200 traces, 1,027 steps, seed 42)
  - PRM800K locked split (4,417 samples, 34,219 steps) — v3.6 PASSED
  - Frozen PRM baseline — v3.8 PASSED
  - KBS audit demo artifacts
- Do NOT rerun failed routes (v2/v2.1/v2.2/v3/v3.1)

### Tests: ADD TMLR PACKAGE VERIFIER TEST
- Add `tests/test_tmlr_submission_package_verifier.py`
  - Verify anonymization (no author names, no affiliations, no acknowledgments with names)
  - Verify TMLR style file usage (tmlr.sty not cas-sc.cls)
  - Verify required sections present (Broader Impact optional, Reproducibility)
  - Verify claim boundary compliance (no forbidden wording from claim_registry.md)
  - Verify page count (TMLR no hard limit, but check 10-25 page sanity)
  - Verify references.bib format compatible with tmlr.bst
- Keep existing 64 tests unchanged
- Add manual QA scenarios for PDF compilation + visual inspection

## Scope Boundaries (FINAL)
### INCLUDE
- LaTeX format conversion (cas-sc.cls → tmlr.sty, A4 → US Letter, [numbers] → authoryear)
- Anonymization (remove authors, affiliations, acknowledgments, funding, CRediT from submission version)
- KBS sections compression (4 KBS sections → 1 Discussion subsection)
- Title reframing for ML audience
- Abstract + introduction rewrite for ML audience
- References expansion (28 → 40-60 entries)
- Figures regeneration for 6.5-inch width
- Supplementary material format conversion
- TMLR package verifier test
- Anonymous GitHub reproducibility package preparation
- Cover letter rewrite for TMLR
- Claim boundary preservation (claim_registry.md compliance)
- Broader Impact section (TMLR recommended)
- Reproducibility statement section

### EXCLUDE
- New experiments (no v4 route, no new datasets)
- Claim upgrades (no status changes in claim_registry.md)
- Rerunning failed routes (v2/v2.1/v2.2/v3/v3.1 stay failed)
- Changing SC-FMA methodology or SCU objective
- Modifying test_calibration_guarantees.py or test_baselines.py passing tests
- Adding new ML baselines not in existing evidence
- External PRM generalization claims
- Causal identification claims

## Clearance Check (PASSED)
☑ Core objective clearly defined: Convert KBS submission to TMLR format and submit
☑ Scope boundaries established: IN/OUT lists above
☑ No critical ambiguities remaining: All 7 decision points resolved
☑ Technical approach decided: Reframe path with KBS compression
☑ Test strategy confirmed: Existing 64 tests + new TMLR verifier test + manual QA
☑ No blocking questions outstanding
