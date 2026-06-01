# s_FMA_v2 Fresh-Holdout Plan

Status: `planned`

Scope: preregister a claim-safe route for testing `structurally_calibrated_fma_v2` on fresh GSM8K and HotpotQA holdout traces. This plan does not run API generation, manifest generation, replay, threshold search, PRM training, or downstream filtering validation.

## 1. Frozen Evidence Boundary

The current real-task pilot is frozen as `development_failure_audit`.

Frozen artifacts:

- `outputs/real_task_pilot/readiness_audit.json`
- `outputs/real_task_pilot/primary_signal_failure_audit.md`
- `outputs/real_task_pilot/primary_signal_failure_audit.json`
- Existing `outputs/real_task_pilot/*` pilot traces, replay rows, Delta-U rows, scores, bootstrap reports, controls, and API preflight reports

Current frozen facts:

- status: `PILOT_BLOCKED`
- pilot pass: `false`
- failure type: evidence-complete but signal-failed
- primary signal: `structurally_calibrated_fma`
- primary signal leakage status: clean
- signal failure: rank-signal gate failed
- HotpotQA result: negative task-level rank signal, retained as a failure and limitation
- API preflight: `PREFLIGHT_FAIL_DRIFT`

Allowed use of the current pilot:

- Diagnose Delta-U sparsity and zero inflation.
- Identify metric limitations, especially HotpotQA exact-match fragility and nondeterministic replay.
- Motivate `s_FMA_v2` design constraints and leakage rules.
- Provide development examples for error analysis only.

Forbidden use of the current pilot:

- Fitting `s_FMA_v2` weights to current pilot Delta-U, correctness, replay, rank, or threshold outcomes.
- Selecting score thresholds based on current pilot rank-signal performance.
- Reusing the 382 current pilot traces for `s_FMA_v2` final validation.
- Rewriting the current pilot into a pass after redesign.
- Treating the HotpotQA negative signal as support for the claim.

Any validation using current `outputs/real_task_pilot/*` rows is development analysis only and cannot produce `TASK_SPECIFIC_S_FMA_V2_PASS` or `GLOBAL_S_FMA_V2_PASS`.

## 2. s_FMA_v2 Scorer Specification

Score name: `structurally_calibrated_fma_v2`

Score rule ID: `s_fma_v2_rule_pre_registered_2026_06_01`

Formula hash: `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628`

Hash scope: SHA256 over the canonical JSON scorer payload with sorted keys and compact separators, excluding the hash field itself. The payload is mirrored in `configs/s_fma_v2_fresh_holdout.yaml`.

Scorer status: frozen deterministic preregistered scoring rule for fresh-holdout validation, not a trained model.

Allowed input fields:

- `observable_trace`
- `reflection_spans`
- `reflection_type` or `operation_type`
- span content
- span token offsets
- `task_type` for stratified reporting only
- non-target structural/proxy features derived before intervention

Forbidden input fields:

- `delta_u`
- `original_score`
- `intervened_score`
- `correctness`
- `replay_outcome`
- `attribution_score`
- `structural_necessity`
- `necessity`
- `final_answer`
- `reference_answer`
- `aliases`
- any post-intervention outcome

Frozen scoring rule:

```text
score = round(clip01(
    0.22 * type_prior
  + 0.16 * answer_check_marker
  + 0.16 * error_diagnosis_marker
  + 0.14 * plan_revision_marker
  + 0.10 * alternative_comparison_marker
  + 0.08 * uncertainty_marker
  + 0.08 * span_length_window
  + 0.06 * relative_position_window
), 6)

clip01(x) = min(1.0, max(0.0, x))
```

No cross-sample min-max normalization is allowed. All feature values are individually normalized to `[0, 1]` before the weighted sum. Weights sum to `1.00`.

Text normalization:

- Normalize span text with NFKC, remove XML tags, lowercase, and collapse whitespace.
- Lexicon features use case-insensitive word or phrase matching after normalization.
- Normalize operation type by lowercasing and replacing hyphens and spaces with underscores.

Feature definitions:

