# s_FMA_v2.2 API Preflight Failure Audit

This is an offline audit of the existing v2.2 API preflight failure. It did not run API calls, retry, rerun preflight, smoke, replay, scoring, validation, or PRM/filtering.

## Frozen Source

The current failed preflight artifacts are frozen as evidence:

| Artifact | SHA-256 |
|---|---|
| `outputs/s_fma_v2_2_fresh_holdout/api_preflight_report.json` | `e520271efeb2d85bb7d947cd1abcf602891fc3f178cbedf336fd0e6979ccd4b9` |
| `outputs/s_fma_v2_2_fresh_holdout/api_preflight_attempts.jsonl` | `dbb82e3fc14c139285f39e6b86ca17b38d6dd8624659e2529aabd65d79f352f0` |
| `outputs/s_fma_v2_2_fresh_holdout/api_preflight_traces.jsonl` | `5e5f8f3fbb0817c6c6f28e368ce41f917ab116a102acd1a906095ea5d7193670` |
| `outputs/s_fma_v2_2_fresh_holdout/logs/api_preflight_cost_report.json` | `0d689cb707c656c1903c46320a768160aaf4490c486a5237af6a25b3a2f52bcf` |

## Observed Failure

| Field | Value |
|---|---|
| Source scope | `V2_2_API_PREFLIGHT_ONLY` |
| Source report status | `PREFLIGHT_FAIL_SCHEMA_OR_TAGS` |
| Drift status | `PREFLIGHT_FAIL_DRIFT` |
| Records expected / evaluated | `20 / 20` |
| Valid trace rows | `19` |
| API attempts | `23` |
| Cost | USD `0.22672` of USD `2.0` |
| JSON parse success | `0.95` |
| Schema success | `0.95` |
| Tag extraction success | `0.95` |
| Final-answer parse success | `0.95` |
| Non-empty raw output | `0.95` |

The immediate transport failure source is one failed preflight record:

| Field | Value |
|---|---|
| `sample_id` | `hotpotqa-00240` |
| `task_id` | `5a85cead5542991dd0999ea9` |
| Failure | `APIConnectionError: Connection error.` |
| `raw_output` | empty |
| `record` | `null` |
| `response_id` | `null` |
| Trace row generated | no |

The 0.95 JSON/schema/tag/final-answer and raw-output rates are explained by one failed transport attempt out of 20 selected preflight records. This does not repair or weaken the independent drift failure.

## Metadata Disclosure

The frozen report also discloses missing provider metadata:

| Disclosure field | Missing count |
|---|---:|
| `fallback_model` | 20 |
| `system_fingerprint` | 20 |

This metadata absence is disclosed separately from schema, tag, and final-answer parsing. It is not positive readiness evidence.

## Claim Boundary

- Current v2.2 is not a pass.
- Current v2.2 is not stochastic-smoke ready.
- No smoke approval is allowed unless recomputed JSON/schema/tag/final-answer gates become clean.
- `PREFLIGHT_FAIL_DRIFT` must not be rewritten.
- Even if a single retry succeeds for `hotpotqa-00240`, deterministic replay remains blocked by the frozen drift failure unless a separately approved and recomputed deterministic preflight route actually resolves drift.
- No deterministic replay claim, task/global pass claim, top-tier-ready claim, or PRM/filtering claim is allowed.

## Request-Only Follow-Up

The only proposed follow-up is a request-only approval package for `V2_2_API_PREFLIGHT_SINGLE_TRANSPORT_RETRY_ONLY`, targeting exactly `hotpotqa-00240`, with max 3 API requests and a USD 1 ceiling:

- `outputs/s_fma_v2_2_fresh_holdout/api_preflight_single_retry_approval_request.json`
- `outputs/s_fma_v2_2_fresh_holdout/api_preflight_single_retry_approval_request.md`

This audit does not grant that approval.
