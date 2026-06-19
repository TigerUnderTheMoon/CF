# Draft: SC-FMA Paper Fix Plan for KBS Submission

## Diagnosis Summary (from review)

### A. Writing / Structural Issues (fixable by editing manuscript.tex + supplementary.tex)

1. **5 pages is too short** for KBS regular article (target 12-20 pages). Content aggressively compressed; algorithm details, ablations, efficiency, stratum analysis all moved to supplementary.
2. **Missing standalone sections**: no experimental setup section, no discussion section, related work merged with boundary declarations.
3. **Defensive writing tone**: abstract and every section heavily qualified with "does not claim" language. Reads as author self-doubt.
4. **PRM800K narrative contradiction**: w_struct (input, not SC-FMA output) is the primary signal (0.611); SC-FMA Ridge only approximates it (0.604); SC-FMA QP degrades (0.442). Paper claims SC-FMA as innovation but data shows Ridge is just a soft proxy for w_struct.
5. **Theory-practice mismatch**: four theorems (convexity, monotonicity, variance reduction, bottleneck protection) over-formalize what is essentially weighted convex optimization. Monotonicity violated in 31.2% of redundant pairs by design.
6. **Related work too thin**: only 3 KBS-journal citations; missing core KB/ontology reasoning literature; many irrelevant NLP benchmark citations (GLUE, SuperGLUE, Dynabench, HELM).
7. **No clear "what does SC-FMA improve in practice" narrative**.

### B. Research / Evidence Gaps (require running experiments, not just writing)

1. **All 6 real-task validation routes failed** (GSM8K, HotpotQA). This is the single biggest blocker.
2. **No KBS system integration**: no case study in actual KG, rule engine, RAG pipeline, or ontology reasoner. "KBS Implications" section is purely analogical.
3. **Synthetic benchmark is the only strong positive result** (200 traces, proxy labels) — weak external validity.
4. **Missing natural baselines**: no comparison against "directly rank by w_struct" or "simple average of c and n".
5. **Countries KG pilot is fixture-level only**, marked `evidence_level=pilot`, `validated_kbs_workflow=false`.

### C. Format / Package Issues (mostly OK)

- CAS template, 5 pages within <=20 gate: PASS
- Author metadata, funding, declarations: PASS
- Reproducibility scripts, seeds: PASS
- DOCX visual rendering: BLOCKED locally (no LibreOffice)
- Claim registry and audit infrastructure: rigorous but contributes to defensive tone

## Critical Ambiguities (need user decision)

### Q1: Strategic path forward?

- **Path A — Pivot journal**: Reframe for Neurocomputing / Neural Networks / AI Open where KBS integration is not required. Lighter scope: writing + narrative restructure only. Real-task validation still recommended but not blocking.
- **Path B — Stay KBS, writing-only fix**: Accept current evidence boundary (all real-task routes failed). Expand paper to 15+ pages, restructure narrative, fix PRM800K contradiction, add KBS framing. High desk-reject risk remains.
- **Path C — Stay KBS, full research push**: Do the heavy work — get at least one real-task route passing, add a real KBS integration case study (RAG / KGQA / rule engine), then expand paper. Largest scope, longest timeline, best chance of acceptance.

### Q2: If Path C, which KBS integration direction?

- **C1 — RAG audit prioritization**: Apply SC-FMA to rank retrieval/reasoning steps in a RAG pipeline for human review prioritization.
- **C2 — KGQA path verification**: Apply SC-FMA to weight multi-hop reasoning paths in KG question answering.
- **C3 — Rule-chain review**: Apply SC-FMA to rule-engine inference chains to flag high-necessity bottleneck rules for curation.
- **C4 — Ontology reasoning**: Apply SC-FMA to ontology reasoning traces to identify critical axiom applications.

### Q3: Real-task validation scope?

- Run new v4 route with fresh non-overlapping data?
- Or accept v3.6 PRM800K + v3.8 frozen PRM as the only real-data evidence and explicitly bound claims?

## Open Questions

- Target page count for revised manuscript? (15? 18? 20?)
- Keep SC-FMA QP as headline variant or pivot headline to Ridge given real-data results?
- Keep current title or reframe?
- Should the plan include code modifications to src/fma/ or only paper text?

## Scope Boundaries (pending user confirmation)

- INCLUDE: manuscript.tex revision, supplementary.tex revision, references.bib expansion, cover_letter.md revision, claim_registry.md update if needed
- TBD: real-task experiments, KBS integration case study, code changes
- EXCLUDE: changing CAS template, changing funding/author metadata
