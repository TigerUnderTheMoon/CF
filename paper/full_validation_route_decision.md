# Full Validation Route Decision

Date: 2026-06-05

This document records the route decision after the current `s_FMA_v2.1` full stochastic validation artifact failed its preregistered pass gates. It summarizes stored evidence only and does not run API calls, replay, full validation, new scoring, or PRM/filtering.

## Decision

The current route is A: conservative diagnostic / workshop. The failed full validation is frozen as provenance in:

- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_rank_signal_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.md`

The pilot stochastic artifact remains a pilot pass only. The full stochastic validation is not a pass. Current status remains `PILOT_BLOCKED`.

## Evidence Boundary

| Evidence | Status |
|---|---|
| Pilot stochastic gate | passed in pilot artifact only |
| Full stochastic validation | failed full-validation provenance |
| Full rank signal | positive pooled/GSM8K/HotpotQA |
| Preregistered full pass gates | failed |
| PRM/filtering | blocked |
| Deterministic replay claim | forbidden |
| Submission/top-tier-ready claim | forbidden |

## Failure Source

The full artifact failed for two direct preregistered reasons:

- Quality success rates are below exact `1.0`: JSON parse, schema, tag extraction, and final-answer parse all report `0.9971181556195965` because 8 attempts have timeout/connection validation errors.
- GSM8K has 16 nonzero Delta-U rows, below the preregistered per-task threshold of 20.

The rank signal is not the failure source: pooled, GSM8K, and HotpotQA all have positive Spearman CI lower bounds.

## Routes

### A. Conservative Diagnostic / Workshop

Use the failed full validation as a diagnostic result. The paper can report that the revised v2.1 route found a positive full-validation rank signal but did not satisfy the preregistered pass gates. This supports workshop/diagnostic framing only.

This route is the active decision.

### B. Preregister v2.2

A future v2.2 route may be preregistered with explicit new gates, sample design, retry policy, and sparse-signal handling. It must not tune or relax gates on the same v2.1 full-validation artifacts. Existing v2.1 artifacts remain failed provenance.

### C. Engineering Retry Only

An engineering retry may target API timeout/connection completeness. It cannot, by itself, solve the sparse-signal gate because the full artifact also has GSM8K nonzero Delta-U `16 < 20`. It also cannot retroactively convert the current failed artifact into a pass. Any retry must be separately scoped and must report whether it changes only completeness, sparse signal, or both.

## Forbidden Upgrades

- Do not claim full-validation `GLOBAL_pass`.
- Do not claim PRM/filtering execution, improvement, or superiority.
- Do not claim top-tier readiness or submission readiness.
- Do not describe the stochastic route as deterministic replay evidence.
- Do not adjust pass gates on the same full-validation artifacts.
