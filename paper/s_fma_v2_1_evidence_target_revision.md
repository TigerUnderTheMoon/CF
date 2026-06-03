# s_FMA v2.1 Evidence-Target Revision

Status: `planned`

Current project status: `PILOT_BLOCKED`

Scope: no-API preregistration for revising the fresh-holdout evidence target after the failed stochastic smoke rerun. This document does not authorize API generation, replay, scoring, threshold search, PRM training, downstream filtering validation, or any claim upgrade.

## Source Failure and Frozen Boundary

The v2.1 route is motivated by the stored stochastic smoke failure, not by a validation pass.

Source artifacts:

- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_report.json`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_sparse_signal_failure_audit.md`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_sparse_signal_failure_audit.json`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_delta_u.jsonl`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_replay_results.jsonl`
- `outputs/s_fma_v2_fresh_holdout/logs/stochastic_smoke_cost_report.json`

Frozen facts:

- Smoke status: `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`
- Current project status remains: `PILOT_BLOCKED`
- Smoke samples: 20 total, with 10 GSM8K and 10 HotpotQA rows
- Replay success: 60/60 successful replay results
- Nonzero Delta-U rows: `0`
- GSM8K exact-match pattern: 9/10 original rows were correct and the same 9 stayed correct after replay
- HotpotQA exact-match pattern: 0/10 original rows were correct and all intervened mean scores stayed 0

The current `outputs/real_task_pilot/*` artifacts remain frozen as development failure audit evidence. The current `outputs/s_fma_v2_fresh_holdout/*` artifacts remain smoke diagnostics only. They must not be rewritten, relabeled as validation evidence, or reused to fit v2.1 weights, tune thresholds, select rows by target outcome, or claim a pass.

Allowed use of frozen evidence:

- Diagnose target sparsity and exact-match saturation.
- Motivate v2.1 target, prompt, and gate design.
- Preserve provenance for the failed v2 and smoke route.

Forbidden use of frozen evidence:

- Same-pilot tuning.
- Current-trace v2.1 validation.
- Retrofitting the current pilot into a pass.
- `TASK_SPECIFIC_S_FMA_V2_PASS`, `GLOBAL_S_FMA_V2_PASS`, or v2.1 pass claims.
- PRM/filtering design or superiority claims.

## Revised Target Definition

v2.1 keeps the intervention-sensitive Delta-U framing but changes the target scoring policy so the fresh holdout can test rank signal against a less sparse target.

Target name: `graded_delta_u_v2_1`

Delta-U definition:

```text
delta_u = original_score - mean(intervened_scores)
```

Repeated replay aggregation:

- Compute per-span Delta-U after repeated intervention replay.
- Aggregate repeats by mean intervened score.
- Report per-task and pooled target variation before any rank-signal interpretation.
- Keep deterministic replay claims forbidden while `PREFLIGHT_FAIL_DRIFT` persists.

### HotpotQA Graded Target

Primary HotpotQA score:

- `normalized_token_f1` from `fma.real_task_pilot.metrics.score_answer()`

Secondary HotpotQA reporting metrics:

- Alias-aware exact match from `score_answer()`
- Raw exact match before alias matching, if available

HotpotQA rationale:

- The failed smoke showed exact-match all-zero behavior: 0/10 original rows and 0/10 intervened mean rows were exact-match correct.
- A deterministic token-overlap score can expose near-miss answer degradation or recovery without adding an LLM judge or API-dependent grading.
- Exact match remains visible as a stricter secondary metric and cannot be used to overstate graded support.

### GSM8K Target

Primary GSM8K score:

- Numeric exact match using `score_answer()` and `normalize_gsm8k_answer()`

GSM8K rationale:

- GSM8K smoke was mostly saturated under exact match: 9/10 original rows were correct and unchanged after replay.
- v2.1 addresses saturation through fresh-row selection using only pre-outcome difficulty proxies, not by introducing post-hoc target labels or a new graded numeric judge.

## GSM8K Unsaturated Fresh-Row Policy

Fresh GSM8K rows must be selected from non-overlapping candidates only. Selection must not use correctness, Delta-U, replay outcomes, final answer quality, reference-answer similarity after generation, rank performance, or any target-side field.

Pre-outcome difficulty proxy:

- Use the existing `question_difficulty_proxy.score` family based on question length, number count, entity count, and supporting-fact count where available.
- Compute the proxy from source question metadata before generation or replay.

Selection rule:

- Exclude any row overlapping current pilot or v2 smoke/fresh artifacts by `sample_id`, `task_id`, dataset/config/split/source index, normalized question hash, reference answer hash, or non-empty alias hash.
- Rank eligible GSM8K candidates by `question_difficulty_proxy.score` descending.
- Break ties deterministically by manifest item hash, then source index.
- Select the top 200 eligible GSM8K rows.

This policy is intended to reduce exact-match saturation risk. It is not evidence that the selected rows are harder until fresh outcomes are generated under an approved future run.

## Span Diversity and Prompt Policy

The current smoke route mostly exercised verification-style spans. v2.1 must preregister a prompt and target-span policy that can test whether non-verification reflection operations have measurable local utility.

Future prompt policy:

- Request exactly visible, auditable solution text, not hidden reasoning.
- Require two visible reflection blocks when the model can produce them:
  - One `<reflection type="verification">...</reflection>` block.
  - One non-verification block with type `error_diagnosis`, `plan_revision`, `self-evaluation`, or `uncertainty_monitoring`.
- Prompt files must be snapshotted with a prompt version before any API execution.
- Prompt edits after manifest lock require a new manifest and new plan version.

Future target-span policy:

- Select at most two target spans per trace.
- Include the first `verification` span when present.
- Include the first eligible non-verification span when present.
- Traces with only verification spans remain schema-valid but count against the span-diversity gate.

Span-diversity reporting:

- Report eligible span count per task.
- Report non-verification span count per task.
- Report operation-type distribution separately from rank-signal metrics.
- Do not mix trajectory-level control results into span-level attribution baselines.

## Gates

### Smoke Gate

The v2.1 smoke gate is a feasibility gate only. It cannot produce a task-specific pass, global pass, deterministic replay claim, v2.1 validation claim, or PRM/filtering claim.

Configured smoke scale:

- 20 fresh rows total
- 10 GSM8K rows
- 10 HotpotQA rows
- No API execution without explicit bounded approval

Smoke stop conditions:

- Any manifest overlap.
- Any target leakage in selection, scoring, or reporting.
- Schema success rate below 0.95.
- Tag extraction success rate below 0.95.
- Replay success rate below 0.85.
- Nonzero Delta-U rows below 1 for either task.
- Pooled nonzero Delta-U rows below 3.
- Prompt snapshot or prompt version missing.
- API drift not logged and disclosed.

If any stop condition is active, v2.1 remains `planned` or smoke-failed, and the route stops for diagnostic reporting.

### Full-Run Gate

The full v2.1 validation route is unavailable until a future approved smoke satisfies the smoke gate and a separate bounded full-run approval is granted.

Full-run configured scale:

- 200 fresh rows per task
- 400 fresh rows total

Task-specific pass gate:

- Fixed manifest count locked before scoring.
- At least 190 valid traces per task.
- At least 150 eligible target spans per task.
- At least 20 nonzero Delta-U rows per task.
- Full coverage for fresh traces, eligible spans, v2.1 scores, baseline scores, replay rows, and Delta-U rows.
- Clean leakage audit.
- No target leakage and no post-intervention outcome fields in scorer inputs.
- No post-hoc threshold or weight tuning.
- Positive task-level preregistered primary rank signal with bootstrap CI lower bound above zero.
- API drift disclosed; deterministic replay claims remain forbidden if preflight drift persists.

`GLOBAL_S_FMA_V2_1_PASS` requires:

- GSM8K satisfies `TASK_SPECIFIC_S_FMA_V2_1_PASS`.
- HotpotQA satisfies `TASK_SPECIFIC_S_FMA_V2_1_PASS`.
- Both tasks meet the same preregistered rank-signal standard.
- Pooled rank signal is not negative.
- No active overlap, leakage, sparse-target, coverage, replay, prompt-version, drift-disclosure, or post-hoc-tuning stop condition.

## Claim Policy

Allowed wording before future approved execution:

- v2.1 evidence-target revision.
- Planned fresh-holdout route.
- Deterministic graded HotpotQA target specification.
- GSM8K unsaturated fresh-row selection policy.
- Span-diversity and prompt policy.
- Smoke and full-run gates.

Allowed wording after a future smoke-only pass:

- Smoke feasibility only.
- Target-variation feasibility only.
- Engineering readiness for a separately approved full validation request.

Forbidden wording:

- Same-pilot validation.
- Same-pilot tuning.
- `TASK_SPECIFIC_S_FMA_V2_PASS`.
- `GLOBAL_S_FMA_V2_PASS`.
- `TASK_SPECIFIC_S_FMA_V2_1_PASS` before full task-specific validation.
- `GLOBAL_S_FMA_V2_1_PASS` before both tasks pass.
- Deterministic replay claim while preflight drift persists.
- v2.1 scoring validation from smoke diagnostics.
- PRM/filtering claim.
- PRM/filtering superiority claim.

## Future Execution Boundary

This revision does not authorize API calls. Future execution requires a separate approval package that states:

- Target route: smoke-only or full validation.
- Manifest source and overlap audit.
- Prompt version.
- Expected API request count.
- Approved budget ceiling.
- Stop conditions.
- Claim boundary.

Until that approval exists, the only current status is:

```text
PILOT_BLOCKED
v2_1_planned_only
no_api_authorized
no_v2_1_validation
no_prm_claim
```
