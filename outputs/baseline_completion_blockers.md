# Baseline Completion Blockers

Submission status: `blocked`

The missing-artifact blocker for the four required baseline families has been cleared. Random masking, span masking, graph removal, and edge dropout now have clean held-out Stage 2 step-level proxy scores in `outputs/stage2_baseline_results.json`.

## Required Baseline Evidence

| Baseline / Control | Current Stage 2 status | target_leakage_status | Step scores |
|---|---|---|---:|
| random masking | `evaluated_stage2_step_scores` | `clean` | 840 |
| span masking | `evaluated_stage2_step_scores` | `clean` | 840 |
| graph removal | `evaluated_stage2_step_scores` | `clean` | 840 |
| edge dropout | `evaluated_stage2_step_scores` | `clean` | 840 |

## Remaining Caveats

1. These rows are frozen conservative proxy controls, not independently rerun perturbation-response experiments.
2. Optional baseline families remain unavailable unless independent score-vector artifacts are later provided.
3. C1, C2, and C3 remain `stratum_dependent`; baseline integration does not upgrade claim labels.
4. Final submission remains blocked pending readiness review, citation/package completion, and venue formatting.
