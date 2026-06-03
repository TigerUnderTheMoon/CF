# s_FMA v2.1 API Preflight Schema Failure Audit

This is a non-API audit. No API, smoke, replay, scoring, full generation, pass claim, or PRM/filtering work was run for this fix.

## Status

- Historical preflight status: `PREFLIGHT_FAIL_SCHEMA_OR_TAGS`
- Current project status: `PILOT_BLOCKED`
- Historical report: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_report.json`
- Historical attempts: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_attempts.jsonl`
- Historical traces: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_traces.jsonl`

## Historical Metrics

- Records evaluated: `20`
- API attempts: `23`
- Cost used: `0.837825` USD
- JSON parse success: `1.0`
- Schema success: `0.85`
- Tag extraction success: `1.0`
- Final-answer parse success: `1.0`
- Drift status: `PREFLIGHT_FAIL_DRIFT`
- Failure codes: `PREFLIGHT_FAIL_SCHEMA`, `PREFLIGHT_FAIL_DRIFT`, `PREFLIGHT_FAIL_METADATA`

## Root Cause

The schema failure was an enum alias mismatch. Three historical records used:

```text
self_evaluation
```

but `schemas/real_task_trace.schema.json` accepts the canonical value:

```text
self-evaluation
```

Invalid historical attempts were dropped before `api_preflight_traces.jsonl`, so the failed rows remain diagnostic attempts rather than valid traces.

Affected samples:

- `gsm8k-00996` / `gsm8k-test-00996`
- `gsm8k-00011` / `gsm8k-test-00011`
- `hotpotqa-00008` / `5a7bbb64554299042af8f7cc`

## Fix Applied

- `fma/real_task_pilot/generation.py` now canonicalizes `self_evaluation -> self-evaluation` and `self_reflection -> self-reflection` before schema validation.
- Raw-to-canonical conversions are preserved in `generation_config.reflection_type_normalization`.
- `prompts/s_fma_v2_1_reflection_generation.txt` and `configs/s_fma_v2_1_fresh_holdout.yaml` now use schema-canonical `self-evaluation`.
- `fma/real_task_pilot/fresh_preflight_v2_1.py` keeps smoke approval false unless status is exactly `API_PREFLIGHT_READY`.
- The v2.1 preflight runner now checks the prompt-version lock before adapter creation.

## Prompt Lock

Historical prompt version:

```text
prompt-sha256:49c492d182e0f66d6dbb2e60c7a66a8c43a8462c28351133354608583ab6c182
```

Current prompt version after the local fix:

```text
prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b
```

Because the prompt changed after manifest lock, the existing v2.1 manifest, contract audit, and approval request are historical provenance. They must not be used to rerun API automatically.

## Claim Boundary

The historical v2.1 preflight still failed. The local fix does not convert it into `API_PREFLIGHT_READY`, does not permit smoke approval, and does not validate v2.1.

Next allowed step:

```text
REGENERATE_V2_1_MANIFEST_CONTRACT_AND_PREFLIGHT_APPROVAL_REQUEST_NON_API_ONLY
```

Forbidden from this audit:

- API rerun without a new approval package
- smoke
- replay
- scoring
- full generation
- v2.1 validation or pass claim
- task/global pass claim
- deterministic replay claim
- PRM/filtering claim
- top-tier-ready claim
