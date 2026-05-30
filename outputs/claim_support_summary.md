# Claim Support Summary

Protocol version: `journal_step_impact_v2_3`
Stage 2 protocol version: `fma_v1_2_stage2_confirmatory`

## Claim Decision Labels

| Label | Required condition |
|---|---|
| `supported` | Stage 1 exploratory support only; never a final claim. |
| `confirmed` | Stage 2 held-out results satisfy all pre-registered metric, projection, and stratum gates. |
| `confirmed_weak` | Final-paper wording for Stage 2 confirmation with small effect size. |
| `qualified` | Stage 2 supports the claim with pre-declared limits. |
| `projection-dependent` | Direction or ranking changes across `pi_1`, `pi_2`, `pi_3`, and `pi_4`. |
| `stratum-dependent` | The claim holds in some required strata but not all. |
| `unsupported` | Required evidence is missing, unstable, contradictory, or fails an audit gate. |
| `insufficient_samples` | One or more required Stage 2 strata is underfilled. |

## Audit Gates

| Gate | Status after Stage 2 run |
|---|---|
| Frozen protocol snapshot saved | complete: `outputs/stage2_frozen_protocol.json` |
| Stratified Stage 1 / Stage 2 split saved | complete: `outputs/stage2_split_manifest.json` |
| Projection audit across all `Pi` | complete: `outputs/stage2_projection_audit.json` |
| Held-out Stage 2 validation | complete: `outputs/stage2_holdout_validation.json` |
| High, mid, low, and random strata included | complete: `outputs/stage2_stratified_metrics.json` |
| Stage 2 baseline results saved | complete: `outputs/stage2_baseline_results.json` |
| Baseline target-leakage audit saved | complete: `outputs/stage2_baseline_leakage_audit.json` |
| Leakage audit checklist saved | complete: `outputs/stage2_leakage_audit.json` |
| Claim gating summary saved | complete: `outputs/stage2_claim_gating_summary.md` |

## Current Claim Table

| Claim ID | Decision | rho_mean | rho_ci95 | Effect size | Evidence files | Notes |
|---|---|---:|---|---|---|---|
| C1_rank_generalization | `stratum-dependent` | 0.1628 | [0.0916, 0.2347] | small | `stage2_holdout_validation.json`; `stage2_projection_audit.json`; `stage2_stratified_metrics.json` | Multiple stratum Spearman CIs include zero: S_mid, S_rand |
| C2_projection_robustness | `stratum-dependent` | 0.1628 | [0.0916, 0.2347] | small | `stage2_holdout_validation.json`; `stage2_projection_audit.json`; `stage2_stratified_metrics.json` | Multiple stratum Spearman CIs include zero: S_mid, S_rand |
| C3_stratified_generalization | `stratum-dependent` | 0.1628 | [0.0916, 0.2347] | small | `stage2_holdout_validation.json`; `stage2_projection_audit.json`; `stage2_stratified_metrics.json` | Multiple stratum Spearman CIs include zero: S_mid, S_rand |

## Scope Note

The Stage 2 run evaluates the preprojected FMA step-level vector and the clean required conservative proxy controls. Optional baselines without held-out step-level prediction vectors are explicitly marked unavailable in the leakage audit rather than imputed.
