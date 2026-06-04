# s_FMA_v2.1 Empty Output Transport Failure Audit

Scope: local artifact and code-path audit only. This audit did not run API, rerun preflight, run smoke, run replay, run scoring, run full generation, or make any PRM/filtering claim.

## Source Artifacts

- `outputs/s_fma_v2_1_fresh_holdout/api_preflight_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/api_preflight_attempts.jsonl`
- `outputs/s_fma_v2_1_fresh_holdout/api_preflight_traces.jsonl`
- `outputs/s_fma_v2_1_fresh_holdout/logs/api_preflight_cost_report.json`

## Attempt Summary

The latest v2.1 API_PREFLIGHT_ONLY rerun remains failed:

- status: `PREFLIGHT_FAIL_SCHEMA_OR_TAGS`
- records evaluated: 20
- API attempts: 23 of max 25
- preflight records: 20
- drift probes: 3
- cost: `0.31611` USD of `2.0` USD
- JSON/schema/tag/final-answer success rates: `0.0`
- valid traces: 0
- trace file size: 0 bytes
- smoke approval request allowed: `false`

All 23 attempts have empty `raw_output`. All 23 attempts have `response_id` and usage. No attempt has a non-empty extracted output.

## Token Distributions

`output_tokens`: count 23, sum 9278, min 244, median 376, mean 403.391304, max 735.

`reasoning_tokens`: count 23, sum 3063, min 36, median 97, mean 133.173913, max 516.

Observed model and structured-output mode were stable:

- `model_name`: `gpt-5.5` for 23/23 attempts
- `structured_output_mode`: `json_schema` for 23/23 attempts
- fallback status: `invalid_output` for 23/23 attempts
- validation error: `<root>: response is not a JSON object` for 23/23 attempts

## Code Path Finding

Audited files:

- `scripts/run_s_fma_v2_1_fresh_holdout_preflight.py`
- `fma/real_task_pilot/openai_client.py`
- `fma/real_task_pilot/generation.py`
- `fma/real_task_pilot/fresh_preflight_v2_1.py`

The failed attempts preserve `response_id` and usage but not enough raw response diagnostics to prove whether the API body was genuinely empty or whether local output extraction missed typed response content. The local extraction path used `response.output_text` first and fell back to `response.output`, but the previous fallback assumed dict-shaped `output[].content[]` items and did not persist `output_extraction_diagnostics` into attempt payloads.

This audit adds local extraction/telemetry/report tests and fixes only:

- typed Responses `output/content` objects are now extractable;
- `output_extraction_diagnostics` is recorded on API result, generated trace result, and future attempt payloads;
- future v2.1 reports classify all-empty `raw_output` as `PREFLIGHT_FAIL_EMPTY_OUTPUT` plus `PREFLIGHT_FAIL_OUTPUT_EXTRACTION`.

## Classification

Root cause classification: `transport_or_output_extraction_failure_suspected`.

Whether the API genuinely returned empty output or the local extraction path missed text is unknown from the current artifacts, because full raw response bodies were not saved. The presence of `response_id`, usage, `output_tokens`, and `reasoning_tokens` with empty extracted text is not model capability evidence and is not a v2.1 evidence signal.

## Claim Boundary

Current status remains `PILOT_BLOCKED`.

No smoke approval request is allowed. No full generation, replay, v2/v2.1 scoring, task/global pass, deterministic replay claim, or PRM/filtering claim is allowed from this audit. The next allowed step, if needed, is only a separately approved tiny transport canary.
