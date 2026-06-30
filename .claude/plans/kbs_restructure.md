# Restructure SC-FMA KBS manuscript into 5 sections + sequential citations

## Goal
Rewrite `paper/kbs_submission/final_source/manuscript.tex` so that:
1. The body is exactly **1. Introduction → 2. Related Work → 3. Methods → 4. Application → 5. Conclusions** (matching the three uploaded KBS reference papers; Siddharth & Luo 2024 uses this exact 5-part shape with Introduction→Background→Method→Application→Conclusions).
2. Citations begin in **Section 1** (Introduction), and are numbered **[1], [2], [3], …** in order of first appearance. Today the Introduction has zero `\cite{}` and the first citation (`sundararajan2017axiomatic`) becomes [1] in Related Work; the user wants citations to start in §1 and run sequentially.

Style references (all three are in `references.bib` and confirmed read):
- `siddharth2024retrieval` (KBS 2024) — 5-part structure; "Application" section uses scenarios (4.1 Overview, 4.2 Generalisable design knowledge, 4.3 Contextualised design knowledge) to demonstrate the method on real data.
- `dai2025llmkg` (KBS 2025) — Introduction → Related works → study/experiment sections → Conclusion; lists numbered "main findings" bullets in the intro.
- `chen2025kgquality` (KBS 2025) — Introduction → Related work → Methods → Results and discussion → Conclusion; intro lists numbered contributions.

## How natbib numbering works (verified)
`\usepackage[numbers,sort&compress]{natbib}` → each `\cite{key}` gets a number **in order of first textual appearance**; `sort&compress` only re-orders/compresses keys *within a single* `\cite{a,b,c}`. The `.bib` file order does **not** drive numbering. So to get [1],[2],… sequential from §1, I must place `\cite{}` calls in the exact desired order in the prose, starting in the Introduction. No change to `references.bib` is required (all 35 keys stay; the three KBS DOIs the test checks for stay present).

## Hard constraints (from `tests/test_claim_boundaries.py`, must keep passing)
- Keep these exact strings (they move but stay verbatim):
  - `trace-level coarse utility anchor`
  - `does not prove that each step has an independent outcome-grounded CIU`
  - `does not validate a deployed KBS workflow`
  - `fixture-level typed-edge construction only; no deployed workflow validation`
  - `SCU component contribution on a structural stress-test benchmark`
  - `\subsection{Real-Knowledge-Graph Graph Construction Pilot}` (section title locked by test line 96)
  - `gamma/delta and alpha/beta QP sensitivity grids`, `TF-IDF topical default (0.0515) did not outperform temporal-only edges (0.0596)`, `embedding backend (0.0615)`
- Must NOT contain forbidden phrases: `per-step counterfactual outcome differences`, `all interventions are structure-preserving`, and all FORBIDDEN_PATTERNS in `scripts/check_claim_boundaries.py` (e.g. "true causal effect", "external generalization", "deployed KBS validation"). All current prose already avoids these; I do not strengthen any claim.
- Keep every `% Claim boundary for tests:` comment verbatim.
- Do **not** upgrade any claim status; do not rewrite history; keep all numeric values identical.

## Content mapping (current → new)
| Current | New home |
|---|---|
| §1 Introduction | **§1 Introduction** (enriched with citations [1]–[6]) |
| §2 Related Work (4 subsections) | **§2 Related Work** (same 4 subsections; citations continue) |
| §3 Methodology (6 subsections) | **§3 Methods** (rename; keep all 6 subsections, theorem, tables, figures) |
| §4 Experimental Setup (2 subsec) + §5 Results (4 subsec) + §6 Discussion (6 subsec) + §7 Conclusion | **§4 Application** + **§5 Conclusions** (see below) |

