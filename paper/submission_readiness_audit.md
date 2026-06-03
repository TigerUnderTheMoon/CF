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
fresh_holdout_next_allowed_step: deterministic route must stop and fix preflight drift before requesting fresh full generation approval; stochastic smoke rerun next step is `STOP_OR_REVISE_EVIDENCE_TARGET`
fresh_holdout_route_fork: `DETERMINISTIC_REPLAY_ROUTE` blocked by drift; `STOCHASTIC_REPEATED_REPLAY_ROUTE` has only 20-row smoke diagnostics and is blocked by sparse signal
fresh_holdout_stochastic_smoke_status: `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`; first smoke failed generation with 8/20 valid original traces and 12 non-JSON original attempts; approved bounded rerun spent `3.14542` USD within the `5` USD ceiling, produced 60/60 successful replay results, but had `nonzero_delta_rows: 0`; sparse-signal failure audit added; current status remains `PILOT_BLOCKED`
v2_1_route: `s_FMA_v2.1` planned-only; historical manifest and contract audits clean for old prompt hash; API preflight-only schema-failed; local schema fix makes prompt package stale
v2_1_manifest_overlap_audit_status: `MANIFEST_OVERLAP_CLEAN`
v2_1_contract_audit_status: `V2_1_CONTRACT_CLEAN`
v2_1_api_preflight_approval_request: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_approval_request.md` and `.json`
v2_1_api_preflight_status: `PREFLIGHT_FAIL_SCHEMA_OR_TAGS`
v2_1_api_preflight_cost_usd: `0.837825`
v2_1_api_preflight_requests: `23` actual API attempts, max `25`
v2_1_api_preflight_success_rates: JSON parse `1.0`; schema `0.85`; tag extraction `1.0`; final-answer parse `1.0`
v2_1_api_preflight_drift_status: `PREFLIGHT_FAIL_DRIFT`
v2_1_schema_failure_audit: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_schema_failure_audit.md` and `.json`
v2_1_next_allowed_step: regenerate v2.1 manifest, contract audit, and preflight approval request without API; `v2_1_smoke_approval_request_allowed` is `false`

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
| s_FMA_v2 fresh holdout | manifest clean; API preflight drift-failed; stochastic smoke sparse-signal failed | `outputs/s_fma_v2_fresh_holdout/fresh_manifest.json` has 400 rows and `outputs/s_fma_v2_fresh_holdout/manifest_overlap_audit.json` reports `MANIFEST_OVERLAP_CLEAN`; `outputs/s_fma_v2_fresh_holdout/api_preflight_report.json` reports `PREFLIGHT_FAIL_DRIFT` with 20 evaluated API records, 10 GSM8K and 10 HotpotQA, and actual preflight cost `0.321005`; the first smoke generation failure is documented in `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_generation_failure_audit.md` and `.json`; the approved bounded rerun updated `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_report.json` to `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL` with 20 smoke samples, 60/60 successful replay results, `nonzero_delta_rows: 0`, and smoke cost `3.14542` within the USD 5 ceiling; `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_sparse_signal_failure_audit.md` and `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_sparse_signal_failure_audit.json` document insufficient target variation under the current smoke protocol; smoke diagnostics are not validation evidence; no full generation, no 400 fresh traces, no v2 scoring, no task/global v2 pass, no PRM claim yet; current status remains `PILOT_BLOCKED` |
| s_FMA_v2.1 evidence-target revision | historical manifest and contract clean; API preflight schema-failed; prompt package stale; validation not run | `outputs/s_fma_v2_1_fresh_holdout/fresh_manifest.json` has 400 rows; `outputs/s_fma_v2_1_fresh_holdout/manifest_overlap_audit.json` reports `MANIFEST_OVERLAP_CLEAN` with zero selected overlap on `sample_id`, `task_id`, dataset/config/split/source index, normalized question hash, reference answer hash, and non-empty alias hash; historical `outputs/s_fma_v2_1_fresh_holdout/v2_1_contract_audit.json` reports `V2_1_CONTRACT_CLEAN` for the old prompt hash; `outputs/s_fma_v2_1_fresh_holdout/api_preflight_report.json` reports `PREFLIGHT_FAIL_SCHEMA_OR_TAGS` after 20 evaluated records, 23 API attempts, cost `0.837825`, JSON/tag/final-answer success `1.0`, schema success `0.85`, and drift `PREFLIGHT_FAIL_DRIFT`; `outputs/s_fma_v2_1_fresh_holdout/api_preflight_schema_failure_audit.json` documents the local enum fix and stale prompt lock; the historical report sets `v2_1_smoke_approval_request_allowed: false`; no smoke, replay, v2.1 scoring, validation, task/global pass, deterministic replay claim, or PRM claim; current status remains `PILOT_BLOCKED` |
| TASK_SPECIFIC_S_FMA_V2_PASS | not run | requires a passing task-specific fresh-holdout rank signal and permits only task-specific or heterogeneous wording |
| GLOBAL_S_FMA_V2_PASS | not run | requires both GSM8K and HotpotQA to satisfy the preregistered rank-signal standard before cross-task expansion design |
| PRM/filtering validation | not run | no PRM claim yet; design is blocked until `GLOBAL_S_FMA_V2_PASS` or a separate downstream validation gate |
| Trajectory controls | pass | `trajectory_controls_complete: true` for readiness; control variants remain partial pilot measurements, not downstream validation |
| API preflight | fail | current real-task pilot preflight reports `PREFLIGHT_FAIL_DRIFT`; v2 fresh-holdout preflight-only reports `PREFLIGHT_FAIL_DRIFT`; v2.1 preflight-only reports `PREFLIGHT_FAIL_SCHEMA_OR_TAGS` with drift `PREFLIGHT_FAIL_DRIFT` |
| Tests | pass | latest local verification used `python -m pytest -q` |

