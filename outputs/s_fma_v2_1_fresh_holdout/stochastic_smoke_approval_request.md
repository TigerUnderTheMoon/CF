# s_FMA_v2.1 Stochastic Smoke Approval Request

This is a request-only artifact. It does not authorize or execute API calls, smoke, replay, scoring, full generation, or PRM/filtering.

## Scope

- `scope`: `V2_1_STOCHASTIC_SMOKE_ONLY`
- `requested_scope`: `V2_1_STOCHASTIC_SMOKE_ONLY`
- `approval_status`: `REQUEST_ONLY_NOT_APPROVED`
- `current_status_remains`: `PILOT_BLOCKED`
- `api_execution_authorized_by_this_request`: `false`
- `api_execution_performed_by_this_request`: `false`
- `smoke_execution_performed_by_this_request`: `false`
- `replay_execution_performed_by_this_request`: `false`
- `scoring_execution_performed_by_this_request`: `false`
- `full_generation_performed_by_this_request`: `false`
- `prm_or_filtering_performed_by_this_request`: `false`

## Current Route Boundary

The latest v2.1 API_PREFLIGHT_ONLY status remains `PREFLIGHT_FAIL_DRIFT`.

- `determinism_drift_max`: `0.48554913294797686`
- drift threshold: `0.05`
- deterministic route: blocked
- blocked route: `DETERMINISTIC_REPLAY_ROUTE`
- stochastic route: drift-disclosed, repeated replay only
- stochastic route approval status: `REQUEST_ONLY_NOT_APPROVED`

This request uses no deterministic replay wording and permits no validation, pass, task/global pass, or PRM/filtering claim.

## Proposed Smoke Design

| Field | Value |
|---|---:|
| sample_count | 20 |
| gsm8k | 10 |
| hotpotqa | 10 |
| original generation requests | 20 |
| target spans per trace | max 2 |
| stochastic replay repeats per span | 3 |
| max replay requests estimate | 20 * 2 * 3 = 120 |
| max total requests | 140 |
| recommended budget ceiling | USD 8 |

Cost estimate: use USD 8 as a hard ceiling for the bounded smoke. This request did not call an API or query pricing.

## Hard Stops

- Stop if projected cost exceeds USD 8.
- Stop if valid original traces are fewer than 15.
- Stop if replay success rate is below 0.85.
- Stop if pooled nonzero Delta-U rows are fewer than 3.
- Stop if any task has 0 nonzero Delta-U rows.
- Stop if drift disclosure is missing.
- Stop if deterministic replay wording is attempted.
- Stop if validation, pass, task/global pass, or PRM/filtering wording is attempted.

## Smoke Feasibility Gates If Approved

| Gate | Required value |
|---|---:|
| valid original traces | at least 15 |
| replay success rate | at least 0.85 |
| pooled nonzero Delta-U rows | at least 3 |
| per-task nonzero Delta-U rows | at least 1 for each task |
| cost ceiling | USD 8 |
| request cap | 140 |

These are smoke feasibility gates only. They are not validation gates and cannot produce a pass claim.

## Allowed Output Paths For A Future Approved Run

- `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_original_attempts.jsonl`
- `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_original_traces.jsonl`
- `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_replay_prefixes.jsonl`
- `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_replay_attempts.jsonl`
- `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_replay_results.jsonl`
- `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_delta_u.jsonl`
- `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/logs/stochastic_smoke_cost_report.json`

## Artifacts Not Rewritten

- `outputs/real_task_pilot/*`
- `outputs/s_fma_v2_fresh_holdout/*`
- current v2.1 preflight report, attempts, traces, and cost report
- canary artifacts
- drift, schema, and empty-output audits

## Forbidden Actions

- API execution without separate explicit approval
- smoke execution by this request
- replay execution by this request
- scoring execution by this request
- full generation
- PRM/filtering
- validation claim
- pass claim
- task/global pass claim
- top-tier claim
- deterministic replay claim
- deterministic replay wording

## Next Allowed Step

Without user approval, the only next step is user review of this request.

After explicit user approval only, run only `V2_1_STOCHASTIC_SMOKE_ONLY` with sample_count 20, max_total_requests 140, stochastic replay repeats per span 3, and recommended_budget_ceiling_usd 8, writing only the allowed stochastic smoke output paths.

Current status remains `PILOT_BLOCKED`.
