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
v2_1_route: `s_FMA_v2.1` planned-only; regenerated package clean for current prompt hash; approved API_PREFLIGHT_ONLY rerun now parses but remains drift-failed; approved transport canary passed as diagnostic-only extraction evidence; latest bounded stochastic smoke was feasible for a pilot-budget request; current pilot stochastic artifact is blocked by one replay transport/APIConnectionError hard stop
v2_1_manifest_overlap_audit_status: `MANIFEST_OVERLAP_CLEAN`
v2_1_contract_audit_status: `V2_1_CONTRACT_CLEAN`
v2_1_api_preflight_approval_request: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_approval_request.md` and `.json`
v2_1_prompt_hash_current: `prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b`
v2_1_api_preflight_approval_status: approved by user for bounded `API_PREFLIGHT_ONLY` rerun only; smoke/replay/scoring not approved
v2_1_api_preflight_status: `PREFLIGHT_FAIL_DRIFT`
v2_1_api_preflight_cost_usd: `0.86245`
v2_1_api_preflight_requests: `23` actual API attempts, max `25`
v2_1_api_preflight_success_rates: JSON parse `1.0`; schema `1.0`; tag extraction `1.0`; final-answer parse `1.0`
v2_1_api_preflight_valid_traces: `20`
v2_1_api_preflight_raw_output_nonempty: `23/23` attempts
v2_1_api_preflight_drift_status: `PREFLIGHT_FAIL_DRIFT`; deterministic replay claim remains forbidden because the drift gate failed
v2_1_api_preflight_drift_failure_audit: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_drift_failure_audit.md` and `.json`
v2_1_schema_failure_audit: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_schema_failure_audit.md` and `.json`
v2_1_empty_output_failure_audit: `outputs/s_fma_v2_1_fresh_holdout/api_preflight_empty_output_failure_audit.md` and `.json`
v2_1_transport_canary_status: `TRANSPORT_CANARY_PASS`; 2 API attempts; cost `0.07631`; 2/2 non-empty `raw_output`; `output_extraction_diagnostics` complete; JSON/schema/tag/final-answer success rates `1.0`; diagnostic only, not validation evidence
v2_1_root_cause_classification: current API_PREFLIGHT_ONLY failure is not empty-output failure; output extraction succeeded, but drift and missing `system_fingerprint` disclosure metadata block readiness
v2_1_stochastic_smoke_status: `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST`
v2_1_stochastic_smoke_report: `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_report.json`
v2_1_stochastic_smoke_prior_failure_audit: `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_failure_audit.md` and `.json`
v2_1_stochastic_smoke_cost_usd: `6.11314`
v2_1_stochastic_smoke_requests: `140` actual API attempts, max `140`
v2_1_stochastic_smoke_valid_original_traces: `20`
v2_1_stochastic_smoke_replay_success_rate: `1.0`; `120/120` successful replay results
v2_1_stochastic_smoke_parse_success_rates: JSON `1.0`; schema `1.0`; tag extraction `1.0`; final-answer parse `1.0`
v2_1_stochastic_smoke_nonzero_delta_u: pooled `20`; GSM8K `7`; HotpotQA `13`
v2_1_stochastic_smoke_signal_absent: `false`; nonzero Delta-U signal exists in both tasks
v2_1_stochastic_smoke_failure_codes: none in the current smoke report
v2_1_stochastic_smoke_next_allowed_step: `REQUEST_V2_1_PILOT_STOCHASTIC_BUDGET`
v2_1_pilot_stochastic_status: `V2_1_PILOT_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`; root cause reclassified by audit as single transport failure hard-stop, not model schema/type failure, rank-signal failure, or evidence sparsity
v2_1_pilot_stochastic_report: `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_report.json`
v2_1_pilot_stochastic_requests: `700` actual API requests
v2_1_pilot_stochastic_cost_usd: `28.04808`
v2_1_pilot_stochastic_valid_original_traces: `100`
v2_1_pilot_stochastic_replay_success: `599/600`
v2_1_pilot_stochastic_parse_success_rates: JSON/schema/tag/final-answer `0.9985714285714286`
v2_1_pilot_stochastic_nonzero_delta_u: pooled `96`; GSM8K `42`; HotpotQA `54`
v2_1_pilot_stochastic_rank_signal: pooled Spearman `0.6245252861282434` CI `[0.5270533908111767, 0.7061756846044145]`; GSM8K `0.8607773460183319` CI `[0.783942543722986, 0.9178556911176244]`; HotpotQA `0.5134994412349974` CI `[0.3830411004694536, 0.620563137771949]`
v2_1_pilot_stochastic_failed_attempt: `gsm8k-00357`; task_id `gsm8k-test-00357`; span_index `1`; repeat_index `2`; failure `api_error:APIConnectionError:Connection error.`
v2_1_pilot_stochastic_task_specific_global_pass: `TASK_SPECIFIC=false`; `GLOBAL=false`; current status remains `PILOT_BLOCKED`
v2_1_pilot_transport_failure_audit: `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_transport_failure_audit.md` and `.json`
v2_1_next_allowed_step: only user review of the request-only `V2_1_PILOT_SINGLE_TRANSPORT_RETRY_ONLY` package; current status remains `PILOT_BLOCKED`; no retry, original regeneration, other replay attempt, full validation, or PRM/filtering is allowed without explicit user approval
v2_1_pilot_single_retry_request_status: `REQUEST_ONLY_NOT_APPROVED`; scope `V2_1_PILOT_SINGLE_TRANSPORT_RETRY_ONLY`; budget ceiling USD 1; max API requests 3; only the failed replay attempt may be retried; no API, retry, original regeneration, other replay attempt, scoring, full validation, pass wording, or PRM/filtering is authorized by the request-only package

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
| s_FMA_v2.1 evidence-target revision | regenerated package clean; API preflight drift-failed; stochastic smoke feasible for pilot-budget request; validation not run | `outputs/s_fma_v2_1_fresh_holdout/fresh_manifest.json` has 400 rows; `outputs/s_fma_v2_1_fresh_holdout/manifest_overlap_audit.json` reports `MANIFEST_OVERLAP_CLEAN` with zero selected overlap on `sample_id`, `task_id`, dataset/config/split/source index, normalized question hash, reference answer hash, and non-empty alias hash; `outputs/s_fma_v2_1_fresh_holdout/v2_1_contract_audit.json` reports `V2_1_CONTRACT_CLEAN` for current prompt hash `prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b`; the approved `API_PREFLIGHT_ONLY` rerun in `outputs/s_fma_v2_1_fresh_holdout/api_preflight_report.json` reports `PREFLIGHT_FAIL_DRIFT` after 20 evaluated records, 23 API attempts, cost `0.86245`, JSON/schema/tag/final-answer success `1.0`, 20 valid trace rows, and 23/23 non-empty `raw_output` attempts; `outputs/s_fma_v2_1_fresh_holdout/api_preflight_drift_failure_audit.md` records `determinism_drift_max: 0.48554913294797686`, resolved schema/transport gates, and deterministic route blocked; the latest bounded stochastic smoke rerun in `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_report.json` reports `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST` after 140 API attempts and cost `6.11314`, with JSON/schema/tag/final-answer success `1.0`, replay success rate `1.0`, 20 nonzero Delta-U rows pooled, 7 GSM8K, and 13 HotpotQA; this permits only a request-only pilot stochastic budget package, not v2.1 validation, task/global pass, deterministic replay claim, pilot execution, full validation, or PRM claim; current status remains `PILOT_BLOCKED` |
| TASK_SPECIFIC_S_FMA_V2_PASS | not run | requires a passing task-specific fresh-holdout rank signal and permits only task-specific or heterogeneous wording |
| GLOBAL_S_FMA_V2_PASS | not run | requires both GSM8K and HotpotQA to satisfy the preregistered rank-signal standard before cross-task expansion design |
| PRM/filtering validation | not run | no PRM claim yet; design is blocked until `GLOBAL_S_FMA_V2_PASS` or a separate downstream validation gate |
| Trajectory controls | pass | `trajectory_controls_complete: true` for readiness; control variants remain partial pilot measurements, not downstream validation |
| API preflight | fail | current real-task pilot preflight reports `PREFLIGHT_FAIL_DRIFT`; v2 fresh-holdout preflight-only reports `PREFLIGHT_FAIL_DRIFT`; v2.1 preflight-only reports `PREFLIGHT_FAIL_DRIFT` with valid traces but failed drift/metadata readiness |
| Tests | pass | latest local verification used `python -m pytest -q` |

## Blocking Items

- `PILOT_FAIL_SIGNAL`: primary signal available but failed rank-signal gate. The leakage-safe `structurally_calibrated_fma` candidate score is present, but pooled Spearman rho is `-0.0182` with CI `[-0.1180, 0.0777]`; GSM8K CI is `[-0.1691, 0.1375]`; HotpotQA CI is `[-0.3433, -0.1059]`.
- `PREFLIGHT_FAIL_DRIFT`: API preflight drift prevents deterministic pilot claims.
- `DETERMINISTIC_REPLAY_ROUTE_BLOCKED`: fresh deterministic full-generation and replay wording require a passing drift gate; the stored fresh preflight is `PREFLIGHT_FAIL_DRIFT`.
- `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`: the approved bounded stochastic smoke rerun finished within budget and produced 60/60 successful replay results, but `nonzero_delta_rows` is `0`, so `next_allowed_step` is `STOP_OR_REVISE_EVIDENCE_TARGET`. The sparse-signal failure audit freezes this as insufficient target variation under the current smoke protocol. The earlier `STOCHASTIC_SMOKE_FAIL_GENERATION` audit remains provenance for the first failed smoke attempt.
- `PREFLIGHT_METADATA_MISSING`: fresh-holdout API preflight-only observed missing `system_fingerprint` metadata for all 20 evaluated records; this disclosure-only field is reported separately from schema/tag/final-answer parsing and does not mask the active drift blocker.
- `V2_1_PREFLIGHT_DRIFT_METADATA_FAILURE`: the approved v2.1 API_PREFLIGHT_ONLY rerun ran 20 records plus 3 determinism probes, spent `0.86245` USD within the `2` USD ceiling, produced 23/23 non-empty `raw_output` attempts, generated 20 valid trace rows, and reached JSON/schema/tag/final-answer success rates of `1.0`; it still reports `PREFLIGHT_FAIL_DRIFT` with missing metadata. This blocks deterministic replay and smoke execution. Stochastic repeated replay remains only a planning route requiring explicit bounded approval, repeated replay, bootstrap uncertainty, and no deterministic wording.
- `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST`: the latest bounded smoke rerun reached JSON/schema/tag/final-answer success rates of `1.0`, replay success rate `1.0`, and nonzero Delta-U counts of 20 pooled, 7 GSM8K, and 13 HotpotQA. This is smoke feasibility for a pilot-budget request only, not validation evidence, not a task/global pass, and not PRM/filtering evidence. Current status remains `PILOT_BLOCKED`.
- `V2_1_PILOT_STOCHASTIC_REQUEST_ONLY`: `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_approval_request.json` and `.md` request only `V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY`. The package is `REQUEST_ONLY_NOT_APPROVED`, recommends a USD 40 ceiling, caps any future approved pilot at 700 API requests, 100 records, and 3 stochastic repeats per eligible span, and does not authorize API execution, pilot execution, replay, scoring, full validation, pass wording, or PRM/filtering.
- `V2_1_TRANSPORT_CANARY_ONLY_PASS`: the separately approved transport canary ran 2 records, spent `0.07631` USD, preserved complete `output_extraction_diagnostics`, produced non-empty `raw_output` for both attempts, and reached JSON/schema/tag/final-answer success rates of `1.0`. This is not a v2.1 evidence claim; it is provenance for the repaired extraction path before the bounded 20-row API_PREFLIGHT_ONLY rerun.
- `V2_1_PACKAGE_REGENERATED_AFTER_SCHEMA_FIX`: the local v2.1 prompt/config fix changed the prompt hash from `prompt-sha256:49c492d182e0f66d6dbb2e60c7a66a8c43a8462c28351133354608583ab6c182` to `prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b`; the manifest, contract audit, and request-only preflight approval package now use the current hash, but this package still does not authorize API execution.
- `V2_1_PREFLIGHT_NOT_READY`: v2.1 preflight status is not ready because the drift gate failed and required disclosure metadata is missing. Passing schema/tag/final-answer gates do not permit deterministic replay wording while the preflight is not `API_PREFLIGHT_READY`.
- `TASK_SPECIFIC_S_FMA_V2_NOT_RUN`: no task has fresh-holdout artifacts satisfying `TASK_SPECIFIC_S_FMA_V2_PASS`.
- `GLOBAL_S_FMA_V2_NOT_RUN`: GSM8K and HotpotQA have not both satisfied `GLOBAL_S_FMA_V2_PASS`.
- `V2_1_VALIDATION_NOT_RUN`: v2.1 has manifest, contract, failed API preflight-only, canary, audit, feasible stochastic smoke diagnostics, and a request-only pilot stochastic budget package. These artifacts do not include rank-signal results, leakage/readiness validation, task/global pass, approved pilot execution, full validation, or PRM validation.

## Fresh-Holdout Policy

The current 382 pilot traces are frozen as development failure audit evidence. They may diagnose Delta-U sparsity, metric limitations, and v2 design constraints, but they must not fit v2 weights, set rank-signal thresholds, or validate `structurally_calibrated_fma_v2`.

The fresh manifest audit revised the alias policy after diagnosing `BLOCKED_INSUFFICIENT_FRESH_ROWS` as an empty-alias false positive: empty alias set is non-informative and not blocking, while non-empty `alias_hash` remains a hard overlap key. `sample_id`, `task_id`, dataset/config/split/source index, normalized question hash, and reference answer hash remain hard-stop keys.

`TASK_SPECIFIC_S_FMA_V2_PASS` can only be evaluated on fresh, non-overlapping GSM8K or HotpotQA holdouts using the frozen formula hash `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628`; it permits only task-specific or heterogeneous wording.

`GLOBAL_S_FMA_V2_PASS` requires both GSM8K and HotpotQA to satisfy their task-specific gates and the preregistered rank-signal standard. Until that global pass exists, expansion is not allowed. PRM/filtering remains blocked until `GLOBAL_S_FMA_V2_PASS` or a separate downstream validation gate, and no PRM claim yet is permitted.

Fresh preflight drift does not equal readiness. With the current `PREFLIGHT_FAIL_DRIFT`, the deterministic route cannot request fresh full generation. The drift-disclosed stochastic route now has only failed 20-row smoke diagnostics: the first smoke failed generation, and the approved bounded rerun failed sparse signal with `nonzero_delta_rows: 0`; current status remains `PILOT_BLOCKED`.

The v2.1 evidence-target revision is separate from the v2 smoke diagnostics. Its manifest route uses a deterministic HotpotQA `normalized_token_f1` target specification, GSM8K pre-outcome `question_difficulty_proxy` selection, and a span-diversity prompt snapshot. The approved v2.1 API_PREFLIGHT_ONLY rerun is `PREFLIGHT_FAIL_DRIFT` with 20 valid trace rows and 23/23 non-empty `raw_output` attempts, but drift and missing disclosure metadata block deterministic readiness. The separately approved transport canary remains diagnostic extraction evidence only. The latest bounded v2.1 stochastic smoke rerun is feasible for a pilot-budget request, with JSON/schema/tag/final-answer success rates of `1.0`, replay success rate `1.0`, and nonzero Delta-U in both tasks. This does not validate the revised target and does not authorize deterministic replay wording, pilot execution, full validation, task/global pass wording, PRM/filtering claims, or claim upgrades. The only next allowed v2.1 action is user review of the request-only `V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY` budget package.

## Claim Labels

The current paper package may claim only guarded diagnostic support:

- Phase 5-7 stored synthetic diagnostics support the distinction between local utility and sparse structural necessity.
- Stage 2 supports a low-magnitude, stratum-dependent diagnostic relation.
- Real-task evidence remains pilot-only and not scale-ready; the candidate score exists, but rank-signal gates fail. The current blocker is failed rank signal plus API drift, not absence of a candidate score.
- `s_FMA_v2` validation is not completed. Fresh manifest/audit is clean, but fresh API preflight-only is drift-failed after 20 evaluated records; deterministic route is blocked; the first approved stochastic smoke failed at the original-generation JSON gate, and the approved bounded rerun failed sparse signal with 60/60 successful replay results but `nonzero_delta_rows: 0`; smoke artifacts remain non-validation diagnostics only, current status remains `PILOT_BLOCKED`, and no full generation, no 400 fresh traces, no v2 scoring, no task/global v2 pass, and no PRM claim yet.
- `s_FMA_v2.1` is a planned evidence-target revision with a regenerated clean manifest/contract package, a failed approved API_PREFLIGHT_ONLY diagnostic, a feasible stochastic smoke diagnostic, and an unapproved pilot stochastic budget request. The failed preflight report is now `PREFLIGHT_FAIL_DRIFT` with valid traces and successful parsing, but it is still not `API_PREFLIGHT_READY`; the drift failure audit blocks deterministic replay. The stochastic smoke report is `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST`, but it only allows the request-only `V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY` package. No v2.1 validation, rank-signal result, task/global pass, deterministic replay claim, pilot execution, full validation, or PRM claim exists.
- PRM/filtering improvement remains future validation, not a completed result.

Do not mark the manuscript as top-tier ready until primary real-task rank signal and API drift gates are resolved.
