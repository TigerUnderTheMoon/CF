# v2.2 Stochastic Smoke Sparse-Signal Failure Audit

This is an offline audit of the completed v2.2 stochastic smoke checkpoint. It did not run API calls, replay, scoring, validation, or PRM/filtering.

## Source

- Report: `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_report.json`
- Delta-U rows: `outputs/s_fma_v2_2_fresh_holdout/stochastic_smoke_delta_u.jsonl`
- Cost report: `outputs/s_fma_v2_2_fresh_holdout/logs/stochastic_smoke_cost_report.json`

## Result

- Scope: `V2_2_STOCHASTIC_SMOKE_SECOND_PROVIDER_RETRY_THEN_RESUME_ONLY`
- Status: `V2_2_STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`
- API requests: `142`
- Cost: USD `2.00082`
- Valid originals: `20/20`
- Replay success: `120/120`
- JSON/schema/tag/final-answer/raw-output success: `1.0`
- Delta-U rows: `40`
- Nonzero Delta-U pooled: `5`
- Nonzero Delta-U GSM8K: `0`
- Nonzero Delta-U HotpotQA: `5`

Transport and schema blockers were resolved. The failure is now interpretable as a task-specific sparse-signal failure: GSM8K has zero nonzero Delta-U rows in this smoke.

## Gate Decision

The v2.2 smoke gate does not pass. A v2.2 pilot approval request is not allowed.

Next allowed direction: `STOP_OR_REVISE_EVIDENCE_TARGET`.

No v2.2 pass claim, pilot/full validation claim, task/global gate claim, deterministic replay claim, top-tier-ready claim, or PRM/filtering claim is allowed.

