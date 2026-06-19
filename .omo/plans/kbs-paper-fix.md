# KBS Paper Fix Plan: SC-FMA Manuscript Expansion and KBS Audit Use Case

## TL;DR

> **Quick Summary**: Expand the SC-FMA manuscript from 12 to 15-20 pages, add one minimal real KBS audit demonstration section (repurposing existing PRM800K audit-prioritization artifacts with explicit KBS framing), fix the PRM800K narrative contradiction, reframe defensive writing, enrich the bibliography, and add missing baselines — all while preserving the claim boundary.
>
> **Deliverables**: Expanded manuscript (15-20pp), new KBS Audit Demonstration section, new simple_average baseline, reframed abstract/intro, enriched bibliography, registered M_KBS_AUDIT_DEMONSTRATION claim, updated package documents, recompiled PDF.
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 -> Task 7 -> Task 9 -> Task 12 -> F1-F4

---

## Context

### Original Request
User reviewed the SC-FMA paper at paper/kbs_submission/, diagnosed problems, and requested a fix plan. Confirmed decisions: stick with KBS, add ONE minimal real KBS audit use case, lightweight real-task reinforcement only, expand to 15-20 pages, no deadline, preserve moderate/preliminary claim boundary.

### Interview Summary
Key decisions: venue=KBS, real-task=lightweight only, KBS integration=Option E (repurpose PRM800K readout), length=15-20pp, deadline=none.

Critical correction from Metis: manuscript is 12 pages (not 5). Expansion delta is 3-8 pages. Countries-KG pilot is a graph construction comparison, NOT an audit use case. PRM800K audit-prioritization module already has w_struct, SIMPLE_BASELINE_METHODS, NDCG@25% — ideal foundation for Option E.

### Metis Review
Addressed gaps: page count recalibrated, KBS use case strategy chosen (Option E), baseline ambiguity resolved, bibliography strategy set (remove-before-add, net-zero), defensive language threshold defined (<=2 phrases in abstract), 7 guardrails added.

---

## Work Objectives

### Core Objective
Transform the 12-page SC-FMA manuscript into a 15-20 page KBS-ready regular article by adding one minimal real KBS audit demonstration, fixing the PRM800K narrative, reframing defensive writing, enriching the bibliography, and adding missing baselines — all within the existing claim boundary.

### Definition of Done
- [ ] manuscript.pdf is 15-20 pages (verified via latexmk log)
- [ ] pytest -q passes with 0 failures
- [ ] Package verifier passes with --min-manuscript-pages 15 --max-manuscript-pages 20
- [ ] No forbidden wording in manuscript source
- [ ] M_KBS_AUDIT_DEMONSTRATION claim registered in paper/claim_registry.md
- [ ] Abstract contains <=2 defensive phrases
- [ ] Bibliography has <=60 references, >=15 irrelevant removed, <=15 KBS-relevant added

### Must Have
- Expanded manuscript (15-20 pages) with new KBS Audit Demonstration section
- simple_average(CIU, necessity) baseline implemented and reported
- PRM800K narrative fix (QP downgrade explained, Ridge recommended, w_struct distinguished)
- Abstract reframed to contribution-led (<=2 defensive phrases)
- Bibliography enriched (net-zero, <=60 total)
- M_KBS_AUDIT_DEMONSTRATION claim registered
- All tests passing
- Zero new API calls (all evidence from frozen artifacts)

### Must NOT Have (Guardrails)
- **G1**: No new API calls (preflight drift blocks any new API work; all evidence from frozen v3.6/v3.8 artifacts)
- **G2**: No claim boundary violations (no downstream PRM training, no GSM8K/HotpotQA replay validation, no production KBS deployment, no causal identification)
- **G3**: No method changes (SCU objective stays; if baselines reveal weakness, reframe narrative, don't change the method)
- **G4**: No scope creep on KBS use case (ONE scenario, ONE metric, ONE comparison; any second scenario requires explicit re-approval)
- **G5**: No bibliography bloat (remove >=15 before adding; net <=60 total)
- **G6**: No real-task smoke test reruns (static analysis of EXISTING artifacts only)
- **G7**: No page padding (each section's expansion must be substantive content, not verbose rephrasing)
- **G8**: No fabrication of evidence (all numbers traceable to frozen artifacts or reproducible scripts)
- AI slop patterns to avoid: excessive hedging, over-abstraction, generic names, redundant qualifications

### Spec Framework Integration
- **Detected Framework**: None (no openspec/ or .specify/ directories)
- This is a conventional LaTeX manuscript project, not spec-driven.

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, test_kbs_submission_package_verifier.py, CI workflow)
- **Automated tests**: YES (tests-after) — add tests for new baseline, KBS use case script, error analysis script
- **Framework**: pytest (existing, with pytest.ini and pyproject.toml config)
- **Existing tests as gates**: test_kbs_submission_package_verifier.py (page range, forbidden wording, author metadata), claim boundary tests

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to .omo/evidence/task-{N}-{scenario-slug}.{ext}.

- **LaTeX compilation**: Use Bash (latexmk) — compile, check exit code, verify page count from log
- **PDF content**: Use Bash (pdftotext or Python pdfplumber) — extract text, assert key phrases present/absent
- **Package verification**: Use Bash (python scripts/verify_kbs_submission_package.py) — run verifier, assert pass
- **Test suite**: Use Bash (pytest -q) — run tests, assert 0 failures
- **Bibliography**: Use Bash (bibtex compile) — check for warnings, verify citation resolution
- **Python scripts**: Use Bash (python scripts/run_kbs_audit_demo.py) — execute, verify output JSON exists and has expected fields
- **Claim registry**: Use Bash (grep) — verify new claim registered, verify forbidden wording absent

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Start Immediately - foundation + scaffolding):
  Task 1: Pre-compute missing baselines (simple_average, w_struct_direct reframe) [deep]
  Task 2: Bibliography audit + enrichment [quick]
  Task 3: Register M_KBS_AUDIT_DEMONSTRATION claim [quick]
  Task 4: PRM800K error case analysis script [unspecified-high]

Wave 2 (After Wave 1 - core manuscript work, MAX PARALLEL):
  Task 5: Reframe abstract + introduction (contribution-led) [unspecified-high]
  Task 6: Expand Related Work (separate from boundary, KBS classics) [unspecified-high]
  Task 7: Fix PRM800K narrative (QP downgrade explanation, Ridge recommendation) [unspecified-high]
  Task 8: Build KBS audit demo script + evidence artifact [deep]

Wave 3 (After Wave 2 - new section + consolidation):
  Task 9: Write new Section 6: KBS Audit Demonstration (~3 pages) [deep]
  Task 10: Consolidate Limitations section (move defensive language here) [quick]
  Task 11: Expand Evaluation section (add error analysis, new baselines) [unspecified-high]

Wave 4 (After Wave 3 - integration + finalization):
  Task 12: Recompile manuscript.pdf, verify 15-20 pages [quick]
  Task 13: Update supplementary.tex (reflect moved content) [quick]
  Task 14: Update cover letter, highlights, manifest, format checklist, lock audit [unspecified-high]
  Task 15: Final package verification + test suite run [quick]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
  Task F1: Plan compliance audit (oracle)
  Task F2: Code quality review (unspecified-high)
  Task F3: Real manual QA (unspecified-high)
  Task F4: Scope fidelity check (deep)
  -> Present results -> Get explicit user okay

Critical Path: Task 1 -> Task 7 -> Task 9 -> Task 12 -> Task 15 -> F1-F4 -> user okay
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Waves 1, 2, 3)

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|---|---|---|---|
| 1 | None | 7, 9, 11 | 1 |
| 2 | None | 6, 14 | 1 |
| 3 | None | 9, 14 | 1 |
| 4 | None | 11 | 1 |
| 5 | 3 | 12 | 2 |
| 6 | 2 | 12 | 2 |
| 7 | 1 | 9, 11 | 2 |
| 8 | 3 | 9 | 2 |
| 9 | 7, 8 | 12 | 3 |
| 10 | 5 | 12 | 3 |
| 11 | 1, 4, 7 | 12 | 3 |
| 12 | 2, 5, 6, 7, 9, 10, 11 | 13, 14, 15 | 4 |
| 13 | 12 | 14, 15 | 4 |
| 14 | 2, 3, 12, 13 | 15 | 4 |
| 15 | 12, 13, 14 | F1-F4 | 4 |

### Agent Dispatch Summary

- **Wave 1 (4 tasks)**: T1 -> deep, T2 -> quick, T3 -> quick, T4 -> unspecified-high
- **Wave 2 (4 tasks)**: T5 -> unspecified-high, T6 -> unspecified-high, T7 -> unspecified-high, T8 -> deep
- **Wave 3 (3 tasks)**: T9 -> deep, T10 -> quick, T11 -> unspecified-high
- **Wave 4 (4 tasks)**: T12 -> quick, T13 -> quick, T14 -> unspecified-high, T15 -> quick
- **FINAL (4 reviews)**: F1 -> oracle, F2 -> unspecified-high, F3 -> unspecified-high, F4 -> deep

---

## TODOs

