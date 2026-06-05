# s_FMA_v2.2 Fresh-Holdout Manifest Overlap Audit

Status: `MANIFEST_OVERLAP_CLEAN`
Overlap clean: `true`
Hard stop: `false`

## Execution Boundary

- Fresh manifest generation and non-overlap audit only.
- No API run.
- No replay.
- No scoring.
- No traces generated.
- No PRM/filtering claim.
- No validation or pass claim.
- Current status remains `PILOT_BLOCKED`.
- Next allowed step: `V2_2_API_PREFLIGHT_APPROVAL_REQUEST_ONLY`.

## Non-Use Boundary

- v2.1 full-validation artifacts are failed provenance and overlap-exclusion inputs only.
- v2.1 full-validation artifacts are not tuning, weighting, threshold, or row-selection sources.

## Task Status

| Task | Source rows | Empty alias rows | Non-empty alias rows | Eligible fresh rows | Required rows | Selected rows | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| gsm8k | 1319 | 1319 | 0 | 719 | 200 | 200 | `MANIFEST_OVERLAP_CLEAN` |
| hotpotqa | 7405 | 7405 | 0 | 6168 | 200 | 200 | `MANIFEST_OVERLAP_CLEAN` |

## Required Non-Overlap Keys

| Key | Candidate pool overlaps | Selected manifest overlaps |
|---|---:|---:|
| sample_id | 1200 | 0 |
| task_id | 800 | 0 |
| dataset_config_split_source_index | 1200 | 0 |
| normalized_question_hash | 1200 | 0 |
| reference_answer_hash | 1837 | 0 |
| alias_hash | 0 | 0 |

## Overlap Sources

| Source | Rows loaded |
|---|---:|
| `outputs/real_task_pilot/pilot_traces.jsonl` | 382 |
| `outputs/real_task_pilot/real_task_delta_u.jsonl` | 382 |
| `outputs/real_task_pilot/real_task_replay_results.jsonl` | 1146 |
| `outputs/real_task_pilot/sample_manifest.json` | 400 |
| `outputs/real_task_pilot/structurally_calibrated_fma_scores.jsonl` | 382 |
| `outputs/s_fma_v2_1_fresh_holdout/api_preflight_traces.jsonl` | 20 |
| `outputs/s_fma_v2_1_fresh_holdout/fresh_manifest.json` | 400 |
| `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_original_traces.jsonl` | 20 |
| `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_replay_results.jsonl` | 120 |
| `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_delta_u.jsonl` | 791 |
| `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_original_traces.jsonl` | 396 |
| `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_rank_signal_report.json` | 0 |
| `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_replay_results.jsonl` | 2372 |
| `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_report.json` | 0 |
| `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` | 16 |
| `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_original_traces.jsonl` | 100 |
| `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_replay_results.jsonl` | 600 |
| `outputs/s_fma_v2_fresh_holdout/api_preflight_traces.jsonl` | 20 |
| `outputs/s_fma_v2_fresh_holdout/fresh_manifest.json` | 400 |
| `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_original_traces.jsonl` | 20 |
| `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_replay_results.jsonl` | 60 |

## Decision

The v2.2 manifest is clean at the manifest-only layer. The only allowed next step is a separate API preflight approval request; API execution, replay, scoring, validation/pass claims, and PRM/filtering remain forbidden.
