# s_FMA_v2.1 API Preflight Approval Request

This is a request only. It does not authorize or execute API calls.

## Scope

- `requested_scope`: `V2_1_API_PREFLIGHT_ONLY`
- `approval_status`: `REQUEST_ONLY_NOT_APPROVED`
- `request_valid_for_review`: `true`
- `api_execution_authorized_by_this_request`: `false`
- `current_status_remains`: `PILOT_BLOCKED`
- `requested_records`: `20`
- `records_per_task`: `{"gsm8k": 10, "hotpotqa": 10}`
- `max_api_requests`: `25`
- `recommended_budget_ceiling_usd`: `2`
- `prompt_version`: `prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b`

## Required Checks

| Check | Required value | Evidence |
|---|---|---|
| v2.1 manifest rows | `400` | `outputs\s_fma_v2_1_fresh_holdout\fresh_manifest.json` |
| manifest_overlap_audit.status | `MANIFEST_OVERLAP_CLEAN` | `outputs\s_fma_v2_1_fresh_holdout\manifest_overlap_audit.json` |
| selected overlaps all zero | `{"alias_hash": 0, "dataset_config_split_source_index": 0, "normalized_question_hash": 0, "reference_answer_hash": 0, "sample_id": 0, "task_id": 0}` | `outputs\s_fma_v2_1_fresh_holdout\manifest_overlap_audit.json` |
| v2_1_contract_audit.status | `V2_1_CONTRACT_CLEAN` | `outputs\s_fma_v2_1_fresh_holdout\v2_1_contract_audit.json` |
| prompt hash lock | `prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b` | `prompts/s_fma_v2_1_reflection_generation.txt` |
| tests pass | `python -m pytest -q exits 0 before any approved API execution` | `local verification command` |

## Selected Overlaps

| Key | Selected overlaps |
|---|---:|
| `alias_hash` | 0 |
| `dataset_config_split_source_index` | 0 |
| `normalized_question_hash` | 0 |
| `reference_answer_hash` | 0 |
| `sample_id` | 0 |
| `task_id` | 0 |

## Historical Provenance Not Rewritten

- `outputs\s_fma_v2_1_fresh_holdout\api_preflight_report.json`
- `outputs\s_fma_v2_1_fresh_holdout\api_preflight_attempts.jsonl`
- `outputs\s_fma_v2_1_fresh_holdout\api_preflight_traces.jsonl`
- `outputs\s_fma_v2_1_fresh_holdout\logs\api_preflight_cost_report.json`

## Forbidden

- smoke
- replay
- full generation
- v2.1 scoring
- task/global pass claim
- PRM/filtering
- deterministic replay claim
- submission-ready claim

## Claim Boundary

- No validation claim.
- No pass claim.
- No PRM/filtering claim.
- Current status remains `PILOT_BLOCKED`.

## Next Step

Run V2_1_API_PREFLIGHT_ONLY for 20 records, 10 gsm8k and 10 hotpotqa, with max_api_requests 25 and recommended_budget_ceiling_usd 2, producing only the allowed API preflight outputs.
