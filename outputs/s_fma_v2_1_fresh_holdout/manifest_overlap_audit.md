# s_FMA_v2.1 Fresh-Holdout Manifest Overlap Audit

Status: `MANIFEST_OVERLAP_CLEAN`
Overlap clean: `true`
Hard stop: `false`

## Execution Boundary

- Manifest generation and overlap audit only.
- No API run.
- No v2.1 scoring.
- No replay.
- No traces generated.
- No PRM/filtering claim.
- Current status remains `PILOT_BLOCKED`.
- `s_FMA_v2.1` remains planned-only.
- Next allowed step: `V2_1_API_PREFLIGHT_APPROVAL_REQUEST_ONLY`.

## Target And Selection Contract

- HotpotQA primary target: `normalized_token_f1`.
- GSM8K primary target: numeric exact match; unsaturated selection uses `question_difficulty_proxy` only before outcomes.
- Empty alias sets are non-informative; non-empty `alias_hash` remains blocking.

## Task Status

| Task | Source rows | Eligible fresh rows | Required rows | Selected rows | Selection policy | Status |
|---|---:|---:|---:|---:|---|---|
| gsm8k | 1319 | 919 | 200 | 200 | `rank_fresh_candidates_by_question_difficulty_proxy_desc` | `MANIFEST_OVERLAP_CLEAN` |
| hotpotqa | 7405 | 6436 | 200 | 200 | `deterministic_non_overlapping_manifest_order` | `MANIFEST_OVERLAP_CLEAN` |

## Required Non-Overlap Keys

| Key | Candidate pool overlaps | Selected manifest overlaps |
|---|---:|---:|
| sample_id | 800 | 0 |
| task_id | 400 | 0 |
| dataset_config_split_source_index | 800 | 0 |
| normalized_question_hash | 800 | 0 |
| reference_answer_hash | 1369 | 0 |
| alias_hash | 0 | 0 |

## Overlap Sources

| Source | Rows loaded |
|---|---:|
| `outputs/real_task_pilot/independent_baseline_scores.jsonl` | 382 |
| `outputs/real_task_pilot/pilot_traces.jsonl` | 382 |
| `outputs/real_task_pilot/primary_signal_failure_audit.json` | 38 |
| `outputs/real_task_pilot/readiness_audit.json` | 0 |
| `outputs/real_task_pilot/real_task_delta_u.jsonl` | 382 |
| `outputs/real_task_pilot/real_task_replay_results.jsonl` | 1146 |
| `outputs/real_task_pilot/sample_manifest.json` | 400 |
| `outputs/real_task_pilot/structurally_calibrated_fma_scores.jsonl` | 382 |
| `outputs/s_fma_v2_fresh_holdout/api_preflight_report.json` | 0 |
| `outputs/s_fma_v2_fresh_holdout/fresh_manifest.json` | 400 |
| `outputs/s_fma_v2_fresh_holdout/manifest_overlap_audit.json` | 10 |
| `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_delta_u.jsonl` | 20 |
| `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_replay_results.jsonl` | 60 |
| `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_report.json` | 0 |
| `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_sparse_signal_failure_audit.json` | 0 |

## Decision

The v2.1 manifest is clean. The only allowed next step is generating a bounded API preflight approval request; API execution, scoring, replay, trace generation, and PRM/filtering remain forbidden.
