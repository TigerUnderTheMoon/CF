# s_FMA_v2.1 Bounded Stochastic Smoke Rerun Approval Request

Status: `REQUEST_ONLY_NOT_APPROVED`

This is a request-only artifact for
`V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX`. It does not authorize or
execute API calls, smoke rerun, replay, scoring, full generation, pilot/full
validation, or PRM/filtering. Current status remains `PILOT_BLOCKED`.

## Scope

| Field | Value |
|---|---:|
| scope | `V2_1_STOCHASTIC_SMOKE_RERUN_AFTER_REPLAY_TYPE_FIX` |
| budget ceiling | USD 8 |
| max API requests | 140 |
| records | 20 |
| GSM8K records | 10 |
| HotpotQA records | 10 |
| stochastic repeats per span | 3 |
| max target spans per trace | 2 |
| max replay requests | 120 |
| approval status | `REQUEST_ONLY_NOT_APPROVED` |

This scope is allowed only after separate explicit user approval.

## Source Failure Boundary

The source stochastic smoke remains failed provenance:

- Source report: `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_report.json`
- Failure audit: `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_failure_audit.json`
- Source status: `V2_1_STOCHASTIC_SMOKE_FAIL_SCHEMA_OR_TAGS`
- Source API requests: 140
- Source cost: USD 5.848195
- Original valid traces: 20
- Replay success: 80/120
- Replay success rate: 0.6666666666666666
- Nonzero Delta-U rows: 9 pooled, 8 GSM8K, 1 HotpotQA
- Root cause: `replay_schema_control_failure_with_partial_nonzero_signal`

The failed smoke must not be reinterpreted as pass.

## Replay Type Fix Preconditions

- `prompts/real_task_replay.txt` restricts replay reflection types to the
  registered enum.
- `configs/s_fma_v2_1_fresh_holdout.yaml` pre-registers
  `final_check -> verification`.
- `configs/s_fma_v2_1_fresh_holdout.yaml` pre-registers
  `correction -> error_diagnosis`.
- Unknown replay reflection types default to `reject`.
- The alias policy is a schema compatibility fix only.

## Future Approved Rerun Boundary

After explicit approval only, the maximum rerun scope is:

- 20 records.
- 3 stochastic repeats per target span.
- 140 API requests total.
- USD 8 hard budget ceiling.
- Write only the bounded stochastic smoke output paths.

The rerun must stop if projected requests exceed 140, projected cost exceeds
USD 8, the source/request gates no longer match, or claim-boundary wording is
attempted.

## Forbidden Actions And Claims

- API execution without separate explicit user approval.
- API execution by this request-only artifact.
- Smoke rerun, replay, scoring, or full generation by this request-only
  artifact.
- Pilot/full validation.
- v2.1 pass claim.
- `TASK_SPECIFIC` or `GLOBAL` pass claim.
- PRM/filtering.
- top-tier-ready claim.
- Deterministic replay claim.
- Reinterpretation of the failed smoke as pass.

## Next Step

Without explicit user approval, the only next step is user review of this
request. Current status remains `PILOT_BLOCKED`.
