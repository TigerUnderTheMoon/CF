# Supplementary Material Manifest

This supplementary package documents failed preliminary tests for the diagnostic KBS manuscript. It is not validation evidence and not a downstream PRM/filtering result.

| Supplementary item | Source artifact | Description |
|---|---|---|
| v2.1 full-validation failure audit | `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` | Failed full stochastic validation provenance. |
| v2.1 abandonment audit | `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json` | Strict v2.1 route abandonment provenance. |
| v2.1 downstream mini report | `outputs/s_fma_v2_1_fresh_holdout/v2_1_downstream_filtering_report.json` | Failed downstream filtering mini diagnostic. |
| v3 DELETE smoke report | `outputs/real_task_v3/qwen36_delete_hotfix_20260607/smoke_report.json` | Failed sparse-signal preliminary test: GSM8K 1/25 and HotpotQA 28/35. |
| v3.1 REPLACE/masked-span smoke report | `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_report.json` | Failed sparse-signal preliminary test: GSM8K 8/25 and HotpotQA 14/35. |
| v3.1 companion audit | `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json` | Records implementation/status/next-step inconsistencies in the raw v3.1 report. |

Claim boundary: current status remains `PILOT_BLOCKED`. These files do not add locked validation, downstream filtering support, claim upgrade, or any stronger readiness status.
