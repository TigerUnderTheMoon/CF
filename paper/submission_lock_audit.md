# Submission Lock Audit

Audit date: 2026-05-30
Repository: `D:\CF`
Branch: `main`
Scope: submission consistency pass over stored artifacts and paper text. No experiments were rerun, no datasets or models were added, and missing baseline results were not inferred.

## Status Fields

```text
stage2_status: completed
effect_regime: heterogeneous_stratum_dependent
c1_status: stratum_dependent
c2_status: stratum_dependent
c3_status: stratum_dependent
baseline_status: blocked_missing_baselines
submission_status: blocked
```

## Verdict

Status: **blocked**.

The Stage 2 held-out validation artifacts are present and internally consistent with the supplied execution summary. They support a small aggregate FMA rank-alignment signal, not global confirmation. C1, C2, and C3 are `stratum_dependent` because the global claim gate requires the full Stage 2 set, all four strata, all projections under sign consistency, and no worst-case projection collapse. `S_mid` and `S_rand` fail that all-strata requirement.

Submission readiness remains blocked because required baseline evidence is unavailable in the unified step-level prediction space. The repository contains baseline mapping and audit artifacts, but random masking, span masking, graph removal, and edge dropout have no independent held-out score vector `s_B(r_i)` and are marked `missing_artifact`.

## Stage 2 Artifact Paths Checked

| Artifact | Status | Use |
|---|---|---|
| `outputs/stage2_holdout_validation.json` | read | full Stage 2 metrics and claim labels |
| `outputs/stage2_projection_audit.json` | read | projection sign consistency and FMA identity projection policy |
| `outputs/stage2_stratified_metrics.json` | read | required strata, stratum gates, and confidence intervals |
| `outputs/stage2_claim_gating_summary.md` | read | manuscript-facing claim labels |
| `outputs/stage2_baseline_results.json` | read | baseline registration and not-evaluated statuses |
| `outputs/stage2_baseline_leakage_audit.json` | read | target-leakage status values |
| `outputs/baseline_mapping_table.csv` | read | required baseline step-level mappings |
| `outputs/structure_degradation_curves.json` | read | specification artifact with empty `results` |
| `outputs/projection_robustness.json` | read | projection specification artifact with empty `results` |

## Claim Label Table

| Claim | Verified label | Evidence note |
|---|---|---|
| C1 rank generalization | `stratum_dependent` | full Stage 2 rho is positive and small, but only 2/4 strata pass |
| C2 projection robustness | `stratum_dependent` | signs are positive across `pi_1`-`pi_4`, but the all-strata gate fails |
| C3 stratified generalization | `stratum_dependent` | `S_mid` and `S_rand` include zero in required confidence-interval checks |

## Verified Stage 2 Values

| Item | Verified value |
|---|---:|
| Stage 2 traces | 280 |
| Stage 2 steps | 840 |
| Full Stage 2 Spearman rho | 0.1628 |
| Full Stage 2 rho CI | [0.0916, 0.2347] |
| Effect-size label | small |
| Projection signs | positive for `pi_1`, `pi_2`, `pi_3`, `pi_4` |
| Projection variance across `pi_1`-`pi_4` | 0.0000 |

## Stratum Heterogeneity Note

| Stratum | rho | CI summary | Gate |
|---|---:|---|---|
| `S_high` | 0.2372 | all projection CIs above zero | pass |
| `S_low` | 0.1283 | all projection CIs above zero | pass |
| `S_mid` | 0.1233 | `pi_3` and `pi_4` lower bounds include zero | fail |
| `S_rand` | 0.0688 | all projection CIs include zero | fail |

The artifact downgrade reason is: `Multiple stratum Spearman CIs include zero: S_mid, S_rand`.

## Projection Audit Summary

FMA is already represented as a step-level vector. The projection audit therefore materializes `pi_1` through `pi_4` as identity mappings for FMA and checks reporting completeness and sign consistency. It must not be described as nontrivial token-to-step projection robustness. Worst-case projection reporting is present; best-projection selection is not used.

## Baseline Artifact Status

| Baseline / Control | Required role | Mapping status | Stage 2 result status | target_leakage_status | Submission effect |
|---|---|---|---|---|---|
| random masking | structural-free perturbation baseline | present | `not_evaluated_no_stage2_step_scores` | `missing_artifact` | blocker |
| span masking | structural-free perturbation baseline | present | `not_evaluated_no_stage2_step_scores` | `missing_artifact` | blocker |
| graph removal | structure control | present | `not_evaluated_no_stage2_step_scores` | `missing_artifact` | blocker |
| edge dropout | structure control | present | `not_evaluated_no_stage2_step_scores` | `missing_artifact` | blocker |

`outputs/structure_degradation_curves.json` and `outputs/projection_robustness.json` are protocol/specification artifacts with empty `results` arrays. They do not provide held-out step-level baseline vectors or baseline metrics.

## Target-Leakage Audit Status

All required baseline rows are `missing_artifact`. No direct target reuse was detected because no baseline prediction vector was available, but no baseline can be marked `clean`. Existing structural necessity or perturbation quantities were not substituted for `s_B(r_i)` because that would risk comparing target-side quantities against `y_i = Delta_U(r_i)`.

## Final Blocker List

1. Required baselines are not integrated: random masking, span masking, graph removal, and edge dropout.
2. Required baseline rows have `target_leakage_status: missing_artifact`, not `clean`.
3. C1, C2, and C3 are `stratum_dependent`; none can be described as globally confirmed.
4. Related-work citation placeholders remain outside this consistency pass.
5. Final venue formatting, figure numbering, bibliography, and git freeze remain incomplete.

## Final Lock Recommendation

Do **not** mark the manuscript ready for submission. Mark it as:

> Stage 2 consistency checked; C1, C2, and C3 remain `stratum_dependent`, required baseline artifacts are missing, and `submission_status` is `blocked`.
