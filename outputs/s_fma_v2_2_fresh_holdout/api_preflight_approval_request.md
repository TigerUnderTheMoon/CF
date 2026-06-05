# s_FMA_v2.2 API Preflight Approval Request

This is a request only. It does not authorize or execute API calls.

## Scope

- `requested_scope`: `V2_2_API_PREFLIGHT_ONLY`
- `approval_status`: `REQUEST_ONLY_NOT_APPROVED`
- `request_valid_for_review`: `true`
- `api_execution_authorized_by_this_request`: `false`
- `current_status_remains`: `PILOT_BLOCKED`
- `requested_records`: `20`
- `records_per_task`: `{"gsm8k": 10, "hotpotqa": 10}`
- `max_api_requests`: `25`
- `recommended_budget_ceiling_usd`: `2`
- `prompt_file`: `prompts/s_fma_v2_2_reflection_generation.txt`
- `replay_prompt_file`: `prompts/s_fma_v2_2_replay.txt`
- `prompt_version`: `prompt-sha256:8f9498811a4534f390d4f0a0ea648aa3701565e05c89174b72f2b8ba2191ae52`
- `prompt_lock_status`: `CURRENT_PACKAGE_PROMPT_LOCK`
- `prompt_hash_scope`: `generation_and_replay_prompt_bundle`

## Required Checks

| Check | Required value | Observed value | Evidence |
|---|---|---|---|
| v2.2 manifest exists | `true` | `true` | `outputs/s_fma_v2_2_fresh_holdout/fresh_manifest.json` |
| v2.2 manifest row count | `400` | `400` | `outputs/s_fma_v2_2_fresh_holdout/fresh_manifest.json` |
| v2.2 manifest task distribution | `{"gsm8k": 200, "hotpotqa": 200}` | `{"gsm8k": 200, "hotpotqa": 200}` | `outputs/s_fma_v2_2_fresh_holdout/fresh_manifest.json` |
| manifest_overlap_audit.status | `MANIFEST_OVERLAP_CLEAN` | `MANIFEST_OVERLAP_CLEAN` | `outputs/s_fma_v2_2_fresh_holdout/manifest_overlap_audit.json` |
| selected overlaps all zero | six selected overlap keys are zero | six selected overlap keys are zero | `outputs/s_fma_v2_2_fresh_holdout/manifest_overlap_audit.json` |
| v2_2_contract_audit.status | `V2_2_CONTRACT_CLEAN` | `V2_2_CONTRACT_CLEAN` | `outputs/s_fma_v2_2_fresh_holdout/v2_2_contract_audit.json` |
| v2.2 prompt hash lock | `prompt-sha256:8f9498811a4534f390d4f0a0ea648aa3701565e05c89174b72f2b8ba2191ae52` | `prompt-sha256:8f9498811a4534f390d4f0a0ea648aa3701565e05c89174b72f2b8ba2191ae52` | `prompts/s_fma_v2_2_reflection_generation.txt`; `prompts/s_fma_v2_2_replay.txt` |
| v2.2 config parses | `YAML_PARSE_OK` | `YAML_PARSE_OK` | `configs/s_fma_v2_2_fresh_holdout.yaml` |
| v2.1 full validation failure audit exists | `true` | `true` | `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` |
| v2.1 failure not rewritten as pass | `TASK_SPECIFIC=false`; `GLOBAL=false` | `TASK_SPECIFIC=false`; `GLOBAL=false` | `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` |
| current status not submission-ready | `PILOT_BLOCKED` | `PILOT_BLOCKED` | `paper/submission_readiness_audit.md` |

## Selected Overlaps

| Key | Selected overlaps |
|---|---:|
| `alias_hash` | 0 |
| `dataset_config_split_source_index` | 0 |
| `normalized_question_hash` | 0 |
| `reference_answer_hash` | 0 |
| `sample_id` | 0 |
| `task_id` | 0 |

## Hard Stops

- JSON parse, schema, tag extraction, or final-answer extraction failure -> stop; write failure accounting; do not continue to smoke, pilot, full validation, replay, scoring, or pass wording.
- Empty raw output or output extraction failure -> stop; preserve failed attempts and classify as transport/output extraction failure unless separately repaired under a preregistered bounded repair scope.
- Drift disclosure failure -> deterministic route blocked; no deterministic replay wording and no deterministic readiness claim.
- Metadata missing -> disclose missing metadata separately; do not treat metadata absence as pass evidence.
- Prompt hash mismatch across config, contract audit, approval request, generation prompt, or replay prompt -> stop before API execution; repair the prompt lock under a non-API prompt-lock scope.
- Request count would exceed 25 or cost would exceed USD 2 -> stop before the next API call and preserve partial preflight accounting.
- Any attempt to start smoke, pilot, full validation, replay, scoring, or PRM/filtering -> stop; those routes require separate explicit approval.

## Forbidden

- API execution by this request
- preflight execution by this request
- smoke
- replay
- scoring
- pilot
- full validation
- validation/pass claim
- deterministic replay positive claim
- top-tier-ready claim
- submission-ready claim
- PRM/filtering design, execution, or comparative gain claim

## Historical Provenance Not Rewritten

- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.md`
- v2.1 full-validation `TASK_SPECIFIC_pass=false` and `GLOBAL_pass=false` remain failed provenance.
- v2.1 full-validation artifacts are failed provenance and overlap-exclusion sources only.

## Claim Boundary

- No v2.2 validation claim.
- No v2.2 pass claim.
- No deterministic replay positive claim.
- No top-tier-ready claim.
- No PRM/filtering claim.
- Current status remains `PILOT_BLOCKED`.

## Next Step

Without explicit user approval, the only next step is user review of this request.

After explicit user approval, the only allowed execution scope is `V2_2_API_PREFLIGHT_ONLY`: 20 total records, 10 GSM8K and 10 HotpotQA, maximum 25 API requests, recommended budget ceiling USD 2, producing only `api_preflight_report.json`, `api_preflight_attempts.jsonl`, `api_preflight_traces.jsonl`, and `logs/api_preflight_cost_report.json`.
