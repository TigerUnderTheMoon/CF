# s_FMA_v2.1 Full Stochastic Validation Approval Request

Status: `REQUEST_ONLY_NOT_APPROVED`

This is a request-only artifact for
`V2_1_FULL_STOCHASTIC_VALIDATION_APPROVAL_REQUEST`. It does not authorize or
execute API calls, full validation, deterministic replay, scoring beyond the
requested validation scope, or PRM/filtering. Current status remains
`PILOT_BLOCKED`.

## Source Pilot Boundary

The controlling recomputed pilot source is
`outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_report.json`.

| Field | Value |
|---|---:|
| source status | `V2_1_PILOT_STOCHASTIC_PASS` |
| source scope | `V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY` |
| recomputed after | `V2_1_PILOT_SINGLE_TRANSPORT_RETRY_ONLY` |
| actual API requests | 700 |
| cost used | USD 28.06931 |
| valid original traces | 100 |
| replay success | 600/600 |
| JSON parse success | 1.0 |
| schema success | 1.0 |
| tag extraction success | 1.0 |
| final-answer parse success | 1.0 |
| nonzero Delta-U pooled | 96 |
| nonzero Delta-U GSM8K | 42 |
| nonzero Delta-U HotpotQA | 54 |
| TASK_SPECIFIC pass | true |
| GLOBAL pass | true |
| full validation approval request allowed | true |
| deterministic replay claim allowed | false |
| current status remains | `PILOT_BLOCKED` |

This pilot result permits only a request for a larger stochastic repeated-replay
validation. It is not full validation, deterministic replay evidence,
top-tier-ready evidence, or PRM/filtering evidence.

## Requested Scope

| Field | Value |
|---|---:|
| requested execution scope | `V2_1_FULL_STOCHASTIC_VALIDATION_ONLY` |
| total records | 400 |
| GSM8K records | 200 |
| HotpotQA records | 200 |
| stochastic repeats per eligible span | 3 |
| max target spans per trace | 2 |
| original generation requests | 400 |
| max replay requests | 2400 |
| max API requests | 2800 |
| budget ceiling recommendation | USD 150 |
| route | stochastic repeated replay only |
| approval status | `REQUEST_ONLY_NOT_APPROVED` |

This scope is allowed only after separate explicit user approval. Deterministic
replay language remains forbidden.

## Hard Stops

- Valid original traces below threshold -> stop.
- Replay success below threshold -> stop.
- JSON/schema/tag/final-answer success below threshold -> stop.
- Nonzero Delta-U sparse by task -> stop.
- Rank-signal CI lower bound not positive -> no `GLOBAL` pass.
- Full validation failure -> keep `PILOT_BLOCKED`.
- No PRM/filtering unless full validation passes and a separate downstream
  approval is generated.
- Deterministic replay language or deterministic replay claim -> stop and
  retract the claim.

## Forbidden Actions And Claims

- API execution without separate explicit user approval.
- API execution by this request-only artifact.
- Full validation execution by this request-only artifact.
- Deterministic replay route or deterministic replay claim.
- top-tier-ready claim.
- PRM/filtering execution or superiority claim.
- Claim upgrade from this request package alone.

## Next Step

Without explicit user approval, the only next step is user review of this
request package. After explicit approval only, run
`V2_1_FULL_STOCHASTIC_VALIDATION_ONLY` with 400 total records, GSM8K 200 plus
HotpotQA 200, 3 stochastic repeats per eligible span, max 2800 API requests,
and a recommended USD 150 budget ceiling.
