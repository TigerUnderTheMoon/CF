# Real-Task v3 Preregistration Plan

Date: 2026-06-06

Status: planned preregistration plus guarded route implementation. Current configuration still does not authorize live API calls, replay, scoring, PRM/filtering, or any validation claim.

This document defines a new `real_task_v3` route after the frozen real-task pilot, v2.1 full-validation failure, v2.1 downstream filtering mini-failure, and archived v2.2 sparse-signal smoke failure. The current config does not authorize API calls, replay, scoring, PRM/filtering, or any validation claim; manifest generation is allowed only through the explicit manifest-only guard.

## Status Boundary

Current project status remains `PILOT_BLOCKED`.

The current failed artifacts may be used only for failure provenance, route motivation, and overlap exclusion. They must not be used to tune v3 thresholds, fit v3 weights, select v3 rows, relabel a failed route as successful, or infer downstream PRM/filtering gain.

## Manifest and Non-Overlap

Manifest generation must stop before API if smoke, dev, or locked splits cannot meet their target row counts after exclusion against the pilot, v2, v2.1, and v2.2 routes.

The six hard non-overlap keys are:

- `sample_id`
- `task_id`
- `dataset_config_split_source_index`
- `normalized_question_hash`
- `reference_answer_hash`
- `non_empty_alias_hash`

Fresh GSM8K source provenance may be added only as a declared input to the manifest-generation command. Split manifests are generated in smoke, dev, locked order, and earlier v3 splits become overlap sources for later splits.

## Scale and Budget

The v3 route uses three preregistered split roles:

| Split | GSM8K | HotpotQA | Purpose |
|---|---:|---:|---|
| Smoke | 100 | 100 | utility-density and transport feasibility |
| Dev/calibration | 500 | 500 | fit and freeze `w_struct` |
| Locked validation | 1000 | 1000 | one-shot validation |

Hard caps:

- Whole route API calls: `90000`
- Smoke API calls: `6500`
- Dev API calls: `32000`
- Locked validation API calls: `52000`
- Downstream API calls: `10000`
- Route cost cap: USD `5000`
- Per-call timeout: `90` seconds
- Max repair attempts per failed request: `2`
- Total repair fraction: `0.03`

API route:

- Endpoint: `POST https://opencode.ai/zen/go/v1/chat/completions`
- Model: `deepseek-v4-flash`
- Adapter: direct Chat Completions JSON-mode request
- Health check: 3 counted JSON-format requests before full smoke
- Circuit breaker: hard stop at 10 consecutive infrastructure errors or more than 20% infrastructure errors in any rolling 50-request window
- Fallback: no silent fallback endpoint; any fallback requires a separate request-only approval package before target statistics are observed

Cost controls:

- Static estimate before smoke
- Smoke-calibrated p50/p90/p95 token and cost forecast before dev and locked validation
- Locked-validation cost checkpoints every 10,000 requests
- If projected remaining locked cost exceeds the route or stage cap, freeze as `cost-exceeded partial locked` with no pass claim

