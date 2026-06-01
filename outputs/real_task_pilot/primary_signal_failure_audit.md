# Primary Signal Failure Audit

Scope: read-only diagnosis of the current real-task pilot primary signal failure. This report does not rerun API generation, expand GSM8K/HotpotQA scale, train PRM/filtering models, tune the current scorer to the current pilot rows, or rewrite historical Phase 5-7 artifacts.

Structured companion artifact: `outputs/real_task_pilot/primary_signal_failure_audit.json`.

## Artifact Status

Source artifacts:

- `outputs/real_task_pilot/readiness_audit.json`
- `outputs/real_task_pilot/rank_signal_report.json`
- `outputs/real_task_pilot/bootstrap_ci_report.json`
- `outputs/real_task_pilot/structurally_calibrated_fma_scores.jsonl`
- `outputs/real_task_pilot/real_task_delta_u.jsonl`
- `outputs/real_task_pilot/pilot_traces.jsonl`
- `outputs/real_task_pilot/real_task_replay_results.jsonl`
- `outputs/real_task_pilot/trajectory_controls_report.json`
- `outputs/real_task_pilot/api_preflight_report.json`
- `outputs/real_task_pilot/structurally_calibrated_fma_leakage_audit.json`

Current status:

- `pilot_pass`: `false`
- `status`: `PILOT_BLOCKED`
- `evidence_completion.status`: `PILOT_EVIDENCE_COMPLETE`
- `primary_signal.available`: `true`
- `primary_signal.name`: `structurally_calibrated_fma`
- `primary_signal.target_leakage_status`: `clean`
- Blockers: `PILOT_FAIL_SIGNAL`, `PREFLIGHT_FAIL_DRIFT`

Diagnosis label: evidence-complete but signal-failed. This is not a missing-signal case: the primary signal exists and is leakage-clean, but it failed the rank-signal gate.

## Main Diagnosis

`structurally_calibrated_fma` fails because it does not rank the observed exact-match Delta-U signal in this pilot. The strongest observed failure drivers are:

1. Delta-U is extremely sparse and zero-inflated: 362 of 382 rows are exactly zero.
2. The score is not constant, but it is task-separated and miscalibrated for the sparse pilot objective: GSM8K scores are much higher than HotpotQA scores, while the rare positive Delta-U rows are not concentrated at high score.
3. HotpotQA exact-match creates noisy negative signal and near-miss artifacts; this is a limitation only, not a replacement for the primary metric.
4. All retained spans are `verification`, so the pilot cannot diagnose reflection-type heterogeneity.
5. API preflight remains failed with `PREFLIGHT_FAIL_DRIFT`; current replay evidence is nondeterministic repeated replay, not deterministic replay evidence.

## Delta-U Distribution

| Scope | n | zero | positive | negative | mean | median | nonzero rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| pooled | 382 | 362 (94.76%) | 8 (2.09%) | 12 (3.14%) | -0.0079 | 0.0000 | 5.24% |
| GSM8K | 200 | 197 (98.50%) | 2 (1.00%) | 1 (0.50%) | 0.0017 | 0.0000 | 1.50% |
| HotpotQA | 182 | 165 (90.66%) | 6 (3.30%) | 11 (6.04%) | -0.0183 | 0.0000 | 9.34% |

Interpretation: the primary target is too sparse for the current score to show a stable positive rank relation. HotpotQA contributes most of the nonzero rows and most of the negative rows.

## Score Distribution

| Scope | n | min | p05 | median | mean | p95 | max | unique | skew |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pooled | 382 | 0.0000 | 0.1786 | 0.5256 | 0.5400 | 0.9532 | 1.0000 | 378 | 0.1615 |
| GSM8K | 200 | 0.3826 | 0.4888 | 0.7890 | 0.7563 | 0.9703 | 1.0000 | 197 | -0.3671 |
| HotpotQA | 182 | 0.0000 | 0.1556 | 0.2831 | 0.3022 | 0.5271 | 0.8754 | 181 | 1.1686 |

Interpretation: the score is not nearly constant. The larger problem is calibration: the score distribution separates tasks more strongly than it separates positive versus nonpositive Delta-U. HotpotQA is also right-skewed, with a small high-score tail that does not correspond to positive Delta-U.

