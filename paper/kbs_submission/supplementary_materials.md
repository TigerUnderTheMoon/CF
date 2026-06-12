# Supplementary Material Descriptions

**Supplementary Figure S1**: Governance diagnostic upset plot. The figure file is `paper/kbs_submission/supplementary/Supplementary_Figure_S1_governance_diagnostic_upset.png`.

**Supplementary Data S1**: Conservative audit trail for failed preliminary routes. The v2.1 full-validation failure and abandonment artifacts are `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` and `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json`. The downstream filtering mini-validation failure artifact is `outputs/s_fma_v2_1_fresh_holdout/v2_1_downstream_filtering_report.json`.

**Supplementary Data S2**: Real-task v3/v3.1 smoke preliminary artifacts. The v3 DELETE smoke report is `outputs/real_task_v3/qwen36_delete_hotfix_20260607/smoke_report.json`; it failed sparse-signal gates with GSM8K 1/25 and HotpotQA 28/35 nonzero Delta-U. The v3.1 REPLACE/masked-span smoke report is `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_report.json`; it failed sparse-signal gates with GSM8K 8/25 and HotpotQA 14/35 nonzero Delta-U. The companion audit is `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json`.

**Supplementary Data S3**: PRM800K locked step-ranking evidence. The v3.6 locked validation report is `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json`; it supports real PRM800K step-label ranking only, with 4,417 locked samples, 34,219 labeled steps, `w_struct` Spearman 0.6113401179642559, raw local utility Spearman -0.07745914322519368, and Holm correction passing.

**Supplementary Data S4**: Frozen PRM baseline context. The v3.7 overlap audit is `outputs/real_task_v3_7_prm_baseline_comparison/training_overlap_audit.json`. The v3.8 locked PRM scoring report is `outputs/real_task_v3_8_prm_locked_scoring/locked_prm_baseline_comparison_report.json`; it supports only an in-distribution, overlap-limited frozen PRM baseline context with frozen PRM prefix-score Spearman 0.2515662235547571 and `w_struct - prm` bootstrap CI [0.34499208448462026, 0.3745467544914783].

**Supplementary Note S1**: Claim boundary. These supplementary files preserve failed and blocked replay/filtering provenance while adding PRM800K step-ranking and overlap-limited frozen PRM baseline-context evidence. They do not add downstream filtering support, PRM training validation, GSM8K/HotpotQA replay validation, causal identification, or claims beyond PRM800K-like process-supervision data.
