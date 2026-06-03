# s_FMA_v2 Stochastic Route Budget/Risk Audit

Status: `planning-only`

This audit estimates the API request volume, token cost, minimum viable scale, failure risks, and reviewer-safe stop conditions for `STOCHASTIC_REPEATED_REPLAY_ROUTE`. It does not authorize or execute API calls. It does not run full generation, v2 scoring, replay, or PRM/filtering, and it does not rewrite historical preflight artifacts.

Current state remains:

- Fresh manifest clean: 400 rows, 200 GSM8K and 200 HotpotQA.
- Fresh API preflight status: `PREFLIGHT_FAIL_DRIFT`.
- Deterministic route: blocked.
- Stochastic repeated-replay route: planned-only.
- `next_allowed_step`: `STOP_AND_FIX_PREFLIGHT`.
- Project status: `PILOT_BLOCKED`.

## Source Basis

Read artifacts:

- `configs/s_fma_v2_fresh_holdout.yaml`
- `paper/s_fma_v2_fresh_holdout_plan.md`
- `outputs/s_fma_v2_fresh_holdout/api_preflight_report.json`
- `outputs/s_fma_v2_fresh_holdout/fresh_manifest.json`
- `outputs/s_fma_v2_fresh_holdout/manifest_overlap_audit.json`

Supporting read-only estimation artifacts:

- `outputs/s_fma_v2_fresh_holdout/api_preflight_attempts.jsonl`
- `outputs/s_fma_v2_fresh_holdout/api_preflight_traces.jsonl`
- `outputs/s_fma_v2_fresh_holdout/logs/api_preflight_cost_report.json`

The preflight report records 20 evaluated rows and 23 API attempts. The attempt log separates 20 base `preflight_record` requests from 3 `determinism_probe` requests. The cost report total is 20,321 tokens and USD 0.321005.

## Unit Costs

Pricing from config:

| Token type | USD per 1M tokens |
|---|---:|
| Input | 5.00 |
| Output | 30.00 |

Observed base generation requests from the 20 `preflight_record` attempts:

| Unit | Input tokens | Output tokens | Total tokens | Cost |
|---|---:|---:|---:|---:|
| Mean base request | 498.95 | 400.25 | 899.20 | USD 0.01450225 |
| Lower observed request | n/a | n/a | 471 | USD 0.007740 |
| Upper observed request | n/a | n/a | 1,754 | USD 0.040395 |

Range convention: lower/expected/upper costs use the observed min/mean/max cost among the 20 base preflight requests. No stochastic replay token artifact exists, so replay costs transfer the base generation request unit as a proxy. Key-row sensitivity is not included in the core counts because no key rows are selected in this planning-only audit; add `2 * key_row_span_count` extra requests if future preregistered key-row spans require 5 repeats instead of the standard 3.

## Full 400-Row Original Generation

Policy: one accepted original trace per manifest row.

| Item | Estimate |
|---|---:|
| Original generation requests | 400 |
| Expected input tokens | 199,580 |
| Expected output tokens | 160,100 |
| Expected total tokens | 359,680 |
| Lower cost | USD 3.096 |
| Expected cost | USD 5.8009 |
| Upper cost | USD 16.158 |

For comparison only, carrying the full preflight 23/20 attempt multiplier, including determinism probes, gives a conservative envelope of 460 request-equivalents, 406,420 tokens, and USD 6.4201. That envelope is not the stochastic route original-generation policy.

## Stochastic Intervention Replay

Preflight traces contain 20 spans across 20 evaluated records, so this audit uses 1.0 expected spans per sample. The configured reviewer gates still control validity: top-tier evaluation needs at least 190 valid traces and 150 eligible spans per task, plus at least 20 nonzero Delta-U rows per task.

For the full 400-row route:

| Item | Estimate |
|---|---:|
| Expected spans | 400 |
| Replay repeats per span | 3 |
| Expected replay requests | 1,200 |
| Expected replay tokens | 1,079,040 |
| Lower replay cost | USD 9.288 |
| Expected replay cost | USD 17.4027 |
| Upper replay cost | USD 48.474 |

## Scale Estimates

| Scale | Samples | Expected spans | Original repeats | Replay repeats/span | Bootstrap resamples | Total API requests | Expected tokens | Cost range | Expected cost | Runtime estimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Minimal smoke | 20 | 20 | 1 | 3 | 10,000 | 80 | 71,936 | USD 0.6192-3.2316 | USD 1.16018 | 7-27 minutes; 1.0h timeout ceiling |
| Pilot | 100 | 100 | 1 | 3 | 10,000 | 400 | 359,680 | USD 3.096-16.158 | USD 5.8009 | 33-133 minutes; 5.0h timeout ceiling |
| Top-tier candidate | 400 | 400 | 1 | 3 | 10,000 | 1,600 | 1,438,720 | USD 12.384-64.632 | USD 23.2036 | 2.2-8.9 hours; 20.0h timeout ceiling |

