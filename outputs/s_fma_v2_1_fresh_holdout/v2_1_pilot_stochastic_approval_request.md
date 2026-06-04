# s_FMA_v2.1 Pilot Stochastic Budget Approval Request

Status: `REQUEST_ONLY_NOT_APPROVED`

This is a request-only artifact for
`V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY`. It does not authorize or execute API
calls, pilot execution, replay, scoring, full validation, or PRM/filtering.
Current status remains `PILOT_BLOCKED`.

## Source Smoke Boundary

The controlling smoke rerun source is
`outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_report.json`.

| Field | Value |
|---|---:|
| smoke status | `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST` |
| JSON parse success | 1.0 |
| schema success | 1.0 |
| tag extraction success | 1.0 |
| final-answer parse success | 1.0 |
| replay success rate | 1.0 |
| nonzero Delta-U pooled | 20 |
| nonzero Delta-U GSM8K | 7 |
| nonzero Delta-U HotpotQA | 13 |
| current status remains | `PILOT_BLOCKED` |

This smoke feasibility result permits only a pilot-budget request. It is not a
task/global pass, full validation, submission-readiness, deterministic replay,
or PRM/filtering result.

## Requested Scope

| Field | Value |
|---|---:|
| scope | `V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY` |
| total records | 100 |
| GSM8K records | 50 |
| HotpotQA records | 50 |
| stochastic repeats per eligible span | 3 |
| max target spans per trace | 2 |
| original generation requests | 100 |
| max replay requests | 600 |
| max API requests | 700 |
| budget ceiling recommendation | USD 40 |
| approval status | `REQUEST_ONLY_NOT_APPROVED` |

This scope is allowed only after separate explicit user approval.

## Hard Stops

- Original valid trace rate below threshold -> stop.
- Replay success rate below threshold -> stop.
- Any JSON/schema/tag/final-answer failure -> stop.
- Nonzero Delta-U too sparse -> stop.
- Rank signal fails -> remain `PILOT_BLOCKED`.
- No task/global pass claim unless the preregistered gate truly passes.
- No PRM/filtering claim.

## Forbidden Actions And Claims

- API execution without separate explicit user approval.
- API execution by this request-only artifact.
- Pilot execution, replay, scoring, or full validation by this request-only
  artifact.
- Task/global pass claim from this request package.
- Full validation or submission-readiness upgrade claim.
- PRM/filtering.
- top-tier-ready claim.

## Next Step

Without explicit user approval, the only next step is user review of this
request package. After explicit approval only, run only
`V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY` with 100 total records, GSM8K 50 plus
HotpotQA 50, 3 stochastic repeats per eligible span, max 700 API requests, and
a recommended USD 40 budget ceiling.
