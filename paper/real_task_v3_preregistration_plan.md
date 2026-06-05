# Real-Task v3 Preregistration Plan

Date: 2026-06-06

Status: planned preregistration only.

This document defines a new `real_task_v3` route after the frozen real-task pilot, v2.1 full-validation failure, v2.1 downstream filtering mini-failure, and archived v2.2 sparse-signal smoke failure. It does not authorize API calls, manifest generation, replay, scoring, PRM/filtering, or any validation claim.

## Status Boundary

Current project status remains `PILOT_BLOCKED`.

The current failed artifacts may be used only for failure provenance, route motivation, and overlap exclusion. They must not be used to tune v3 thresholds, fit v3 weights, select v3 rows, relabel a failed route as successful, or infer downstream PRM/filtering gain.

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
U = 0.45 * alias_token_f1
  + 0.25 * reference_only_f1
  + 0.20 * support_overlap
  + 0.10 * semantic_equivalence
```

The semantic-equivalence judge model, prompt, rubric, temperature, retry rule, and human audit sheet must be locked before smoke execution.

## Dense-Target Reliability Gate

No dev or locked validation may run unless smoke passes all dense-target reliability checks:

- Per-task unique utility values `>= 10`
- Fractional utility rows `>= 25%`
- Nonzero dense Delta-U: GSM8K `>= 25%`, HotpotQA `>= 35%`
- Residual utility variance beyond binary correctness `>= 15%`
- HotpotQA semantic judge human audit: 50 random pairs, Cohen's kappa `>= 0.70`
- Semantic judge length-bias partial correlation absolute value `<= 0.20`

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
- raw local utility * structural necessity
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
- Structural necessity coefficient positive in at least 4 of 5 GroupKFold folds
- Mean Spearman difference over raw local utility greater than `0.03`
- Brier score improvement over base rate at least `0.01`
- Calibration slope in `[0.7, 1.3]`

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

Scenario B: one task passes, one task fails, and pooled passes. This forbids a global claim and permits only task-specific wording for the passing task.

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

Downstream filtering or supervision runs only after Scenario A or explicit task-specific Scenario B. It compares `w_struct` against raw local utility, vanilla PRM, length-calibrated PRM, token attribution, and heuristic reflection scoring.

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