Runtime basis: no route-specific wall-clock measurement exists. Estimates assume sequential requests, 5-20 seconds per request, and the configured 45-second request timeout as a ceiling.

## Gates And Claims

| Scale | Gate/stop condition | Claim allowed if pass | Claim forbidden even if pass |
|---|---|---|---|
| Minimal smoke | Planning-only until explicit stochastic budget approval. If later approved, stop on schema/tag/final-answer failure, replay success below 0.85, missing drift disclosure, cost above approved ceiling, or any attempt to treat smoke output as validation. | Engineering smoke only: request-shape feasibility, rough cost confirmation, and preliminary replay-agreement diagnostics under disclosed drift. | No task-specific v2 pass, no global v2 pass, no deterministic replay claim, no full-generation-ready claim, no causal claim, and no PRM/filtering claim. |
| Pilot | Cannot satisfy preregistered per-task gates because it is below 190 valid traces and 150 eligible spans per task. If later approved, stop rather than scale if replay success is below 0.85, nonzero Delta-U remains too sparse, exact-match noise dominates, or cost/runtime exceed the approved pilot ceiling. | Pilot-only feasibility and variance diagnostics; possible evidence for whether scaling to the full 400-row route is worth a separate budget request. | No task-specific v2 pass, no global v2 pass, no deterministic replay claim, no full-generation-ready claim, no causal claim, and no PRM/filtering claim. |
| Top-tier candidate | Minimum reviewer-viable scale for the configured fresh holdout, but still blocked now. If later approved and run, stop on any active manifest overlap, target leakage, post-hoc weight/threshold change, schema/tag success below 0.95, replay success below 0.85, valid traces below 190 per task, eligible spans below 150 per task, nonzero Delta-U below 20 per task, unlogged API drift, missing same-table baselines, or cost above the approved ceiling. | Conditional future wording only: stochastic repeated-replay fresh-holdout evidence. Task-specific support is allowed only for tasks satisfying their preregistered gates; global v2 support is allowed only if both tasks pass and the same-table baseline/reporting contract is satisfied. | No deterministic replay claim, no deterministic causal claim, no full-generation-ready claim, no true causal effect claim, and no PRM/filtering superiority claim. |

Minimum scale distinction:

- Minimum for budget learning: 20 samples, 80 core API requests, expected cost USD 1.16018. This is not reviewer-viable validation.
- Minimum reviewer-viable configured scale: 400 samples, 1,600 core API requests, expected cost USD 23.2036. This is the first scale that can satisfy the per-task coverage gates if data quality holds.

## Reviewer Risks

- Drift/non-determinism: active. `PREFLIGHT_FAIL_DRIFT` forbids deterministic replay and deterministic full-generation wording. Repeated replay and bootstrap can only be used after explicit stochastic budget approval and drift disclosure.
- Sparse Delta-U: active prior risk. If either task has fewer than 20 nonzero Delta-U rows, stop as `insufficient_target_variation`.
- Exact-match noise: active metric risk. Exact-match brittleness can dominate HotpotQA or paraphrase-sensitive rows; appendix metrics do not replace preregistered gates.
- Task heterogeneity: active. A pass on one task cannot imply global support; task-specific wording remains the ceiling unless both tasks pass.
- API model drift over time: active. Any future run must log API date, endpoint, model, fallback, service tier, request parameters, response IDs, SDK/transport version, and drift disclosure.
- Cost-driven underpowering: active design risk. Smoke and 100-sample pilot scales are cheaper but cannot satisfy task/global pass gates.

## Stop Conditions

- Current state: do not run any API; `next_allowed_step` remains `STOP_AND_FIX_PREFLIGHT`.
- Any future API execution requires separate explicit stochastic validation budget approval; this audit is not approval.
- Any manifest overlap is a hard stop before scoring, replay, or reporting.
- Any target leakage or post-hoc weight/threshold change is a hard stop.
- Schema success rate below 0.95 or tag extraction success rate below 0.95 is a hard stop.
- Replay success rate below 0.85 is a hard stop.
- Valid trace count below 190 per task blocks task/global v2 pass.
- Eligible span count below 150 per task blocks task/global v2 pass.
- Nonzero Delta-U count below 20 per task is `insufficient_target_variation`.
- API drift not logged and disclosed is a hard stop.
- Missing required baselines in the same table blocks v2 pass wording.
- No PRM/filtering claim is allowed without `GLOBAL_S_FMA_V2_PASS` or a separate downstream validation gate.

## Budget Recommendation

Cost alone does not rule out the route: the top-tier candidate expected cost is USD 23.2036 and the observed-max proxy is USD 64.632, both below the USD 150 planning ceiling. Scientific risk is the limiting factor, not the expected token bill.

Do not request or spend a top-tier execution budget from this audit alone. If the user later chooses the stochastic route despite disclosed drift, use staged approval: minimal smoke first, pilot only if replay agreement and nonzero Delta-U look viable, and top-tier candidate only after pilot diagnostics justify scaling.

Current API allowed: `false`.
