# Supplementary Material Descriptions

**Supplementary Figure S1**: Governance diagnostic upset plot. The figure file is `paper/dke_submission/supplementary/Supplementary_Figure_S1_governance_diagnostic_upset.png`.

**Supplementary Data S1**: Conservative audit trail for failed preliminary routes. The v2.1 full-validation failure and abandonment artifacts are `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` and `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json`. The downstream filtering mini-validation failure artifact is `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_downstream_filtering_report.json`.

**Supplementary Data S2**: Real-task v3/v3.1 smoke preliminary artifacts. The v3 DELETE smoke report is `outputs/archive/real_task_v3/qwen36_delete_hotfix_20260607/smoke_report.json`; it failed sparse-signal gates with GSM8K 1/25 and HotpotQA 28/35 nonzero Delta-U. The v3.1 REPLACE/masked-span smoke report is `outputs/archive/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_report.json`; it failed sparse-signal gates with GSM8K 8/25 and HotpotQA 14/35 nonzero Delta-U. The companion audit is `outputs/archive/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json`.

**Supplementary Data S3**: PRM800K locked annotation-distribution evidence. The v3.6 locked validation report is `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json`; it supports PRM800K annotation-order consistency only, with 4,417 locked samples, 34,219 labeled steps, `w_struct` Spearman 0.6113401179642559, raw local utility Spearman -0.07745914322519368, and Holm correction passing.

**Supplementary Data S4**: Frozen PRM baseline context. The v3.7 overlap audit is `outputs/real_task_v3_7_prm_baseline_comparison/training_overlap_audit.json`. The v3.8 locked PRM scoring report is `outputs/real_task_v3_8_prm_locked_scoring/locked_prm_baseline_comparison_report.json`; it supports only an in-distribution, overlap-limited frozen PRM baseline context with frozen PRM prefix-score Spearman 0.2515662235547571 and `w_struct - prm` bootstrap CI [0.34499208448462026, 0.3745467544914783].

**Supplementary Data S5**: PRM800K audit-prioritization context. The offline readout is `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json`, with the human-readable summary at `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md`. It is audit-prioritization context only and does not add PRM-training, filtering, or replay validation evidence.

**Supplementary Note S1**: Scope note. These supplementary files preserve failed and blocked replay/filtering provenance while adding PRM800K annotation-signal evidence, overlap-limited frozen PRM baseline-context evidence, and offline audit-prioritization context. They do not add downstream filtering support, downstream training support, GSM8K/HotpotQA replay-pass evidence, mechanism-recovery claims, or claims beyond PRM800K-like annotation-signal data.

**Supplementary Note S2**: Full derivation of the variance reduction bound (Theorem 3). Contains the complete algebraic expansion of the two-term objective, variance decomposition, and the non-expansive projection argument.

**Supplementary Note S3**: Tightness construction for the bottleneck lower bound (Theorem 4). Contains the explicit $k=2$ construction, the first-order condition $w_1^* = \sqrt{\delta/(4(\alpha+\beta))}$, and the proof that setting $\varepsilon = \sqrt{\delta/(4(\alpha+\beta))}$ makes the bound exact.

**Supplementary Note S4**: SLSQP convergence diagnostics by trace size. Contains the full table of warm-start and cold-start iteration counts and wall-clock times for $k = 3$--$8$, including standard deviations and convergence rate analysis.

**Supplementary Note S5**: Graph construction parameter sensitivity. Contains the full sensitivity table for $\pm 20\%$ perturbation of $\tau_{\text{tfidf}}$ and $w_{\text{topical}}$, including per-trace-size breakdowns and bottleneck count variations.

**Supplementary Note S6**: Stratum-dependent held-out analysis. Contains the full Stage 2 validation results stratified by difficulty tier ($S_{\text{high}}$, $S_{\text{mid}}$, $S_{\text{low}}$, $S_{\text{rand}}$) with bootstrap confidence intervals.

**Supplementary Note S7**: Taxonomy-stratified ablation analysis. Contains the full ablation results broken down by reflective operation category (ERROR_CORRECTION, VERIFICATION, PLANNING, BACKTRACKING, DECOMPOSITION, CONSTRAINT_TRACKING, RETRIEVAL, UNCERTAINTY_MON).
