# Supplementary Material Descriptions

**Supplementary Data S1**: Claim-safe audit trail for failed boundary routes. The v2.1 full-validation failure and abandonment artifacts are `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` and `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json`. The downstream filtering mini-validation failure artifact is `outputs/s_fma_v2_1_fresh_holdout/v2_1_downstream_filtering_report.json`.

**Supplementary Data S2**: Real-task v3/v3.1 smoke boundary artifacts. The v3 DELETE smoke report is `outputs/real_task_v3/qwen36_delete_hotfix_20260607/smoke_report.json`; it failed sparse-signal gates with GSM8K 1/25 and HotpotQA 28/35 nonzero Delta-U. The v3.1 REPLACE/masked-span smoke report is `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_report.json`; it failed sparse-signal gates with GSM8K 8/25 and HotpotQA 14/35 nonzero Delta-U. The companion audit is `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json`.

**Supplementary Note S1**: Claim boundary. These supplementary files preserve failed and blocked provenance. They do not add locked validation, downstream filtering support, claim upgrade, or any status beyond `PILOT_BLOCKED`.
