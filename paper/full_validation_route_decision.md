# Full Validation Route Decision

Date: 2026-06-06

This document records the route decision after the current `s_FMA_v2.1` full stochastic validation artifact failed its preregistered pass gates and the strict engineering retry also failed. It summarizes stored evidence only and does not run PRM/filtering.

## Decision

The current route is A: abandon strict v2.1 full validation and use conservative diagnostic / workshop wording. The failed full validation and failed strict engineering retry are frozen as provenance in:

- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_rank_signal_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.md`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_engineering_retry_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_engineering_retry_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.md`

The pilot stochastic artifact remains a pilot pass only. The full stochastic validation is not a pass, and strict v2.1 full validation is abandoned as non-viable under the current contract. Current status remains `PILOT_BLOCKED`.

## Evidence Boundary

| Evidence | Status |
|---|---|
| Pilot stochastic gate | passed in pilot artifact only |
| Full stochastic validation | failed full-validation provenance |
| Strict engineering retry | failed; 119 incremental retry API calls |
| Strict v2.1 full route | abandoned as non-viable |
| Full rank signal | positive pooled/GSM8K/HotpotQA |
| Preregistered full pass gates | failed |
| PRM/filtering | blocked |
| Deterministic replay claim | forbidden |
| Submission-upgrade claim | forbidden |

## Failure Source

The full artifact failed for two direct preregistered reasons:

- Quality success rates are below exact `1.0`: JSON parse, schema, tag extraction, and final-answer parse all report `0.9971181556195965` because 8 attempts have timeout/connection validation errors.
- GSM8K has 16 nonzero Delta-U rows, below the preregistered per-task threshold of 20.

The rank signal is not the failure source: pooled, GSM8K, and HotpotQA all have positive Spearman CI lower bounds.

## Engineering Retry Result

The strict engineering retry targeted timeout/connection completeness only and wrote separate artifacts. It did not rewrite the failed full-validation artifact.

| Field | Value |
|---|---:|
| Retry status | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS` |
| Retry failure codes | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`; `V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL` |
| Incremental retry API calls | 119 |
| Cumulative route API calls | 2895 |
| Effective report API attempts | 2794 |
| Cumulative route cost | USD `65.806855` |
| Retry abandon reason | `transport_unresolved_and_gsm8k_sparse_signal_below_preregistered_threshold` |
| Retry `TASK_SPECIFIC_pass` | `false` |
| Retry `GLOBAL_pass` | `false` |

The unresolved transport failures are HotpotQA-side. Even if those transport failures were fully cleared, the strict transport-only retry path cannot change GSM8K Delta-U rows. GSM8K remains at 16 nonzero Delta-U rows, below the preregistered threshold of 20.

## Routes

### A. Abandon v2.1 Full Validation / Conservative Diagnostic

Use the failed full validation and failed engineering retry as diagnostic results. The paper can report that the revised v2.1 route found a positive full-validation rank signal but did not satisfy the preregistered pass gates, and that strict v2.1 full validation was abandoned as non-viable under the current contract. This supports workshop/diagnostic framing only.

This route is the active decision.

### B. Preregister v2.2

A future v2.2 route may be preregistered with explicit new gates, sample design, retry policy, and sparse-signal handling. It must not tune or relax gates on the same v2.1 full-validation artifacts. Existing v2.1 artifacts remain failed provenance.

### C. Engineering Retry Only

The engineering retry has been executed and failed. It did not produce a v2.1 pass and cannot rescue the route because GSM8K remains nonzero Delta-U `16 < 20`. Further repeated v2.1 reruns to chase a passing artifact would be post-hoc pass hunting under the current contract.

## Forbidden Upgrades

- Do not claim full-validation `GLOBAL_pass`.
- Do not claim PRM/filtering execution, improvement, or superiority.
- Do not claim submission readiness or downstream validation readiness.
- Do not describe the stochastic route as deterministic replay evidence.
- Do not adjust pass gates on the same full-validation artifacts.
- Do not describe the failed engineering retry as a v2.1 rescue or pass.
