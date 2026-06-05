# s_FMA v2.2 Preregistration Plan

Date: 2026-06-05

Status: planned preregistration only

Scope: create a new route after the failed `s_FMA_v2.1` full stochastic validation. This document does not run API calls, generate a manifest, replay, score, train PRM, run filtering, or upgrade any claim.

## Status Boundary

Current project status remains `PILOT_BLOCKED`.

The current `s_FMA_v2.1` full stochastic validation is frozen as failed full-validation provenance in:

- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_rank_signal_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.md`
- `paper/full_validation_route_decision.md`

The v2.1 full artifact is not a validation success. Its positive pooled/GSM8K/HotpotQA rank signal can be reported only as part of failed full-validation diagnostics. The v2.1 pilot stochastic artifact remains a pilot-only gate artifact.

## Why v2.2 Exists

The v2.2 route is motivated by three observed v2.1 limitations:

1. GSM8K binary exact-match Delta-U is sparse at full scale. The v2.1 full artifact had 16 nonzero GSM8K Delta-U rows against the preregistered threshold of 20.
2. The full-scale quality gate required exact `1.0` success for JSON parse, schema, tag extraction, and final-answer parsing. Eight timeout/connection attempts lowered all four rates to `0.9971181556195965`, which blocked the route even though no distinct parser error string was observed.
3. Stochastic repeated replay needs fuller uncertainty reporting. A future route must report bootstrap confidence intervals and variance for all rank-signal metrics rather than relying on a single Spearman summary.

These limitations justify a new preregistered route. They do not justify relaxing v2.1 gates on the same v2.1 artifacts.

## Non-Use Rules for v2.1 Artifacts

The v2.1 full validation artifacts may be used only for:

- failure provenance
- motivation for v2.2 target design
- reviewer-facing explanation of why v2.1 did not clear its own gates

They must not be used to:

- tune v2.2 thresholds
- fit v2.2 weights
- select v2.2 rows
- choose v2.2 bootstrap settings
- relabel v2.1 as a validation success
- infer PRM/filtering improvement

Any v2.2 threshold, split, retry cap, metric, or reporting rule must be fixed before v2.2 manifest generation, API execution, replay, scoring, or rank-signal analysis.

## Fresh Data Boundary

v2.2 must use one of these two data routes:

1. A fresh non-overlapping holdout with no overlap against the current real-task pilot, v2, or v2.1 artifacts.
2. A new preregistered split whose source, split rule, seed, sample count, and exclusion keys are locked before manifest generation.

Required non-overlap keys:

- `sample_id`
- `task_id`
- dataset/config/split/source index
- `normalized_question_hash`
- `reference_answer_hash`
- non-empty `alias_hash`

Empty alias sets remain non-informative and do not block by themselves. Any non-empty alias hash overlap is a hard stop before API generation, replay, scoring, or reporting.

## Primary Utility Target

v2.2 replaces the sparse binary-only target with `graded_stochastic_delta_u_v2_2`.

General definition:

```text
Delta-U_v2.2 = original_primary_utility - mean(intervened_primary_utility over preregistered replay repeats)
```

All task-level and global utility summaries must be computed from sample-level aggregates, with `sample_id` as the bootstrap unit.

### GSM8K

Primary target: `repeated_numeric_success_probability`.

Definition:

- Generate the original answer under a preregistered repeat count.
- Score each original answer by numeric exact match after `normalize_gsm8k_answer()`.
- Estimate original utility as the mean numeric-success indicator across original repeats.
- For each eligible intervention span, estimate intervened utility as the mean numeric-success indicator across replay repeats.
- Compute Delta-U from probabilities, not from a single binary original-vs-intervened exact-match row.

Secondary reporting:

- single-run numeric exact match
- numeric parse failure rate
- repeated-answer agreement
- optional graded numeric error score if a deterministic numeric-distance scorer is preregistered before execution

This keeps exact match visible but prevents the primary GSM8K utility target from depending only on sparse one-shot binary Delta-U.

### HotpotQA

Primary target: `normalized_token_f1`.

Normalization policy:

- lowercase
- replace punctuation with spaces
- remove English articles `a`, `an`, and `the`
- collapse whitespace
- compute token overlap F1 after normalization

Alias policy:

- Primary HotpotQA F1 is the maximum normalized token F1 over the reference answer and all non-empty aliases.
- Reference-only normalized token F1 must also be reported.
- Alias-aware exact match is a secondary reporting metric only.
- Empty alias sets are non-informative and do not create overlap blockers or scoring alternatives.

## Schema and Transport Failure Policy

Schema, tag, final-answer, timeout, and connection failures must not be silently ignored.

v2.2 may preregister a bounded repair policy:

- retry only timeout, connection, or transport/output-extraction failures
- never edit generated answer content after the fact
- preserve every original failed attempt in attempts/audit files
- report initial failure rates, repaired failure rates, final usable coverage, and unrepaired failure counts separately
- cap repair attempts per failed request and total repair attempts before execution
- stop with an incomplete or failed status if unrepaired failures exceed the preregistered cap

A bounded repair can repair transport completeness for the new v2.2 run only. It cannot retroactively convert v2.1 failed full-validation provenance into a success.

## Rank Signal Reporting

Each task-specific report and the global report must include:

- Spearman rho with bootstrap confidence interval
- Kendall tau-b with bootstrap confidence interval
- NDCG at preregistered cutoffs
- top-k high-utility AUC at preregistered k values
- bootstrap standard error and variance for every rank metric
- number of bootstrap resamples, confidence level, random seed, and bootstrap unit
- target variation diagnostics for the primary utility target

Rank signal must be reported per task and pooled. Task-specific and global gates are evaluated separately.

## Gates

Task-specific gate:

- evaluated independently for GSM8K and HotpotQA
- requires the fresh split/non-overlap audit to be clean for that task
- requires the task primary utility target and all secondary diagnostics to be reported
- requires valid-trace, eligible-span, replay-success, schema/transport, and target-variation thresholds fixed before execution
- requires Spearman, Kendall, NDCG, and top-k AUC bootstrap intervals
- permits only task-specific or heterogeneous wording if satisfied
- does not unlock PRM/filtering

Global gate:

- requires both task-specific gates to be satisfied
- requires pooled rank signal to satisfy the preregistered standard
- requires no active schema/transport, leakage, overlap, or target-variation stop condition
- still does not establish PRM/filtering improvement by itself

No PRM/filtering design, execution, approval request, or comparative downstream gain claim is allowed until the v2.2 full validation gates are satisfied or a separate downstream validation gate is preregistered and satisfied.

## Allowed and Forbidden Wording

Allowed before execution:

- v2.2 is a planned preregistered route.
- v2.2 addresses v2.1 target sparsity, exact quality-gate brittleness, and stochastic uncertainty reporting.
- v2.1 full validation remains failed provenance.
- PRM/filtering remains downstream blocked.

Forbidden before execution:

- v2.2 validation success wording
- v2.1 full-validation success wording
- deterministic replay upgrade wording
- top-tier readiness wording
- PRM/filtering execution or comparative gain wording
- threshold tuning on v2.1 full-validation artifacts

## Current Task Boundary

This preregistration task creates only:

- `paper/s_fma_v2_2_preregistration_plan.md`
- `configs/s_fma_v2_2_fresh_holdout.yaml`
- `paper/v2_1_to_v2_2_transition_audit.md`

It also synchronizes `README.md`, `PLANS.md`, `paper/claim_registry.md`, and `paper/submission_readiness_audit.md`.

It does not create v2.2 outputs under `outputs/`, and it does not authorize later execution.
