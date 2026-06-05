# s_FMA_v2.2 Stochastic Smoke Approval Request After Drift Disclosure

This is a request-only artifact. It does not authorize or execute API calls, smoke, replay, scoring, pilot validation, full validation, or PRM/filtering.

## Scope

- `request_name`: `V2_2_STOCHASTIC_SMOKE_APPROVAL_REQUEST_AFTER_DRIFT_DISCLOSURE`
- `scope`: `V2_2_STOCHASTIC_SMOKE_ONLY`
- `requested_scope`: `V2_2_STOCHASTIC_SMOKE_ONLY`
- `approval_status`: `REQUEST_ONLY_NOT_APPROVED`
- `current_status_remains`: `PILOT_BLOCKED`
- `api_execution_authorized_by_this_request`: `false`
- `api_execution_performed_by_this_request`: `false`
- `smoke_execution_performed_by_this_request`: `false`
- `replay_execution_performed_by_this_request`: `false`
- `scoring_execution_performed_by_this_request`: `false`
- `validation_execution_performed_by_this_request`: `false`
- `pilot_execution_performed_by_this_request`: `false`
- `prm_or_filtering_performed_by_this_request`: `false`

## Current Preflight Boundary

The current v2.2 API_PREFLIGHT_ONLY artifact remains failed with status `PREFLIGHT_FAIL_DRIFT`.

| Field | Value |
|---|---:|
| records evaluated | 20 |
| GSM8K / HotpotQA | 10 / 10 |
| JSON parse success | 1.0 |
| schema success | 1.0 |
| tag extraction success | 1.0 |
| final-answer parse success | 1.0 |
| non-empty raw output | 1.0 |
| required metadata success | 1.0 |
| determinism drift max | 0.6944444444444444 |

Failure codes remain:

- `PREFLIGHT_FAIL_DRIFT`
- `PREFLIGHT_FAIL_METADATA`

`fallback_model` and `system_fingerprint` are missing for all 20 evaluated records as disclosure-only metadata. This metadata absence is reported separately from schema, tag, final-answer, and raw-output success. It is not readiness evidence and does not repair the drift blocker.

## Route Boundary

The deterministic route remains blocked by `PREFLIGHT_FAIL_DRIFT`. Deterministic replay wording and deterministic replay claims remain forbidden.

The only route described by this request is:

- drift-disclosed stochastic repeated replay only
- request-only candidate
- repeated replay with bootstrap uncertainty
- smoke diagnostics only
- no deterministic replay wording
- no pilot/full validation
- no v2.2 pass, task/global pass, top-tier-ready, or PRM/filtering claim

## Proposed Smoke Design

| Field | Value |
|---|---:|
| sample count | 20 |
| GSM8K records | 10 |
| HotpotQA records | 10 |
| original generation requests | 20 |
| target spans per trace | max 2 |
| stochastic replay repeats per eligible span | 3 |
| max replay requests estimate | 20 * 2 * 3 = 120 |
| max total API requests | 140 |
| recommended budget ceiling | USD 8 |

Cost estimate: use USD 8 as a hard ceiling for the bounded smoke. This request did not call an API or query pricing.

## Hard Stops

- Stop if projected cost exceeds USD 8.
- Stop if JSON parse, schema, tag extraction, final-answer parse, or non-empty raw-output success falls below 1.0.
- Stop if valid original traces are fewer than 15.
- Stop if replay success rate is below 0.85.
- Stop if pooled nonzero Delta-U rows are fewer than 3.
- Stop if any task has 0 nonzero Delta-U rows.
- Stop if rank signal is evaluated beyond smoke diagnostics.
- Stop if drift disclosure is missing.
- Stop if deterministic replay wording is attempted.
- Stop if pilot or full validation is attempted without later separate approval.
- Stop if validation-pass, v2.2-pass, task/global-pass, top-tier-ready, or PRM/filtering wording is attempted.

## Smoke Feasibility Gates If Approved

| Gate | Required value |
|---|---:|
| JSON parse success | 1.0 |
| schema success | 1.0 |
| tag extraction success | 1.0 |
| final-answer parse success | 1.0 |
| non-empty raw output | 1.0 |
| valid original traces | at least 15 |
| replay success rate | at least 0.85 |
| pooled nonzero Delta-U rows | at least 3 |
| per-task nonzero Delta-U rows | at least 1 for each task |
| cost ceiling | USD 8 |
| request cap | 140 |

These are smoke feasibility gates only. They are not pilot or full-validation gates and cannot produce a pass claim.

## Allowed Output Paths For A Future Approved Run

- `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_original_attempts.jsonl`
- `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_original_traces.jsonl`
- `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_replay_prefixes.jsonl`
- `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_replay_attempts.jsonl`
- `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_replay_results.jsonl`
- `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_delta_u.jsonl`
- `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_report.json`
- `outputs/s_fma_v2_2_fresh_holdout/logs/stochastic_smoke_cost_report.json`

## Artifacts Not Rewritten

- `outputs/real_task_pilot/*`
- `outputs/s_fma_v2_fresh_holdout/*`
- `outputs/s_fma_v2_1_fresh_holdout/*`
- current v2.2 preflight report, attempts, traces, and cost report
- v2.2 preflight failure audit
- v2.2 single transport retry request files

## Forbidden Actions

- API execution without separate explicit approval
- smoke execution by this request
- replay execution by this request
- scoring execution by this request
- pilot validation
- full validation
- full generation
- PRM/filtering
- validation claim
- v2.2 pass claim
- task/global pass claim
- top-tier-ready claim
- deterministic replay claim
- deterministic replay wording

## Next Allowed Step

Without user approval, the only next step is user review of this request.

After explicit user approval only, run only `V2_2_STOCHASTIC_SMOKE_ONLY` with 20 total records, 10 GSM8K plus 10 HotpotQA, max total requests 140, stochastic replay repeats per eligible span 3, and recommended budget ceiling USD 8, writing only the allowed stochastic smoke output paths.

Current status remains `PILOT_BLOCKED`.
