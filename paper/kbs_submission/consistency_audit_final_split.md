# KBS Submission Consistency Audit - Final Split

Date: 2026-06-16

Purpose: record the final code/evidence-to-paper consistency check for the KBS split submission package.

## Evidence Alignment

| Paper claim surface | Source artifact | Checked value | Status |
|---|---|---:|---|
| PRM800K real step-label ranking | `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json` | 4,417 samples; 34,219 steps; `w_struct` Spearman 0.6113401179642559; raw local utility -0.07745914322519368 | aligned |
| PRM800K SC-FMA variants | `outputs/scfma_variants_prm800k/scfma_variant_report.json` | Ridge 0.6040922426297788; QP 0.4423117458477998; Projection -0.13466999413309325 | aligned; Ridge is closest approximation |
| Frozen PRM baseline context | `outputs/real_task_v3_8_prm_locked_scoring/locked_prm_baseline_comparison_report.json` | frozen PRM Spearman 0.2515662235547571; `w_struct - prm` CI [0.34499208448462026, 0.3745467544914783] | aligned; context only |
| Offline audit prioritization | `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json` and `.md` summary | `w_struct` top-1 hit 0.9169 and NDCG@25 0.9506; Ridge top-1 hit 0.9054 and NDCG@25 0.9460 | aligned; audit context only |
| KBS ontology-aware edge pilot | `outputs/kbs_ontology_edge_pilot/diagnostic_report.json`; optional `kg_pilot_report.json` | diagnostic artifact has `evidence_level=diagnostic` and `validated_kbs_workflow=false`; KG pilot has `evidence_level=pilot` and `validated_kbs_workflow=false` | aligned as pilot/diagnostic only |

## Code Surface Alignment

- Implemented modules used by the manuscript exist under `src/fma/`: `calibration`, `ciu`, `eval`, `graph`, `prm`, `ranking`, `real_task_pilot`, `utility`, and related helpers.
- Planned or non-operational modules remain absent: `src/fma/conditional`, `src/fma/matching`, and `src/fma/dr` do not exist. The manuscript must not describe conditional sampling, counterfactual matching, or doubly robust estimation as implemented evidence.
- The paper wording now treats streaming, online, edge, and KBS deployment statements as future integration directions or computational compatibility claims, not as deployment validation.

## Claim Boundary

Allowed:

- Methodological SC-FMA contribution for auditable verification-step weighting.
- Controlled synthetic proxy-label ranking evidence where QP is strongest.
- PRM800K locked step-label ranking evidence where `w_struct` is the primary real-data signal and Ridge is the closest SC-FMA approximation.
- Frozen PRM comparison as in-distribution, overlap-limited baseline context only.
- Offline PRM800K audit prioritization as fixed-review-budget context only.
- Ontology/KG edge construction as fixture-level diagnostic or pilot evidence only.

Not allowed:

- Downstream PRM training gains.
- GSM8K/HotpotQA replay-pass evidence.
- Filtering superiority or task-success gains.
- Production KBS workflow validation.
- Formal causal identification, Rubin-style causal-effect language, matched estimates, or DR-corrected estimates.

## Package Split Status

- Authoritative manuscript source: `paper/kbs_submission/final_source/manuscript.tex`.
- Expected compiled manuscript artifact: `paper/kbs_submission/final_package/manuscript.pdf`, 35 pages.
- Final upload boundary after cleanup: `cover_letter.docx`, `Highlights.docx`, `manuscript.pdf`, `supplementary.docx`, and `latex_source.zip`.
- Reproducibility source bundle keeps `manuscript.tex`, `supplementary.tex`, `references.bib`, CAS files, and figures, while excluding local build artifacts.
