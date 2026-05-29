# Baseline Integration Summary

Protocol version: `journal_step_impact_v2_3`
Stage 2 protocol version: `fma_v1_2_stage2_confirmatory`
Scope: existing-artifact integration only. No new baselines were run and no missing values were inferred.

## Integration Status

```text
baseline_status: blocked_missing_baselines
submission_status: blocked
```

## Unified Comparison Space

All primary comparisons must use the same step-level prediction frame:

- Prediction target: step-level `Delta U(r_i)`
- Method output: step-level score vector `s_B(r_i)`
- Metrics: ranking correlation, top-k alignment, high-impact step AUC, and confidence intervals when available

FMA is available as a preprojected step-level vector. Required baseline families are mapped in `outputs/baseline_mapping_table.csv`, and they are registered in `outputs/stage2_baseline_results.json`, but none has an independent held-out Stage 2 score vector.

## Unified Comparison Table

| Comparison group | Method or family | Artifact status | target_leakage_status | Integrated? |
|---|---|---|---|---|
| FMA | `fma_v1_2_step_attribution` | evaluated in `outputs/stage2_holdout_validation.json` and `outputs/stage2_projection_audit.json` | not a baseline row | yes |
| Structural-free perturbation baseline | random masking | registered but `not_evaluated_no_stage2_step_scores` | `missing_artifact` | no; blocker |
| Structural-free perturbation baseline | span masking | registered but `not_evaluated_no_stage2_step_scores` | `missing_artifact` | no; blocker |
| Structure control | graph removal | registered but `not_evaluated_no_stage2_step_scores` | `missing_artifact` | no; blocker |
| Structure control | edge dropout | registered but `not_evaluated_no_stage2_step_scores` | `missing_artifact` | no; blocker |
| Optional or unavailable baselines | token dropout, white-box attribution rows, extra structure controls, self-refine, reflexion | registered as unavailable or secondary | `missing_artifact` | no |
| Oracle/control rows | none available | no artifact | not applicable | no |

## Required Baseline Handling

| Family | Required role | Mapping artifact | Stage 2 result artifact | Leakage audit artifact | Integration decision |
|---|---|---|---|---|---|
| random masking | structural-free perturbation baseline | present | no step-level scores | `missing_artifact` | blocker |
| span masking | structural-free perturbation baseline | present | no step-level scores | `missing_artifact` | blocker |
| graph removal | structure control | present | no step-level scores | `missing_artifact` | blocker |
| edge dropout | structure control | present | no step-level scores | `missing_artifact` | blocker |

## Non-Integrated Artifacts

`outputs/structure_degradation_curves.json` and `outputs/projection_robustness.json` are protocol/specification artifacts with empty `results` arrays. They do not provide held-out step-level baseline vectors, rank correlations, AUC values, or confidence intervals.

Existing Phase 5-7 structural artifacts are not substituted for baseline results because doing so would either compare different quantities or risk reusing target-side perturbation measurements as predictions. No baseline row is marked integrated.

## Reviewer Risk

Reviewer could say: the paper reports a held-out FMA signal but does not compare it against required perturbation baselines or structure controls in the same step-level prediction space.

Severity: major for journal submission.

Mitigation: provide clean held-out baseline artifacts or narrow the claim so it no longer implies baseline-integrated validation.
