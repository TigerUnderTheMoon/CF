# Claim Registry

Purpose: this file is the manuscript claim contract. Proposal language is not evidence. A claim can be upgraded only when the listed artifacts exist and the listed gates pass.

Status labels:

- `supported`: current artifacts support the bounded claim.
- `stratum_dependent`: current artifacts support the claim only with explicit heterogeneity limits.
- `pilot_blocked`: pilot infrastructure exists, but readiness gates block evidence use.
- `planned`: preregistered route; no validation result yet.
- `future_validation`: planned work; not a current result.

## Active Claims

| Claim ID | Claim | Status | Artifact owner | Allowed wording | Blocked wording |
|---|---|---|---|---|---|
| `C_DIAG_LOCAL_STRUCTURAL` | Local utility is more widespread than sparse structural necessity in stored reflective traces. | `supported` | `outputs/counterfactual_summary.json`; `outputs/structural_diagnostics.json`; `outputs/redundancy_analysis.json`; `paper/results.md` | diagnostic support; local utility vs structural necessity | downstream improvement; broad superiority |
| `C_STAGE2_RANK_SIGNAL` | Stage 2 held-out validation shows a low-magnitude aggregate rank signal with heterogeneous strata. | `stratum_dependent` | `outputs/stage2_holdout_validation.json`; `outputs/stage2_claim_gating_summary.md`; `outputs/stage2_stratified_metrics.json` | weak aggregate alignment; stratum-dependent support | protocol-independent confirmation; universal generalization |
| `C_BASELINE_PROXY_CONTROLS` | Required Stage 2 baseline rows are clean conservative proxy controls. | `supported` | `outputs/stage2_baseline_results.json`; `outputs/stage2_baseline_leakage_audit.json`; `outputs/baseline_integration_summary.md` | clean conservative proxy controls | strong perturbation-response baselines; reviewer-proof superiority |
| `C_REAL_TASK_PILOT` | GSM8K/HotpotQA real-task evidence is guarded pilot evidence only. | `pilot_blocked` | `outputs/real_task_pilot/readiness_audit.json`; `outputs/real_task_pilot/rank_signal_report.json`; `outputs/real_task_pilot/real_task_delta_u.jsonl`; `outputs/real_task_pilot/structurally_calibrated_fma_scores.jsonl`; `outputs/real_task_pilot/primary_signal_failure_audit.md` | pilot evidence complete but rank signal not supported; primary signal available but failed rank-signal gate; blocked by signal/API drift | `scale_ready_real_task_support_assertion` |
| `C_S_FMA_V2_FRESH_HOLDOUT` | `structurally_calibrated_fma_v2` is a planned preregistered fresh-holdout route, not a completed validation. | `planned` | `paper/s_fma_v2_fresh_holdout_plan.md`; `configs/s_fma_v2_fresh_holdout.yaml`; future `outputs/s_fma_v2_fresh_holdout/*` artifacts | current pilot is frozen as development failure audit; v2 is planned only; fresh holdout required; formula hash `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628`; task-specific evidence requires `TASK_SPECIFIC_S_FMA_V2_PASS`; cross-task expansion requires `GLOBAL_S_FMA_V2_PASS` | `same_pilot_pass_assertion`; `current_trace_v2_validation_assertion`; `same_pilot_tuning_validation_assertion`; `single_task_global_unlock_assertion` |
| `C_TRAJECTORY_CONTROLS` | Trajectory-level controls are defined separately from step-level attribution baselines. | `pilot_blocked` | `outputs/real_task_pilot/trajectory_controls_report.json` | partial pilot control family; readiness-level control gate complete | completed downstream trajectory-control validation |
| `C_PRM_FILTERING` | Structurally calibrated FMA may become a PRM/filtering signal only after global v2 fresh-holdout validation or a separate downstream validation gate. | `future_validation` | `fma/prm/`; future PRM/filtering reports | no PRM claim yet; design allowed only after `GLOBAL_S_FMA_V2_PASS` or `DOWNSTREAM_PRM_FILTERING_VALIDATION_PASS` | `completed_prm_filtering_gain_assertion`; `prm_filtering_superiority_assertion`; `task_specific_pass_unlocks_prm_filtering_assertion` |

## Upgrade Rules

- `C_REAL_TASK_PILOT` can move out of `pilot_blocked` only when `outputs/real_task_pilot/readiness_audit.json` reports `pilot_pass: true`.
- `C_S_FMA_V2_FRESH_HOLDOUT` can move out of `planned` only when fresh, non-overlapping GSM8K/HotpotQA holdout artifacts exist under `outputs/s_fma_v2_fresh_holdout/` and satisfy the preregistered gates in `configs/s_fma_v2_fresh_holdout.yaml`.
- `TASK_SPECIFIC_S_FMA_V2_PASS` permits only task-specific or heterogeneous wording for the passing task; it does not permit cross-task expansion.
- `GLOBAL_S_FMA_V2_PASS` requires both GSM8K and HotpotQA to satisfy their task-specific gates and the preregistered rank-signal standard before any cross-task expansion design.
- `C_TRAJECTORY_CONTROLS` can move out of `pilot_blocked` only when every configured control has measured accuracy, token, validity, reflection-count, and cost metrics.
- `C_PRM_FILTERING` can move out of `future_validation` only after `GLOBAL_S_FMA_V2_PASS` or `DOWNSTREAM_PRM_FILTERING_VALIDATION_PASS`, and only when a PRM/filtering experiment exists and compares against vanilla PRM, length-calibrated PRM, token-attribution baselines, and frozen reflection-weight baselines.
- No paper section should upgrade a claim beyond this registry.
