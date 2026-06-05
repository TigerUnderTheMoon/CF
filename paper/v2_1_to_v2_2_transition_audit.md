# v2.1 to v2.2 Transition Audit

Date: 2026-06-05

Scope: transition audit for preregistering `s_FMA_v2.2` after the failed `s_FMA_v2.1` full stochastic validation. This audit summarizes stored evidence and new preregistration boundaries only. It does not run API calls, generate a manifest, replay, score, or run PRM/filtering.

## Frozen v2.1 Provenance

The current v2.1 full stochastic validation is frozen as failed full-validation provenance. The controlling artifacts are:

- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_rank_signal_report.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.md`
- `paper/full_validation_route_decision.md`

The source report status is `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`, with failure codes `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS` and `V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL`. `TASK_SPECIFIC_pass` and `GLOBAL_pass` are both `false`.

Direct failed gates:

- JSON/schema/tag/final-answer success rates were `0.9971181556195965`, below the preregistered exact `1.0` requirement, due to 8 timeout/connection attempts.
- GSM8K had 16 nonzero Delta-U rows, below the preregistered threshold of 20.

The full artifact has positive pooled/GSM8K/HotpotQA rank signal. That rank signal does not override the failed preregistered gates.

## Transition Decision

v2.2 is a new preregistered route. It is not an interpretation layer that rescues v2.1.

| v2.1 failure source | v2.2 preregistered response |
|---|---|
| GSM8K single-run binary exact-match Delta-U was sparse. | GSM8K primary target becomes repeated numeric success probability, with exact match retained as secondary reporting. |
| Exact `1.0` quality gate made a small number of transport/schema failures block full scale. | v2.2 may use a bounded repair policy, but every failed attempt must be audited and unrepaired failures must count against the gate. |
| Stochastic repeated replay uncertainty was underspecified beyond Spearman bootstrap. | v2.2 requires Spearman, Kendall, NDCG, top-k AUC, bootstrap confidence intervals, standard errors, and variances. |
| v2.1 artifacts failed their own gates. | v2.1 remains failed provenance; v2.2 must use a fresh non-overlapping holdout or new preregistered split. |

## New Route Artifacts

This task adds:

- `paper/s_fma_v2_2_preregistration_plan.md`
- `configs/s_fma_v2_2_fresh_holdout.yaml`
- `paper/v2_1_to_v2_2_transition_audit.md`

It syncs:

- `README.md`
- `PLANS.md`
- `paper/claim_registry.md`
- `paper/submission_readiness_audit.md`

No `outputs/s_fma_v2_2_fresh_holdout/` artifacts are created by this task.

## Claim Boundary

Allowed now:

- v2.1 full stochastic validation failed its preregistered full-validation gates.
- v2.2 is preregistered as a new route motivated by the v2.1 failure audit.
- v2.2 must use fresh non-overlapping data or a new preregistered split.
- PRM/filtering remains downstream blocked.

Forbidden now:

- claiming v2.1 full-validation success
- changing v2.1 thresholds after seeing the full artifact
- using v2.1 full-validation artifacts to tune v2.2 thresholds
- claiming v2.2 validation success before v2.2 execution artifacts exist
- claiming deterministic-route support from this preregistration
- claiming top-tier readiness
- claiming PRM/filtering execution or comparative downstream gain

## Next Allowed Step

The next allowed step is a separate, explicitly scoped v2.2 manifest-or-split preregistration task. That future task must still avoid API execution unless a later user request explicitly authorizes it with budget and stop conditions.
