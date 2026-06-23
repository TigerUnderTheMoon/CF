# Supplementary Material Manifest

This supplementary package documents the diagnostic manuscript evidence boundary: v3.6/v3.8 provide positive PRM800K step-ranking and in-distribution frozen PRM baseline-context evidence; GSM8K/HotpotQA task-specific replay and downstream filtering were not completed. It is not a downstream training/filtering result.

| Supplementary item | Source artifact | Description |
|---|---|---|
| v2.1 full-validation failure audit | `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` | Failed full stochastic validation provenance. |
| v2.1 abandonment audit | `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json` | Strict v2.1 route abandonment provenance. |
| v2.1 downstream mini report | `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_downstream_filtering_report.json` | Failed downstream filtering mini diagnostic. |
| v3 DELETE smoke report | `outputs/archive/real_task_v3/qwen36_delete_hotfix_20260607/smoke_report.json` | Failed sparse-signal preliminary test: GSM8K 1/25 and HotpotQA 28/35. |
| v3.1 REPLACE/masked-span smoke report | `outputs/archive/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_report.json` | Failed sparse-signal preliminary test: GSM8K 8/25 and HotpotQA 14/35. |
| v3.1 companion audit | `outputs/archive/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json` | Records implementation/status/next-step inconsistencies in the raw v3.1 report. |
| v3.6 PRM800K locked validation report | `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json` | Positive real PRM800K step-label ranking evidence: 4,417 samples, 34,219 steps, `w_struct` Spearman 0.611, raw local utility Spearman -0.077, Holm pass. |
| v3.6 PRM800K decision report | `outputs/real_task_v3_6_prm800k_hash/decision_report.json` | Claim permission artifact for `M_STEP_RANKING` and `M_STEP_RANKING_REAL_PRM800K` only. |
| v3.7 PRM800K overlap audit | `outputs/real_task_v3_7_prm_baseline_comparison/training_overlap_audit.json` | Bidirectional PRM800K contamination audit used to restrict baseline wording to in-distribution comparison with acknowledged overlap risk. |
| v3.8 frozen PRM locked scoring report | `outputs/real_task_v3_8_prm_locked_scoring/locked_prm_baseline_comparison_report.json` | Frozen PRM baseline context: prefix-score Spearman 0.252, `w_struct - prm` bootstrap CI [0.345, 0.375], Holm pass. |
| v3.8 frozen PRM decision report | `outputs/real_task_v3_8_prm_locked_scoring/decision_report.json` | Claim permission artifact for `M_BASELINE_COMPARISON_CONTEXT_ONLY`; broad baseline comparison, PRM training, replay validation, and claims beyond PRM800K-like process-supervision data are not allowed. |

Claim boundary: PRM800K provides positive real-data evidence for step-label ranking and in-distribution frozen PRM baseline comparison. GSM8K/HotpotQA task-specific replay and downstream filtering were not completed and do not provide additional validation evidence. These files do not add downstream filtering support, downstream training support, replay-pass evidence, mechanism-recovery claims, or any stronger readiness status.
