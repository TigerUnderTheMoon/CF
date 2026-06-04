# s_FMA_v2.1 Stochastic Smoke Failure Audit

Audit date: 2026-06-04

This is an independent failure audit of the already executed
`V2_1_STOCHASTIC_SMOKE_ONLY` artifacts. This audit did not run API calls, did
not rerun smoke, did not replay, did not score, did not run full generation, and
did not run pilot or full validation.

## Source Status

- Source report: `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_report.json`
- Current smoke status: `V2_1_STOCHASTIC_SMOKE_FAIL_SCHEMA_OR_TAGS`
- Source API requests: 140
- Source cost: 5.848195 USD
- Valid original traces: 20/20
- Replay attempts: 120
- Replay success/failure: 80/40
- Replay success rate: 0.6666666666666666
- Failure codes: `V2_1_STOCHASTIC_SMOKE_FAIL_SCHEMA_OR_TAGS`, `V2_1_STOCHASTIC_SMOKE_FAIL_REPLAY`
- Current status remains: `PILOT_BLOCKED`
- Current smoke can be considered pass: no
- Pilot/full validation request allowed: no

## Failure Counts

Replay failures by task:

| Task | Failures | Successes |
|---|---:|---:|
| GSM8K | 10 | 50 |
| HotpotQA | 30 | 30 |

Unsupported reflection type distribution:

| Type | Count |
|---|---:|
| `final_check` | 16 |
| `correction` | 13 |
| `conclusion` | 4 |
| `final-check` | 2 |
| `resolution` | 2 |
| `answer-check` | 1 |
| `answer_selection` | 1 |
| `answer_check` | 1 |

The dominant validation errors are schema enum violations on
`reflection_spans.2.operation_type`. The largest unsupported types are
`final_check` and `correction`.

## Delta-U Signal

- Delta-U rows: 30
- Nonzero Delta-U pooled: 9
- Nonzero Delta-U by task: GSM8K 8, HotpotQA 1
- Signal absent: no
- Partial nonzero signal exists: yes
- HotpotQA remains weak: yes

Interpretation: the smoke is not signal-missing. It has partial nonzero Delta-U,
but it is engineering/schema blocked because replay schema/type control failed
and replay success is below the 0.85 gate.

## Root Cause Classification

Primary classification:

`replay_schema_control_failure_with_partial_nonzero_signal`

Classification flags:

- `signal_missing`: false
- `replay_schema_control_failure`: true
- `prompt_enum_drift`: true
- `parser_canonicalization_gap`: true
- `task_specific_sparse_signal`: HotpotQA watch item, not the primary hard stop

## Non-API Replay Type Fix Plan

The replay prompt and config must allow only this schema enum:

- `verification`
- `error_diagnosis`
- `plan_revision`
- `self-evaluation`
- `uncertainty_monitoring`
- `strategy_critique`
- `planning`
- `other`

The replay prompt must forbid invented types such as `final_check`,
`correction`, `conclusion`, `resolution`, and answer-check variants.

Pre-registered alias policy:

- `final_check -> verification`
- `correction -> error_diagnosis`

Unknown unsupported types remain rejected unless a config explicitly switches
the unknown policy to `map_to_other`. The alias mapping is a schema
compatibility fix only. It must not be used to reinterpret the current failed
smoke as pass.

## Claim Boundary

The current stochastic smoke remains failed provenance. No validation, pass,
top-tier, deterministic replay, pilot/full validation request, or PRM/filtering
claim is unlocked from these artifacts.

Next allowed step: only a separately approved bounded stochastic smoke rerun
approval request after the replay type fix and local audit are clean.
