# s_FMA v2.1 API Preflight Drift Failure Audit

Scope: independent drift-failure audit and route-fork planning for the latest `s_FMA_v2.1` API_PREFLIGHT_ONLY report. This audit performed no API calls, no preflight rerun, no smoke, no replay, no scoring, no full generation, and no PRM/filtering work.

Source report: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_report.json`

## Current Preflight Status

- status: `PREFLIGHT_FAIL_DRIFT`
- failure codes: `PREFLIGHT_FAIL_DRIFT`, `PREFLIGHT_FAIL_METADATA`
- records: 20 total, with 10 GSM8K and 10 HotpotQA
- API attempts in the source run: 23 of 25
- cost in the source run: `0.86245` of `2.0` USD
- current project status remains: `PILOT_BLOCKED`

## Schema, Transport, and Extraction

The current schema/transport blocker from the earlier empty-output failure is resolved for this preflight artifact:

- raw output non-empty: 23/23 attempts
- output extraction diagnostics complete: 23/23 attempts
- preflight trace rows: 20/20
- JSON parse success rate: `1.0`
- schema success rate: `1.0`
- tag extraction success rate: `1.0`
- final-answer parse success rate: `1.0`

This does not make the preflight ready. It only means the active blocker is no longer empty output or schema/tag/final-answer parsing.

## Metadata

The report still carries metadata failure:

- required metadata missing counts: `fallback_model: 20`, all other required fields `0`
- disclosure metadata missing counts: `system_fingerprint: 20`
- metadata disclosure status: `PREFLIGHT_METADATA_MISSING`
- required metadata success rate: `0.0`

The missing metadata is reported separately from schema, tag extraction, final-answer parsing, and raw-output extraction.

## Drift Metric

The deterministic drift gate failed.

- drift probe outputs: 3
- metric: maximum pairwise token-diff ratio over determinism probe `observable_trace` outputs
- threshold: `0.05`
- observed max: `0.48554913294797686`
- determinism gate pass: `false`

Pairwise drift details:

| Probe pair | Token counts | token_diff_ratio |
|---|---:|---:|
| 1 vs 2 | 147 vs 173 | `0.48554913294797686` |
| 1 vs 3 | 147 vs 161 | `0.2670807453416149` |
| 2 vs 3 | 173 vs 161 | `0.47398843930635837` |

## Route Fork

`DETERMINISTIC_REPLAY_ROUTE` is blocked by `PREFLIGHT_FAIL_DRIFT`. Deterministic replay language, deterministic full-generation language, task/global pass wording, and any deterministic replay claim remain forbidden.

`STOCHASTIC_REPEATED_REPLAY_ROUTE` is only a planning candidate. It is not approved and was not run. Any future stochastic route must use repeated replay, bootstrap uncertainty at the `sample_id` unit, explicit drift disclosure, explicit budget approval, and no deterministic replay wording.

Planning-only parameters for a future request:

- repeats per intervention: 3
- bootstrap unit: `sample_id`
- minimum replay success rate: `0.85`
- minimum nonzero Delta-U rows: at least 1 per task and at least 3 pooled
- smoke stage: request-only; 20 records; up to 2 target spans per trace; no automatic execution
- pilot stage: unavailable until smoke feasibility gates pass and a separate approval exists
- full stage: unavailable until smoke/pilot gates pass and a separate approval exists

Stop conditions include manifest overlap, target leakage, missing prompt lock, schema/tag success below `0.95`, replay success below `0.85`, nonzero Delta-U below the configured minima, missing drift disclosure, and budget/request cap violations.

## Claim Boundary

Allowed wording:

- v2.1 transport/schema preflight gates now pass.
- v2.1 deterministic route is blocked by `PREFLIGHT_FAIL_DRIFT`.
- current status remains `PILOT_BLOCKED`.
- a future stochastic route is planning-only unless a separate bounded request is approved.

Forbidden wording:

- no smoke run
- no replay run
- no scoring run
- no pass claim
- no deterministic replay claim
- no PRM/filtering claim
- no readiness-upgrade claim

The next allowed step is only generating a v2.1 stochastic smoke approval request if route planning is clean. That request cannot automatically run smoke or any API work.
