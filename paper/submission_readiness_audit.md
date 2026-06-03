# Submission Readiness Audit

Scope: repository-level readiness check against the current real-task pilot artifacts. This audit summarizes stored evidence only; it does not rerun API generation, replay, baseline scoring, or PRM/filtering validation.

status: `PILOT_BLOCKED`
pilot_pass: `false`
submission_recommendation: `blocked`
failure_type: evidence-complete but signal-failed
fresh_holdout_route: `s_FMA_v2` planned-only; fresh manifest/audit clean
fresh_holdout_formula_hash: `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628`
fresh_holdout_audit_status: `MANIFEST_OVERLAP_CLEAN`
fresh_holdout_api_preflight_status: `PREFLIGHT_FAIL_DRIFT`
fresh_holdout_next_allowed_step: stop and fix preflight drift before requesting fresh full generation approval
fresh_holdout_route_fork: `DETERMINISTIC_REPLAY_ROUTE` blocked by drift; `STOCHASTIC_REPEATED_REPLAY_ROUTE` planned-only and requires explicit stochastic validation budget approval before any API
fresh_holdout_stochastic_budget_risk_audit: exists; route remains planned-only; no API run; no scoring; no replay; no task/global v2 pass; no PRM claim

## Gate Status

| Gate | Current status | Evidence |
|---|---:|---|
| Valid traced samples | pass | `outputs/real_task_pilot/readiness_audit.json` reports `valid_trace_count: true` |
| Span validity proxy | pass | `span_validity_rate: true` |
| Replay coverage | pass | `replay_coverage: true`; 382 observed span keys out of 382 expected |
| Delta-U coverage | pass | `delta_coverage: true`; 382 observed span keys out of 382 expected |
| Rank-signal coverage | pass | `rank_signal_coverage: true`; 382 observed span keys out of 382 expected |
| Baseline coverage | pass | `baseline_coverage: true`; 382 observed span rows out of 382 expected |
| Baseline leakage | pass | `baseline_leakage_clean: true` |
| Hygiene | pass | `outputs/real_task_pilot/hygiene_audit.md` reports `hygiene_clean: true` |
| Primary real-task signal | fail | primary signal available but failed rank-signal gate: `structurally_calibrated_fma` is clean for 382 spans, but pooled and per-task bootstrap CI lower bounds are not above zero; see `outputs/real_task_pilot/primary_signal_failure_audit.md` |
| Frozen failure audit | pass | `outputs/real_task_pilot/primary_signal_failure_audit.md` and `.json` freeze the current pilot as `development_failure_audit` |
| s_FMA_v2 fresh holdout | manifest clean; API preflight drift-failed | `outputs/s_fma_v2_fresh_holdout/fresh_manifest.json` has 400 rows and `outputs/s_fma_v2_fresh_holdout/manifest_overlap_audit.json` reports `MANIFEST_OVERLAP_CLEAN`; `outputs/s_fma_v2_fresh_holdout/api_preflight_report.json` reports `PREFLIGHT_FAIL_DRIFT` with 20 evaluated API records, 10 GSM8K and 10 HotpotQA, and actual preflight cost `0.321005`; `outputs/s_fma_v2_fresh_holdout/stochastic_route_budget_risk_audit.json` and `.md` exist as budget/risk planning artifacts only; `DETERMINISTIC_REPLAY_ROUTE` is blocked because drift did not pass; `STOCHASTIC_REPEATED_REPLAY_ROUTE` is planned-only and not run; no full generation, no 400 fresh traces, no v2 scoring, no replay, no task/global v2 pass, no PRM claim yet; current status remains `PILOT_BLOCKED` |
| TASK_SPECIFIC_S_FMA_V2_PASS | not run | requires a passing task-specific fresh-holdout rank signal and permits only task-specific or heterogeneous wording |
| GLOBAL_S_FMA_V2_PASS | not run | requires both GSM8K and HotpotQA to satisfy the preregistered rank-signal standard before cross-task expansion design |
| PRM/filtering validation | not run | no PRM claim yet; design is blocked until `GLOBAL_S_FMA_V2_PASS` or a separate downstream validation gate |
| Trajectory controls | pass | `trajectory_controls_complete: true` for readiness; control variants remain partial pilot measurements, not downstream validation |
| API preflight | fail | current real-task pilot preflight reports `PREFLIGHT_FAIL_DRIFT`; fresh-holdout preflight-only reports `PREFLIGHT_FAIL_DRIFT` after the guarded live API preflight-only run |
| Tests | pass | latest local verification used `python -m pytest -q` |

