# Draft: SC-FMA Paper Fix Plan for KBS Submission

## Diagnosis Summary (confirmed from review)

### Writing/Structural Issues (fixable by editing manuscript)
- Paper is 5 pages — far below KBS regular article norm (12-20 pages)
- Missing sections: no standalone experimental setup, no discussion, abbreviated related work
- Defensive writing tone — abstract spends 40%+ on "does not claim"
- Heavy math formalism (4 theorems) vs. weak empirical results — mismatch
- Bibliography: only 3 KBS-journal refs, many arXiv preprints, some irrelevant NLP benchmark refs
- PRM800K narrative contradiction: SC-FMA QP (the "strongest" variant) degrades to 0.442 vs w_struct 0.611; Ridge just approximates w_struct

### Research/Evidence Gaps (require running experiments)
- All 6 real-task validation routes failed (GSM8K/HotpotQA)
- No actual KBS system integration — only "methodological analogy"
- No comparison with using w_struct directly as baseline
- Synthetic benchmark is only 200 traces / 1027 steps
- No case study showing SC-FMA improves a real knowledge-based system

### Scope Boundary Considerations
- AGENTS.md claim registry forbids upgrading failed routes without fresh preregistered validation
- v3.6 (PRM800K step-ranking) and v3.8 (frozen PRM baseline context) are the only allowed positive real-data claims
- Cannot overclaim; must preserve claim boundaries

## Open Strategic Questions (need user decision)

1. Target venue: stay with KBS, or pivot to more fitting journal (Neurocomputing, etc.)?
2. Scope: writing-only fix, or include new research experiments?
3. If research: which gaps to prioritize — real-task validation, KBS integration case study, or both?

## Research Findings
- Codebase infrastructure is strong (src/fma/, tests, scripts, configs)
- Claim registry and audit system are rigorous
- Reproducibility tooling (DVC, seeds, configs) is in place
- Countries KG pilot exists as fixture-level diagnostic only

## Test Strategy Decision
- N/A for paper writing tasks (no unit tests)
- QA Scenarios = compilation checks, page-count validation, claim-boundary audit, visual PDF render check
- For any new experiments: existing test infrastructure (pytest) applies

## Default Assumptions (will disclose in summary)
- If user picks "writing-only + stay KBS": plan covers manuscript expansion, narrative restructuring, bibliography cleanup, supplementary reorganization
- If user picks "include research": plan adds real-task validation tasks + KBS integration case study tasks
- All tasks respect existing claim boundaries (no overclaiming)
