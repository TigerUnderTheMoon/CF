# Stage 2 Claim Gating Summary

Protocol version: `journal_step_impact_v2_3`
Stage 2 protocol version: `fma_v1_2_stage2_confirmatory`

Stage 2 is confirmatory. Labels are assigned without Stage 2 threshold tuning, projection selection, or adaptive filtering. `confirmed_weak` is final-paper wording for Stage 2 confirmation with small effect size.

| Claim ID | Label | rho_mean | rho_ci95 | CI excludes 0 | Effect size | Passing strata | Projection status | Downgrade reason | Notes |
|---|---|---:|---|---|---|---:|---|---|---|
| C1_rank_generalization | `stratum-dependent` | 0.1628 | [0.0916, 0.2347] | true | small | 2/4 | sign_consistent_positive | Multiple stratum Spearman CIs include zero: S_mid, S_rand | Multiple stratum Spearman CIs include zero: S_mid, S_rand |
| C2_projection_robustness | `stratum-dependent` | 0.1628 | [0.0916, 0.2347] | true | small | 2/4 | sign_consistent_positive | Multiple stratum Spearman CIs include zero: S_mid, S_rand | Multiple stratum Spearman CIs include zero: S_mid, S_rand |
| C3_stratified_generalization | `stratum-dependent` | 0.1628 | [0.0916, 0.2347] | true | small | 2/4 | sign_consistent_positive | Multiple stratum Spearman CIs include zero: S_mid, S_rand | Multiple stratum Spearman CIs include zero: S_mid, S_rand |

## Leakage Controls

- Stage 2 split uses fixed-seed hashing within frozen stratification cells.
- Strata use only allowed pre-perturbation metadata and a fixed random seed.
- S_high, S_mid, and S_low are a mutually exclusive partition; S_rand is an overlapping non-adaptive audit layer.
- Effect-size labels are descriptive only: rho in [0.10, 0.30) is `small`.
- Underfilled strata are labeled `insufficient_samples` rather than dropped.
- The baseline artifact audit first searches for hidden independent vectors; required proxy controls are integrated only when their frozen non-target score vectors are clean.
- Optional baselines without held-out step-level vectors remain unavailable, not imputed.
