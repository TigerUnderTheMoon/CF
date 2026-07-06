# Information Sciences Transfer Consistency Audit - Final Split

Date: 2026-07-04

Purpose: record the code/evidence-to-paper consistency check for the Information Sciences transfer package.

## Evidence Alignment

| Paper claim surface | Source artifact | Checked value | Status |
|---|---|---:|---|
| Process-annotation consistency | `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json` | 4,417 samples; 34,219 artifacts; `w_struct` Spearman 0.6113401179642559; raw local utility -0.07745914322519368 | aligned |
| Process-annotation SC-FMA variants | `outputs/scfma_variants_prm800k/scfma_variant_report.json` | Ridge 0.6040922426297788; QP 0.4423117458477998; Projection -0.13466999413309325 | aligned; Ridge is closest approximation |
| Frozen PRM reference context | archived v3.8 frozen PRM reference report | frozen PRM Spearman 0.2515662235547571; `w_struct - prm` CI [0.34499208448462026, 0.3745467544914783] | aligned; context only |
| Offline audit-record coverage | `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` and `.md` summary | `w_struct` top-1 hit 0.9169 and Coverage NDCG@25 0.9506; Ridge top-1 hit 0.9054 and Coverage NDCG@25 0.9460 | aligned; audit context only |
| Countries-KG representation study | archived graph-backend diagnostics and figure assets | typed ontology edges affect structural-priority allocation | aligned as representation-backend evidence |

## Code Surface Alignment

- Implemented modules used by the manuscript exist under `src/fma/`: `calibration`, `ciu`, `eval`, `graph`, `prm`, audit-allocation helpers, `real_task_pilot`, `utility`, and related helpers.
- Planned or non-operational modules remain absent: `src/fma/conditional`, `src/fma/matching`, and `src/fma/dr` do not exist. The manuscript must not describe conditional sampling, counterfactual matching, or doubly robust estimation as implemented evidence.
- The paper wording treats production deployment, online maintenance, and external transfer as outside the reported audit-record representation evidence.

## Scope

Allowed:

- SC-FMA as a knowledge-engineering representation for graph-aware audit records.
- Controlled synthetic annotation-consistency evidence where QP is strongest.
- Locked process-annotation evidence where `w_struct` is the primary real-data signal and Ridge is the closest SC-FMA approximation.
- Frozen PRM reference as in-distribution, overlap-limited context only.
- Offline process-annotation audit-record coverage as fixed-review-budget context only.
- Countries-KG representation-backend sensitivity as knowledge-graph diagnostic evidence.

Not allowed:

- Downstream PRM training gains.
- GSM8K/HotpotQA replay-pass evidence.
- Filtering superiority or task-success gains.
- Production knowledge-base workflow validation.
- Formal causal identification, Rubin-style causal-effect language, matched estimates, or DR-corrected estimates.

## Package Split Status

- Authoritative manuscript source: `paper/information_sciences_submission/final_source/manuscript.tex`.
- Expected compiled manuscript artifact: `paper/information_sciences_submission/final_package/manuscript.pdf`.
- Final upload boundary after cleanup: `cover_letter.docx`, `Highlights.docx`, `manuscript.pdf`, `supplementary.pdf`, and `latex_source.zip`.
- Reproducibility source bundle keeps `manuscript.tex`, `supplementary.tex`, `references.bib`, CAS files, and figures, while excluding local build artifacts.