## Blocking Items

- `PILOT_FAIL_SIGNAL`: primary signal available but failed rank-signal gate. The leakage-safe `structurally_calibrated_fma` candidate score is present, but pooled Spearman rho is `-0.0182` with CI `[-0.1180, 0.0777]`; GSM8K CI is `[-0.1691, 0.1375]`; HotpotQA CI is `[-0.3433, -0.1059]`.
- `PREFLIGHT_FAIL_DRIFT`: API preflight drift prevents deterministic pilot claims.
- `DETERMINISTIC_REPLAY_ROUTE_BLOCKED`: fresh deterministic full-generation and replay wording require a passing drift gate; the stored fresh preflight is `PREFLIGHT_FAIL_DRIFT`.
- `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`: the approved bounded stochastic smoke rerun finished within budget and produced 60/60 successful replay results, but `nonzero_delta_rows` is `0`, so `next_allowed_step` is `STOP_OR_REVISE_EVIDENCE_TARGET`. The sparse-signal failure audit freezes this as insufficient target variation under the current smoke protocol. The earlier `STOCHASTIC_SMOKE_FAIL_GENERATION` audit remains provenance for the first failed smoke attempt.
- `PREFLIGHT_METADATA_MISSING`: fresh-holdout API preflight-only observed missing `system_fingerprint` metadata for all 20 evaluated records; this disclosure-only field is reported separately from schema/tag/final-answer parsing and does not mask the active drift blocker.
- `V2_1_PREFLIGHT_FAIL_SCHEMA_OR_TAGS`: v2.1 API preflight-only ran 20 records and failed the schema gate with schema success `0.85`; JSON parse, tag extraction, and final-answer parse rates were all `1.0`. The root cause was `self_evaluation` versus schema-canonical `self-evaluation`; the local fix is documented in `outputs/s_fma_v2_1_fresh_holdout/api_preflight_schema_failure_audit.json`, but the historical preflight remains failed and blocks smoke approval.
- `V2_1_PROMPT_PACKAGE_STALE`: the local v2.1 prompt/config fix changed the prompt hash from `prompt-sha256:49c492d182e0f66d6dbb2e60c7a66a8c43a8462c28351133354608583ab6c182` to `prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b`, so the historical manifest, contract audit, and approval request cannot authorize any future API rerun.
- `V2_1_PREFLIGHT_FAIL_DRIFT`: v2.1 preflight drift status is `PREFLIGHT_FAIL_DRIFT`; deterministic replay wording remains forbidden.
- `TASK_SPECIFIC_S_FMA_V2_NOT_RUN`: no task has fresh-holdout artifacts satisfying `TASK_SPECIFIC_S_FMA_V2_PASS`.
- `GLOBAL_S_FMA_V2_NOT_RUN`: GSM8K and HotpotQA have not both satisfied `GLOBAL_S_FMA_V2_PASS`.
- `V2_1_VALIDATION_NOT_RUN`: v2.1 has only manifest, contract, and failed API preflight-only artifacts. It has no smoke, replay rows, Delta-U rows, v2.1 scores, rank-signal results, task/global pass, or PRM validation.

