# s_FMA_v2 Fresh-Holdout Manifest Overlap Audit

Status: `MANIFEST_OVERLAP_CLEAN`
Overlap clean: `true`
Hard stop: `false`

## Execution Boundary

- Fresh manifest generation/audit only.
- No API run.
- No v2 scoring.
- No replay.
- No traces generated.
- No PRM claim yet.
- Current status remains `PILOT_BLOCKED`.
- `s_FMA_v2` remains planned-only.
- Next allowed step: `API_PREFLIGHT_ONLY`.

## Alias Policy

- Empty alias set is non-informative and not blocking.
- Non-empty `alias_hash` remains a hard blocking overlap key.
- `sample_id`, `task_id`, dataset/config/split/source index, normalized question hash, and reference answer hash remain hard-stop keys.

## Blocker Diagnosis

- Prior blocker: `BLOCKED_INSUFFICIENT_FRESH_ROWS`.
- Root cause: empty alias sets shared the SHA256 hash of the empty string and were previously treated as blocking alias_hash overlaps.
- Policy revision: empty alias set is non-informative and not blocking; non-empty alias_hash remains blocking.

## Task Status

| Task | Source rows | Empty alias rows | Non-empty alias rows | Eligible fresh rows | Required rows | Selected rows | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| gsm8k | 1319 | 1319 | 0 | 1119 | 200 | 200 | `MANIFEST_OVERLAP_CLEAN` |
| hotpotqa | 7405 | 7405 | 0 | 6672 | 200 | 200 | `MANIFEST_OVERLAP_CLEAN` |

## Required Non-Overlap Keys

| Key | Candidate pool overlaps | Selected manifest overlaps |
|---|---:|---:|
| sample_id | 400 | 0 |
| task_id | 0 | 0 |
| dataset_config_split_source_index | 400 | 0 |
| normalized_question_hash | 400 | 0 |
| reference_answer_hash | 933 | 0 |
| alias_hash | 0 | 0 |

## Current Pilot Sources

| Source | Rows loaded |
|---|---:|
| `outputs/real_task_pilot/independent_baseline_scores.jsonl` | 382 |
| `outputs/real_task_pilot/pilot_traces.jsonl` | 382 |
| `outputs/real_task_pilot/real_task_delta_u.jsonl` | 382 |
| `outputs/real_task_pilot/real_task_replay_results.jsonl` | 1146 |
| `outputs/real_task_pilot/sample_manifest.json` | 400 |
| `outputs/real_task_pilot/structurally_calibrated_fma_scores.jsonl` | 382 |

## Decision

Fresh manifest generated and hard non-overlap audit clean. The only allowed next step is API preflight-only; API full run, v2 scoring, replay, trace generation, and PRM/filtering remain forbidden.