- [ ] 1. Pre-compute Missing Baselines (simple_average + w_struct_direct reframe)

  **What to do**:
  - Implement `src/fma/baselines/simple_average.py`: unweighted mean of normalized CIU (c_tilde) and structural necessity (n_tilde), rank steps by this average. Signature: `def simple_average_baseline(ciu: Sequence[float], necessity: Sequence[float]) -> list[float]` returning simplex weights.
  - Run on synthetic calibration benchmark (200 traces, 1027 steps, seed 42): compute Spearman rho, Kendall tau, NDCG@3, NDCG@5 (same as Table 1).
  - Run on PRM800K locked split (4417 samples, 34219 steps): compute Spearman rho, NDCG@25% (same as Table 2).
  - Save to `outputs/baselines/simple_average_results.json` with fields: `synthetic_metrics`, `prm800k_metrics`, `config`.
  - Document `w_struct_direct` reframe in `outputs/baselines/w_struct_direct_reframe.md`: w_struct is already a standalone row in Table 2 (Spearman 0.611); treat as independent method claim, not just SC-FMA input.
  - Add `tests/test_simple_average_baseline.py` with 3 tests: (a) output length matches input, (b) output on probability simplex, (c) toy input where CIU and necessity agree on ranking -> simple_average preserves ranking.

  **Must NOT do**:
  - Do NOT change the SCU objective or SC-FMA method (G3)
  - Do NOT add other baselines (Shapley variants, gradient variants) — only simple_average
  - Do NOT call any APIs — use frozen synthetic data and frozen PRM800K v3.6 artifacts only (G1)
  - Do NOT fabricate numbers — all results must come from running the script

  **Recommended Agent Profile**:
  - **Category**: `deep` — multi-step reasoning: implement baseline, integrate with two benchmark harnesses, handle frozen artifact loading, write tests. Concept is simple but integration needs care.
  - **Skills**: [`python-debug`] — for fma.* import paths, frozen artifact loading, metric alignment with existing ranking module.
  - **Skills Evaluated but Omitted**: `repo-map` (codebase already mapped in interview), `safe-edit` (new file creation, not edit).

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 7, 9, 11 (need baseline results for narrative)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `src/fma/baselines/oracle_baselines.py` — existing baseline pattern; follow function signature, normalization, return type so it plugs into benchmark harness without adapter code.
  - `src/fma/eval/prm800k_audit_prioritization.py:136-280` — `summarize_audit_prioritization`, `classify_stratified_decision`, `SIMPLE_BASELINE_METHODS`; shows where w_struct and simple baselines live and how NDCG@25% is computed; new simple_average must integrate with this list.
  - `src/fma/ranking/` (directory) — existing Spearman/Kendall/NDCG computation; reuse, do not reimplement.

  **API/Type References**:
  - `src/fma/calibration/types.py` — CIUResult, FMAResult dataclasses; baseline output should be compatible.
  - `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json` — frozen PRM800K artifact (4417 samples / 34219 steps); loading exact field names correctly avoids rerunning API calls.

  **Test References**:
  - `tests/test_baselines.py` — existing baseline tests (19/19 passing); follow test structure and assertion style.

  **External References**: None — internal baseline implementation.

  **WHY Each Reference Matters**:
  - `oracle_baselines.py`: Exact function signature pattern for harness compatibility.
  - `prm800k_audit_prioritization.py`: Integration point for SIMPLE_BASELINE_METHODS so simple_average appears in tables automatically.
  - `ranking/`: Metric consistency with Tables 1 and 2.
  - `locked_validation_report.json`: Frozen artifact; correct field-name loading is critical to avoid API calls.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: simple_average baseline runs on synthetic benchmark
    Tool: Bash (python)
    Preconditions: synthetic traces exist; fma package installed (pip install -e .)
    Steps:
      1. Run: python scripts/run_simple_average_baseline.py --benchmark synthetic --output outputs/baselines/simple_average_results.json
      2. Assert: outputs/baselines/simple_average_results.json exists
      3. Assert: file has field synthetic_metrics.spearman_rho that is a finite float in [-1, 1]
    Expected Result: synthetic_metrics.spearman_rho is finite; value reasonable (between raw CIU 0.483 and w_struct-equivalent, since simple_average combines CIU and necessity)
    Failure Indicators: NaN, KeyError, file not created
    Evidence: .omo/evidence/task-1-simple-average-synthetic.json

  Scenario: simple_average baseline runs on PRM800K frozen split (zero API calls)
    Tool: Bash (python)
    Preconditions: outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json exists
    Steps:
      1. Record mtime of all files in outputs/real_task_v3_6_prm800k_hash/
      2. Run: python scripts/run_simple_average_baseline.py --benchmark prm800k --artifact outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json --output outputs/baselines/simple_average_results.json
      3. Assert: outputs/baselines/simple_average_results.json has field prm800k_metrics.spearman_rho finite in [-1, 1]
      4. Assert: no files in outputs/real_task_v3_6_prm800k_hash/ have mtime after task start (zero API calls)
    Expected Result: prm800k_metrics.spearman_rho finite; zero new files in frozen artifact dir
    Failure Indicators: API call detected (new files with recent mtime), NaN, artifact not loaded
    Evidence: .omo/evidence/task-1-simple-average-prm800k.json

  Scenario: simple_average tests pass
    Tool: Bash (pytest)
    Preconditions: tests/test_simple_average_baseline.py created
    Steps:
      1. Run: pytest -q tests/test_simple_average_baseline.py
      2. Assert: exit code 0, "3 passed"
    Expected Result: 3 tests pass (length, simplex, ranking preservation)
    Failure Indicators: any test fails, import error
    Evidence: .omo/evidence/task-1-simple-average-tests.txt

  Scenario: Contingency check — simple_average vs SC-FMA QP
    Tool: Bash (python)
    Preconditions: simple_average_results.json exists
    Steps:
      1. Read synthetic_metrics.spearman_rho
      2. If > 0.608 (SC-FMA QP synthetic), flag contingency (G3: reframe narrative in Task 7, don't change method)
      3. If in [0.50, 0.608], report as expected
      4. If < 0.50, investigate normalization bug
    Expected Result: simple_average in [0.45, 0.62] on synthetic
    Failure Indicators: > 0.65 (undermines SC-FMA claim, trigger contingency) or < 0.40 (bug)
    Evidence: .omo/evidence/task-1-simple-average-contingency-check.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(baselines): add simple_average baseline and w_struct_direct reframe note`
  - Files: `src/fma/baselines/simple_average.py`, `scripts/run_simple_average_baseline.py`, `tests/test_simple_average_baseline.py`, `outputs/baselines/simple_average_results.json`, `outputs/baselines/w_struct_direct_reframe.md`
  - Pre-commit: `pytest -q tests/test_simple_average_baseline.py`

- [ ] 2. Bibliography Audit and Enrichment

  **What to do**:
  - Audit `paper/kbs_submission/final_source/references.bib` (~83 entries). Remove >=15 irrelevant: `wang2018glue`, `wang2019superglue`, `kiela2021dynabench`, `liang2022helm`, `lhoest2021datasets`, `huggingface2024datasetsrevision`, `lee2022deduplicating`, `golchin2023dcq`, `yang2023rephrased`, `zhang2024gsm1k`, `dodge2021documenting`, `raji2021benchmark`, + 2-3 more NLP-infra refs with zero KBS relevance.
  - Verify each removed ref is NOT cited in manuscript.tex or supplementary.tex (grep cite key). If cited, do NOT remove — flag for Task 5/6.
  - Add <=15 KBS-relevant references: KBS journal audit/triage/verification papers (2022-2025), expert system validation, KG quality assessment, ontology reasoning. Real DOIs/URLs only.
  - Ensure total <=60 after removal+addition.
  - Ensure no orphan references (all cited at least once in manuscript.tex or supplementary.tex).
  - Run `bibtex manuscript` in `paper/kbs_submission/final_source/`; verify zero warnings in `manuscript.blg`.

  **Must NOT do**:
  - Do NOT remove references cited in the manuscript (G8 — breaks compilation)
  - Do NOT add fabricated references (G8 — all new refs must have real DOIs/URLs)
  - Do NOT exceed 60 total references (G5)
  - Do NOT add references unrelated to KBS, process supervision, or attribution (scope creep)

  **Recommended Agent Profile**:
  - **Category**: `quick` — bibliography editing is mechanical; judgment is in selecting KBS refs but volume is small (<=15 additions).
  - **Skills**: [`python-debug`] — for running bibtex and parsing .blg warnings.
  - **Skills Evaluated but Omitted**: `repo-map` (target file already known).

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 6 (related work needs new refs), 14 (manifest update)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/references.bib` (lines 1-890) — target file; follow existing BibTeX format (author, title, journal/booktitle, year, doi, url).
  - `paper/kbs_submission/final_source/manuscript.tex:69-75` — current citation usage in Related Work; shows which refs are cited.

  **API/Type References**: None — .bib file edit.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — verifier checks compilation; bibliography warnings gate.

  **External References**:
  - KBS journal website (https://www.sciencedirect.com/journal/knowledge-based-systems) — source of real, recent KBS papers.
  - Existing KBS refs as style anchors: `yang2025kbllmsurvey`, `huang2025kglongtail`, `siddharth2024engineeringrag`, `bellomarini2024knowledgegraphs`.

  **WHY Each Reference Matters**:
  - `references.bib`: Target file; existing entry format is the template.
  - `manuscript.tex:69-75`: Cite-key usage gate; removing a cited key breaks compilation.
  - KBS journal website: Source of truth for real KBS papers — avoids fabrication.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Bibliography compiles without warnings
    Tool: Bash (bibtex)
    Preconditions: references.bib edited
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
      3. bibtex manuscript
      4. Read manuscript.blg
      5. Assert: zero lines containing "warning" or "error"
    Expected Result: bibtex exits 0; .blg clean
    Failure Indicators: .blg contains "warning--", "error--", or "undefined citation"
    Evidence: .omo/evidence/task-2-bibtex-blg.txt

  Scenario: No orphan references
    Tool: Bash (python/grep)
    Preconditions: references.bib finalized
    Steps:
      1. Extract bib keys: grep "^@" references.bib -> parse key after "{"
      2. Extract cited keys: grep "\\cite{" and "\\citep{" from manuscript.tex + supplementary.tex
      3. Compute orphan set = bib_keys - cited_keys
      4. Assert: orphan set empty
    Expected Result: orphan set empty
    Failure Indicators: orphan set non-empty
    Evidence: .omo/evidence/task-2-orphan-check.txt

  Scenario: Reference count within limit
    Tool: Bash (grep)
    Preconditions: references.bib finalized
    Steps:
      1. Run: grep -c "^@" paper/kbs_submission/final_source/references.bib
      2. Assert: count <= 60
    Expected Result: count in [45, 60]
    Failure Indicators: count > 60 (G5 violation) or < 40 (over-pruning)
    Evidence: .omo/evidence/task-2-ref-count.txt

  Scenario: Removed refs not cited
    Tool: Bash (grep)
    Preconditions: >=15 refs removed
    Steps:
      1. For each removed cite key (wang2018glue, wang2019superglue, ...), grep manuscript.tex and supplementary.tex
      2. Assert: zero matches per removed key
    Expected Result: all removed keys have zero citations
    Failure Indicators: any removed key still cited
    Evidence: .omo/evidence/task-2-removed-refs-not-cited.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `chore(bibliography): remove 15+ irrelevant refs, add KBS-relevant refs, net <=60`
  - Files: `paper/kbs_submission/final_source/references.bib`, `paper/kbs_submission/references.bib`
  - Pre-commit: `bibtex manuscript` in final_source/

- [ ] 3. Register M_KBS_AUDIT_DEMONSTRATION Claim

  **What to do**:
  - Add new claim row to `paper/claim_registry.md` in "Active Claims (Methodological)" table:
    - Claim ID: `M_KBS_AUDIT_DEMONSTRATION`
    - Claim: "SC-FMA provides preliminary audit-prioritization demonstration on a knowledge-intensive reasoning task (PRM800K-like process supervision), supporting KBS audit relevance as a methodological analogy."
    - Status: `supported`
    - Artifact owner: `outputs/kbs_audit_demo/audit_demo_report.json`; `scripts/run_kbs_audit_demo.py`; `tests/test_kbs_audit_demo.py`
    - Allowed wording: "preliminary demonstration"; "supports KBS audit relevance"; "methodological analogy"; "fixed-budget audit prioritization on PRM800K-like annotations"
    - Blocked wording: "validates production KBS deployment"; "proves KBS improvement"; "downstream PRM training"; "GSM8K/HotpotQA replay validation"; "external generalization"
  - Add upgrade rule in "Upgrade Rules" section: "`M_KBS_AUDIT_DEMONSTRATION` can move from `supported` to `stratum_dependent` or stronger only with a passing external KBS benchmark audit. It cannot be upgraded to production deployment validation."
  - Verify table structure intact (markdown parses).
  - Run claim-boundary tests: `pytest -q tests/ -k "claim"`; assert 0 failures.

  **Must NOT do**:
  - Do NOT upgrade existing claims (G2 — claim boundary preserved)
  - Do NOT add blocked wording contradicting `M_STEP_RANKING` or `M_PRM_BASELINE_CONTEXT`
  - Do NOT register the claim before `outputs/kbs_audit_demo/` exists — but this task creates the registry entry; Task 8 creates the artifact. The registry entry can precede the artifact as long as Task 8 completes.
  - Do NOT change claim statuses of existing M_* claims

  **Recommended Agent Profile**:
  - **Category**: `quick` — markdown table edit + test run; mechanical.
  - **Skills**: [] — no specialized skill needed; pure markdown + pytest.
  - **Skills Evaluated but Omitted**: `python-debug` (no Python logic), `safe-edit` (new row, not modifying existing).

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Tasks 5 (abstract reframe references this claim), 8 (KBS demo script framing), 9 (KBS section references this claim), 14 (manifest mentions claim)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `paper/claim_registry.md:7-14` — existing Active Claims table; follow exact column format (Claim ID | Claim | Status | Artifact owner | Allowed wording | Blocked wording).
  - `paper/claim_registry.md:31-38` — Upgrade Rules section; follow bullet format.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_claim_boundaries.py` (if exists) or any test matching `claim` — verifies claim registry consistency.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `claim_registry.md:7-14`: Exact table format to preserve markdown parsing.
  - `claim_registry.md:31-38`: Upgrade rule format; new rule must match style.
  - Claim tests: Regression gate — adding a claim must not break existing claim-boundary enforcement.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: New claim registered in registry
    Tool: Bash (grep)
    Preconditions: paper/claim_registry.md edited
    Steps:
      1. Run: grep "M_KBS_AUDIT_DEMONSTRATION" paper/claim_registry.md
      2. Assert: at least one match in the Active Claims table
      3. Run: grep -c "|" paper/claim_registry.md (table row count sanity)
    Expected Result: M_KBS_AUDIT_DEMONSTRATION appears in a table row with 6 columns (| separators)
    Failure Indicators: no match, or malformed table row
    Evidence: .omo/evidence/task-3-claim-registered.txt

  Scenario: Claim-boundary tests pass
    Tool: Bash (pytest)
    Preconditions: registry updated
    Steps:
      1. Run: pytest -q tests/ -k "claim"
      2. Assert: exit code 0
    Expected Result: all claim tests pass (no regression from new claim)
    Failure Indicators: any test fails (new claim may have introduced forbidden wording overlap)
    Evidence: .omo/evidence/task-3-claim-tests.txt

  Scenario: Upgrade rule added
    Tool: Bash (grep)
    Preconditions: registry updated
    Steps:
      1. Run: grep "M_KBS_AUDIT_DEMONSTRATION.*stratum_dependent\|M_KBS_AUDIT_DEMONSTRATION.*upgrade" paper/claim_registry.md
      2. Assert: at least one match in Upgrade Rules section
    Expected Result: upgrade rule text present
    Failure Indicators: no match (rule not added)
    Evidence: .omo/evidence/task-3-upgrade-rule.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `docs(claims): register M_KBS_AUDIT_DEMONSTRATION claim for KBS audit use case`
  - Files: `paper/claim_registry.md`
  - Pre-commit: `pytest -q tests/ -k "claim"`

- [ ] 4. PRM800K Error Case Analysis Script (Lightweight Real-Task Reinforcement)

  **What to do**:
  - Create `scripts/analyze_prm800k_error_cases.py`: a static analysis script that loads frozen PRM800K v3.6 artifacts (`outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json`) and computes:
    - Stratified error analysis: for traces where SC-FMA QP underperforms w_struct (delta rho < 0), what trace characteristics predict the degradation? (trace length, redundancy density, bottleneck count, position of high-necessity steps)
    - Variant behavior comparison: group traces by whether QP > Ridge, QP < Ridge, or QP << w_struct; report mean characteristics of each group
    - Case study examples: select 3 representative traces (one where QP wins, one where Ridge wins, one where w_struct wins) and dump their step-level weights for all variants
  - Output to `outputs/real_task_v3_6_prm800k_hash/error_case_analysis.json` with fields: `stratified_summary`, `variant_comparison`, `case_studies`.
  - Generate a human-readable summary `outputs/real_task_v3_6_prm800k_hash/error_case_analysis.md` (markdown).
  - Add `tests/test_prm800k_error_analysis.py` with 2 tests: (a) script runs and produces JSON with expected top-level fields, (b) zero API calls (no new files in frozen artifact dir beyond the two new analysis outputs).
  - The analysis MUST produce a concrete finding reportable in the manuscript, e.g., "QP underperforms on traces with high redundancy density (>0.5) where w_struct already captures the dominant ordering; Ridge is robust because it soft-averages rather than fully optimizing."

  **Must NOT do**:
  - Do NOT call any APIs (G1 — use frozen artifacts only)
  - Do NOT rerun v3/v3.1/v3.2 smoke tests (G6 — static analysis only)
  - Do NOT change the SC-FMA method (G3 — if analysis reveals weakness, reframe in Task 7)
  - Do NOT upgrade claim statuses based on this analysis (G2)
  - Do NOT fabricate findings — all numbers from frozen artifact

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires careful data analysis, statistical grouping, and synthesis of a concrete narrative finding. Not trivial but not open-ended research.
  - **Skills**: [`python-debug`] — for loading frozen JSON, pandas/numpy grouping, handling nested artifact structure.
  - **Skills Evaluated but Omitted**: `repo-map` (artifacts already located in interview).

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Tasks 7 (PRM800K narrative uses error analysis findings), 11 (evaluation expansion uses this analysis)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json` — frozen artifact with per-sample, per-step w_struct, raw CIU, SC-FMA variant predictions, and PRM800K labels. Field names must be read from this file.
  - `src/fma/eval/prm800k_audit_prioritization.py` — shows how the audit module loads and processes the same artifact; follow the loading pattern.
  - `outputs/real_task_v3_6_prm800k_hash/decision_report.json` — companion artifact with variant-level metrics; may contain per-trace breakdown.

  **API/Type References**:
  - `src/fma/real_task_pilot/` — real task pilot module; may have helpers for trace characteristic computation (length, redundancy, bottleneck).

  **Test References**:
  - `tests/test_real_task_v3_6_prm800k_hash_validation.py` — existing test for v3.6; follow assertion style for artifact loading.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `locked_validation_report.json`: The primary data source; field-name accuracy is critical.
  - `prm800k_audit_prioritization.py`: Loading pattern precedent; avoids reinventing artifact parsing.
  - `decision_report.json`: May contain pre-computed per-trace variant predictions, avoiding recomputation.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Error analysis script runs and produces JSON
    Tool: Bash (python)
    Preconditions: outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json exists
    Steps:
      1. Record mtime of all files in outputs/real_task_v3_6_prm800k_hash/ (except the two new outputs)
      2. Run: python scripts/analyze_prm800k_error_cases.py --artifact outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json --output outputs/real_task_v3_6_prm800k_hash/error_case_analysis.json
      3. Assert: error_case_analysis.json exists
      4. Assert: has top-level fields stratified_summary, variant_comparison, case_studies
      5. Assert: error_case_analysis.md exists and is non-empty
      6. Assert: no files in outputs/real_task_v3_6_prm800k_hash/ (other than the 2 new outputs) have mtime after task start
    Expected Result: JSON + MD produced; zero API calls; fields populated with finite numbers
    Failure Indicators: file not created, missing fields, API call detected (new/modified frozen files)
    Evidence: .omo/evidence/task-4-error-analysis-run.json

  Scenario: Concrete finding produced
    Tool: Bash (grep/python)
    Preconditions: error_case_analysis.md exists
    Steps:
      1. Read error_case_analysis.md
      2. Assert: contains at least one sentence matching pattern "QP underperforms" or "Ridge is robust" or similar concrete variant-behavior statement
      3. Assert: contains at least 3 numeric values (e.g., trace counts, mean densities, rho values)
    Expected Result: markdown contains a reportable finding with supporting numbers
    Failure Indicators: generic/vague text, no numbers, no variant comparison
    Evidence: .omo/evidence/task-4-concrete-finding.txt

  Scenario: Error analysis tests pass
    Tool: Bash (pytest)
    Preconditions: tests/test_prm800k_error_analysis.py created
    Steps:
      1. Run: pytest -q tests/test_prm800k_error_analysis.py
      2. Assert: exit code 0, "2 passed"
    Expected Result: 2 tests pass (script runs, zero API calls)
    Failure Indicators: test fails, API call detected
    Evidence: .omo/evidence/task-4-error-analysis-tests.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(analysis): add PRM800K error case analysis script and findings`
  - Files: `scripts/analyze_prm800k_error_cases.py`, `tests/test_prm800k_error_analysis.py`, `outputs/real_task_v3_6_prm800k_hash/error_case_analysis.json`, `outputs/real_task_v3_6_prm800k_hash/error_case_analysis.md`
  - Pre-commit: `pytest -q tests/test_prm800k_error_analysis.py`

- [ ] 5. Reframe Abstract and Introduction (Contribution-Led)

  **What to do**:
  - Edit `paper/kbs_submission/final_source/manuscript.tex`:
    - **Abstract** (lines 51-53): Rewrite to open with the positive contribution ("This paper presents SC-FMA, a claim-bounded methodology that converts coarse utility signals into auditable verification-step weights via a convex SCU objective..."). Move all "does not claim" language to a single boundary sentence at the end of the abstract. Target: <=2 defensive phrases (sentences containing "does not claim", "is not", "remains outside", "this paper does not", "not a"). Current abstract has ~5 such phrases.
    - **Introduction** (lines 61-67): Rewrite the four contributions paragraph (line 67) in positive language. Currently: "All claims are bounded to methodology and audit prioritization; downstream PRM training, task-specific replay validation, production KBS deployment, and causal identification remain outside the evidence surface." Reframe to: "The contributions are: (1) SC-FMA calibration methodology; (2) SCU objective with formal guarantees; (3) controlled synthetic ranking evidence; (4) bounded real-data evidence on PRM800K and an offline audit-prioritization readout. Section 7 discusses the claim boundary and future validation directions." Move boundary language to Limitations.
  - Verify the reframed abstract still contains all key numbers: 0.483 -> 0.608 (synthetic), 0.611 (w_struct), 0.604 (Ridge), 4417 samples, 34219 steps.
  - Ensure no forbidden wording introduced (grep for "downstream PRM training", "GSM8K replay", "production deployment", "causal effect" — these are fine in Limitations but NOT in abstract/intro as claims).
  - Recompile manuscript.pdf and verify abstract renders correctly.

  **Must NOT do**:
  - Do NOT remove the claim boundary entirely (G2 — must preserve boundary, just relocate to Limitations)
  - Do NOT over-claim (G2 — no new positive claims beyond what registry allows)
  - Do NOT change the numbers (G8 — 0.483, 0.608, 0.611, 0.604, 4417, 34219 must remain exact)
  - Do NOT change author metadata, funding, or declarations

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires careful prose rewriting that preserves all numbers, claim boundaries, and registry compliance while shifting tone. Judgment-heavy.
  - **Skills**: [] — LaTeX editing is direct; no specialized skill needed beyond careful text work.
  - **Skills Evaluated but Omitted**: `safe-edit` (substantial rewrite, not minimal edit), `frontend-ui-ux` (not UI).

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 6, 7, 8 — different sections/files; Task 6 edits Related Work, Task 7 edits Evaluation, Task 8 is a script)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 12 (recompile needs all manuscript edits)
  - **Blocked By**: Task 3 (claim registry must be updated so reframed text can reference M_KBS_AUDIT_DEMONSTRATION)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/final_source/manuscript.tex:51-53` — current abstract; rewrite preserving all numbers.
  - `paper/kbs_submission/final_source/manuscript.tex:61-67` — current introduction; reframe contributions paragraph.
  - `paper/claim_registry.md` — governs allowed/blocked wording for each claim.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — verifies PDF text content; reframed abstract must still pass.
  - `tests/test_claim_boundaries.py` (if exists) — verifies no forbidden wording.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `manuscript.tex:51-53, 61-67`: The exact text to rewrite; numbers and key phrases must be preserved.
  - `claim_registry.md`: Wording gate; reframed text must use only "Allowed wording" from each claim.
  - Verifier tests: Regression gate; reframed text must not break PDF text checks.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Abstract defensive phrase count <= 2
    Tool: Bash (python/grep)
    Preconditions: manuscript.tex abstract edited
    Steps:
      1. Extract abstract text (between \begin{abstract} and \end{abstract})
      2. Count sentences containing any of: "does not claim", "is not", "remains outside", "this paper does not", "not a"
      3. Assert: count <= 2
    Expected Result: 0, 1, or 2 defensive phrases (down from ~5)
    Failure Indicators: count > 2
    Evidence: .omo/evidence/task-5-abstract-defensive-count.txt

  Scenario: Key numbers preserved in abstract
    Tool: Bash (grep)
    Preconditions: abstract edited
    Steps:
      1. grep abstract for "0.483", "0.608", "0.611", "0.604", "4,417" or "4417", "34,219" or "34219"
      2. Assert: all 6 numbers present
    Expected Result: all key numbers present in abstract
    Failure Indicators: any number missing or altered
    Evidence: .omo/evidence/task-5-numbers-preserved.txt

  Scenario: No forbidden wording in abstract/intro
    Tool: Bash (grep)
    Preconditions: abstract + intro edited
    Steps:
      1. grep abstract and intro for: "downstream PRM training", "GSM8K replay validation", "production KBS deployment", "causal effect", "true causal"
      2. Assert: zero matches (these phrases belong only in Limitations)
    Expected Result: zero forbidden phrases in abstract/intro
    Failure Indicators: any match
    Evidence: .omo/evidence/task-5-no-forbidden-wording.txt

  Scenario: Manuscript compiles after reframe
    Tool: Bash (latexmk)
    Preconditions: manuscript.tex edited
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
      3. Assert: exit code 0
      4. Assert: manuscript.pdf produced
    Expected Result: compilation succeeds; PDF updated
    Failure Indicators: LaTeX error, missing PDF
    Evidence: .omo/evidence/task-5-compile.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `refactor(paper): reframe abstract and introduction as contribution-led`
  - Files: `paper/kbs_submission/final_source/manuscript.tex`
  - Pre-commit: `latexmk -pdf manuscript.tex` in final_source/

- [ ] 6. Expand Related Work (Separate from Boundary, Add KBS Classics)

  **What to do**:
  - Edit `paper/kbs_submission/final_source/manuscript.tex` Section 2 "Related Work and Boundary" (lines 69-76):
    - Split into two subsections: "2.1 Related Work" and "2.2 Scope and Boundary" (or keep as one section but expand the Related Work portion from ~1 paragraph to ~3 paragraphs).
    - Expand Related Work to cover three strands with citations to the newly-added KBS references (from Task 2):
      1. **Process supervision and PRMs**: Lightman et al. 2023, Math-Shepherd, ProcessBench — position SC-FMA as calibration, not PRM training.
      2. **Attribution and explanation**: Integrated Gradients, SHAP, ERASER, GNNExplainer — position SC-FMA as structural, not independent-unit.
      3. **Knowledge-based systems**: Classic expert systems (MYCIN, DENDRAL, SOAR, ACT-R) + modern KBS/KG/LLM integration (Hu et al. 2024, Pan et al. 2024, Yang et al. 2025, Bellomarini et al. 2024) + NEW KBS refs added in Task 2 (audit, verification, KG quality). Position SC-FMA as a weighting layer for auditable intermediate evidence in KBS.
    - Keep the "Boundary" content (validated_kbs_workflow=false) but condense it; the full boundary discussion moves to Limitations (Task 10).
  - Add ~0.5-1 page of net new content (within the page budget).
  - Ensure all new citations resolve (cite keys exist in references.bib after Task 2).
  - Recompile and verify no undefined references.

  **Must NOT do**:
  - Do NOT cite references not in references.bib (would break compilation)
  - Do NOT over-claim KBS integration (G2 — SC-FMA does not validate production KBS)
  - Do NOT pad with generic survey prose (G7 — every paragraph must add substantive positioning)
  - Do NOT remove the validated_kbs_workflow=false boundary marker (G2)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires synthesizing three literature strands into coherent positioning prose; judgment-heavy.
  - **Skills**: [] — LaTeX prose writing; no specialized skill.
  - **Skills Evaluated but Omitted**: `python-debug` (no code), `repo-map` (target section known).

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 7, 8)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 12 (recompile)
  - **Blocked By**: Task 2 (needs new KBS references in references.bib before citing them)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/final_source/manuscript.tex:69-76` — current Section 2; expand Related Work, condense Boundary.
  - `paper/kbs_submission/references.bib` (post-Task-2) — cite keys available for the three strands.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — PDF text and undefined-reference checks.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `manuscript.tex:69-76`: The section to expand; existing structure is the scaffold.
  - `references.bib`: Cite-key source; every \cite{} must resolve.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Related Work expanded with three strands
    Tool: Bash (grep)
    Preconditions: Section 2 edited
    Steps:
      1. Extract Section 2 text
      2. Assert: contains "process supervision" or "process reward" (strand 1)
      3. Assert: contains "attribution" or "explanation" (strand 2)
      4. Assert: contains "knowledge-based" or "expert system" or "knowledge graph" (strand 3)
    Expected Result: all three strands present
    Failure Indicators: any strand missing
    Evidence: .omo/evidence/task-6-three-strands.txt

  Scenario: No undefined references
    Tool: Bash (latexmk/bibtex)
    Preconditions: manuscript.tex edited, references.bib finalized (Task 2)
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
      3. bibtex manuscript
      4. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex (second pass)
      5. grep manuscript.log for "undefined" or "Citation"
      6. Assert: zero "undefined citation" warnings
    Expected Result: all citations resolve
    Failure Indicators: "Citation ... undefined" in log
    Evidence: .omo/evidence/task-6-no-undefined-refs.txt

  Scenario: Boundary marker preserved
    Tool: Bash (grep)
    Preconditions: Section 2 edited
    Steps:
      1. grep manuscript.tex for "validated_kbs_workflow" or "validated\\_kbs\\_workflow"
      2. Assert: at least one match
    Expected Result: boundary marker retained (may be condensed but not removed)
    Failure Indicators: no match (boundary removed — G2 violation)
    Evidence: .omo/evidence/task-6-boundary-preserved.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `refactor(paper): expand Related Work into three strands, condense boundary`
  - Files: `paper/kbs_submission/final_source/manuscript.tex`
  - Pre-commit: `latexmk -pdf manuscript.tex` + `bibtex manuscript` in final_source/

- [ ] 7. Fix PRM800K Narrative (QP Downgrade Explanation, Ridge Recommendation, w_struct Distinction)

  **What to do**:
  - Edit `paper/kbs_submission/final_source/manuscript.tex` Section 4.3 "PRM800K Evidence and Audit Readout" (lines 141-165):
    - Add a new paragraph (or expand existing) that explicitly explains WHY SC-FMA QP underperforms on PRM800K (rho 0.442 vs w_struct 0.611):
      - Use the error case analysis findings from Task 4 (e.g., "QP underperforms on traces with high redundancy density where w_struct already captures the dominant ordering; the full constrained optimization over-corrects against a strong input signal").
      - Distinguish "w_struct's inherent quality" (the input signal, rho 0.611) from "SC-FMA's achievement" (Ridge preserves it at 0.604; QP and Projection are downgraded).
      - State the recommendation clearly: "On PRM800K-like annotations where a strong structural-necessity signal already exists, SC-FMA Ridge is the recommended variant because it preserves the signal while adding mild calibration; QP is reserved for settings where the input signal is weaker and full structural optimization is beneficial (as in the synthetic benchmark)."
    - Update Table 2 caption or surrounding text to clarify that w_struct is reported as an independent baseline (per Task 1's w_struct_direct reframe), not just as SC-FMA's input.
    - Add the simple_average baseline row to Table 2 (from Task 1 results) so the comparison is complete.
    - Ensure the narrative does NOT claim "SC-FMA achieves 0.611" — that is w_struct's number. SC-FMA Ridge achieves 0.604.
  - Verify all numbers match frozen artifacts (0.611, 0.604, 0.442, -0.135, -0.077, 0.252, 0.006).

  **Must NOT do**:
  - Do NOT claim SC-FMA achieves w_struct's number (G2 — claim boundary; must distinguish input from output)
  - Do NOT change the numbers (G8 — all values must match frozen artifacts exactly)
  - Do NOT change the SCU objective or method (G3 — if QP weakness revealed, explain it, don't fix it)
  - Do NOT remove the route-specific downgrade language (G2 — "QP and Projection are downgraded on this route" must stay)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires synthesizing error analysis findings into honest narrative that doesn't over-claim but also doesn't undersell. Judgment-heavy.
  - **Skills**: [] — LaTeX prose + table editing.
  - **Skills Evaluated but Omitted**: `python-debug` (no code), `safe-edit` (substantial prose addition).

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 6, 8)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 9 (KBS section references PRM800K narrative), 11 (evaluation expansion), 12 (recompile)
  - **Blocked By**: Task 1 (needs simple_average baseline results for Table 2 row), Task 4 (needs error case analysis findings for QP explanation)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/final_source/manuscript.tex:141-165` — current Section 4.3; the text to expand.
  - `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json` — frozen artifact; source of truth for all numbers.
  - `outputs/real_task_v3_6_prm800k_hash/error_case_analysis.md` (from Task 4) — findings to incorporate.
  - `outputs/baselines/simple_average_results.json` (from Task 1) — simple_average row for Table 2.
  - `paper/claim_registry.md` — M_STEP_RANKING and M_PRM_BASELINE_CONTEXT govern allowed wording.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_real_task_v3_6_prm800k_hash_validation.py` — verifies numbers match frozen artifact.
  - `tests/test_kbs_submission_package_verifier.py` — PDF text checks.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `manuscript.tex:141-165`: The section to edit; existing structure and numbers are the scaffold.
  - `locked_validation_report.json`: Source of truth for 0.611, 0.604, 0.442, etc.; any number in the narrative must trace here.
  - `error_case_analysis.md`: The substantive content for the QP-downgrade explanation; without this, the narrative is hand-waving.
  - `simple_average_results.json`: The new Table 2 row data.
  - `claim_registry.md`: Wording gate; "SC-FMA achieves 0.611" is blocked, "SC-FMA Ridge achieves 0.604, closely preserving w_struct's 0.611" is allowed.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: QP downgrade explanation present
    Tool: Bash (grep)
    Preconditions: Section 4.3 edited
    Steps:
      1. Extract Section 4.3 text
      2. Assert: contains "QP" AND ("underperform" OR "downgrade" OR "over-correct" OR "high redundancy")
      3. Assert: contains a concrete reason referencing redundancy or signal strength
    Expected Result: explanation paragraph present with specific mechanism
    Failure Indicators: no explanation, or vague ("QP is worse" without reason)
    Evidence: .omo/evidence/task-7-qp-explanation.txt

  Scenario: w_struct vs SC-FMA distinction clear
    Tool: Bash (grep/python)
    Preconditions: Section 4.3 edited
    Steps:
      1. Extract Section 4.3 text
      2. Assert: contains "0.611" associated with w_struct (not SC-FMA)
      3. Assert: contains "0.604" associated with SC-FMA Ridge
      4. Assert: does NOT contain phrase "SC-FMA achieves 0.611" or "SC-FMA.*0.611" as a claim
    Expected Result: numbers correctly attributed
    Failure Indicators: SC-FMA claimed to achieve 0.611 (G2 violation)
    Evidence: .omo/evidence/task-7-wstruct-distinction.txt

  Scenario: simple_average row added to Table 2
    Tool: Bash (grep)
    Preconditions: Table 2 edited
    Steps:
      1. grep manuscript.tex for "Simple Average" or "simple_average" or "Avg (CIU, Necessity)"
      2. Assert: at least one match in Table 2 region
    Expected Result: simple_average baseline row present in Table 2
    Failure Indicators: row missing
    Evidence: .omo/evidence/task-7-simple-average-row.txt

  Scenario: All numbers match frozen artifacts
    Tool: Bash (python)
    Preconditions: Section 4.3 edited
    Steps:
      1. Load outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json
      2. Extract canonical values: w_struct rho, Ridge rho, QP rho, Projection rho, raw CIU rho
      3. grep manuscript.tex for each value
      4. Assert: all canonical values present and none altered
    Expected Result: every number in narrative matches frozen artifact
    Failure Indicators: any number altered or fabricated
    Evidence: .omo/evidence/task-7-numbers-match.txt

  Scenario: Manuscript compiles
    Tool: Bash (latexmk)
    Preconditions: manuscript.tex edited
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
      3. Assert: exit code 0
    Expected Result: compilation succeeds
    Failure Indicators: LaTeX error
    Evidence: .omo/evidence/task-7-compile.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `refactor(paper): fix PRM800K narrative — explain QP downgrade, distinguish w_struct, add simple_average row`
  - Files: `paper/kbs_submission/final_source/manuscript.tex`
  - Pre-commit: `latexmk -pdf manuscript.tex` in final_source/

- [ ] 8. Build KBS Audit Demo Script and Evidence Artifact

  **What to do**:
  - Create `scripts/run_kbs_audit_demo.py`: a script that repurposes the existing PRM800K audit-prioritization module (`src/fma/eval/prm800k_audit_prioritization.py`) with an explicit KBS audit scenario framing.
  - The script MUST:
    - Load frozen PRM800K v3.6 artifact (`outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json`) — ZERO new API calls.
    - Frame the scenario: "A knowledge-intensive reasoning system reviewer with a fixed budget to inspect 25% of process steps must prioritize which steps to audit. We compare SC-FMA Ridge, raw CIU, w_struct, and random ranking on this audit-prioritization task using PRM800K-like process-supervision annotations."
    - Compute for each method: top-1 hit rate, mass@25%, NDCG@25% (these metrics already exist in `prm800k_audit_prioritization.py`).
    - Produce a single comparison table (saved as JSON) showing SC-FMA Ridge vs. raw CIU vs. w_struct vs. random on the audit-prioritization metrics.
    - Output to `outputs/kbs_audit_demo/audit_demo_report.json` with fields: `scenario`, `methods` (dict of method -> metrics), `config`, `evidence_level` (="demonstration"), `validated_kbs_workflow` (=false).
  - Also produce `outputs/kbs_audit_demo/audit_demo_summary.md` (human-readable summary).
  - Add `tests/test_kbs_audit_demo.py` with 2 tests: (a) script runs and produces JSON with expected fields, (b) zero API calls (no new files in frozen artifact dir).
  - The script MUST use only frozen artifacts and the existing audit module; it is a thin wrapper that adds KBS framing, NOT new computation.

  **Must NOT do**:
  - Do NOT call any APIs (G1 — frozen artifacts only)
  - Do NOT build a new KBS system or ontology (G4 — ONE scenario, ONE metric set, reuse existing module)
  - Do NOT claim production KBS validation (G2 — evidence_level=demonstration, validated_kbs_workflow=false)
  - Do NOT add a second scenario (G4 — any second scenario requires explicit re-approval)
  - Do NOT reimplement audit metrics (reuse `prm800k_audit_prioritization.py`)

  **Recommended Agent Profile**:
  - **Category**: `deep` — requires understanding the existing audit module, framing a KBS scenario correctly, and ensuring zero API calls. Integration-heavy.
  - **Skills**: [`python-debug`] — for loading frozen JSON, calling existing audit module functions, handling nested artifact structure.
  - **Skills Evaluated but Omitted**: `repo-map` (module already located), `safe-edit` (new script, not edit).

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 6, 7)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9 (KBS section references this artifact)
  - **Blocked By**: Task 3 (M_KBS_AUDIT_DEMONSTRATION claim must be registered so the script's output framing is registry-compliant)

  **References**:

  **Pattern References**:
  - `src/fma/eval/prm800k_audit_prioritization.py:44-90` — `max_label_hit_at_budget`, `label_mass_at_budget`, `ndcg_at_budget`; the exact functions to call for top-1 hit, mass@25%, NDCG@25%.
  - `src/fma/eval/prm800k_audit_prioritization.py:136-280` — `summarize_audit_prioritization`; shows how to wire methods, labels, and budgets together.
  - `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json` — frozen artifact; field names for predictions and labels.
  - `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` — existing audit report; may already contain the comparison; the demo script can reformat this with KBS framing rather than recomputing.

  **API/Type References**:
  - `src/fma/eval/prm800k_audit_prioritization.py` (entire module) — the API surface to reuse.

  **Test References**:
  - `tests/test_prm800k_audit_prioritization.py` (if exists, 161 lines per Oracle) — existing test for the audit module; follow assertion style.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `prm800k_audit_prioritization.py:44-90`: The metric functions; calling these directly ensures consistency with supplementary Table S2.
  - `prm800k_audit_prioritization.py:136-280`: The orchestration pattern; the demo script is a thin wrapper around this.
  - `locked_validation_report.json` + `audit_prioritization_report.json`: Frozen data sources; if the latter already has the comparison, the demo script reformats rather than recomputes (further reducing risk).

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: KBS audit demo script runs and produces evidence
    Tool: Bash (python)
    Preconditions: outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json exists; Task 3 claim registered
    Steps:
      1. Record mtime of all files in outputs/real_task_v3_6_prm800k_hash/
      2. Run: python scripts/run_kbs_audit_demo.py --artifact outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json --output outputs/kbs_audit_demo/audit_demo_report.json
      3. Assert: outputs/kbs_audit_demo/audit_demo_report.json exists
      4. Assert: has fields scenario, methods, config, evidence_level, validated_kbs_workflow
      5. Assert: evidence_level == "demonstration"
      6. Assert: validated_kbs_workflow == false
      7. Assert: methods dict contains keys for SC-FMA Ridge, raw CIU, w_struct, random
      8. Assert: no files in outputs/real_task_v3_6_prm800k_hash/ have mtime after task start
    Expected Result: JSON + MD produced; zero API calls; evidence_level=demonstration; validated_kbs_workflow=false
    Failure Indicators: file missing, fields missing, evidence_level != "demonstration", validated_kbs_workflow != false, API call detected
    Evidence: .omo/evidence/task-8-audit-demo-run.json

  Scenario: Audit demo metrics match existing supplementary Table S2
    Tool: Bash (python)
    Preconditions: audit_demo_report.json exists
    Steps:
      1. Load audit_demo_report.json; extract w_struct NDCG@25%
      2. Compare to value in supplementary Table S2 (0.9506 per supplementary.tex:325)
      3. Assert: values match (within floating-point tolerance, e.g., abs diff < 1e-4)
    Expected Result: w_struct NDCG@25% in demo == 0.9506 (matches supplementary)
    Failure Indicators: values diverge (indicates recomputation bug or wrong artifact)
    Evidence: .omo/evidence/task-8-metrics-match.txt

  Scenario: KBS audit demo tests pass
    Tool: Bash (pytest)
    Preconditions: tests/test_kbs_audit_demo.py created
    Steps:
      1. Run: pytest -q tests/test_kbs_audit_demo.py
      2. Assert: exit code 0, "2 passed"
    Expected Result: 2 tests pass (script runs, zero API calls)
    Failure Indicators: test fails, API call detected
    Evidence: .omo/evidence/task-8-audit-demo-tests.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(kbs): add KBS audit demonstration script repurposing PRM800K audit-prioritization`
  - Files: `scripts/run_kbs_audit_demo.py`, `tests/test_kbs_audit_demo.py`, `outputs/kbs_audit_demo/audit_demo_report.json`, `outputs/kbs_audit_demo/audit_demo_summary.md`
  - Pre-commit: `pytest -q tests/test_kbs_audit_demo.py`

- [ ] 9. Write New Section 6: KBS Audit Demonstration (~3 pages)

  **What to do**:
  - Add a new Section 6 "KBS Audit Demonstration" to `paper/kbs_submission/final_source/manuscript.tex`, inserted between current Section 5 (KBS Implications and Limitations) and Section 6 (Conclusion). Renumber Conclusion to Section 7.
  - Section content (~3 pages):
    - **6.1 Scenario**: Describe the fixed-budget audit-prioritization scenario — a reviewer of a knowledge-intensive reasoning system must inspect 25% of process steps; which steps to prioritize? Frame as KBS audit relevance (methodological analogy to rule-chain / RAG / KGQA review prioritization).
    - **6.2 Data and Methods**: PRM800K-like process-supervision annotations (4417 samples, 34219 steps, frozen hash split). Methods compared: SC-FMA Ridge, raw CIU, w_struct, random. Metrics: top-1 hit, mass@25%, NDCG@25%. Reference the M_KBS_AUDIT_DEMONSTRATION claim.
    - **6.3 Results**: A table (Table 3) showing the four methods on the three metrics. Numbers from `outputs/kbs_audit_demo/audit_demo_report.json` (Task 8). Key finding: SC-FMA Ridge and w_struct concentrate high-rated steps better than raw CIU and random.
    - **6.4 Interpretation**: Moderate, preliminary real-data support for PRM800K-like audit prioritization. Explicitly NOT downstream PRM training, NOT filtering superiority, NOT GSM8K/HotpotQA replay, NOT production KBS deployment. Reference the claim boundary.
    - **6.5 KBS Methodological Analogy**: Map the audit scenario to KBS curation priorities — high-necessity bottleneck checks deserve review; highly redundant checks may be consolidation candidates. State clearly this is a methodological analogy, not a validated system integration (validated_kbs_workflow=false).
  - Ensure the section uses only "Allowed wording" from M_KBS_AUDIT_DEMONSTRATION claim.
  - Ensure all numbers trace to `outputs/kbs_audit_demo/audit_demo_report.json`.
  - Recompile and verify ~3 pages added.

  **Must NOT do**:
  - Do NOT claim production KBS validation (G2 — validated_kbs_workflow=false must appear)
  - Do NOT add a second scenario (G4 — ONE scenario only)
  - Do NOT fabricate numbers (G8 — all from Task 8 artifact)
  - Do NOT use blocked wording from claim registry (G2)
  - Do NOT exceed ~3 pages (G7 — substantive content, no padding)

  **Recommended Agent Profile**:
  - **Category**: `deep` — requires synthesizing the audit scenario, KBS methodological analogy, and claim-boundary-compliant prose into a coherent 3-page section. Judgment-heavy and claim-sensitive.
  - **Skills**: [] — LaTeX prose + table writing.
  - **Skills Evaluated but Omitted**: `python-debug` (no code), `safe-edit` (new section, substantial).

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 7, 8)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 12 (recompile)
  - **Blocked By**: Task 7 (PRM800K narrative must be fixed first so Section 6 is consistent), Task 8 (needs audit_demo_report.json for Table 3 numbers)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/final_source/manuscript.tex:141-165` — existing Section 4.3 (PRM800K Evidence); Section 6 extends this with KBS framing; follow the table and prose style.
  - `paper/kbs_submission/final_source/supplementary.tex:316-335` — supplementary Table S2 (audit-prioritization); Section 6 Table 3 should be consistent with this.
  - `outputs/kbs_audit_demo/audit_demo_report.json` (from Task 8) — source of all numbers.
  - `outputs/kbs_audit_demo/audit_demo_summary.md` (from Task 8) — human-readable findings to adapt.
  - `paper/claim_registry.md` — M_KBS_AUDIT_DEMONSTRATION governs wording.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — page count, PDF text, forbidden wording checks.
  - `tests/test_claim_boundaries.py` (if exists) — claim registry enforcement.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `manuscript.tex:141-165`: Style precedent; Section 6 mirrors Section 4.3's structure.
  - `supplementary.tex:316-335`: Consistency gate; Table 3 must not contradict Table S2.
  - `audit_demo_report.json`: Sole source of numbers for Table 3.
  - `claim_registry.md`: Wording gate; every sentence must use "Allowed wording" only.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Section 6 exists with required subsections
    Tool: Bash (grep)
    Preconditions: manuscript.tex edited
    Steps:
      1. grep manuscript.tex for "section{KBS Audit Demonstration}" or "section\{KBS Audit"
      2. Assert: match found
      3. grep for subsections: "Scenario", "Data and Methods", "Results", "Interpretation", "Methodological Analogy"
      4. Assert: at least 4 of 5 subsection labels present
    Expected Result: Section 6 with subsections present
    Failure Indicators: section missing or subsections missing
    Evidence: .omo/evidence/task-9-section-structure.txt

  Scenario: Table 3 numbers match audit demo artifact
    Tool: Bash (python)
    Preconditions: Section 6 Table 3 written
    Steps:
      1. Load outputs/kbs_audit_demo/audit_demo_report.json
      2. Extract NDCG@25% for w_struct, Ridge, raw CIU, random
      3. grep manuscript.tex Table 3 region for each value
      4. Assert: all values present and match artifact
    Expected Result: every number in Table 3 matches audit_demo_report.json
    Failure Indicators: any number missing or altered
    Evidence: .omo/evidence/task-9-table3-numbers.txt

  Scenario: Claim boundary preserved (validated_kbs_workflow=false)
    Tool: Bash (grep)
    Preconditions: Section 6 written
    Steps:
      1. grep Section 6 text for "validated_kbs_workflow" or "validated\\_kbs\\_workflow" or "not a validated" or "methodological analogy"
      2. Assert: at least one boundary marker present
      3. grep Section 6 for forbidden phrases: "production deployment", "downstream PRM training", "GSM8K replay", "causal effect"
      4. Assert: zero forbidden matches
    Expected Result: boundary marker present; no forbidden wording
    Failure Indicators: boundary missing or forbidden wording present (G2 violation)
    Evidence: .omo/evidence/task-9-claim-boundary.txt

  Scenario: Section adds ~3 pages
    Tool: Bash (latexmk + pdfinfo or log)
    Preconditions: manuscript.tex edited
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
      3. Read manuscript.log for "Output written on manuscript.pdf (N pages"
      4. Assert: N >= 15 (was 12; +3 pages from Section 6 and other Wave 2/3 edits)
    Expected Result: page count in [15, 20]
    Failure Indicators: N < 15 (Section 6 too short) or N > 20 (over-expansion)
    Evidence: .omo/evidence/task-9-page-count.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(paper): add Section 6 KBS Audit Demonstration with fixed-budget scenario`
  - Files: `paper/kbs_submission/final_source/manuscript.tex`
  - Pre-commit: `latexmk -pdf manuscript.tex` in final_source/

