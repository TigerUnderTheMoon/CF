# Submission Lock Audit

Audit date: 2026-06-08
Original audit date: 2026-05-30
Repository: `D:\CF`
Branch: `main`
Scope: submission consistency pass over stored artifacts and paper text, with a 2026-06-08 operational finalization update for line-ending normalization and KBS diagnostic package freeze status. No experiments were rerun, no datasets or models were added, and Stage 2 claim labels were not upgraded.

Current repository-level readiness remains governed by `paper/submission_readiness_audit.md`; this lock audit preserves the Stage 2 consistency boundary and records only the finalization checklist status changes below.

## Status Fields

```text
stage2_status: completed
effect_regime: heterogeneous_stratum_dependent
c1_status: stratum_dependent
c2_status: stratum_dependent
c3_status: stratum_dependent
baseline_status: integrated
submission_status: blocked_for_submission
```

## Verdict

Status: **blocked_for_submission**.

The Stage 2 held-out validation artifacts remain internally consistent with the supplied execution summary. They support a small aggregate FMA rank-alignment signal, not protocol-independent confirmation. C1, C2, and C3 remain `stratum_dependent` because `S_mid` and `S_rand` fail the all-strata requirement.

The required baseline gate is no longer blocked by missing artifacts. `outputs/baseline_artifact_audit.md` found no hidden independent Stage 2 baseline score vectors, so random masking, span masking, graph removal, and edge dropout were evaluated with frozen conservative non-target proxy rules. All four required baselines have 840 held-out step scores and `target_leakage_status: clean`.

Submission readiness remains blocked for final readiness review, citation/package completion, and claim-scope discipline. The clean proxy baselines close the missing-baseline gate but do not turn stratum-dependent Stage 2 evidence into protocol-independent confirmation.

## PRM800K Stratified Decision Gate

The PRM800K locked-split audit-prioritization analysis now controls the submission-status boundary for the KBS package:

| Result tier | Required action |
|---|---|
| `strong` | Retain methodology wording only for PRM800K-like audit prioritization; do not extend to task success, PRM training, or KBS deployment. |
| `moderate` | Weaken title/abstract to "moderate" or "preliminary real-data support"; cover letter must use the same wording. |
| `diagnostic` | Change title to a diagnostic-framework framing; downgrade abstract, conclusion, cover letter, and package manifest. |
| `blocked` | Set `submission_status: blocked_for_submission`; update `paper/claim_registry.md` so active empirical claims are `stratum_dependent` or `failed_validation`; do not mark the final package submission-ready; keep only an internal diagnostic package. |

If the stratified analysis is unavailable, blocked, or fails the hard-stratum/simple-baseline gate, the package remains `blocked_for_submission` until the claim registry and final package are regenerated under the downgraded status.

## Artifact Paths Checked

| Artifact | Status | Use |
|---|---|---|
| `outputs/baseline_artifact_audit.md` | read | hidden-score-vector audit |
| `outputs/stage2_holdout_validation.json` | read | full Stage 2 metrics and claim labels |
| `outputs/stage2_projection_audit.json` | read | projection sign consistency and FMA identity projection policy |
| `outputs/stage2_stratified_metrics.json` | read | required strata and confidence intervals |
| `outputs/stage2_claim_gating_summary.md` | read | manuscript-facing claim labels |
| `outputs/stage2_baseline_results.json` | read | evaluated required baseline rows |
| `outputs/stage2_baseline_leakage_audit.json` | read | target-leakage status values |
| `outputs/baseline_mapping_table.csv` | read | required baseline step-level mappings |

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
| Passing strata | 2/4 |

## Baseline Status

| Baseline / Control | Stage 2 status | target_leakage_status | Step scores | Spearman rho |
|---|---|---|---:|---:|
| random masking | `evaluated_stage2_step_scores` | `clean` | 840 | 0.0155 |
| span masking | `evaluated_stage2_step_scores` | `clean` | 840 | -0.0889 |
| graph removal | `evaluated_stage2_step_scores` | `clean` | 840 | 0.0000 |
| edge dropout | `evaluated_stage2_step_scores` | `clean` | 840 | 0.0284 |

No required baseline uses `Delta U`, `necessity`, `delta_utility`, `attribution_score`, `utility_score`, or `structural_necessity` as a prediction source. Optional baseline rows remain unavailable unless independent score-vector artifacts are later added.

## Final Blocker List

1. C1, C2, and C3 are `stratum_dependent`; none can be described as broad confirmation findings.
2. Required baselines are clean but conservative proxies, not independently rerun perturbation-response experiments.
3. Related-work bibliography anchors are maintained outside this consistency pass.
4. Final venue formatting, figure numbering, and bibliography remain subject to venue/package QA.

Completed operational finalization items:

- Repository line endings have been renormalized under `.gitattributes`; the 2026-06-08 check produced no additional staged changes.
- KBS diagnostic package freeze is represented by the annotated Git tag `kbs-submission-v1`.

## Final Lock Recommendation

Do **not** mark the manuscript ready for submission yet. Mark it as:

> Stage 2 consistency checked; required baselines integrated as clean conservative controls; C1, C2, and C3 remain `stratum_dependent`; `submission_status` is `blocked_for_submission` unless the PRM800K stratified audit-prioritization gate permits a stronger package status.
