# Claim Registry (Methodological Revision)

Purpose: this file is the manuscript claim contract for the SC-FMA methodological contribution. Claims use the same status labels: `supported`, `stratum_dependent`, `pilot_blocked`, `planned`, `failed_validation`, `archived`, `future_validation`.

## Active Claims (Methodological)

| Claim ID | Claim | Status | Artifact owner | Allowed wording | Blocked wording |
|---|---|---|---|---|---|
| `M_SCFMA_CALIBRATION` | SC-FMA produces calibrated supervision weights via convex constrained optimization that balances CIU fidelity against structural consistency. | `supported` | `src/fma/calibration/`; `tests/test_calibration_guarantees.py` (15/15 passing) | SC-FMA is a structural calibration methodology; convex optimization with unique solution | the only way to produce supervision weights |
| `M_SCU_OBJECTIVE` | The SCU objective is strictly convex with unique global minimum, monotonicity for non-redundant steps, variance reduction, and bottleneck protection. | `supported` | `tests/test_calibration_guarantees.py` (G1-G6 all passing); `paper/methodology.md` (Section: Theoretical Properties) | formal convexity, monotonicity, variance reduction, bottleneck guarantees | causal effect identification; mechanism recovery |
| `M_STEP_RANKING` | SC-FMA achieves higher Spearman rank correlation with oracle step labels than raw CIU and heuristic baselines on step importance ranking. | `supported` | `outputs/real_task_v3_6_prm800k_hash/decision_report.json`; `outputs/real_task_v3_6_prm800k_hash/locked_validation_report.json`; `tests/test_ranking.py`; `tests/test_real_task_v3_6_prm800k_hash_validation.py` | superior rank correlation on PRM800K real step labels; outperforms raw CIU and heuristic baselines | universally optimal; beats all possible methods; validates GSM8K/HotpotQA replay |
| `M_ABLATION` | Each SCU constraint term (fidelity, structure, redundancy, bottleneck) independently contributes to ranking quality. | `supported` | `src/fma/calibration/optimizer.py` (ablation via parameter control); `paper/results.md` (ablation table) | each term contributes; ablation supports design | each term is independently necessary under all conditions |
| `M_BASELINE_COMPARISON` | SC-FMA is compared against 6 baseline families (gradient attribution, Shapley, information-theoretic, heuristic, oracle) using multiple metrics and statistical tests. | `supported` | `src/fma/baselines/`; `src/fma/ranking/`; `tests/test_baselines.py` (19/19 passing) | compared against baselines; outperforms heuristics and information-theoretic methods | beats trained PRMs (requires future validation) |
| `M_PRM_BASELINE_CONTEXT` | SC-FMA's PRM800K step-ranking signal is compared against a frozen public PRM scorer on the same locked PRM800K hash split. | `stratum_dependent` | `outputs/real_task_v3_7_prm_baseline_comparison/decision_report.json`; `outputs/real_task_v3_8_prm_locked_scoring/decision_report.json`; `outputs/real_task_v3_8_prm_locked_scoring/locked_prm_baseline_comparison_report.json`; `tests/test_real_task_v3_7_prm_baseline_comparison.py`; `tests/test_real_task_v3_8_prm_locked_scoring.py` | in-distribution PRM baseline comparison with acknowledged PRM800K overlap risk; strengthens baseline context for PRM800K step-ranking | external PRM generalization; beats public PRMs generally; validates PRM training; validates GSM8K/HotpotQA replay |

## Diagnostic Claims (Retained from Diagnostic Phase)

| Claim ID | Claim | Status | Artifact owner | Allowed wording |
|---|---|---|---|---|
| `C_DIAG_LOCAL_STRUCTURAL` | Local utility is more widespread than sparse structural necessity. | `supported` | `outputs/counterfactual_summary.json`; `outputs/structural_diagnostics.json` | diagnostic support; motivates SC-FMA |
| `C_BASELINE_PROXY_CONTROLS` | Required Stage 2 baseline rows are clean conservative proxy controls. | `supported` | `outputs/stage2_baseline_results.json` | clean conservative proxy controls |
| `C_S_FMA_V2_1_EVIDENCE_TARGET` | The v2.1 evidence-target route is retained as failed validation provenance. | `failed_validation` | `outputs/archive/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json`; `paper/submission_readiness_audit.md` | failed/abandoned provenance only; no validation pass |

## Future Validation Claims

| Claim ID | Claim | Status | Allowed wording |
|---|---|---|---|
| `F_PRM_TRAINING` | SC-FMA-calibrated weights improve PRM training over binary supervision. | `future_validation` | future application hypothesis; requires downstream training validation |
| `F_REAL_TASK_SC_FMA` | SC-FMA generalizes to real GSM8K/HotpotQA traces with Qwen3-6B backbone. | `future_validation` | requires passing smoke test and full validation gates |

## Upgrade Rules

- `F_PRM_TRAINING` can move to `supported` only with a passing downstream PRM training validation artifact comparing SC-FMA-supervised PRM vs binary-supervised PRM vs raw CIU-supervised PRM.
- `F_REAL_TASK_SC_FMA` can move to `supported` only with fresh, non-overlapping real-task traces passing preregistered smoke gates and full validation gates.
- `M_PRM_BASELINE_CONTEXT` must remain context-only while PRM800K overlap risk is known or unresolved. It cannot be upgraded to external PRM generalization without a clean non-overlap audit and an independently preregistered external benchmark.
- All diagnostic claims (`C_*`) are retained as motivation for the SC-FMA methodology but are not themselves the primary contribution.
- The methodological claims (`M_*`) constitute the current paper's contribution.
- If PRM800K stratified analysis is blocked, then every active empirical claim used in the KBS package must be downgraded to `stratum_dependent` or `failed_validation`, and the final package must not be labeled submission-ready.

## Legacy Route Status

All prior real-task validation routes (v2, v2.1, v2.2, v3, v3.1) remain in their respective statuses (`failed_validation`, `pilot_blocked`, `archived`) as recorded in the original claim registry. v3.5 PRM800K contiguous split is preserved as failed validation provenance in `outputs/real_task_v3_5_prm800k/failure_audit.json`. v3.6 PRM800K hash-stratified validation supports the step-ranking methodological claim (`M_STEP_RANKING`, `M_STEP_RANKING_REAL_PRM800K`) and does not constitute GSM8K/HotpotQA replay validation. v3.7/v3.8 add in-distribution frozen PRM baseline context (`M_BASELINE_COMPARISON_CONTEXT_ONLY`) only; they do not authorize `F_PRM_TRAINING`, `F_REAL_TASK_SC_FMA`, external PRM generalization, deterministic replay, or causal identification wording.

## Real-Task v3/v3.1 Final Status (2026-06-08)

The real-task replay status remains `PILOT_BLOCKED`: v3 and v3.1 are negative preliminary tests only. They cannot be used for threshold retuning, validation claim upgrades, downstream PRM/filtering gain claims, or any replacement for a fresh preregistered validation route.
