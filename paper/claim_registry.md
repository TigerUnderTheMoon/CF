# Claim Registry (Methodological Revision)

Purpose: this file is the manuscript claim contract for the SC-FMA methodological contribution. Claims use the same status labels: `supported`, `stratum_dependent`, `pilot_blocked`, `planned`, `failed_validation`, `archived`, `future_validation`.

## Active Claims (Methodological)

| Claim ID | Claim | Status | Artifact owner | Allowed wording | Blocked wording |
|---|---|---|---|---|---|
| `M_SCFMA_CALIBRATION` | SC-FMA produces calibrated supervision weights via convex constrained optimization that balances CIU fidelity against structural consistency. | `supported` | `src/fma/calibration/`; `tests/test_calibration_guarantees.py` (15/15 passing) | SC-FMA is a structural calibration methodology; convex optimization with unique solution | the only way to produce supervision weights |
| `M_SCU_OBJECTIVE` | The SCU objective is strictly convex with unique global minimum, monotonicity for non-redundant steps, variance reduction, and bottleneck protection. | `supported` | `tests/test_calibration_guarantees.py` (G1-G6 all passing); `paper/methodology.md` (Section: Theoretical Properties) | formal convexity, monotonicity, variance reduction, bottleneck guarantees | causal effect identification; mechanism recovery |
| `M_STEP_RANKING` | SC-FMA achieves higher Spearman rank correlation with oracle step labels than raw CIU and heuristic baselines on step importance ranking. | `supported` | `outputs/downstream_ranking/comparison_report.json`; `tests/test_ranking.py` (22/22 passing) | superior rank correlation; outperforms raw CIU and random baselines | universally optimal; beats all possible methods |
| `M_ABLATION` | Each SCU constraint term (fidelity, structure, redundancy, bottleneck) independently contributes to ranking quality. | `supported` | `src/fma/calibration/optimizer.py` (ablation via parameter control); `paper/results.md` (ablation table) | each term contributes; ablation supports design | each term is independently necessary under all conditions |
| `M_BASELINE_COMPARISON` | SC-FMA is compared against 6 baseline families (gradient attribution, Shapley, information-theoretic, heuristic, oracle) using multiple metrics and statistical tests. | `supported` | `src/fma/baselines/`; `src/fma/ranking/`; `tests/test_baselines.py` (19/19 passing) | compared against baselines; outperforms heuristics and information-theoretic methods | beats trained PRMs (requires future validation) |

## Diagnostic Claims (Retained from Diagnostic Phase)

| Claim ID | Claim | Status | Artifact owner | Allowed wording |
|---|---|---|---|---|
| `C_DIAG_LOCAL_STRUCTURAL` | Local utility is more widespread than sparse structural necessity. | `supported` | `outputs/counterfactual_summary.json`; `outputs/structural_diagnostics.json` | diagnostic support; motivates SC-FMA |
| `C_BASELINE_PROXY_CONTROLS` | Required Stage 2 baseline rows are clean conservative proxy controls. | `supported` | `outputs/stage2_baseline_results.json` | clean conservative proxy controls |

## Future Validation Claims

| Claim ID | Claim | Status | Allowed wording |
|---|---|---|---|
| `F_PRM_TRAINING` | SC-FMA-calibrated weights improve PRM training over binary supervision. | `future_validation` | future application hypothesis; requires downstream training validation |
| `F_REAL_TASK_SC_FMA` | SC-FMA generalizes to real GSM8K/HotpotQA traces with Qwen3-6B backbone. | `future_validation` | requires passing smoke test and full validation gates |

## Upgrade Rules

- `F_PRM_TRAINING` can move to `supported` only with a passing downstream PRM training validation artifact comparing SC-FMA-supervised PRM vs binary-supervised PRM vs raw CIU-supervised PRM.
- `F_REAL_TASK_SC_FMA` can move to `supported` only with fresh, non-overlapping real-task traces passing preregistered smoke gates and full validation gates.
- All diagnostic claims (`C_*`) are retained as motivation for the SC-FMA methodology but are not themselves the primary contribution.
- The methodological claims (`M_*`) constitute the current paper's contribution.

## Legacy Route Status

All prior real-task validation routes (v2, v2.1, v2.2, v3, v3.1) remain in their respective statuses (`failed_validation`, `pilot_blocked`, `archived`) as recorded in the original claim registry. They are preserved as provenance and motivation for the structural calibration approach, but do not constitute current methodological evidence.
