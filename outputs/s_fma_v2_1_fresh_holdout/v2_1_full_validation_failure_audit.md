# v2.1 Full Stochastic Validation Failure Audit

Date: 2026-06-05

This audit freezes the current `V2_1_FULL_STOCHASTIC_VALIDATION_ONLY` artifact as failed full-validation provenance. It did not run API calls, replay, full validation, new scoring, or PRM/filtering.

## Status Boundary

- Pilot stochastic gate: passed in `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_report.json`.
- Full stochastic validation: failed in `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_report.json`.
- Rank signal: positive for pooled, GSM8K, and HotpotQA in the full artifact.
- Preregistered pass gates: failed.
- PRM/filtering: still blocked; no execution, approval request, or superiority claim is allowed.
- Current top-level status: `PILOT_BLOCKED`.

## Full Artifact Summary

| Field | Value |
|---|---:|
| Full status | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS` |
| Failure codes | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`; `V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL` |
| Samples | 400 total; 200 GSM8K; 200 HotpotQA |
| API attempts in source artifact | 2776 |
| Cost in source artifact | USD `65.689985` of approved USD `150.0` |
| Valid original traces | 396 total; 200 GSM8K; 196 HotpotQA |
| Replay results | 2372 successful of 2376 expected |
| Delta-U rows | 791 |
| Full `TASK_SPECIFIC_pass` | `false` |
| Full `GLOBAL_pass` | `false` |

## Quality Gate Failures

The preregistered quality gates require exact `1.0` success for JSON parse, schema, tag extraction, and final-answer parse. The full artifact reports `0.9971181556195965` for all four rates, which implies 8 failed attempts out of 2776.

The observed validation-error strings are transport/API errors:

| Error | Count |
|---|---:|
| `api_error:APITimeoutError:Request timed out.` | 6 |
| `api_error:APIConnectionError:Connection error.` | 2 |

No distinct schema/tag/final-answer parser error string was observed beyond those API failures. They still make the all-success quality gate fail.

## Invalid Original Traces

There are 4 invalid original trace attempts, all HotpotQA:

| sample_id | task_id | error |
|---|---|---|
| `hotpotqa-00021` | `5ae6050f55429929b0807a5e` | `api_error:APITimeoutError:Request timed out.` |
| `hotpotqa-00178` | `5a74c85055429916b0164218` | `api_error:APITimeoutError:Request timed out.` |
| `hotpotqa-00179` | `5a88dcf9554299206df2b383` | `api_error:APIConnectionError:Connection error.` |
| `hotpotqa-00180` | `5a7625c7554299109176e668` | `api_error:APIConnectionError:Connection error.` |

## Replay Failures

There are 4 failed replay attempts, all HotpotQA and all timeout failures:

| sample_id | task_id | span_index | repeat_index |
|---|---|---:|---:|
| `hotpotqa-00006` | `5a85b2d95542997b5ce40028` | 0 | 0 |
| `hotpotqa-00006` | `5a85b2d95542997b5ce40028` | 0 | 1 |
| `hotpotqa-00006` | `5a85b2d95542997b5ce40028` | 0 | 2 |
| `hotpotqa-00006` | `5a85b2d95542997b5ce40028` | 1 | 1 |

## Delta-U and Rank Signal

| Scope | Delta-U rows | Nonzero Delta-U | Positive | Negative |
|---|---:|---:|---:|---:|
| Pooled | 791 | 158 | 37 | 121 |
| GSM8K | 400 | 16 | 8 | 8 |
| HotpotQA | 391 | 142 | 29 | 113 |

| Scope | n | Spearman rho | 95% CI | CI lower > 0 |
|---|---:|---:|---|---|
| Pooled | 791 | `0.40429826194063756` | `[0.33018536417588107, 0.47498179008098873]` | true |
| GSM8K | 400 | `0.39190746956761374` | `[0.20969565326846643, 0.5611862887115356]` | true |
| HotpotQA | 391 | `0.26541149212099957` | `[0.18518584662107646, 0.3476265903398467]` | true |

Rank signal is positive. It is not the failure source.

## Direct Pass-Gate Causes

Passed gates:

- Cost within budget.
- Request count within cap.
- Valid original traces per task meet the threshold.
- Eligible spans per task meet the threshold.
- Replay success rate meets the threshold.
- Rank-signal CI lower bounds are positive for pooled, GSM8K, and HotpotQA.
- HotpotQA nonzero Delta-U count meets the threshold.

Failed gates:

- JSON/schema/tag/final-answer quality rates are `0.9971181556195965`, below the required `1.0`.
- GSM8K has 16 nonzero Delta-U rows, below the preregistered threshold of 20.

Therefore `TASK_SPECIFIC_pass_by_task` is `{"gsm8k": false, "hotpotqa": false}` and `GLOBAL_pass` is `false`. HotpotQA has enough nonzero Delta-U and a positive rank signal, but the global quality gate is shared and failed.

## Route Decision

A. Conservative diagnostic / workshop route: selected for the current paper state. Use this artifact as failed full-validation provenance only. Keep pilot pass wording pilot-only and keep `PILOT_BLOCKED`.

B. Preregister v2.2: allowed only as a new preregistered route. Do not tune, relax, or reinterpret gates on the same v2.1 full-validation artifacts.

C. Engineering retry only: a retry may address timeout/connection completeness, but it cannot solve the GSM8K sparse-signal gate by itself and cannot directly turn this failed artifact into a pass.

## Claim Boundary

Allowed wording:

- The v2.1 pilot stochastic artifact passed its pilot gates.
- The v2.1 full stochastic validation artifact failed the preregistered full-validation gates.
- The failed full artifact has positive pooled/GSM8K/HotpotQA rank signal.
- PRM/filtering remains blocked.

Forbidden wording:

- Do not claim full-validation `GLOBAL_pass`.
- Do not claim submission-ready or top-tier-ready status.
- Do not claim deterministic replay positive evidence.
- Do not claim PRM/filtering execution, improvement, or superiority.
- Do not tune thresholds post hoc on the same full-validation artifact.
