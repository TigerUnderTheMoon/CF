# Closed Validation Routes Record

This document consolidates the outcomes of all attempted real-task validation routes. All routes have failed or been abandoned. No real-task validation evidence may be claimed.

---

## v2: s_FMA Stochastic Smoke (Fresh Holdout)

- **Plan**: `s_fma_v2_fresh_holdout_plan.md` (archived)
- **Route**: Deterministic replay + stochastic repeated replay on non-overlapping GSM8K/HotpotQA traces
- **Outcome**: **PILOT_BLOCKED** - API preflight failed with `PREFLIGHT_FAIL_DRIFT`. Stochastic smoke produced zero nonzero Delta-U rows for GSM8K.
- **Status**: Failed sparse signal. Archived to `outputs/archive/s_fma_v2_fresh_holdout/`.

## v2.1: Evidence Target Revision (Fresh Holdout)

- **Plan**: `s_fma_v2_1_evidence_target_revision.md` (archived)
- **Route**: Revised Delta-U targets (graded for GSM8K, token-F1 for HotpotQA), full stochastic validation
- **Outcome**: **ABANDONED** - Full stochastic validation failed quality gates (quality rates < 1.0, only 16 nonzero GSM8K Delta-U vs. threshold 20). Engineering retry also failed.
- **Status**: V2.1 frozen as failed provenance. The archive has been restored as DVC-managed failed provenance under `outputs/archive/s_fma_v2_1_fresh_holdout/`; archive integrity is recorded in `outputs/archive/s_fma_v2_1_archive_integrity_audit.json`.
- **Transition**: Audited in `v2_1_to_v2_2_transition_audit.md` (archived). V2.1 artifacts must not be reused for v2.2 tuning.

## v2.2: Exploratory Stochastic Smoke

- **Plan**: `s_fma_v2_2_preregistration_plan.md` (archived)
- **Route**: Repeated-numeric-success-probability for GSM8K, bounded transport repair, full bootstrap CI
- **Outcome**: **FAILED** - Stochastic smoke produced zero nonzero Delta-U for GSM8K. Preflight also failed drift and metadata gates.
- **Status**: Failed sparse signal. Archived to `outputs/archive/s_fma_v2_2_fresh_holdout/`.

## v3: Real-Task DELETE Intervention

- **Plan**: `real_task_v3_preregistration_plan.md` (archived)
- **Route**: Three-split route (smoke/dev/locked) with DELETE intervention, logistic-regression w_struct
- **Outcome**: **FAILED** - Data scarcity: strict 6-key OR-logic deduplication exhausted all available rows. GSM8K 0 rows, HotpotQA 0 rows post-dedup.
- **Status**: Manifest generation blocked. Archived to `outputs/archive/real_task_v3/`.

## v3.1: Real-Task REPLACE Intervention

- **Plan**: `real_task_v3_1_preregistration_plan.md` (archived)
- **Route**: REPLACE (masked-span) fallback after v3 DELETE failure
- **Outcome**: **FAILED** - REPLACE smoke failed sparse-signal gates for both tasks (GSM8K 8 nonzero vs. gate 25; HotpotQA 14 nonzero vs. gate 35).
- **Status**: Both DELETE and REPLACE interventions produced insufficient Delta-U variation. Archived to `outputs/archive/real_task_v3_1/`.

## v2.1 Full Validation Route Decision

- **Document**: `full_validation_route_decision.md` (archived)
- **Decision**: Abandon strict v2.1 full validation as non-viable. Route A (conservative diagnostic wording) adopted.
- **Constraint**: Any future validation route must use fresh data with independently preregistered gates. No reusing v2.1 artifacts.

---

## Summary

| Route | Status | Key Blocker |
|-------|--------|-------------|
| v2 (stochastic smoke) | FAILED | 0 nonzero GSM8K Delta-U; preflight drift |
| v2.1 (evidence target) | ABANDONED | Quality gates < 1.0; sparse GSM8K Delta-U |
| v2.2 (exploratory) | FAILED | 0 nonzero GSM8K Delta-U; preflight drift |
| v3 (real-task DELETE) | FAILED | Data scarcity (0 rows post-dedup) |
| v3.1 (real-task REPLACE) | FAILED | Sparse signal both tasks |
| Legacy pilot | BLOCKED | Preflight drift failure |

**No real-task validation evidence exists.** All claims involving real-task data MUST be labeled `failed_validation` or `pilot_blocked`.
