# Stochastic Smoke Sparse-Signal Failure Audit

Status: `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`

Current project status: `PILOT_BLOCKED`

Scope: non-API audit of the already executed bounded stochastic smoke rerun. This audit reads stored artifacts only. It does not run API generation, replay, scoring, or PRM/filtering validation.

## Source Artifacts

- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_report.json`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_delta_u.jsonl`
- `outputs/s_fma_v2_fresh_holdout/logs/stochastic_smoke_cost_report.json`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_replay_results.jsonl`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_rerun_approval_request.json`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_generation_failure_audit.json`

## Rerun Summary

| Field | Value |
|---|---:|
| approved budget | `5.0` USD |
| cost used | `3.14542` USD |
| cost within budget | `true` |
| API attempts | `80` |
| input tokens | `415586` |
| output tokens | `35583` |
| total tokens | `451169` |
| smoke samples | `20` |
| GSM8K samples | `10` |
| HotpotQA samples | `10` |
| replay attempts | `60` |
| successful replay results | `60` |
| replay success rate | `1.0` |
| Delta-U rows | `20` |
| nonzero Delta-U rows | `0` |
| next allowed step | `STOP_OR_REVISE_EVIDENCE_TARGET` |

## Delta-U Pattern

All 20 Delta-U rows have `delta_u == 0.0`.

| Task | Rows | Nonzero Delta-U rows | Original exact-match correct rows | Intervened mean score 1 rows | Intervened mean score 0 rows | Successful repeats |
|---|---:|---:|---:|---:|---:|---:|
| GSM8K | 10 | 0 | 9 | 9 | 1 | 30/30 |
| HotpotQA | 10 | 0 | 0 | 0 | 10 | 30/30 |

## Root-Cause Assessment

The rerun did not fail because replay infrastructure collapsed. Replay produced 60/60 successful results.

The rerun did not fail because it exceeded the approved budget. It spent `3.14542` USD within the `5.0` USD ceiling.

The operative failure mode is insufficient target variation under the current smoke protocol:

- GSM8K is mostly saturated under exact match: 9/10 original rows are correct, and the intervened mean score remains correct for the same 9 rows.
- HotpotQA is uniformly unsuccessful under exact match: 0/10 original rows are correct, and all intervened mean scores are 0.
- With original and intervened outcomes aligned within each task pattern, the smoke has no nonzero Delta-U rows to support a rank-signal validation route.

## Claim Policy

This audit is a failure diagnostic, not validation evidence.

Allowed wording:

- engineering feasibility
- cost calibration
- preliminary replay agreement diagnostics
- sparse-signal failure diagnosis

Forbidden wording:

- `TASK_SPECIFIC_S_FMA_V2_PASS`
- `GLOBAL_S_FMA_V2_PASS`
- deterministic replay claim
- v2 scoring validation
- PRM/filtering claim

No full generation, no 400 fresh traces, no v2 scoring, no task/global v2 pass, and no PRM claim are allowed from this smoke result.

## Decision

The current stochastic smoke rerun should be frozen as failure diagnostic evidence. It should not be repeated under the same protocol without revising the evidence target and preregistering a new bounded route. Any future stochastic API work requires explicit bounded approval.