## Blocking Items

- `PILOT_FAIL_SIGNAL`: primary signal available but failed rank-signal gate. The leakage-safe `structurally_calibrated_fma` candidate score is present, but pooled Spearman rho is `-0.0182` with CI `[-0.1180, 0.0777]`; GSM8K CI is `[-0.1691, 0.1375]`; HotpotQA CI is `[-0.3433, -0.1059]`.
- `PREFLIGHT_FAIL_DRIFT`: API preflight drift prevents deterministic pilot claims.
- `DETERMINISTIC_REPLAY_ROUTE_BLOCKED`: fresh deterministic full-generation and replay wording require a passing drift gate; the stored fresh preflight is `PREFLIGHT_FAIL_DRIFT`.
- `STOCHASTIC_REPEATED_REPLAY_ROUTE_PLANNED_ONLY`: stochastic repeated-replay validation is pre-registered as a possible route after drift disclosure, and `outputs/s_fma_v2_fresh_holdout/stochastic_route_budget_risk_audit.json` exists as a budget/risk audit, but the route has not been approved, budgeted for execution, or run.
- `PREFLIGHT_METADATA_MISSING`: fresh-holdout API preflight-only observed missing `system_fingerprint` metadata for all 20 evaluated records; this disclosure-only field is reported separately from schema/tag/final-answer parsing and does not mask the active drift blocker.
- `TASK_SPECIFIC_S_FMA_V2_NOT_RUN`: no task has fresh-holdout artifacts satisfying `TASK_SPECIFIC_S_FMA_V2_PASS`.
- `GLOBAL_S_FMA_V2_NOT_RUN`: GSM8K and HotpotQA have not both satisfied `GLOBAL_S_FMA_V2_PASS`.

## Fresh-Holdout Policy

The current 382 pilot traces are frozen as development failure audit evidence. They may diagnose Delta-U sparsity, metric limitations, and v2 design constraints, but they must not fit v2 weights, set rank-signal thresholds, or validate `structurally_calibrated_fma_v2`.

The fresh manifest audit revised the alias policy after diagnosing `BLOCKED_INSUFFICIENT_FRESH_ROWS` as an empty-alias false positive: empty alias set is non-informative and not blocking, while non-empty `alias_hash` remains a hard overlap key. `sample_id`, `task_id`, dataset/config/split/source index, normalized question hash, and reference answer hash remain hard-stop keys.

`TASK_SPECIFIC_S_FMA_V2_PASS` can only be evaluated on fresh, non-overlapping GSM8K or HotpotQA holdouts using the frozen formula hash `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628`; it permits only task-specific or heterogeneous wording.

`GLOBAL_S_FMA_V2_PASS` requires both GSM8K and HotpotQA to satisfy their task-specific gates and the preregistered rank-signal standard. Until that global pass exists, expansion is not allowed. PRM/filtering remains blocked until `GLOBAL_S_FMA_V2_PASS` or a separate downstream validation gate, and no PRM claim yet is permitted.

Fresh preflight drift does not equal readiness. With the current `PREFLIGHT_FAIL_DRIFT`, the deterministic route cannot request fresh full generation. The only reviewer-safe next work is to preregister the stochastic repeated-replay route or rerun preflight with stronger determinism settings; either path still requires explicit user approval before any API execution.

## Claim Labels

The current paper package may claim only guarded diagnostic support:

- Phase 5-7 stored synthetic diagnostics support the distinction between local utility and sparse structural necessity.
- Stage 2 supports a low-magnitude, stratum-dependent diagnostic relation.
- Real-task evidence remains pilot-only and not scale-ready; the candidate score exists, but rank-signal gates fail. The current blocker is failed rank signal plus API drift, not absence of a candidate score.
- `s_FMA_v2` is planned only. Fresh manifest/audit is clean, but fresh API preflight-only is drift-failed after 20 evaluated records; stochastic route budget/risk audit exists; deterministic route is blocked; stochastic route is planned-only and not run; no full generation, no 400 fresh traces, no v2 scoring, no replay, no task/global v2 pass, and no PRM claim yet.
- PRM/filtering improvement remains future validation, not a completed result.

Do not mark the manuscript as top-tier ready until primary real-task rank signal and API drift gates are resolved.