## Fresh-Holdout Policy

The current 382 pilot traces are frozen as development failure audit evidence. They may diagnose Delta-U sparsity, metric limitations, and v2 design constraints, but they must not fit v2 weights, set rank-signal thresholds, or validate `structurally_calibrated_fma_v2`.

The fresh manifest audit revised the alias policy after diagnosing `BLOCKED_INSUFFICIENT_FRESH_ROWS` as an empty-alias false positive: empty alias set is non-informative and not blocking, while non-empty `alias_hash` remains a hard overlap key. `sample_id`, `task_id`, dataset/config/split/source index, normalized question hash, and reference answer hash remain hard-stop keys.

`TASK_SPECIFIC_S_FMA_V2_PASS` can only be evaluated on fresh, non-overlapping GSM8K or HotpotQA holdouts using the frozen formula hash `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628`; it permits only task-specific or heterogeneous wording.

`GLOBAL_S_FMA_V2_PASS` requires both GSM8K and HotpotQA to satisfy their task-specific gates and the preregistered rank-signal standard. Until that global pass exists, expansion is not allowed. PRM/filtering remains blocked until `GLOBAL_S_FMA_V2_PASS` or a separate downstream validation gate, and no PRM claim yet is permitted.

Fresh preflight drift does not equal readiness. With the current `PREFLIGHT_FAIL_DRIFT`, the deterministic route cannot request fresh full generation. The drift-disclosed stochastic route now has only failed 20-row smoke diagnostics: the first smoke failed generation, and the approved bounded rerun failed sparse signal with `nonzero_delta_rows: 0`; current status remains `PILOT_BLOCKED`.

The v2.1 evidence-target revision is separate from the v2 smoke diagnostics. Its manifest route uses a deterministic HotpotQA `normalized_token_f1` target specification, GSM8K pre-outcome `question_difficulty_proxy` selection, and a span-diversity prompt snapshot. The historical v2.1 manifest/contract audits supported a bounded API preflight-only run, but that run is `PREFLIGHT_FAIL_SCHEMA_OR_TAGS` with drift `PREFLIGHT_FAIL_DRIFT`. The local schema fix changes the prompt hash, so a new non-API manifest/contract/approval package is required before any future bounded preflight rerun request. It is not validation and does not authorize smoke, replay, scoring, deterministic replay wording, or claim upgrades.

## Claim Labels

The current paper package may claim only guarded diagnostic support:

- Phase 5-7 stored synthetic diagnostics support the distinction between local utility and sparse structural necessity.
- Stage 2 supports a low-magnitude, stratum-dependent diagnostic relation.
- Real-task evidence remains pilot-only and not scale-ready; the candidate score exists, but rank-signal gates fail. The current blocker is failed rank signal plus API drift, not absence of a candidate score.
- `s_FMA_v2` validation is not completed. Fresh manifest/audit is clean, but fresh API preflight-only is drift-failed after 20 evaluated records; deterministic route is blocked; the first approved stochastic smoke failed at the original-generation JSON gate, and the approved bounded rerun failed sparse signal with 60/60 successful replay results but `nonzero_delta_rows: 0`; smoke artifacts remain non-validation diagnostics only, current status remains `PILOT_BLOCKED`, and no full generation, no 400 fresh traces, no v2 scoring, no task/global v2 pass, and no PRM claim yet.
- `s_FMA_v2.1` is a planned evidence-target revision with historical clean manifest and contract artifacts plus a failed API preflight-only diagnostic. The preflight report is `PREFLIGHT_FAIL_SCHEMA_OR_TAGS`; the local enum fix requires non-API package regeneration before another approval request. No smoke approval request, replay, v2.1 scoring, validation, task/global pass, deterministic replay claim, or PRM claim exists.
- PRM/filtering improvement remains future validation, not a completed result.

Do not mark the manuscript as top-tier ready until primary real-task rank signal and API drift gates are resolved.
