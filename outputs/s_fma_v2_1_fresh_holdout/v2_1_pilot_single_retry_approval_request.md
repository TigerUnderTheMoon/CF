# s_FMA v2.1 Pilot Single Transport Retry Approval Request

Status: `REQUEST_ONLY_NOT_APPROVED`

This request-only artifact covers only `V2_1_PILOT_SINGLE_TRANSPORT_RETRY_ONLY`. It does not authorize or execute API calls, retry, replay, scoring, original regeneration, full validation, or PRM/filtering. Current status remains `PILOT_BLOCKED`.

## Source Failure Boundary

- Source audit: `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_transport_failure_audit.json`
- Source pilot report: `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_report.json`
- Source status: `V2_1_PILOT_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`
- Actual API requests: `700`
- Actual cost: USD `28.04808`
- Valid original traces: `100`
- Replay success: `599/600`
- JSON/schema/tag/final-answer success: `0.9985714285714286`
- Current `TASK_SPECIFIC` pass: `false`
- Current `GLOBAL` pass: `false`
- Current status: `PILOT_BLOCKED`
- Failure reason: single transport failure hard-stop, not signal failure

## Retry Scope

| Field | Value |
|---|---:|
| scope | `V2_1_PILOT_SINGLE_TRANSPORT_RETRY_ONLY` |
| max API requests | 3 |
| budget ceiling | USD 1 |
| retry attempts allowed | 1 |
| original generation requests | 0 |
| approval status | `REQUEST_ONLY_NOT_APPROVED` |

Only this failed replay attempt may be retried after separate explicit approval:

| Field | Value |
|---|---|
| sample_id | `gsm8k-00357` |
| task_id | `gsm8k-test-00357` |
| task_type | `gsm8k` |
| span_index | `1` |
| repeat_index | `2` |
| failure | `api_error:APIConnectionError:Connection error.` |

## Required Pre-Run Checks After Explicit Approval

- Approval status has been explicitly changed by the user or approval command to an approved state.
- Requested scope is exactly `V2_1_PILOT_SINGLE_TRANSPORT_RETRY_ONLY`.
- Source audit still classifies the blocker as `single_transport_failure_hard_stop`.
- Failed attempt key remains `gsm8k-00357` / `gsm8k-test-00357` / span `1` / repeat `2`.
- Projected API requests are at most `3`.
- Approved budget ceiling is at most USD `1`.
- No original regeneration, other replay attempt, full validation, or PRM/filtering is requested.

## Forbidden Actions And Claims

- API execution without separate explicit user approval.
- API execution or retry by this request-only artifact.
- Original regeneration.
- Any replay attempt other than `gsm8k-00357` / `gsm8k-test-00357` / span `1` / repeat `2`.
- Full replay rerun.
- New scoring experiment.
- Full validation.
- PRM/filtering.
- `TASK_SPECIFIC` or `GLOBAL` pass claim unless recomputed post-retry artifacts truly satisfy all gates.
- Top-tier-ready claim.
- Historical artifact rewrite into a stronger claim.

## Next Step

Without explicit user approval, the only next step is user review of this request. After explicit approval only, run exactly the single failed replay retry under the 3-request and USD 1 caps, then recompute the affected pilot artifacts before any pass wording is considered.
