# s_FMA_v2.2 Manifest-Only Contract Audit

Status: `V2_2_CONTRACT_CLEAN`
Current status remains: `PILOT_BLOCKED`
Current task scope: `S_FMA_V2_2_PROMPT_LOCK_ONLY`
Manifest generation scope: `S_FMA_V2_2_MANIFEST_ONLY_NON_OVERLAP_AUDIT`
Manifest generation performed by this task: `false`
Validation/pass claim allowed: `false`
Prompt lock status: `CURRENT_PACKAGE_PROMPT_LOCK`
Prompt version: `prompt-sha256:8f9498811a4534f390d4f0a0ea648aa3701565e05c89174b72f2b8ba2191ae52`

## Execution Boundary

- No API execution.
- No replay.
- No scoring.
- No PRM/filtering.
- No validation/pass claim.

## Prompt Lock

- Generation prompt: `prompts/s_fma_v2_2_reflection_generation.txt`.
- Replay prompt: `prompts/s_fma_v2_2_replay.txt`.
- Hash scope: `generation_and_replay_prompt_bundle`.
- The prompt enum uses schema-canonical reflection types, including `self-evaluation`.
- The prompts forbid invented reflection types.
- The prompts support `graded_stochastic_delta_u_v2_2`, with GSM8K `repeated_numeric_success_probability` and HotpotQA `normalized_token_f1`.

## Checks

| Check | Status |
|---|---|
| `manifest_only_scope` | `clean` |
| `no_api_replay_scoring_prm_boundary` | `clean` |
| `current_status_not_submission_ready` | `clean` |
| `failed_v2_1_provenance_present` | `clean` |
| `v2_1_non_use_policy` | `clean` |
| `fresh_split_non_overlap_policy` | `clean` |
| `utility_target_policy` | `clean` |
| `schema_transport_policy` | `clean` |
| `rank_signal_reporting_policy` | `clean` |
| `claim_policy` | `clean` |
| `preregistration_plan_boundary` | `clean` |
| `manifest_overlap_audit` | `clean` |
| `prompt_lock` | `clean` |

## Blockers

- None at the manifest-only contract layer.

## Decision

Next allowed step: `V2_2_API_PREFLIGHT_APPROVAL_REQUEST_ONLY`.
This is not an API approval and not a validation/pass claim.