- [ ] 10. Consolidate Limitations Section (Move Defensive Language Here)

  **What to do**:
  - Edit `paper/kbs_submission/final_source/manuscript.tex` — restructure the current Section 5 "KBS Implications and Limitations" (lines 167-171):
    - Rename to "Limitations and Claim Boundary" (or keep "KBS Implications and Limitations" but reorganize).
    - Consolidate ALL defensive/boundary language moved out of abstract (Task 5), intro (Task 5), and related work (Task 6) into this section.
    - Structure as: (a) KBS Implications (methodological analogy — keep brief, ~1 paragraph); (b) Limitations (the 5 existing limitations at lines 171 — synthetic benchmark, PRM800K route, graph construction, CIU signal, causal claims); (c) Claim Boundary (explicit list of what is NOT claimed: no downstream PRM training, no GSM8K/HotpotQA replay, no production KBS deployment, no causal identification).
    - Ensure the section is ~1 page (currently ~0.5 page; expand to consolidate moved content).
  - Verify no defensive language remains in abstract, intro, or related work (it should all be here now).

  **Must NOT do**:
  - Do NOT remove the claim boundary (G2 — must preserve, just consolidate here)
  - Do NOT weaken the limitations (G2 — all 5 limitations must remain)
  - Do NOT add new limitations not supported by evidence (G8)
  - Do NOT pad (G7 — consolidation, not expansion for its own sake)

  **Recommended Agent Profile**:
  - **Category**: `quick` — reorganization and consolidation of existing text; mechanical once the moved content is identified.
  - **Skills**: [] — LaTeX text reorganization.
  - **Skills Evaluated but Omitted**: `python-debug` (no code), `safe-edit` (reorganization, not minimal edit — but still quick).

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 11 — different sections)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 12 (recompile)
  - **Blocked By**: Task 5 (abstract/intro reframe must be done so defensive language is identified for moving)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/final_source/manuscript.tex:167-171` — current Section 5; restructure this.
  - Tasks 5, 6 outputs — the defensive language moved out of abstract/intro/related work; collect it here.
  - `paper/claim_registry.md` — governs boundary wording.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — PDF text checks.
  - `tests/test_claim_boundaries.py` (if exists).

  **External References**: None.

  **WHY Each Reference Matters**:
  - `manuscript.tex:167-171`: The section to restructure.
  - Tasks 5/6 outputs: Source of the defensive language to consolidate.
  - `claim_registry.md`: Wording gate for the boundary list.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Limitations section contains claim boundary list
    Tool: Bash (grep)
    Preconditions: Section 5 restructured
    Steps:
      1. Extract Section 5 text
      2. Assert: contains "downstream PRM training" (as a NOT-claimed item)
      3. Assert: contains "GSM8K" or "HotpotQA" (as NOT-claimed replay)
      4. Assert: contains "production KBS deployment" or "production deployment" (as NOT-claimed)
      5. Assert: contains "causal identification" or "causal effect" (as NOT-claimed)
    Expected Result: all four boundary items present in Limitations
    Failure Indicators: any boundary item missing (was it lost in consolidation?)
    Evidence: .omo/evidence/task-10-boundary-list.txt

  Scenario: All 5 existing limitations retained
    Tool: Bash (grep)
    Preconditions: Section 5 restructured
    Steps:
      1. Extract Section 5 text
      2. Assert: contains "synthetic benchmark" (limitation 1)
      3. Assert: contains "PRM800K route" or "PRM800K-like" (limitation 2)
      4. Assert: contains "graph construction" or "temporal and topical" (limitation 3)
      5. Assert: contains "binary-correctness CIU" or "trace-level coarse" (limitation 4)
      6. Assert: contains "Rubin" or "Pearl" or "causal" (limitation 5)
    Expected Result: all 5 limitations present
    Failure Indicators: any limitation missing
    Evidence: .omo/evidence/task-10-limitations-retained.txt

  Scenario: Manuscript compiles
    Tool: Bash (latexmk)
    Preconditions: manuscript.tex edited
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
      3. Assert: exit code 0
    Expected Result: compilation succeeds
    Failure Indicators: LaTeX error
    Evidence: .omo/evidence/task-10-compile.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `refactor(paper): consolidate defensive language into Limitations and Claim Boundary section`
  - Files: `paper/kbs_submission/final_source/manuscript.tex`
  - Pre-commit: `latexmk -pdf manuscript.tex` in final_source/

- [ ] 11. Expand Evaluation Section (Add Error Analysis, New Baselines)

  **What to do**:
  - Edit `paper/kbs_submission/final_source/manuscript.tex` Section 4 "Evaluation" (lines 104-165):
    - Add a new subsection "4.4 PRM800K Error Case Analysis" (~0.5-1 page) summarizing findings from Task 4:
      - Stratified summary: trace characteristics where QP underperforms (redundancy density, trace length).
      - Variant comparison: mean characteristics of QP-wins vs Ridge-wins vs w_struct-wins groups.
      - 1-2 case study examples (brief, with step-level weight patterns).
      - Concrete finding: "QP underperforms on traces with [characteristic]; Ridge is robust because [reason]."
    - Update Table 1 (synthetic ranking) to add the simple_average baseline row (from Task 1).
    - Update Table 2 (PRM800K) — already done in Task 7, but verify simple_average row is consistent.
    - Add a brief paragraph interpreting the simple_average baseline position (between raw CIU and SC-FMA variants, confirming that structural calibration adds value beyond simple averaging).

  **Must NOT do**:
  - Do NOT change the SC-FMA method (G3 — if error analysis reveals weakness, explain, don't fix)
  - Do NOT fabricate findings (G8 — all from Task 4 artifact)
  - Do NOT upgrade claims (G2 — error analysis is diagnostic, not validation)
  - Do NOT exceed ~1 page of new content (G7 — substantive, not padding)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires synthesizing error analysis findings into manuscript prose and interpreting baseline positioning. Judgment-heavy.
  - **Skills**: [] — LaTeX prose + table editing.
  - **Skills Evaluated but Omitted**: `python-debug` (no code), `safe-edit` (substantial additions).

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 10 — different subsections)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 12 (recompile)
  - **Blocked By**: Task 1 (simple_average results for Table 1 row), Task 4 (error analysis findings for 4.4), Task 7 (Table 2 consistency)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/final_source/manuscript.tex:104-165` — current Section 4; add 4.4 and update Tables 1, 2.
  - `outputs/real_task_v3_6_prm800k_hash/error_case_analysis.md` (from Task 4) — findings to summarize.
  - `outputs/baselines/simple_average_results.json` (from Task 1) — simple_average row for Table 1.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — PDF text and table checks.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `manuscript.tex:104-165`: The section to expand; existing structure is the scaffold.
  - `error_case_analysis.md`: Sole source of findings for subsection 4.4.
  - `simple_average_results.json`: Sole source of numbers for Table 1 row.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Subsection 4.4 present with concrete finding
    Tool: Bash (grep)
    Preconditions: Section 4 edited
    Steps:
      1. grep manuscript.tex for "Error Case Analysis" or "error case"
      2. Assert: match found
      3. Extract subsection 4.4 text
      4. Assert: contains at least one concrete statement matching "QP underperform" or "Ridge robust" or "redundancy"
    Expected Result: subsection 4.4 with specific finding
    Failure Indicators: subsection missing or vague
    Evidence: .omo/evidence/task-11-subsection-44.txt

  Scenario: simple_average row in Table 1
    Tool: Bash (grep)
    Preconditions: Table 1 edited
    Steps:
      1. grep manuscript.tex Table 1 region for "Simple Average" or "simple_average" or "Avg (CIU"
      2. Assert: match found
    Expected Result: simple_average row in Table 1
    Failure Indicators: row missing
    Evidence: .omo/evidence/task-11-simple-average-table1.txt

  Scenario: Table 1 simple_average number matches artifact
    Tool: Bash (python)
    Preconditions: Table 1 edited
    Steps:
      1. Load outputs/baselines/simple_average_results.json; extract synthetic_metrics.spearman_rho
      2. grep manuscript.tex Table 1 for that value
      3. Assert: value present
    Expected Result: simple_average Spearman in Table 1 matches artifact
    Failure Indicators: value missing or altered
    Evidence: .omo/evidence/task-11-table1-number-match.txt

  Scenario: Manuscript compiles
    Tool: Bash (latexmk)
    Preconditions: manuscript.tex edited
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
      3. Assert: exit code 0
    Expected Result: compilation succeeds
    Failure Indicators: LaTeX error
    Evidence: .omo/evidence/task-11-compile.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(paper): add Evaluation subsection 4.4 error case analysis and simple_average baseline row`
  - Files: `paper/kbs_submission/final_source/manuscript.tex`
  - Pre-commit: `latexmk -pdf manuscript.tex` in final_source/

- [ ] 12. Recompile Manuscript PDF and Verify 15-20 Pages

  **What to do**:
  - After all manuscript.tex edits (Tasks 5, 6, 7, 9, 10, 11) and references.bib edits (Task 2) are complete:
    - cd `paper/kbs_submission/final_source`
    - Run full compile cycle: `latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex` (latexmk handles multiple passes + bibtex automatically)
    - Verify exit code 0
    - Read `manuscript.log`; extract page count from "Output written on manuscript.pdf (N pages"
    - Assert N in [15, 20]
    - Copy compiled `manuscript.pdf` to `paper/kbs_submission/final_package/manuscript.pdf`
  - If page count < 15: identify which section is under-budget and flag for content addition (do NOT pad — G7).
  - If page count > 20: identify which section is over-budget and flag for trimming.
  - Run `bibtex manuscript` explicitly and check `manuscript.blg` for zero warnings.
  - Generate fresh PNG contact sheets for visual QA (optional, if rendering tool available).

  **Must NOT do**:
  - Do NOT pad content to reach page count (G7)
  - Do NOT remove substantive content to fit page limit (G7)
  - Do NOT ignore compilation warnings (must be zero)
  - Do NOT skip the bibtex check

  **Recommended Agent Profile**:
  - **Category**: `quick` — mechanical compilation and verification; no judgment beyond page-count interpretation.
  - **Skills**: [`python-debug`] — for parsing log files and page-count extraction programmatically.
  - **Skills Evaluated but Omitted**: `repo-map` (target known), `safe-edit` (no source edits).

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on all manuscript edits)
  - **Parallel Group**: Wave 4 (first task)
  - **Blocks**: Tasks 13, 14, 15 (need compiled PDF)
  - **Blocked By**: Tasks 5, 6, 7, 9, 10, 11 (all manuscript edits), Task 2 (bibliography)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/final_source/manuscript.tex` — the source to compile (post all edits).
  - `paper/kbs_submission/final_source/manuscript.log` — log file to parse for page count and warnings.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — page-range gate (min=12 default; will update to min=15 in Task 15 or here).

  **External References**: None.

  **WHY Each Reference Matters**:
  - `manuscript.tex`: The source; compilation is the gate.
  - `manuscript.log`: Page count and warning source of truth.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Manuscript compiles successfully
    Tool: Bash (latexmk)
    Preconditions: all manuscript.tex and references.bib edits complete
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
      3. Assert: exit code 0
      4. Assert: manuscript.pdf exists and is non-empty
    Expected Result: compilation succeeds; PDF produced
    Failure Indicators: non-zero exit, missing PDF, LaTeX errors in log
    Evidence: .omo/evidence/task-12-compile.txt

  Scenario: Page count in 15-20 range
    Tool: Bash (grep)
    Preconditions: manuscript.pdf compiled
    Steps:
      1. grep manuscript.log for "Output written on manuscript.pdf"
      2. Extract page count N from match
      3. Assert: 15 <= N <= 20
    Expected Result: N in [15, 20]
    Failure Indicators: N < 15 (under-budget) or N > 20 (over-budget)
    Evidence: .omo/evidence/task-12-page-count.txt

  Scenario: Zero bibtex warnings
    Tool: Bash (bibtex/grep)
    Preconditions: manuscript compiled
    Steps:
      1. cd paper/kbs_submission/final_source
      2. bibtex manuscript
      3. grep manuscript.blg for "warning" or "error"
      4. Assert: zero matches
    Expected Result: clean bibtex log
    Failure Indicators: any warning or error
    Evidence: .omo/evidence/task-12-bibtex-clean.txt

  Scenario: PDF copied to final_package
    Tool: Bash (file check)
    Preconditions: manuscript.pdf compiled
    Steps:
      1. Copy paper/kbs_submission/final_source/manuscript.pdf to paper/kbs_submission/final_package/manuscript.pdf
      2. Assert: final_package/manuscript.pdf exists
      3. Assert: file sizes match (source == package)
    Expected Result: PDF deployed to final_package
    Failure Indicators: copy failed, size mismatch
    Evidence: .omo/evidence/task-12-pdf-deployed.txt
  ```

  **Commit**: YES (groups with Wave 4)
  - Message: `chore(paper): recompile manuscript.pdf (15-20 pages) and deploy to final_package`
  - Files: `paper/kbs_submission/final_source/manuscript.pdf`, `paper/kbs_submission/final_package/manuscript.pdf`
  - Pre-commit: none (binary PDF)

- [ ] 13. Update Supplementary Material (Reflect Moved Content)

  **What to do**:
  - Edit `paper/kbs_submission/final_source/supplementary.tex`:
    - If any content was moved FROM supplementary TO main text (per Wave 2/3 expansions), remove the duplicate from supplementary and add a note: "This content is now in the main manuscript, Section X."
    - Conversely, if any content was moved FROM main text TO supplementary (unlikely given expansion, but possible for proofs), add it to supplementary.
    - Verify supplementary still compiles standalone: `latexmk -pdf supplementary.tex`.
    - Update supplementary abstract (line 53) if the scope changed.
  - Regenerate `paper/kbs_submission/final_package/supplementary.docx` from the updated supplementary.tex (if conversion tool available; otherwise note in manifest that docx needs regeneration).

  **Must NOT do**:
  - Do NOT duplicate content in both main and supplementary (G7 — no bloat)
  - Do NOT remove supplementary content without noting where it moved (G8 — provenance)
  - Do NOT change supplementary evidence boundary (G2)

  **Recommended Agent Profile**:
  - **Category**: `quick` — supplementary reorganization; mechanical once moved content is identified.
  - **Skills**: [] — LaTeX editing.
  - **Skills Evaluated but Omitted**: `python-debug` (no code).

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 14 — different files)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 15 (final verification needs both main and supplementary updated)
  - **Blocked By**: Task 12 (main manuscript must be finalized to know what moved)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/final_source/supplementary.tex` (439 lines) — the file to edit.
  - `paper/kbs_submission/final_source/manuscript.tex` (post-edits) — to identify what content moved.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — supplementary.docx structure checks.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `supplementary.tex`: The file to update.
  - `manuscript.tex`: Shows what content is now in main text (to remove duplicate from supplementary).

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Supplementary compiles standalone
    Tool: Bash (latexmk)
    Preconditions: supplementary.tex edited
    Steps:
      1. cd paper/kbs_submission/final_source
      2. latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary.tex
      3. Assert: exit code 0
      4. Assert: supplementary.pdf exists
    Expected Result: supplementary compiles successfully
    Failure Indicators: LaTeX error, missing PDF
    Evidence: .omo/evidence/task-13-supplementary-compile.txt

  Scenario: No content duplicated in main and supplementary
    Tool: Bash (grep/python)
    Preconditions: both manuscript.tex and supplementary.tex finalized
    Steps:
      1. Extract section headings and key paragraphs from both files
      2. Compute overlap (e.g., identical sentences > 50 words)
      3. Assert: no significant duplication (allow small overlaps like notation tables)
    Expected Result: minimal duplication
    Failure Indicators: large duplicated passages
    Evidence: .omo/evidence/task-13-no-duplication.txt
  ```

  **Commit**: YES (groups with Wave 4)
  - Message: `chore(paper): update supplementary to reflect content moved to main manuscript`
  - Files: `paper/kbs_submission/final_source/supplementary.tex`, `paper/kbs_submission/final_package/supplementary.docx` (if regenerated)
  - Pre-commit: `latexmk -pdf supplementary.tex` in final_source/

- [ ] 14. Update Cover Letter, Highlights, Manifest, Format Checklist, Submission Lock Audit

  **What to do**:
  - Update all package documents to reflect the expanded manuscript and new KBS audit demonstration:
    - **`paper/kbs_submission/cover_letter.md`**: Reframe to contribution-led (mirror Task 5 abstract reframe). Mention the new KBS audit demonstration section. Preserve "moderate/preliminary" boundary language. Update any page-count references.
    - **`paper/kbs_submission/final_submission_manifest.md`**: Update manuscript page count (15-20). Add mention of new Section 6 (KBS Audit Demonstration) and `outputs/kbs_audit_demo/` artifact. Update claim boundary section to reference M_KBS_AUDIT_DEMONSTRATION.
    - **`paper/kbs_submission/format_checklist.md`**: Update page-count gate from "5 pages" to "15-20 pages". Update verifier command to use `--min-manuscript-pages 15 --max-manuscript-pages 20`. Add checklist item for KBS audit demo artifact.
    - **`paper/submission_lock_audit.md`**: Update audit date. Add KBS audit demonstration to allowed claims. Update page count. Reaffirm PRM800K stratified gate remains "moderate".
    - **`paper/claim_registry.md`**: Verify M_KBS_AUDIT_DEMONSTRATION (Task 3) is consistent with the new Section 6 wording. No status changes to existing claims.
  - If DOCX conversion tools available (LibreOffice/soffice), regenerate `cover_letter.docx`, `Highlights.docx`, `supplementary.docx` from updated sources. If not, note in manifest that DOCX needs manual regeneration.

  **Must NOT do**:
  - Do NOT change claim statuses (G2)
  - Do NOT remove boundary language from cover letter (G2 — "moderate/preliminary" must stay)
  - Do NOT claim production KBS deployment in any document (G2)
  - Do NOT fabricate page counts (G8 — must match actual compiled PDF)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — requires consistent updates across 5 documents with claim-boundary sensitivity. Judgment-heavy.
  - **Skills**: [] — markdown/text editing.
  - **Skills Evaluated but Omitted**: `python-debug` (no code), `safe-edit` (multiple files, substantial).

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 13 — different files)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 15 (final verification needs all docs updated)
  - **Blocked By**: Task 2 (bibliography), Task 3 (claim), Task 12 (compiled PDF with final page count)

  **References**:

  **Pattern References**:
  - `paper/kbs_submission/cover_letter.md` (25 lines) — current cover letter; reframe.
  - `paper/kbs_submission/final_submission_manifest.md` (49 lines) — current manifest; update.
  - `paper/kbs_submission/format_checklist.md` (25 lines) — current checklist; update page gate.
  - `paper/submission_lock_audit.md` (107 lines) — current audit; update.
  - `paper/claim_registry.md` (46 lines) — verify Task 3 entry.

  **API/Type References**: None.

  **Test References**:
  - `tests/test_kbs_submission_package_verifier.py` — verifies package structure, PDF text, author metadata.

  **External References**: None.

  **WHY Each Reference Matters**:
  - Each document: The exact file to update; existing structure is the scaffold.
  - `claim_registry.md`: Wording gate for all documents.
  - Verifier tests: Regression gate.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Cover letter is contribution-led
    Tool: Bash (grep)
    Preconditions: cover_letter.md updated
    Steps:
      1. Read cover_letter.md
      2. Assert: opens with positive contribution (not "We are pleased to submit... does not claim")
      3. Assert: mentions KBS audit demonstration
      4. Assert: contains "moderate" or "preliminary" (boundary preserved)
    Expected Result: contribution-led cover letter with boundary
    Failure Indicators: still defense-led, or boundary removed
    Evidence: .omo/evidence/task-14-cover-letter.txt

  Scenario: Manifest page count matches PDF
    Tool: Bash (grep/python)
    Preconditions: manifest updated, manuscript.pdf compiled
    Steps:
      1. Extract page count from manifest (grep for "pages")
      2. Extract actual page count from manuscript.log
      3. Assert: manifest page count == actual page count
    Expected Result: manifest and PDF agree
    Failure Indicators: mismatch
    Evidence: .omo/evidence/task-14-manifest-page-count.txt

  Scenario: Format checklist page gate updated
    Tool: Bash (grep)
    Preconditions: format_checklist.md updated
    Steps:
      1. grep format_checklist.md for "15" and "20" (the new gate)
      2. Assert: both present in page-count context
      3. grep for "--min-manuscript-pages 15" or "max-manuscript-pages 20"
      4. Assert: updated verifier command present
    Expected Result: page gate updated to 15-20
    Failure Indicators: still references old "5 pages" or "12 pages" gate
    Evidence: .omo/evidence/task-14-format-checklist.txt

  Scenario: Submission lock audit updated
    Tool: Bash (grep)
    Preconditions: submission_lock_audit.md updated
    Steps:
      1. grep submission_lock_audit.md for current date or "KBS Audit Demonstration"
      2. Assert: at least one match (audit refreshed)
    Expected Result: audit reflects new section and date
    Failure Indicators: stale audit (no mention of KBS audit demo)
    Evidence: .omo/evidence/task-14-lock-audit.txt

  Scenario: No forbidden wording in any package document
    Tool: Bash (grep)
    Preconditions: all documents updated
    Steps:
      1. grep cover_letter.md, manifest, format_checklist, lock_audit for: "production deployment validated", "downstream PRM training validated", "GSM8K replay validated", "causal effect proven"
      2. Assert: zero matches (these are forbidden as positive claims)
    Expected Result: no forbidden positive claims
    Failure Indicators: any forbidden match
    Evidence: .omo/evidence/task-14-no-forbidden-wording.txt
  ```

  **Commit**: YES (groups with Wave 4)
  - Message: `docs(paper): update cover letter, manifest, checklist, lock audit for expanded manuscript`
  - Files: `paper/kbs_submission/cover_letter.md`, `paper/kbs_submission/final_submission_manifest.md`, `paper/kbs_submission/format_checklist.md`, `paper/submission_lock_audit.md`, `paper/claim_registry.md` (verification only)
  - Pre-commit: none (markdown)

