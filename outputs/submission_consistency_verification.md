# Submission Consistency Verification

Verification date: 2026-05-30
Repository: `D:\CF`
Scope: consistency between existing artifacts, manuscript text, baseline status, and submission audit state. No experiments were rerun.

## Artifact Paths Read

| Artifact | Status | Notes |
|---|---|---|
| `outputs/stage2_holdout_validation.json` | read | authoritative full Stage 2 metrics and claim labels |
| `outputs/stage2_projection_audit.json` | read | projection audit and baseline projection status |
| `outputs/stage2_stratified_metrics.json` | read | required strata and stratum confidence intervals |
| `outputs/stage2_claim_gating_summary.md` | read | manuscript-facing claim table |
| `outputs/stage2_baseline_results.json` | read | baseline registration; no evaluated baselines |
| `outputs/stage2_baseline_leakage_audit.json` | read | target-leakage status table |
| `outputs/baseline_mapping_table.csv` | read | step-level baseline mapping requirements |
| `outputs/structure_degradation_curves.json` | read | specification artifact with empty `results` |
| `outputs/projection_robustness.json` | read | specification artifact with empty `results` |

No required artifact path from the prompt was absent. Baseline evidence is still blocked because the existing baseline artifacts record `missing_artifact` for the required baseline score vectors.

## Verified Stage 2 Claim Labels

| Claim | Verified label | Artifact evidence |
|---|---|---|
| C1_rank_generalization | `stratum_dependent` | claim table reports downgrade because `S_mid` and `S_rand` include zero |
| C2_projection_robustness | `stratum_dependent` | projection signs are consistent, but the all-strata gate fails |
| C3_stratified_generalization | `stratum_dependent` | only 2/4 required strata pass |

## Verified Stage 2 Metric Values

| Quantity | Verified value |
|---|---:|
| fma_version | v1.2 |
| stage2_protocol_version | fma_v1_2_stage2_confirmatory |
| Stage 2 traces | 280 |
| Stage 2 steps | 840 |
| Full Stage 2 Spearman rho | 0.1628 |
| Full Stage 2 95 percent CI | [0.0916, 0.2347] |
| Effect-size label | small |
| Projection signs | positive for `pi_1`, `pi_2`, `pi_3`, `pi_4` |
| Projection variance across `pi_1`-`pi_4` | 0.0000 |
| Passing strata | 2/4 |
| Failing strata | `S_mid`, `S_rand` |

## Stratum Status Table

| Stratum | rho | CI summary | Gate |
|---|---:|---|---|
| `S_high` | 0.2372 | all projection lower bounds above zero | pass |
| `S_low` | 0.1283 | all projection lower bounds above zero | pass |
| `S_mid` | 0.1233 | `pi_3` and `pi_4` lower bounds include zero | fail |
| `S_rand` | 0.0688 | all projection lower bounds include zero | fail |

## Baseline Artifact Status Table

| Baseline / Control | Mapping present | Stage 2 result vector present | target_leakage_status | Decision |
|---|---|---|---|---|
| random masking | yes | no | `missing_artifact` | blocker |
| span masking | yes | no | `missing_artifact` | blocker |
| graph removal | yes | no | `missing_artifact` | blocker |
| edge dropout | yes | no | `missing_artifact` | blocker |

`outputs/stage2_baseline_results.json` reports `evaluated_baselines: 0`, `not_evaluated_baselines: 13`, and `fabricated_baseline_scores: false`.

## Target-Leakage Audit Table

| Baseline / Control | direct_target_reuse_detected | stage2_prediction_vector_available | target_leakage_status |
|---|---|---|---|
| random masking | false | false | `missing_artifact` |
| span masking | false | false | `missing_artifact` |
| graph removal | false | false | `missing_artifact` |
| edge dropout | false | false | `missing_artifact` |

No required baseline result artifact was available, so no baseline score could be verified as `clean`. Missing baselines are not treated as target-leaking; they are blockers. Existing structural necessity or perturbation artifacts were not reused as baseline predictions because that could collapse prediction `s_B(r_i)` into the evaluation target `Delta U(r_i)`.

## Context Match Check

The supplied Stage 2 summary matches the verified artifacts on fma_version, Stage 2 protocol version, claim labels, and baseline leakage status. No artifact-context mismatch was found. Stale local wording that used a weaker nonzero-only effect-regime label or referenced an obsolete non-Stage 2 baseline-result path was corrected to the verified Stage 2 artifact state.

## Wording Replacements Applied

| Location | Change |
|---|---|
| `paper/abstract.md` | Added Stage 2 `stratum_dependent` labels and blocked baseline status |
| `paper/introduction.md` | Added Stage 2 all-strata caveat and baseline-blocked submission state |
| `paper/results.md` | Added baseline gate section and changed claim labels to `stratum_dependent` |
| `paper/experiments.md` | Defined the unified comparison space and separated FMA, perturbation baselines, structure controls, unavailable rows, and oracle/control rows |
| `paper/limitations.md` | Replaced obsolete non-Stage 2 baseline-result wording with the verified Stage 2 baseline artifact status |
| `paper/conclusion.md` | Replaced hyphenated status wording with `stratum_dependent` and retained blocked baseline conclusion |
| `paper/submission_lock_audit.md` | Synchronized status fields to `heterogeneous_stratum_dependent`, blocked baselines, and blocked submission |
| `outputs/baseline_integration_summary.md` | Rebuilt integration table from existing Stage 2 baseline and leakage artifacts |
| `outputs/baseline_completion_blockers.md` | Listed required baseline blockers from current artifact statuses |

## Files Updated

- `paper/abstract.md`
- `paper/introduction.md`
- `paper/results.md`
- `paper/experiments.md`
- `paper/limitations.md`
- `paper/conclusion.md`
- `paper/submission_lock_audit.md`
- `outputs/baseline_integration_summary.md`
- `outputs/baseline_completion_blockers.md`
- `outputs/submission_consistency_verification.md`

## Consistency Checks

| Check | Result |
|---|---|
| all reported Stage 2 numbers trace to artifacts | pass |
| no claim exceeds Stage 2 effect size | pass |
| no conclusion contradicts confidence interval bounds | pass |
| C1 is not described as globally confirmed | pass |
| C2 is not described as globally confirmed | pass |
| C3 is never described as globally confirmed | pass |
| every required baseline is integrated or listed as blocker | pass |
| baseline leakage audit is complete enough to mark unavailable rows | pass with blocker: all required rows are `missing_artifact` |
| projection claims match artifact values | pass |
| stratum heterogeneity is preserved | pass |
| submission blocked if baseline integration incomplete | pass |
| submission blocked if all baseline leakage statuses are `missing_artifact` | pass |

## Remaining Blockers

1. Required baseline families are not integrated: random masking, span masking, graph removal, and edge dropout.
2. Required baseline rows have `target_leakage_status: missing_artifact`, not `clean`.
3. C1, C2, and C3 are `stratum_dependent`, so none can be described as globally confirmed.
4. Related-work citation placeholders remain outside this consistency pass.
5. Final venue formatting, figure numbering, bibliography, and git freeze remain incomplete.

## Final Submission Status

```text
stage2_status: completed
effect_regime: heterogeneous_stratum_dependent
c1_status: stratum_dependent
c2_status: stratum_dependent
c3_status: stratum_dependent
baseline_status: blocked_missing_baselines
submission_status: blocked
```
