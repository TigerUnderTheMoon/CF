# s_FMA_v2 Stochastic Smoke Approval Request

Status: `PENDING_USER_APPROVAL`

This is a minimal execution approval package for a stochastic smoke run only. It is not an approval, not an API execution record, not a v2 scoring record, not a pilot validation, and not a PRM/filtering validation.

## Current State

- Fresh manifest clean: 400 rows.
- API preflight drift persists: `PREFLIGHT_FAIL_DRIFT`.
- Deterministic route: blocked.
- Stochastic route: planned-only.
- Stochastic budget/risk audit: exists.
- Current API allowed: `false`.
- Project status: `PILOT_BLOCKED`.

## Approval Request

| Field | Value |
|---|---|
| Requested route | `STOCHASTIC_REPEATED_REPLAY_ROUTE` |
| Requested scale | `minimal smoke only` |
| Sample count | `20` |
| Expected spans | `20` |
| Expected API requests | `80` |
| Expected cost | `USD 1.16018` |
| Recommended approval ceiling | `USD 5` |
| Max allowed action after approval | `smoke original generation + stochastic replay only` |
| Approval status | `pending user approval` |
| API allowed now | `false` |

If the user explicitly approves this request, this does not authorize pilot expansion, top-tier expansion, deterministic replay wording, v2 scoring, PRM/filtering work, or any task-specific/global pass wording.

## Explicit Non-Authorizations

- No full generation.
- No v2 scoring.
- No replay before explicit user approval.
- No pilot expansion.
- No top-tier expansion.
- No deterministic replay claim.
- No PRM/filtering.
- No `TASK_SPECIFIC` pass claim.
- No `GLOBAL` pass claim.

## Smoke Gate

The smoke run, if later approved and executed, must stop unless all of the following hold:

- Schema, reflection tag, and final-answer parsing succeed.
- Stochastic replay succeeds at the smoke scale.
- Replay agreement and variance stay within the predeclared smoke threshold.
- Nonzero Delta-U values are available.
- Cost stays within the approved budget ceiling.
- Leakage audit finds no target leakage.

The smoke gate can support only engineering feasibility, cost calibration, and variance/agreement diagnostics. It cannot support task-specific validation, global validation, deterministic replay wording, or downstream PRM/filtering claims.

## Post-Smoke Branches

- Engineering fail: fix the pipeline; do not scale.
- Engineering pass but sparse signal: stop or revise the evidence target; do not scale by default.
- Engineering pass and target variation sufficient: request a separate pilot stochastic budget before any pilot run.

## Required User Decision

To proceed, the user must explicitly approve a minimal smoke budget with a ceiling of `USD 5`. Until that approval is given, API execution remains forbidden and the project remains `PILOT_BLOCKED`.