## Score and Delta-U Alignment

| Scope | Spearman rho | 95% CI | CI lower > 0? |
|---|---:|---:|---:|
| pooled | -0.0182 | [-0.1180, 0.0777] | false |
| GSM8K | -0.0199 | [-0.1691, 0.1375] | false |
| HotpotQA | -0.2322 | [-0.3433, -0.1059] | false |

Decile check:

| Scope | decile n | bottom-decile mean Delta-U | top-decile mean Delta-U | top-decile positives | top-decile nonpositive |
|---|---:|---:|---:|---:|---:|
| pooled | 39 | 0.0513 | 0.0256 | 1 | 38 |
| GSM8K | 20 | 0.0167 | 0.0000 | 0 | 20 |
| HotpotQA | 19 | 0.0175 | -0.1053 | 0 | 19 |

High-score false positives:

| sample_id | task | score | Delta-U | original | intervened mean | note |
|---|---|---:|---:|---:|---:|---|
| `gsm8k-00534` | GSM8K | 1.0000 | 0.0000 | 1.0 | 1.0 | high score, no intervention sensitivity |
| `gsm8k-00353` | GSM8K | 0.9862 | 0.0000 | 1.0 | 1.0 | high score, no intervention sensitivity |
| `gsm8k-00450` | GSM8K | 0.9810 | 0.0000 | 1.0 | 1.0 | high score, no intervention sensitivity |
| `gsm8k-00395` | GSM8K | 0.9769 | 0.0000 | 1.0 | 1.0 | high score, no intervention sensitivity |
| `gsm8k-00675` | GSM8K | 0.9757 | 0.0000 | 1.0 | 1.0 | high score, no intervention sensitivity |

Low-score false negatives:

| sample_id | task | score | Delta-U | original | intervened mean | note |
|---|---|---:|---:|---:|---:|---|
| `hotpotqa-00114` | HotpotQA | 0.1627 | 0.3333 | 1.0 | 0.6667 | low score, positive Delta-U |
| `hotpotqa-01777` | HotpotQA | 0.1914 | 0.6667 | 1.0 | 0.3333 | low score, positive Delta-U |
| `hotpotqa-03765` | HotpotQA | 0.1955 | 0.3333 | 1.0 | 0.6667 | low score, positive Delta-U |
| `hotpotqa-05258` | HotpotQA | 0.2030 | 0.6667 | 1.0 | 0.3333 | low score, positive Delta-U |
| `hotpotqa-00776` | HotpotQA | 0.2418 | 0.3333 | 1.0 | 0.6667 | low score, positive Delta-U |

Interpretation: this is a rank failure, not only a confidence-interval failure. Top-score rows are mostly insensitive, and multiple low-score HotpotQA rows have positive Delta-U.

## Group Diagnostics

| Group | n | mean score | mean Delta-U | nonzero rate | positive rate | negative rate | Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
| task: GSM8K | 200 | 0.7563 | 0.0017 | 1.50% | 1.00% | 0.50% | -0.0199 |
| task: HotpotQA | 182 | 0.3022 | -0.0183 | 9.34% | 3.30% | 6.04% | -0.2322 |
| reflection: verification | 382 | 0.5400 | -0.0079 | 5.24% | 2.09% | 3.14% | -0.0182 |
| relative position: [0,.25) | 1 | 0.0000 | 0.0000 | 0.00% | 0.00% | 0.00% | n/a |
| relative position: [.25,.5) | 304 | 0.4872 | -0.0099 | 5.92% | 2.30% | 3.62% | -0.0523 |
| relative position: [.5,.75) | 77 | 0.7551 | 0.0000 | 2.60% | 1.30% | 1.30% | 0.0743 |
| span length: <50 tokens | 352 | 0.5270 | -0.0047 | 5.11% | 2.27% | 2.84% | -0.0352 |
| span length: 50-74 tokens | 30 | 0.6922 | -0.0444 | 6.67% | 0.00% | 6.67% | 0.2772 |

Interpretation:

- Reflection type cannot explain the failure because all rows are `verification`.
- Position contributes a distribution bias: most rows are in `[.25,.5)`, while the higher-score `[.5,.75)` bin has no positive mean Delta-U.
- Span length is not a decisive explanation. The longer 50-74 token bin has negative mean Delta-U, but only 30 rows.

