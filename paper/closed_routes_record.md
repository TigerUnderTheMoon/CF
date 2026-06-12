# Closed Validation Routes Record

This document consolidates the outcomes of attempted real-task validation routes. GSM8K/HotpotQA replay routes remain failed, blocked, or abandoned. A later PRM800K hash-split route passed for real step-label ranking only, and a frozen PRM scorer comparison passed as in-distribution baseline context only. These do not validate GSM8K/HotpotQA replay or downstream PRM training.

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

## v3.5: PRM800K Contiguous Step-Ranking Route

- **Plan**: `real_task_v3_5_prm800k_preregistration_plan.md`
- **Route**: Offline real PRM800K phase2 step-label ranking with a contiguous dev/locked row split
- **Outcome**: **FAILED** - Locked validation failed sample/step gates, `w_struct` did not beat raw local utility, and Holm correction failed.
- **Root cause**: Contiguous PRM800K row splitting introduced row-order distribution drift; dev rows did not generalize to locked rows.
- **Status**: Failed validation provenance only. Failure audit: `outputs/real_task_v3_5_prm800k/failure_audit.json`.

## v3.6: PRM800K Hash-Split Step-Ranking Route

- **Plan**: `real_task_v3_6_prm800k_hash_preregistration_plan.md`
- **Route**: Offline real PRM800K phase2 step-label ranking with hash-stratified dev/locked split
- **Outcome**: **PASSED FOR STEP-RANKING ONLY** - Locked validation used 4417 samples and 34219 steps; `w_struct` mean Spearman was `0.6113401179642559`, raw local utility mean Spearman was `-0.07745914322519368`, and Holm correction passed.
- **Cost**: 0 API calls; estimated API cost USD `0.0`.
- **Status**: Supports only `M_STEP_RANKING` / `M_STEP_RANKING_REAL_PRM800K`. It does not support `F_REAL_TASK_SC_FMA`, `F_PRM_TRAINING`, GSM8K/HotpotQA replay validation, deterministic replay validation, or causal identification claims.

## v3.7: PRM Baseline Contamination Audit

- **Plan**: `real_task_v3_7_prm_baseline_comparison_preregistration_plan.md`
- **Route**: Bidirectional PRM800K contamination audit for public PRM/process-supervision baselines
- **Outcome**: **PASSED WITH IN-DISTRIBUTION LIMITATION** - Qwen PRM800K and unresolved public PRM overlap risk block external-generalization wording.
- **Cost**: 0 API calls; estimated API cost USD `0.0`.
- **Status**: Permits only in-distribution PRM baseline context. It does not support broad public-PRM superiority, `F_PRM_TRAINING`, `F_REAL_TASK_SC_FMA`, GSM8K/HotpotQA replay validation, deterministic replay validation, or causal identification claims.

## v3.8: Frozen PRM Locked Scoring Route

- **Plan**: `configs/real_task_v3_8_prm_locked_scoring.yaml`
- **Route**: Frozen public PRM scorer comparison on the v3.6 locked PRM800K hash split
- **Outcome**: **PASSED FOR IN-DISTRIBUTION BASELINE CONTEXT ONLY** - Locked scoring used 4417 samples and 34219 steps; frozen PRM prefix-score mean Spearman was `0.2515662235547571`, `w_struct` mean Spearman was `0.6113401179642559`, `w_struct - prm` bootstrap CI was `[0.34499208448462026, 0.3745467544914783]`, and Holm correction passed.
- **Cost**: 0 API calls; estimated API cost USD `0.0`.
- **Status**: Supports only `M_BASELINE_COMPARISON_CONTEXT_ONLY` under the v3.7 overlap limitation. It does not support external PRM generalization, `F_PRM_TRAINING`, `F_REAL_TASK_SC_FMA`, GSM8K/HotpotQA replay validation, deterministic replay validation, or causal identification claims.

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
| v3.5 (PRM800K contiguous) | FAILED | Row-order distribution drift |
| v3.6 (PRM800K hash split) | PASSED STEP-RANKING ONLY | Supports real PRM800K step-label ranking; not replay |
| v3.7 (PRM contamination audit) | PASSED WITH LIMITATION | PRM800K overlap risk blocks external PRM generalization |
| v3.8 (frozen PRM scoring) | PASSED CONTEXT ONLY | Supports in-distribution PRM baseline context; not PRM training |
| Legacy pilot | BLOCKED | Preflight drift failure |

**No GSM8K/HotpotQA replay validation evidence exists.** Claims involving real-task replay MUST remain `failed_validation`, `pilot_blocked`, or `future_validation`. The positive real-data evidence currently recorded here is limited to v3.6 PRM800K step-ranking and v3.8 overlap-limited PRM baseline context.