- [ ] 15. Final Package Verification and Test Suite Run

  **What to do**:
  - Run the complete verification suite:
    - `pytest -q` (full test suite) — assert 0 failures.
    - `python scripts/verify_kbs_submission_package.py --package-dir paper/kbs_submission/final_package --require-author-metadata --require-pdf-text --min-manuscript-pages 15 --max-manuscript-pages 20` — assert exit 0.
    - `pytest -q tests/test_kbs_submission_package_verifier.py` — assert pass.
    - `pytest -q tests/test_simple_average_baseline.py tests/test_kbs_audit_demo.py tests/test_prm800k_error_analysis.py` — assert all new tests pass.
    - Verify `paper/kbs_submission/final_package/` contains exactly 5 files: `cover_letter.docx`, `Highlights.docx`, `manuscript.pdf`, `supplementary.docx`, `latex_source.zip`.
    - Regenerate `latex_source.zip` from `paper/kbs_submission/final_source/` (excluding build artifacts: *.aux, *.bbl, *.blg, *.fdb_latexmk, *.fls, *.log, *.out, *.abs, *.synctex.gz).
    - Verify no forbidden wording in the entire package (grep manuscript.tex, supplementary.tex, cover_letter.md, manifest for forbidden phrases).
  - Produce a final verification report at `.omo/evidence/final-verification-report.md` summarizing all checks.

  **Must NOT do**:
  - Do NOT skip any verification step
  - Do NOT ignore test failures (must fix or document before marking complete)
  - Do NOT include build artifacts in latex_source.zip

  **Recommended Agent Profile**:
  - **Category**: `quick` — running verification commands and collecting results; mechanical.
  - **Skills**: [`python-debug`] — for running pytest, verifier script, and parsing results.
  - **Skills Evaluated but Omitted**: `repo-map` (targets known).

  **Parallelization**:
  - **Can Run In Parallel**: NO (final gate; depends on all prior tasks)
  - **Parallel Group**: Wave 4 (last task)
  - **Blocks**: F1-F4 (Final Verification Wave)
  - **Blocked By**: Tasks 12, 13, 14 (all package artifacts finalized)

  **References**:

  **Pattern References**:
  - `scripts/verify_kbs_submission_package.py` — the verifier script; run with updated page gates.
  - `tests/test_kbs_submission_package_verifier.py` — verifier tests.
  - `paper/kbs_submission/final_package/` — the package directory to verify.

  **API/Type References**: None.

  **Test References**:
  - All test files created in Waves 1-2.
  - Existing test suite.

  **External References**: None.

  **WHY Each Reference Matters**:
  - `verify_kbs_submission_package.py`: The canonical package verifier; its pass is the gate.
  - Test suite: Regression gate for all existing functionality.
  - `final_package/`: The deliverable; must contain exactly 5 files.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Full test suite passes
    Tool: Bash (pytest)
    Preconditions: all tasks complete
    Steps:
      1. Run: pytest -q
      2. Assert: exit code 0
      3. Assert: "0 failed" in output
    Expected Result: all tests pass
    Failure Indicators: any test fails
    Evidence: .omo/evidence/task-15-full-test-suite.txt

  Scenario: Package verifier passes with updated page gate
    Tool: Bash (python)
    Preconditions: final_package/ finalized
    Steps:
      1. Run: python scripts/verify_kbs_submission_package.py --package-dir paper/kbs_submission/final_package --require-author-metadata --require-pdf-text --min-manuscript-pages 15 --max-manuscript-pages 20
      2. Assert: exit code 0
    Expected Result: verifier passes
    Failure Indicators: non-zero exit (page count, missing files, forbidden wording, etc.)
    Evidence: .omo/evidence/task-15-verifier.txt

  Scenario: New tests pass
    Tool: Bash (pytest)
    Preconditions: new test files created
    Steps:
      1. Run: pytest -q tests/test_simple_average_baseline.py tests/test_kbs_audit_demo.py tests/test_prm800k_error_analysis.py
      2. Assert: exit code 0, all pass
    Expected Result: all new tests pass
    Failure Indicators: any new test fails
    Evidence: .omo/evidence/task-15-new-tests.txt

  Scenario: final_package contains exactly 5 files
    Tool: Bash (file listing)
    Preconditions: package finalized
    Steps:
      1. List files in paper/kbs_submission/final_package/
      2. Assert: exactly 5 files: cover_letter.docx, Highlights.docx, manuscript.pdf, supplementary.docx, latex_source.zip
    Expected Result: exactly 5 required files
    Failure Indicators: missing file or extra file
    Evidence: .omo/evidence/task-15-package-contents.txt

  Scenario: latex_source.zip excludes build artifacts
    Tool: Bash (unzip -l)
    Preconditions: latex_source.zip regenerated
    Steps:
      1. unzip -l paper/kbs_submission/final_package/latex_source.zip
      2. Assert: no .aux, .bbl, .blg, .log, .out, .abs, .fdb_latexmk, .fls, .synctex.gz files
      3. Assert: contains manuscript.tex, supplementary.tex, references.bib, cas-common.sty, cas-sc.cls, cas-model2-names.bst, figures/*.png
    Expected Result: clean source bundle
    Failure Indicators: build artifacts present, or required source files missing
    Evidence: .omo/evidence/task-15-latex-source-zip.txt

  Scenario: No forbidden wording anywhere in package
    Tool: Bash (grep)
    Preconditions: all source files finalized
    Steps:
      1. grep -r "production deployment validated\|downstream PRM training validated\|GSM8K replay validated\|causal effect proven" paper/kbs_submission/final_source/ paper/kbs_submission/cover_letter.md paper/kbs_submission/final_submission_manifest.md
      2. Assert: zero matches
    Expected Result: no forbidden positive claims
    Failure Indicators: any match
    Evidence: .omo/evidence/task-15-no-forbidden-wording.txt

  Scenario: Final verification report produced
    Tool: Bash (file check)
    Preconditions: all checks run
    Steps:
      1. Assert: .omo/evidence/final-verification-report.md exists
      2. Assert: report contains pass/fail status for each check
    Expected Result: comprehensive verification report
    Failure Indicators: report missing or incomplete
    Evidence: .omo/evidence/final-verification-report.md
  ```

  **Commit**: YES (final commit)
  - Message: `test(paper): final package verification and test suite — KBS submission ready`
  - Files: `.omo/evidence/final-verification-report.md`, `paper/kbs_submission/final_package/latex_source.zip` (regenerated)
  - Pre-commit: all verification commands

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — oracle
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search manuscript source for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT

- [ ] F2. **Code Quality Review** — unspecified-high
  Run the build, lint, and test commands. Review all changed files for: type suppression, empty catches, debug logging, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names. Verify LaTeX compiles without warnings. Verify bibliography compiles without warnings.
  Output: Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT

- [ ] F3. **Real Manual QA** — unspecified-high
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (manuscript compiles with all sections, KBS use case script runs end-to-end, tests pass together). Test edge cases: missing evidence files, page count boundary, forbidden wording. Save to .omo/evidence/final-qa/.
  Output: Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT

- [ ] F4. **Scope Fidelity Check** — deep
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination. Verify claim boundary preserved (no forbidden wording anywhere). Flag unaccounted changes.
  Output: Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT

---

## Commit Strategy

- **Wave 1**: feat(baselines): add simple_average baseline; audit bibliography; register KBS audit claim — src/fma/baselines/simple_average.py, references.bib, paper/claim_registry.md
- **Wave 2**: refactor(paper): reframe abstract/intro, expand related work, fix PRM800K narrative; feat(kbs): build audit demo script — manuscript.tex, scripts/run_kbs_audit_demo.py
- **Wave 3**: feat(paper): add KBS Audit Demonstration section, consolidate limitations, expand evaluation — manuscript.tex, supplementary.tex
- **Wave 4**: chore(paper): recompile PDF, update supplementary, cover letter, manifest, verifier — manuscript.pdf, cover_letter.md, final_submission_manifest.md
- **Final**: test(paper): final package verification and test suite — .omo/evidence/

---

## Success Criteria

### Verification Commands
- Page count: latexmk then grep log for "Output written on manuscript.pdf (N pages" — expect N in 15-20
- Test suite: pytest -q — expect 0 failures
- Package verifier: python scripts/verify_kbs_submission_package.py --package-dir paper/kbs_submission/final_package --require-author-metadata --require-pdf-text --min-manuscript-pages 15 --max-manuscript-pages 20 — expect exit 0
- Bibliography: bibtex compile then check .blg for warnings — expect 0 warnings
- Claim registry: grep M_KBS_AUDIT_DEMONSTRATION paper/claim_registry.md — expect match
- Forbidden wording: grep manuscript.tex for forbidden phrases — expect no matches

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Page count in 15-20 range
- [ ] Claim boundary preserved
