# s_FMA_v2 Bounded Stochastic Smoke Rerun Approval Request

Status: `PENDING_USER_APPROVAL`

This package requests approval for `STOCHASTIC_SMOKE_RERUN_ONLY`. It does not approve API execution by itself, does not execute a rerun, and does not upgrade the project status. Current status remains `PILOT_BLOCKED`.

## Requested Scope

| Field | Value |
|---|---:|
| requested_scope | `STOCHASTIC_SMOKE_RERUN_ONLY` |
| approved_budget_required | `true` |
| recommended_budget_ceiling_usd | `5` |
| max_original_requests | `20` |
| max_replay_requests | `60` |
| total_max_api_requests | `80` |

## Rerun Rules

- Run original generation first.
- Run stochastic replay only if original generation produces `20/20` valid originals.
- If valid originals are fewer than `20`, stop immediately before replay and write `STOCHASTIC_SMOKE_FAIL_GENERATION`.
- The rerun may not perform pilot expansion, top-tier expansion, full generation, v2 scoring, deterministic replay claims, PRM/filtering, or task/global pass claims.

## Required Pre-Run Checks

- `manifest_overlap_audit == MANIFEST_OVERLAP_CLEAN`
- `api_preflight_report.status == PREFLIGHT_FAIL_DRIFT`
- `prior smoke report == STOCHASTIC_SMOKE_FAIL_GENERATION`
- generation failure audit exists
- tests pass

## Stop Conditions

- cost >= approved budget
- valid originals < 20 after original generation
- invalid attempt telemetry missing
- replay success rate below threshold

## Forbidden Claims

- `TASK_SPECIFIC_S_FMA_V2_PASS`
- `GLOBAL_S_FMA_V2_PASS`
- deterministic replay claim
- PRM/filtering claim
- top-tier-ready

## Approval Boundary

The prior smoke failed at original generation: 12/20 original attempts were invalid, mainly `gpt-5.4` empty `raw_output` plus non-JSON output. The non-API pipeline fixes are complete, but this package still requires explicit user approval before any rerun API call.

After explicit user approval, the only allowed command is:

```powershell
python scripts/run_s_fma_v2_stochastic_smoke.py --config configs/s_fma_v2_fresh_holdout.yaml --allow-stochastic-smoke-only --approved-budget-usd 5
```
