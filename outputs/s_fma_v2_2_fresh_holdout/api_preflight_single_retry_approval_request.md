# s_FMA_v2.2 Single Transport Retry Approval Request

This is a request only. It does not authorize or execute API calls, retry, preflight rerun, smoke, replay, scoring, validation, or PRM/filtering.

## Scope

- `requested_scope`: `V2_2_API_PREFLIGHT_SINGLE_TRANSPORT_RETRY_ONLY`
- `approval_status`: `REQUEST_ONLY_NOT_APPROVED`
- `approval_granted`: `false`
- `api_execution_authorized_by_this_request`: `false`
- `current_status_remains`: `PILOT_BLOCKED`
- Target record: `hotpotqa-00240`
- Max API requests: `3`
- Budget ceiling: USD `1`

## Frozen Source Summary

The source preflight remains failed:

| Field | Value |
|---|---|
| Source report | `outputs/s_fma_v2_2_fresh_holdout/api_preflight_report.json` |
| Source status | `PREFLIGHT_FAIL_SCHEMA_OR_TAGS` |
| Drift status | `PREFLIGHT_FAIL_DRIFT` |
| Valid trace rows | `19 / 20` |
| JSON/schema/tag/final-answer success | `0.95` |
| Non-empty raw output | `0.95` |
| Missing disclosure metadata | `fallback_model: 20`, `system_fingerprint: 20` |

The failed record is exactly:

| Field | Value |
|---|---|
| `sample_id` | `hotpotqa-00240` |
| `task_id` | `5a85cead5542991dd0999ea9` |
| `task_type` | `hotpotqa` |
| Failure | `api_error:APIConnectionError:Connection error.` |
| `raw_output` | empty |
| `record` | `null` |
| `response_id` | `null` |

## Future Approved Retry Boundary

If and only if explicitly approved later, the allowed execution scope is a single transport retry for `hotpotqa-00240`.

Allowed future outputs are only retry/recomputed preflight artifacts:

- `outputs/s_fma_v2_2_fresh_holdout/api_preflight_attempts.jsonl`
- `outputs/s_fma_v2_2_fresh_holdout/api_preflight_traces.jsonl`
- `outputs/s_fma_v2_2_fresh_holdout/api_preflight_report.json`
- `outputs/s_fma_v2_2_fresh_holdout/logs/api_preflight_cost_report.json`

## Hard Stops

- Stop if the target record differs from `hotpotqa-00240`.
- Stop if projected API requests exceed `3`.
- Stop if projected or approved cost exceeds USD `1`.
- Stop if any other preflight record is requested.
- Stop if a determinism probe rerun, full preflight rerun, smoke, replay, scoring, validation, or PRM/filtering is requested.
- Stop and retract any deterministic replay claim after retry; drift remains failed unless a separately approved route recomputes and resolves it.
- Stop and retract any smoke approval claim unless recomputed JSON/schema/tag/final-answer gates become clean.

## Claim Boundary

- This request is not a v2.2 pass.
- This request is not stochastic-smoke readiness.
- Even if the single retry succeeds, deterministic replay remains blocked by the frozen `PREFLIGHT_FAIL_DRIFT` evidence.
- No task/global pass claim, deterministic replay positive claim, top-tier-ready claim, or PRM/filtering claim is allowed.

## Next Step

Without explicit user approval, the only next step is user review of this request.