| Feature | Weight | Exact definition |
|---|---:|---|
| `type_prior` | 0.22 | Lookup normalized operation type: `verification=0.90`, `error_diagnosis=0.85`, `plan_revision=0.80`, `self_evaluation=0.75`, `strategy_critique=0.70`, `uncertainty_monitoring=0.65`, `planning=0.60`, `self_reflection=0.55`, `other=0.35`. Unknown types map to `other`. |
| `answer_check_marker` | 0.16 | `1.0` if normalized span text contains any of `answer`, `arithmetic`, `calculate`, `calculation`, `check`, `confirm`, `evidence`, `final`, `support`, `verify`; else `0.0`. |
| `error_diagnosis_marker` | 0.16 | `1.0` if normalized span text contains any of `contradiction`, `error`, `fix`, `inconsistent`, `incorrect`, `mistake`, `not sure`, `problem`, `reconsider`, `wrong`; else `0.0`. |
| `plan_revision_marker` | 0.14 | `1.0` if normalized span text contains any of `adjust`, `alternative approach`, `backtrack`, `instead`, `new plan`, `redo`, `revise`, `switch`, `try another`; else `0.0`. |
| `alternative_comparison_marker` | 0.10 | `1.0` if normalized span text contains any of `alternative`, `another`, `candidate`, `compare`, `either`, `option`, `or`, `versus`; else `0.0`. |
| `uncertainty_marker` | 0.08 | `1.0` if normalized span text contains any of `could`, `confidence`, `likely`, `maybe`, `might`, `need to check`, `uncertain`; else `0.0`. |
| `span_length_window` | 0.08 | Let `span_tokens` be the normalized span token count. If `<4`, value `0.0`; if `4-11`, `(span_tokens - 4) / 8`; if `12-48`, `1.0`; if `49-96`, `1 - (span_tokens - 48) / 48`; if `>96`, `0.0`; then `clip01`. |
| `relative_position_window` | 0.06 | Let `relative_position = clip01(start_token / max(trace_tokens, 1))`. Feature value is `clip01(1 - abs(relative_position - 0.60) / 0.40)`. |

Missing-value policy:

- Missing or empty `reflection_spans`: mark the sample invalid, emit no score row, and count it against coverage gates.
- Missing `observable_trace`: mark the sample invalid, emit no score row, and count it against coverage gates.
- Missing operation type: use `other`.
- Missing span content: set content marker features and `span_length_window` to `0.0`.
- Missing token offsets: derive `span_tokens` from span content and `trace_tokens` from `observable_trace`; if `start_token` is missing, use `0`.

Tie handling:

- Spearman: average ranks for tied score values and tied target labels.
- Kendall: Kendall tau-b.
- NDCG: ties are sorted by score descending and then `task_type`, `sample_id`, `span_index` for deterministic display only; no target value can be used to break ties.
- AUC: tied score pairs count as `0.5`.

Required output schema:

```json
{
  "sample_id": "string",
  "task_type": "gsm8k | hotpotqa",
  "span_index": 0,
  "score_name": "structurally_calibrated_fma_v2",
  "score": 0.0,
  "score_rule_id": "s_fma_v2_rule_pre_registered_2026_06_01",
  "formula_hash": "sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628",
  "source_fields_used": [
    "observable_trace",
    "reflection_spans",
    "operation_type",
    "span_content",
    "span_token_offsets",
    "task_type"
  ],
  "leakage_status": "clean | fail"
}
```

Any change to the score formula, feature list, weights, normalization, missing-value policy, tie handling, `score_rule_id`, or formula hash after manifest lock invalidates this route and requires a new plan version.

## 3. Fresh-Holdout Design

Output root: `outputs/s_fma_v2_fresh_holdout/`

Machine-readable plan: `configs/s_fma_v2_fresh_holdout.yaml`

Fixed task counts and variation gates:

| Task | Dataset/config/split | Fixed sample count | Minimum valid traces | Minimum eligible spans | Minimum nonzero Delta-U rows |
|---|---|---:|---:|---:|---:|
| GSM8K | `gsm8k/main/test` | 200 | 190 | 150 | 20 |
| HotpotQA | `hotpot_qa/distractor/validation` | 200 | 190 | 150 | 20 |

If a task has fewer than the required nonzero Delta-U rows, the task receives `insufficient_target_variation` and cannot produce `TASK_SPECIFIC_S_FMA_V2_PASS`; the global route stops as `GLOBAL_S_FMA_V2_BLOCKED_INSUFFICIENT_TARGET_VARIATION`.

Fresh non-overlap policy:

- Fresh GSM8K holdout rows must not overlap with any current pilot manifest, trace, replay, Delta-U, candidate score, or baseline row.
- Fresh HotpotQA holdout rows must not overlap with any current pilot manifest, trace, replay, Delta-U, candidate score, or baseline row.
- Current 382 pilot traces are excluded from final validation.
- Manifest edits after scoring or replay invalidate the route.

Required non-overlap keys:

- `sample_id`
- `task_id`
- composite `dataset`, `config`, `split`, `source_index`
- normalized question hash
- reference answer hash
- alias hash

Hash policy:

