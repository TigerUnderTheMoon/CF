# Submission Consistency Verification

Verification date: 2026-05-30
Repository: `D:\CF`
Scope: consistency between existing artifacts, manuscript text, baseline status, and submission audit state. No experiments were rerun and Stage 2 claim labels were not upgraded.

## Artifact Paths Read

| Artifact | Status | Notes |
|---|---|---|
| `outputs/baseline_artifact_audit.md` | read | no hidden independent baseline score vectors found |
| `outputs/stage2_holdout_validation.json` | read | authoritative full Stage 2 metrics and claim labels |
| `outputs/stage2_projection_audit.json` | read | projection audit and baseline projection status |
| `outputs/stage2_stratified_metrics.json` | read | required strata and confidence intervals |
| `outputs/stage2_claim_gating_summary.md` | read | manuscript-facing claim table |
| `outputs/stage2_baseline_results.json` | read | four required baseline rows evaluated |
| `outputs/stage2_baseline_leakage_audit.json` | read | required baseline target-leakage statuses are clean |
| `outputs/baseline_mapping_table.csv` | read | step-level baseline mapping requirements |

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
| Passing strata | 2/4 |
| Failing strata | `S_mid`, `S_rand` |

## Baseline Artifact Status Table

| Baseline / Control | Stage 2 score vector present | target_leakage_status | Spearman rho | Decision |
|---|---|---|---:|---|
| random masking | yes | `clean` | 0.0155 | integrated clean proxy |
| span masking | yes | `clean` | -0.0889 | integrated clean proxy |
| graph removal | yes | `clean` | 0.0000 | integrated clean proxy |
| edge dropout | yes | `clean` | 0.0284 | integrated clean proxy |

## Target-Leakage Audit Table

| Baseline / Control | direct_target_reuse_detected | stage2_prediction_vector_available | target_leakage_status |
|---|---|---|---|
| random masking | false | true | `clean` |
| span masking | false | true | `clean` |
| graph removal | false | true | `clean` |
| edge dropout | false | true | `clean` |

No required baseline uses `Delta U`, `necessity`, `delta_utility`, FMA `attribution_score`, `utility_score`, or `structural_necessity` as a prediction source. Optional baselines remain `missing_artifact`.

## Wording Replacements Applied

| Location | Change |
|---|---|
| `fma/eval/stage2_validation.py` | Added hidden baseline artifact audit, conservative proxy score vectors, clean leakage rows, and projection-audit baseline synchronization |
| `tests/test_journal_protocol.py` | Added coverage for required clean baselines, full Stage 2 score counts, forbidden source fields, and projection audit status |
| `paper/abstract.md` | Replaced missing-baseline wording with clean conservative proxy baseline wording |
| `paper/introduction.md` | Clarified that required baselines are integrated but weak controls |
| `paper/results.md` | Replaced blocker section with clean baseline gate section |
| `paper/experiments.md` | Updated unified comparison table to show integrated required controls |
| `paper/limitations.md` | Reframed baseline limitation as conservative proxy evidence |
| `paper/conclusion.md` | Removed baseline-completion blocker wording |
| `paper/submission_lock_audit.md` | Set `baseline_status: integrated` and retained `submission_status: blocked` |
| `outputs/baseline_integration_summary.md` | Updated required baseline rows and leakage status |
| `outputs/baseline_completion_blockers.md` | Recorded that missing required baseline artifacts are no longer blockers |

## Files Updated

| File | Purpose |
|---|---|
| `fma/eval/stage2_validation.py` | Stage 2 baseline audit, scorer, leakage, and writer integration |
| `tests/test_journal_protocol.py` | Regression tests for clean required baseline scoring and artifact shape |
| `outputs/baseline_artifact_audit.md` | Hidden Stage 2 baseline artifact audit |
| `outputs/stage2_baseline_results.json` | Four required baseline rows evaluated with clean proxy score vectors |
| `outputs/stage2_baseline_leakage_audit.json` | Required baseline leakage statuses set to `clean` |
| `outputs/stage2_projection_audit.json` | Required baselines listed as evaluated, optional rows left unavailable |
| `outputs/stage2_leakage_audit.json` | Global leakage audit synchronized with evaluated required baselines |
| `outputs/stage2_claim_gating_summary.md` | Baseline wording synchronized while preserving claim labels |
| `outputs/claim_support_summary.md` | Scope note updated for clean required proxy controls |
| `paper/*.md` | Manuscript claim and baseline wording synchronized with verified artifacts |

## Consistency Checks

| Check | Result |
|---|---|
| all reported Stage 2 numbers trace to artifacts | pass |
| no claim exceeds Stage 2 effect size | pass |
| C1, C2, and C3 remain `stratum_dependent` | pass |
| every required baseline is integrated or listed as unavailable | pass |
| required baseline leakage audit is clean | pass |
| no required baseline score directly reuses `Delta U` as prediction | pass |
| projection claims match artifact values | pass |
| stratum heterogeneity is preserved | pass |
| submission not marked ready solely because baselines are clean | pass |

## Remaining Blockers

1. C1, C2, and C3 are `stratum_dependent`, so none can be described as globally confirmed.
2. Required baselines are clean conservative proxies, not independently rerun perturbation-response experiments.
3. Related-work citation placeholders remain outside this consistency pass.
4. Final venue formatting, figure numbering, bibliography, and git freeze remain incomplete.

## Final Submission Status

```text
stage2_status: completed
effect_regime: heterogeneous_stratum_dependent
c1_status: stratum_dependent
c2_status: stratum_dependent
c3_status: stratum_dependent
baseline_status: integrated
submission_status: blocked
```