## HotpotQA Exact-Match Diagnostic

HotpotQA is the only task with a clearly negative task-level rank signal:

- Spearman rho: `-0.2322`
- 95% CI: `[-0.3433, -0.1059]`
- Negative Delta-U rows: 11 of 182
- Positive Delta-U rows: 6 of 182

Exact-match limitations observed from the stored traces:

- Nonempty answer aliases in HotpotQA traces: 0 of 182.
- Original exact-match false rows with positive normalized token F1: 63 of 182 (34.62%).
- Negative Delta-U rows whose original answer has positive normalized token F1 against the reference: 6 of 11 (54.55%).
- HotpotQA replay rows with more than one final answer across repeats: 47 of 182 (25.82%).
- HotpotQA replay rows with correctness variation across repeats: 13 of 182 (7.14%).

Examples of exact-match-sensitive HotpotQA rows:

| sample_id | score | Delta-U | original answer | reference answer | token F1 | replay pattern |
|---|---:|---:|---|---|---:|---|
| `hotpotqa-00927` | 0.5632 | -1.0000 | EA-18G Growler | Boeing EA-18G Growler | 0.8571 | all three replays exact-correct |
| `hotpotqa-02044` | 0.4745 | -0.3333 | Duval County, Florida | Duval County | 0.8000 | one exact-correct, two exact-false |
| `hotpotqa-06167` | 0.4439 | -0.6667 | Taylor Swift, Max Martin, and Shellback | Max Martin and Shellback | 0.8000 | two exact-correct, one exact-false |
| `hotpotqa-03206` | 0.2651 | -0.3333 | Prime Minister of Denmark / President of the Council | Prime Minister of Denmark | 0.7273 | one exact-correct, two exact-false |

Interpretation: HotpotQA exact-match noise plausibly amplifies the negative task-level signal, especially for alias-like or over-specified answers. This does not rescue the primary gate. The primary artifact metric is exact-match Delta-U, and the exact-match rank signal fails.

## Leakage Audit

The leakage audit is clean:

- `target_leakage_status`: `clean`
- `target_leakage_detected`: `false`
- Checks: 382
- Forbidden fields used: none
- Allowed source-field union: `entity_count`, `number_count`, `observable_trace`, `question`, `question_length`, `reflection_spans`, `sample_id`, `supporting_fact_count`, `task_type`

Interpretation: the failure should not be described as target leakage. The available primary score avoids forbidden target-side fields such as `delta_u`, `correctness`, `final_answer`, `reference_answer`, `original_score`, and `intervened_score`.

## API Drift and Replay Status

`outputs/real_task_pilot/api_preflight_report.json` reports:

- `status`: `fail`
- `failure_codes`: `PREFLIGHT_FAIL_DRIFT`
- `records_evaluated`: 20
- JSON parse, schema, and tag extraction success rates: 1.0
- `determinism_drift_max`: `null`

Replay diagnostics from the stored repeated replay outputs:

- Rows with more than one final answer across repeats: 68 of 382 (17.80%).
- Rows with correctness variation across repeats: 14 of 382 (3.66%).

Interpretation: the current pilot can only be described as nondeterministic repeated replay evidence. It must not be described as deterministic replay evidence.

## Claim-Safe Conclusion

Current pilot outcome: failed.

Failure type: evidence-complete but signal-failed.

Allowed wording:

- The real-task pilot evidence is complete for the configured pilot artifacts.
- The leakage-clean primary signal is available.
- The primary signal failed the rank-signal gate.
- The pilot remains blocked by `PILOT_FAIL_SIGNAL` and `PREFLIGHT_FAIL_DRIFT`.

Blocked wording:

- Treating this as an absent-candidate case.
- HotpotQA negative signal supports the claim.
- The real-task pilot passed.
- Expansion to scale is justified from these rows.
- PRM/filtering superiority is established.

Next step, if continuing the real-task path: preregister an `s_FMA_v2` proposal and validate it only on a fresh holdout. The current pilot rows can motivate the diagnosis, but they cannot upgrade the claim.
