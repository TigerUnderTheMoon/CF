# Claim Registry

Purpose: this file is the manuscript claim contract. Proposal language is not evidence. A claim can be upgraded only when the listed artifacts exist and the listed gates pass.

Status labels:

- `supported`: current artifacts support the bounded claim.
- `stratum_dependent`: current artifacts support the claim only with explicit heterogeneity limits.
- `pilot_blocked`: pilot infrastructure exists, but readiness gates block evidence use.
- `future_validation`: planned work; not a current result.

## Active Claims

| Claim ID | Claim | Status | Artifact owner | Allowed wording | Blocked wording |
|---|---|---|---|---|---|
| `C_DIAG_LOCAL_STRUCTURAL` | Local utility is more widespread than sparse structural necessity in stored reflective traces. | `supported` | `outputs/counterfactual_summary.json`; `outputs/structural_diagnostics.json`; `outputs/redundancy_analysis.json`; `paper/results.md` | diagnostic support; local utility vs structural necessity | downstream improvement; broad superiority |
| `C_STAGE2_RANK_SIGNAL` | Stage 2 held-out validation shows a low-magnitude aggregate rank signal with heterogeneous strata. | `stratum_dependent` | `outputs/stage2_holdout_validation.json`; `outputs/stage2_claim_gating_summary.md`; `outputs/stage2_stratified_metrics.json` | weak aggregate alignment; stratum-dependent support | protocol-independent confirmation; universal generalization |
| `C_BASELINE_PROXY_CONTROLS` | Required Stage 2 baseline rows are clean conservative proxy controls. | `supported` | `outputs/stage2_baseline_results.json`; `outputs/stage2_baseline_leakage_audit.json`; `outputs/baseline_integration_summary.md` | clean conservative proxy controls | strong perturbation-response baselines; reviewer-proof superiority |
| `C_REAL_TASK_PILOT` | GSM8K/HotpotQA real-task evidence is guarded pilot evidence only. | `pilot_blocked` | `outputs/real_task_pilot/readiness_audit.json`; `outputs/real_task_pilot/rank_signal_report.json`; `outputs/real_task_pilot/real_task_delta_u.jsonl` | pilot-only; blocked by coverage/replay/signal/API gates | top-tier-ready real-task support |
| `C_TRAJECTORY_CONTROLS` | Trajectory-level controls are defined separately from step-level attribution baselines. | `pilot_blocked` | `outputs/real_task_pilot/trajectory_controls_report.json` | defined control family; unmeasured or incomplete until metrics are populated | completed trajectory-control result |
| `C_PRM_FILTERING` | Structurally calibrated FMA may become a PRM/filtering signal after downstream validation. | `future_validation` | `fma/prm/`; future PRM/filtering reports | required downstream validation target | completed PRM/filtering gain |

## Upgrade Rules

- `C_REAL_TASK_PILOT` can move out of `pilot_blocked` only when `outputs/real_task_pilot/readiness_audit.json` reports `pilot_pass: true`.
- `C_TRAJECTORY_CONTROLS` can move out of `pilot_blocked` only when every configured control has measured accuracy, token, validity, reflection-count, and cost metrics.
- `C_PRM_FILTERING` can move out of `future_validation` only when a PRM/filtering experiment exists and compares against vanilla PRM, length-calibrated PRM, token-attribution baselines, and heuristic reflection-scoring baselines.
- No paper section should upgrade a claim beyond this registry.