- `normalized_question_hash`: SHA256 over NFKC-normalized, lowercased question text with collapsed whitespace.
- `reference_answer_hash`: SHA256 over NFKC-normalized, lowercased reference answer text with collapsed whitespace.
- `alias_hash`: SHA256 over sorted, normalized alias strings joined by newline; empty alias list hashes the empty string.
- Any overlap on any required key is a hard stop before scoring, replay, or reporting.

Seed and manifest policy:

- Planning seed: `20260601`.
- Fresh manifest generation is not part of this documentation-only task.
- Fresh manifest must be generated and locked before scoring or replay.
- Manifest lock must store dataset name, config, split, source index, sampled task ID, seed, prompt version, normalized question hash, reference answer hash, alias hash, and SHA256 hash.

Prompt version policy:

- Prompt files must be snapshotted with a prompt version ID before API execution.
- Prompt edits after manifest lock require a new manifest and new plan version.
- Prompt versions used for current pilot may motivate failure analysis but cannot be tuned on current pilot rank performance.

API and model logging:

- Log API date, endpoint, model name, fallback model, service tier, request parameters, response IDs, system fingerprint when available, and SDK or transport version.
- Keep `PREFLIGHT_FAIL_DRIFT` visible if drift persists.
- If API preflight still fails, the estimand must be written as a stochastic repeated-replay estimand with repeated replay and bootstrap confidence intervals; deterministic replay claims are forbidden.

Replay repeat policy:

- Original generation: one accepted trace per manifest row after schema and tag validation.
- Intervention replay: at least 3 repeats per eligible span under nondeterministic replay.
- Key-row replay: at least 5 repeats for sensitivity examples selected by pre-registered criteria that do not use target outcomes.
- Replay failures count against replay success rate and coverage gates.

Cost ceiling:

- Default planning ceiling: USD 150.
- No API execution is allowed from this plan unless the user explicitly approves a fresh-holdout run and budget.
- Spending above the approved ceiling is a hard stop.

Stop conditions:

- Any overlap on any required non-overlap key.
- Any target leakage in scorer inputs.
- Any post-hoc threshold or weight change after seeing fresh-holdout target outcomes.
- Schema success rate below `0.95`.
- Tag extraction success rate below `0.95`.
- Replay success rate below `0.85`.
- Valid trace count below `190` for either task.
- Eligible span count below `150` for either task.
- Nonzero Delta-U count below `20` for either task, reported as `insufficient_target_variation`.
- API drift is not logged and disclosed.
- Both task-specific rank-signal gates fail; in that case the top-tier route stops and the work moves to diagnostic or workshop framing.

## 4. Metrics, Baselines, and Gates

Primary target label for validation: fresh-holdout Delta-U only, computed after the frozen scorer has produced `structurally_calibrated_fma_v2` scores.

Required metrics for `structurally_calibrated_fma_v2` and every required baseline:

- Spearman rank correlation.
- Kendall tau-b rank correlation.
- NDCG@3 and NDCG@5.
- Top-10 percent high-impact AUC.
- Bootstrap confidence intervals with sample-level resampling.

Required fresh-holdout baselines in the same comparison table as v2:

- `s_FMA_v1`
- `random`
- `span_length`
- `relative_position`
- `taxonomy_prior`
- `uniform_reflection_weight`
- `question_difficulty_proxy`

Required reports:

- Per-task reports for GSM8K and HotpotQA.
- Pooled report across tasks.
- Valid trace count.
- Eligible span count.
- Nonzero Delta-U count.
- Replay success rate.
- Leakage audit status.
- API drift disclosure.
- Trajectory controls reported separately from span-level attribution.

`TASK_SPECIFIC_S_FMA_V2_PASS` is evaluated independently for each task and requires all of the following for that task:

- Configured fixed sample count is locked before scoring.
- Valid trace count is at least `190`.
- Eligible span count is at least `150`.
- Nonzero Delta-U count is at least `20`; otherwise stop as `insufficient_target_variation`.
- Full configured coverage for fresh traces, eligible spans, v2 scores, baseline scores, replay rows, and Delta-U rows.
- Leakage audit clean.
- No target leakage and no post-intervention outcome fields in scorer inputs.
- No post-hoc threshold tuning.
- The task-level pre-registered primary rank signal is positive with bootstrap CI lower bound above zero.
- API drift is disclosed; deterministic replay claims are forbidden if preflight drift persists.
- Trajectory controls are reported separately and are not mixed with span-level attribution baselines.

Allowed claim after `TASK_SPECIFIC_S_FMA_V2_PASS`:

- Task-specific support for the passing task.
- Heterogeneous or task-dependent rank-signal evidence.

Blocked after `TASK_SPECIFIC_S_FMA_V2_PASS` alone:

- Cross-task expansion.
- Global confirmation across GSM8K and HotpotQA.
- PRM/filtering design or superiority claims.

`GLOBAL_S_FMA_V2_PASS` requires all of the following:

- GSM8K satisfies `TASK_SPECIFIC_S_FMA_V2_PASS`.
- HotpotQA satisfies `TASK_SPECIFIC_S_FMA_V2_PASS`.
- Both tasks meet the same pre-registered rank-signal standard with bootstrap CI lower bound above zero.
- Pooled rank signal is not negative.
- The v2 score and all required baselines are reported in the same metric table for Spearman, Kendall, NDCG, and AUC.
- No API drift, leakage, manifest overlap, insufficient target variation, coverage, or post-hoc tuning stop condition is active.

Allowed claim after `GLOBAL_S_FMA_V2_PASS`:

- Cross-task fresh-holdout rank-signal support for the pre-registered v2 scorer.
- Designing a larger real-task expansion.

PRM/filtering policy:

- PRM/filtering can be designed only after `GLOBAL_S_FMA_V2_PASS` or a separate explicit `DOWNSTREAM_PRM_FILTERING_VALIDATION_PASS`.
- A single task-specific pass cannot unlock PRM/filtering.
- No PRM/filtering superiority claim is allowed until a downstream experiment is designed, run, and compared against explicit baselines.

Heterogeneity rules:

- If GSM8K passes but HotpotQA does not, the result can only be task-specific or heterogeneous; it is not global confirmation.
- If HotpotQA passes but GSM8K does not, the result can only be task-specific or heterogeneous; it is not global confirmation.
- If pooled and per-task rank signals all fail, stop the top-tier route and reframe as diagnostic or workshop evidence.

## 5. Claim Policy

Claim registry requirements:

- `C_REAL_TASK_PILOT` remains `pilot_blocked`.
- `C_S_FMA_V2_FRESH_HOLDOUT` remains `planned` until fresh non-overlapping artifacts exist and pass the relevant gate.
- `C_PRM_FILTERING` remains `future_validation`.

Allowed wording before the fresh-holdout run:

- The current pilot is a frozen development failure audit.
- `s_FMA_v2` is a planned, preregistered fresh-holdout route.
- Formula hash `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628` identifies the frozen scorer.
- Fresh holdout validation is required before any real-task rank-signal upgrade.
- PRM/filtering validation can be designed only after `GLOBAL_S_FMA_V2_PASS` or a separate downstream validation gate.

Blocked wording:

- `same_pilot_pass_after_redesign_assertion`
- `current_382_trace_v2_validation_assertion`
- `hotpotqa_negative_support_assertion`
- `prm_filtering_superiority_assertion`
- `pre_global_scale_expansion_assertion`
- `task_specific_pass_unlocks_prm_filtering_assertion`

## 6. Readiness Policy

Current manuscript readiness remains blocked.

Reasons:

- Current real-task pilot failed the rank-signal gate.
- Current failure audit is frozen and cannot be upgraded by same-pilot tuning.
- `s_FMA_v2` fresh holdout has not been run.
- API preflight still has `PREFLIGHT_FAIL_DRIFT`.
- No PRM/filtering experiment exists.

Expansion policy:

- No scale expansion before `GLOBAL_S_FMA_V2_PASS`.
- No PRM/filtering design before `GLOBAL_S_FMA_V2_PASS` or a separate explicit downstream validation gate.
- No PRM/filtering superiority claim until a separate downstream experiment is designed, run, and compared against explicit baselines.

## 7. Verification Plan

For this documentation/configuration change:

```powershell
python -m pytest -q
python - <<'PY'
import yaml
yaml.safe_load(open("configs/s_fma_v2_fresh_holdout.yaml", encoding="utf-8"))
PY
rg -n "TASK_SPECIFIC_S_FMA_V2_PASS|GLOBAL_S_FMA_V2_PASS|sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628" paper/s_fma_v2_fresh_holdout_plan.md configs/s_fma_v2_fresh_holdout.yaml paper/claim_registry.md
```

Expected status after this plan lands:

- Current pilot failed.
- Current status remains `PILOT_BLOCKED`.
- Failure audit remains frozen.
- `s_FMA_v2` is planned only.
- Fresh holdout is required for any v2 upgrade.
- Scale expansion is not allowed before `GLOBAL_S_FMA_V2_PASS`.
- PRM/filtering superiority is not allowed before a later, separate downstream validation.