### §4 Application subsection plan (Siddharth-style: method applied to real/controlled scenarios)
- 4.1 Experimental Setup (current §4.1 Data and Baselines + §4.2 Evidence Routes and Claim Accounting; keep `tab:evidence-routes`)
- 4.2 Synthetic Step-Importance Ranking (current §5.1; keep `tab:ranking-results`, `tab:scu-component-contribution`, `tab:scu-stress-test`, `tab:graph-construction-analysis`; keep label `sec:synthetic-ranking`)
- 4.3 Real-Knowledge-Graph Graph Construction Pilot (current §5.2; **title locked by test**; keep label `sec:kg-pilot`, `tab:kg-pilot`, claim-boundary comment)
- 4.4 PRM800K Evidence and Audit Readout (current §5.3; keep `tab:prm800k-audit`)
- 4.5 PRM800K Error Case Analysis (current §5.4 incl. 4 subsubsections; keep label `sec:prm800k-error`)
- 4.6 Audit Interpretation and Boundaries (current §6 Discussion): merge the analysis subsections (KBS Implications, Audit Interpretation + oracle `tab:oracle-auto-validation` + `tab:compact-audit-card-case`, Variant-Selection Policy `tab:variant-policy`, Practical Implications) and the boundary subsections (Limitations and Claim Boundary, Scope and Applicability). Keep labels `sec:discussion`, `sec:why-calibration`, `sec:scope-applicability`, `sec:audit-kbs-analogy` so all `\ref{}` resolve. Keep the "Excluded claims" itemize and all boundary sentences verbatim.

### §5 Conclusions
- Current §7 Conclusion prose, lightly adapted to the 5-part frame (no claim strengthening). Keep the three-paragraph structure and exact numbers (0.483→0.597, ρ=0.611, 0.604, 0.946 vs 0.951, 0.235→0.699, 0.353→0.978).

## Citation seeding in §1 Introduction (desired [1]..[n] order)
First appearances in Introduction, in this order:
1. `lightman2023verify` — PRM800K / process supervision (motivates step-level review) → **[1]**
2. `uesato2022solving` — process feedback reduces errors → **[2]**
3. `lewis2020rag` — retrieval-augmented generation exposes inspectable evidence → **[3]**
4. `edge2024graphrag` — GraphRAG / structured inspectable evidence → **[4]**
5. `sundararajan2017axiomatic` — attribution foundation → **[5]**
6. `buchanan1984mycin` — auditable KBS tradition (MYCIN) → **[6]**

Related Work then introduces the remaining keys in their existing narrative order; each new first-appearance gets the next number. The existing RW prose already orders keys sensibly, so the numbered bibliography will read continuously [1]→[35].

## Edits
1. Rewrite **§1 Introduction** body to weave the six seeded citations into the motivation/landscape paragraph (keep the framework figure `fig:overall-framework`, contributions list, and `Section~\ref{sec:discussion}` pointer).
2. Change `\section{Related Work}` stays.
3. Rename `\section{Methodology}` → `\section{Methods}`.
4. Replace the `\section{Experimental Setup}` / `\section{Results}` / `\section{Discussion}` trio with a single `\section{Application}` and re-parent their subsections per the plan above (preserve labels, tables, figures, claim-boundary comments).
5. Rename `\section{Conclusion}` → `\section{Conclusions}`.
6. Leave appendices A/B, front matter, and `references.bib` untouched.
7. Rebuild PDF with `latexmk` and re-run `scripts/check_claim_boundaries.py` + the manuscript-relevant pytest subset.

## Verification
- `cd paper/kbs_submission/final_source && latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex` → builds, no undefined refs/citations.
- `python scripts/check_claim_boundaries.py` → exit 0.
- `python -m pytest tests/test_claim_boundaries.py -q` → green (esp. `test_kbs_source_preserves_main_text_diagnostic_context`, `test_kbs_source_contains_ciu_granularity_and_adapter_contract`, `test_kbs_source_explicitly_bounds_hyperparameter_and_graph_ablation_claims`).
- Inspect `manuscript.bbl` to confirm numbered bibliography starts at the Introduction-seeded keys and is continuous.