Pricing references are [OpenCode Zen docs](https://dev.opencode.ai/docs/zen) and [DeepSeek pricing docs](https://api-docs.deepseek.com/quick_start/pricing).

Each problem has three original traces. Each trace may contribute at most three scored spans. Each span receives three replay repeats, with five repeats allowed only for predeclared high-variance rows.

## Utility Target

GSM8K primary utility:

```text
U = 0.60 * repeated_numeric_exact + 0.40 * numeric_proximity
numeric_proximity = exp(-abs(log((pred_abs + 1) / (ref_abs + 1))))
```

Parse failure receives `0`.

HotpotQA primary utility:

```text
U = 0.50 * alias_token_f1
  + 0.2777777778 * reference_only_f1
  + 0.2222222222 * support_overlap
```

The semantic-equivalence judge is disabled for the v3 target revision. Smoke must instead write `hotpotqa_surface_match_risk_report.json`, using the predicate `alias_token_f1 > 0.8` and `support_overlap < 0.2`, with count, fraction, and examples.

## Dense-Target Reliability Gate

No dev or locked validation may run unless smoke passes all dense-target reliability checks:

- Per-task unique utility values `>= 10`
- Fractional utility rows `>= 25%`
- Nonzero dense Delta-U: GSM8K `>= 25%`, HotpotQA `>= 35%`
- Residual utility variance beyond binary correctness `>= 15%`
- HotpotQA surface-match risk report emitted as diagnostic risk only

## w_struct Lock

The primary `w_struct` model is:

```text
sklearn.linear_model.LogisticRegression(
  penalty="l1",
  C=0.25,
  solver="liblinear",
  class_weight="balanced"
)
```

The target label is task-stratified top 20% dense Delta-U spans in the dev split. The model is fit only on dev and frozen before locked validation.

Allowed features:

- raw local utility
- structural necessity
- raw local utility and structural-profile interaction
- redundancy
- compensation
- bottleneck flag
- span type
- relative position
- span length
- task type
- question difficulty proxy

Forbidden source fields include correctness, original utility, intervened utility, Delta-U, replay outcome, final answer, reference similarity after generation, and rank metrics.

Dev stability gate:

- Raw local utility coefficient positive in at least 4 of 5 GroupKFold folds
- Structural-profile block direction nonnegative in at least 4 of 5 GroupKFold folds
- Structural-profile block bootstrap CI positive in at least 2 of 5 GroupKFold folds
- Structural-profile zero-rate `<= 0.90`, pooled and per task
- Sparse-signal warning when real-task structural zero-rate `> 0.80`
- Mean Spearman difference over raw local utility greater than `0.03`
- Brier score improvement over base rate at least `0.01`
- Calibration slope in `[0.7, 1.3]`

Dev must also write `synthetic_vs_real_structural_profile_alignment.json`, explicitly comparing zero-rate, bottleneck ratio, redundancy density, compensation, and local-utility alignment between synthetic and real-task profiles.

## Baselines

Must-have diagnostic baselines:

- random
- span length
- relative position
- taxonomy heuristic
- raw local utility
- structural necessity only
- token-occlusion attribution
- heuristic reflection score
- frozen reflection weight

PRM baseline policy:

- Preferred mode: frozen public PRM inference fixed in config before execution.
- Candidate: Qwen2.5-Math-PRM if hardware allows.
- Fallback mode: lightweight local PRM trained only on fixed dev data, labeled as `lightweight local PRM, not SOTA`.
- Hidden tuning after dev is forbidden.

A baseline fairness ledger must report model, data, compute, prompt, inference batch size, hardware, and failure status.

## Locked Validation Decision Tree

Scenario A: GSM8K pass, HotpotQA pass, pooled pass, and paired bootstrap shows `w_struct > raw local utility`. This permits a global real-task diagnostic validation claim.

Scenario B: exactly one task passes, the pooled gate passes, the paired CI lower bound for `w_struct - raw_local_utility` is greater than zero, the failed task has no leakage/transport/schema/baseline blocker, and the passing task survives Holm correction. This forbids a global claim and permits only task-specific diagnostic wording for the passing task.

Scenario C: rank gate passes but downstream gate fails. This permits diagnostic validation only and forbids PRM/filtering improvement.

Scenario D: any overlap, leakage, dense-target reliability, schema/transport, unrepaired-failure, or baseline-completion gate fails. This is a validation failure.

Statistical settings:

- Bootstrap resamples: `10000`
- Confidence level: `0.95`
- Bootstrap unit: `sample_id`
- Primary paired test: lower CI of `w_struct - raw_local_utility` is greater than zero
- Multiple-comparison correction: Holm-Bonferroni over task-level primary rank metrics

Secondary metrics may be reported but cannot rescue a failed primary gate.

## Downstream Gate

Downstream filtering or supervision runs only after Scenario A, or after an explicitly predeclared task-specific Scenario B downstream scope for the passing task. It compares `w_struct` against raw local utility, vanilla PRM, length-calibrated PRM, token attribution, and heuristic reflection scoring.

The downstream gate passes only if pooled mean advantage is positive, each task advantage is nonnegative, and the pooled paired-bootstrap lower CI is greater than zero.

## Claim Boundary

Allowed before execution:

- v3 is a planned preregistered route.
- v3 addresses sparse target variation, overfitting risk, cost control, and baseline fairness risks.
- v2.1 and v2.2 remain failed or archived provenance.

Forbidden before execution:

- real-task v3 validation success
- v2.1 or v2.2 rescue wording
- deterministic replay claim
- submission-ready or top-tier-ready wording
- PRM/filtering improvement or superiority
- repeated locked-set retry-until-pass wording
