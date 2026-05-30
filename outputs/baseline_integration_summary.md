# Baseline Integration Summary

Protocol version: `journal_step_impact_v2_3`
Stage 2 protocol version: `fma_v1_2_stage2_confirmatory`
Scope: existing-artifact integration plus frozen conservative non-target proxy scoring. No experiments were rerun and no missing values were inferred from `Delta U`.

## Integration Status

```text
baseline_status: integrated
submission_status: blocked
```

## Unified Comparison Space

All primary comparisons use the same step-level prediction frame:

- Prediction target: step-level `Delta U(r_i)`
- Method output: step-level score vector `s_B(r_i)`
- Metrics: ranking correlation, top-k alignment, high-impact step AUC, and confidence intervals

`outputs/baseline_artifact_audit.md` found no hidden independent Stage 2 baseline score vectors. The required baseline rows were therefore evaluated with frozen conservative proxy rules that do not use target-side fields.

## Unified Comparison Table

| Comparison group | Method or family | Artifact status | target_leakage_status | Integrated? |
|---|---|---|---|---|
| FMA | `fma_v1_2_step_attribution` | evaluated in `outputs/stage2_holdout_validation.json` | not a baseline row | yes |
| Structural-free perturbation baseline | random masking | 840 proxy scores | `clean` | yes |
| Structural-free perturbation baseline | span masking | 840 proxy scores | `clean` | yes |
| Structure control | graph removal | 840 proxy scores | `clean` | yes |
| Structure control | edge dropout | 840 proxy scores | `clean` | yes |
| Optional or unavailable baselines | token dropout, white-box attribution rows, extra structure controls, self-refine, reflexion | no independent score vector | `missing_artifact` | no |
| Oracle/control rows | none available | no artifact | not applicable | no |

## Required Baseline Handling

| Family | Score rule | Stage 2 scores | Spearman rho | Integration decision |
|---|---|---:|---:|---|
| random masking | stable hash over `trace_id`, `step_idx`, and frozen seed | 840 | 0.0155 | integrated clean proxy |
| span masking | normalized span token count from graph node content | 840 | -0.0889 | integrated clean proxy |
| graph removal | normalized incident graph degree | 840 | 0.0000 | integrated clean proxy |
| edge dropout | frozen edge-dropout incident weight, p=0.15 | 840 | 0.0284 | integrated clean proxy |

## Leakage Decision

The required baseline rows do not use `Delta U`, `necessity`, `delta_utility`, `attribution_score`, `utility_score`, or `structural_necessity` as prediction sources. `outputs/stage2_baseline_leakage_audit.json` marks all four required rows as `clean`.

## Reviewer Risk

Reviewer could say: the required baselines are conservative proxy controls rather than independently rerun perturbation-response baselines.

Severity: medium to major, depending on venue expectations.

Mitigation: present them as clean conservative controls, not as strong empirical competitors or superiority evidence.
