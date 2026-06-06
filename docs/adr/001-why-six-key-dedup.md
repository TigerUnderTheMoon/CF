# ADR 001: Why Six-Key Deduplication

Status: accepted

Date: 2026-06-06

## Context

Six-key deduplication (六键去重) is the manifest policy (清单策略) that excludes a candidate validation row if it overlaps historical data on any hard provenance key (硬溯源键). FMA uses it because real-task validation can otherwise leak prior pilot (试点) or smoke evidence (冒烟测试证据) into a supposedly fresh holdout (新留存验证集).

The six keys are:

1. `sample_id`: dataset-provided or pipeline-assigned sample identifier.
2. `task_id`: task-level identifier used by FMA runners.
3. dataset/config/split/source index: split provenance and original row position.
4. `normalized_question_hash`: normalized prompt or question hash.
5. `reference_answer_hash`: normalized reference answer hash.
6. `alias_hash`: hash of non-empty answer aliases.

## Decision

Keep six-key deduplication as the default manifest gate for fresh real-task routes. Treat overlap on any hard key as a blocker unless an ADR or preregistered config explicitly narrows that key for a dataset-specific reason.

Empty aliases are non-informative for some datasets and should not by themselves imply semantic overlap. Non-empty `alias_hash` remains a hard key because aliases can reveal answer-equivalence leakage even when the question text differs.

## Rationale

FMA is a diagnostic framework, so its validation claims depend on provenance discipline as much as metric values. Six-key deduplication protects against three common leakage modes:

- identifier reuse (标识符复用) across regenerated manifests,
- question paraphrase (问题改写) or normalization collisions,
- answer alias reuse (答案别名复用) that can hide duplicate answer targets.

The policy is intentionally conservative. It can reduce available fresh rows, but the alternative is a validation set that appears fresh while sharing latent evidence (潜在证据) with historical pilot routes.

## Consequences

Positive:

- Fresh-holdout claims are easier to audit.
- Historical failed artifacts can remain frozen without contaminating new route evidence.
- Reviewers can inspect each exclusion key separately.

Negative:

- Strict OR-logic can create data-scarcity blockers.
- Dataset-specific alias conventions require explicit handling.
- A blocked manifest can be a governance result rather than a model-performance result.

## Claim Boundary

Passing a six-key manifest audit only proves non-overlap under the recorded keys. It does not prove task success, full validation, deterministic replay, or PRM/filtering improvement.
