# Submission Readiness Audit

Scope: repository-level readiness check against the current real-task pilot artifacts. This audit summarizes stored evidence only; it does not rerun API generation, replay, baseline scoring, or PRM/filtering validation.

status: `PILOT_BLOCKED`
pilot_pass: `false`
submission_recommendation: `blocked`

## Gate Status

| Gate | Current status | Evidence |
|---|---:|---|
| Valid traced samples | pass | `outputs/real_task_pilot/readiness_audit.json` reports `valid_trace_count: true` |
| Span validity proxy | pass | `span_validity_rate: true` |
| Replay coverage | fail | `replay_coverage: false`; 22 observed span rows out of 382 expected |
| Delta-U coverage | fail | `delta_coverage: false`; 22 observed span rows out of 382 expected |
| Rank-signal coverage | fail | `rank_signal_coverage: false`; 22 observed span rows out of 382 expected |
| Baseline coverage | pass | `baseline_coverage: true`; 382 observed span rows out of 382 expected |
| Baseline leakage | pass | `baseline_leakage_clean: true` |
| Hygiene | pass | `outputs/real_task_pilot/hygiene_audit.md` reports `hygiene_clean: true` |
| Primary real-task signal | fail | `structurally_calibrated_fma` is not available in the real-task rank-signal report |
| Trajectory controls | fail | `trajectory_controls_report.json` is marked `skeleton_unmeasured` |
| API preflight | fail | preflight reports `PREFLIGHT_FAIL_DRIFT` |
| Tests | pass | latest local verification used `python -m pytest -q` |

## Blocking Items

- `PILOT_FAIL_CONTROLS`: trajectory controls are defined but not complete.
- `PILOT_FAIL_COVERAGE`: replay, Delta-U, and rank-signal artifacts cover only 22 of 382 expected span keys.
- `PILOT_FAIL_REPLAY`: replay coverage and replay success gate are not satisfied.
- `PILOT_FAIL_SIGNAL`: no real-task structurally calibrated FMA candidate score artifact is present.
- `PREFLIGHT_FAIL_DRIFT`: API preflight drift prevents deterministic pilot claims.
- Trajectory controls are defined but unmeasured; their report is a skeleton, not a completed control experiment.

## Claim Labels

The current paper package may claim only guarded diagnostic support:

- Phase 5-7 stored synthetic diagnostics support the distinction between local utility and sparse structural necessity.
- Stage 2 supports a low-magnitude, stratum-dependent diagnostic relation.
- Real-task evidence remains pilot-only and blocked.
- PRM/filtering improvement remains future validation, not a completed result.

Do not mark the manuscript as top-tier ready until replay/delta/rank-signal coverage, API drift, trajectory controls, and primary real-task signal gates are resolved.
