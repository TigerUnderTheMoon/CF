# PLANS.md - Functional Metacognitive Attribution (FMA)

> **Version**: 2.3
> **Status**: Research Proposal / Living Document  
> **Last Updated**: 2026-06-12

---

## 0. Planning Boundary

This document separates three layers:

- Vision: long-term target architecture and archived future-application ideas.
- Contract: current required artifacts, gates, and allowed claim wording.
- Evidence: generated artifacts and tests that have actually passed.

Proposal text is not evidence. Current claim status is governed by `paper/claim_registry.md`; current pilot readiness is governed by `outputs/real_task_pilot/readiness_audit.json` and summarized in `paper/submission_readiness_audit.md`.

## 0. Implementation Status

| Phase | Status | Artifact |
|---|---|---|
| Phase 1 | Completed | Core attribution engine |
| Phase 2 | Completed | Taxonomy-stratified evaluation |
| Phase 3 | Completed | Intervention locality |
| Phase 4 | Completed | Functional validity |
| Phase 5 | Completed | Counterfactual Functional Attribution |
| Phase 6 | Completed | Structural Reflection Attribution |
| Phase 7 | Completed | Redundancy and compensation analysis |
| Real-task pilot | Guarded / blocked | GSM8K/HotpotQA API preflight, replay, baselines, controls, readiness audit |
| s_FMA_v2 fresh holdout | Planned / preflight drift-failed / stochastic smoke sparse-signal failed | Fresh manifest/audit clean; guarded API preflight-only reports `PREFLIGHT_FAIL_DRIFT`; first approved 20-row stochastic smoke reported `STOCHASTIC_SMOKE_FAIL_GENERATION`; bounded rerun reports `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL` with 60/60 successful replay results, `nonzero_delta_rows: 0`, and `cost_used_usd: 3.14542`; current status remains `PILOT_BLOCKED`; no full generation, no v2 scoring, no task/global pass |
| s_FMA_v2.1 evidence-target revision | Full stochastic validation abandoned / pilot stochastic pass only | HotpotQA `normalized_token_f1` target, GSM8K `question_difficulty_proxy` selection, and span-diversity prompt policy materialized; schema-fix non-API package regeneration produced `outputs/s_fma_v2_1_fresh_holdout/fresh_manifest.json` with 400 rows, zero selected overlap, `V2_1_CONTRACT_CLEAN`, and request-only API_PREFLIGHT_ONLY approval files locked to prompt hash `prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b`; the approved API_PREFLIGHT_ONLY rerun remains `PREFLIGHT_FAIL_DRIFT`; the bounded stochastic smoke rerun was feasible for a pilot-budget request; the recomputed pilot stochastic report passed pilot gates only; the full stochastic validation artifact reports `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`, positive pooled/GSM8K/HotpotQA rank signal, `TASK_SPECIFIC_pass: false`, and `GLOBAL_pass: false`; failure sources are 8 timeout/connection attempts lowering JSON/schema/tag/final-answer rates to `0.9971181556195965` and GSM8K nonzero Delta-U `16 < 20`; the strict engineering retry also failed with `GLOBAL_pass: false`, 119 incremental retry API calls, effective report API attempts `2794`, and abandonment reason `transport_unresolved_and_gsm8k_sparse_signal_below_preregistered_threshold`; strict v2.1 full validation is abandoned as non-viable under the current contract; the failure audit is `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json` and `.md`; the abandonment audit is `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json` and `.md`; no deterministic replay, submission-upgrade, gate-relaxation, or PRM/filtering claim is allowed; status remains `PILOT_BLOCKED` |
| v2.1 downstream filtering mini-validation | Failed / abandoned mini diagnostic | One preregistered pilot-sourced online mini-validation ran under `V2_1_DOWNSTREAM_FILTERING_MINI_VALIDATION_ONLY`; artifacts are `outputs/s_fma_v2_1_fresh_holdout/v2_1_downstream_filtering_preregistration.{json,md}`, `v2_1_downstream_filtering_report.{json,md}`, attempts/traces/jobs/candidate-score/leakage-audit files, and `logs/v2_1_downstream_filtering_cost_report.json`; it used 20 paired samples, 40 API calls, USD `1.629725`, and 20/20 valid pairs, but failed `V2_1_DOWNSTREAM_FILTERING_MINI_FAIL_FILTERING_SIGNAL` with pooled mean advantage `-0.05`, GSM8K `-0.2`, and HotpotQA `0.1`; next allowed step is `ABANDON_MINI_DOWNSTREAM_FILTERING_ROUTE`; current status remains `PILOT_BLOCKED`; no full-validation, deterministic replay, submission-upgrade, new-route, or PRM/filtering superiority claim is allowed |
| s_FMA_v2.2 exploratory route | Archived failed exploratory provenance | Manifest/prompt/preflight/smoke artifacts exist, but the route is stopped for the current diagnostic paper. API preflight is drift-failed, stochastic smoke is sparse-signal failed, and no pilot validation, route-pass wording, or PRM/filtering claim is authorized. |
| real_task_v3 / v3.1 smoke boundary | Failed sparse-signal preliminary test | v3 DELETE smoke failed sparse-signal gates with GSM8K `1/25` and HotpotQA `28/35`; v3.1 REPLACE/masked-span smoke failed sparse-signal gates with GSM8K `8/25` and HotpotQA `14/35`; companion audit `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json` freezes implementation/status/next-step inconsistencies; current status remains `PILOT_BLOCKED`; no locked validation, claim upgrade, or downstream PRM/filtering gain claim is allowed. |
| real_task_v3.5 / v3.6 PRM800K step-ranking | v3.5 failed; v3.6 passed for methodological step-ranking only | v3.5 failed because a contiguous PRM800K row split introduced row-order distribution drift; failure audit is `outputs/real_task_v3_5_prm800k/failure_audit.json`. v3.6 uses hash-stratified PRM800K phase2 rows and passes locked step-ranking validation: 4417 samples, 34219 steps, `w_struct` Spearman `0.6113401179642559`, raw local utility Spearman `-0.07745914322519368`, Holm correction passed, 0 API calls. It supports only `M_STEP_RANKING` / `M_STEP_RANKING_REAL_PRM800K`; it does not validate GSM8K/HotpotQA replay, deterministic replay, PRM training, or causal claims. |
| PRM/filtering validation | Not supported / current mini diagnostic failed | The v2.1 mini downstream filtering run failed and is abandoned; PRM/filtering is a future application hypothesis, not a current submission requirement. |

The v2.1 pilot transport failure audit and single retry package remain provenance for the corrected pilot route. The former request-only full validation package is retained as approval provenance, while the current execution artifacts are frozen as failed full-validation provenance under `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_stochastic_*` plus `v2_1_full_validation_failure_audit.*`. The strict engineering retry artifacts under `v2_1_full_stochastic_engineering_retry_*` and `v2_1_full_validation_abandonment_audit.*` record the final v2.1 abandonment decision. They do not authorize deterministic replay language, submission-upgrade claims, status upgrade, gate relaxation, or PRM/filtering.

The v2.2 preregistration is archived as failed exploratory provenance, not a rescue of the v2.1 full artifact and not the current paper route. It must not be used to tune gates, choose rows, fit weights, or upgrade claims. No further v2.2 execution is planned for the diagnostic manuscript.

Phase 7 is implemented as a deterministic structural interpretation layer over stored Phase 6 outputs. The initial hypothesis was that reflection may exhibit distributed compensatory organization, but the observed results refine this into locally useful but structurally sparse reflective organization: moderate redundancy, weak compensation, low distributedness, sparse bottlenecks, and weak alignment between attribution and necessity.

The real-task pilot layer is implemented as a guarded extension rather than a replacement for historical Phase 5-7 artifacts. It uses `configs/real_task_pilot.yaml`, `schemas/real_task_trace.schema.json`, and `scripts/run_real_task_pilot.py`. Live API execution requires `--allow-api`; without an explicit `user_approved_budget_usd`, the cost gate blocks full pilot execution. The current readiness state is `PILOT_BLOCKED`: replay, Delta-U, rank-signal coverage, baseline leakage, and readiness-level trajectory-control gates pass, but `PILOT_FAIL_SIGNAL` and `PREFLIGHT_FAIL_DRIFT` remain.

The current pilot failed the primary rank-signal gate and is frozen as `development_failure_audit` in `outputs/real_task_pilot/primary_signal_failure_audit.md` and `.json`. It can motivate error analysis and `s_FMA_v2` design, but it cannot fit v2 weights, tune thresholds, or validate a redesigned score. The fresh holdout required for v2 is specified in `paper/s_fma_v2_fresh_holdout_plan.md` and `configs/s_fma_v2_fresh_holdout.yaml`; `outputs/s_fma_v2_fresh_holdout/manifest_overlap_audit.json` is `MANIFEST_OVERLAP_CLEAN` after the empty-alias policy revision. The fresh-holdout live API preflight-only report is `PREFLIGHT_FAIL_DRIFT` after 20 evaluated records, with schema/tag/final-answer success rates all `1.0` and actual preflight cost `0.321005`; the first approved 20-row stochastic smoke was finalized as `STOCHASTIC_SMOKE_FAIL_GENERATION` with 8/20 valid original traces and 12 non-JSON original attempts. The approved bounded rerun updated `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_report.json` to `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL` with 20 smoke samples, 60/60 successful replay results, `nonzero_delta_rows: 0`, and `cost_used_usd: 3.14542`.

The approved v2.1 API_PREFLIGHT_ONLY rerun used the regenerated prompt-locked package and rewrote only the allowed preflight outputs. It remains `PREFLIGHT_FAIL_DRIFT` after 20 records and 23 API attempts, with cost `0.86245`, JSON/schema/tag/final-answer success `1.0`, 20 valid trace rows, and 23/23 non-empty `raw_output` attempts; the current preflight failure is drift plus missing metadata, not empty extracted output. The latest bounded v2.1 stochastic smoke rerun wrote only the allowed smoke artifacts under `outputs/s_fma_v2_1_fresh_holdout/` and reports `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST`: JSON/schema/tag/final-answer success rates are `1.0`, replay success rate is `1.0`, and nonzero Delta-U counts are 20 pooled, 7 GSM8K, and 13 HotpotQA. The recomputed v2.1 pilot stochastic report reports `V2_1_PILOT_STOCHASTIC_PASS`, but this remains pilot stochastic gate evidence only. The later full stochastic validation failed its preregistered gates despite positive rank signal: quality rates were `0.9971181556195965` rather than required `1.0`, and GSM8K nonzero Delta-U was `16 < 20`. The strict engineering retry failed as well: it used 119 incremental retry API calls, produced an effective report with 2794 API attempts, retained `GLOBAL_pass: false`, and hard-stopped with `transport_unresolved_and_gsm8k_sparse_signal_below_preregistered_threshold`. Strict v2.1 full validation is therefore abandoned, not rescued. No deterministic replay claim, full validation pass claim, submission-upgrade claim, gate-relaxation claim, or PRM/filtering claim is allowed from these results.

The one-shot v2.1 downstream filtering mini-validation was preregistered separately from full validation and executed once under a USD `5` ceiling and 60-request cap. It finished at 40 API calls and USD `1.629725`, with 20/20 valid paired samples, but failed the filtering-signal gate: pooled mean advantage was `-0.05`, GSM8K `-0.2`, and HotpotQA `0.1`. This route is abandoned as a failed mini diagnostic, not retried or scaled. It does not unlock `DOWNSTREAM_PRM_FILTERING_VALIDATION_PASS`, PRM/filtering claims, a new route, or any readiness upgrade.

The v2.2 artifacts are retained only as archived failed exploratory provenance. The current API preflight is drift-failed and the current smoke checkpoint is sparse-signal failed. They are not part of the active paper plan and should not drive additional execution, route-pass wording, or PRM/filtering claims.

The current real-task v3/v3.1 replay evidence is frozen as negative preliminary test. v3 DELETE smoke executed and failed sparse-signal gates despite passing transport and trace-count gates. v3.1 REPLACE/masked-span smoke executed and also failed sparse-signal gates; the companion audit records the raw report's implementation/status/next-step inconsistencies. These replay routes do not authorize locked validation, threshold retuning, downstream claims, or any status upgrade beyond `PILOT_BLOCKED`.

The PRM800K step-ranking branch is separate from GSM8K/HotpotQA replay. v3.5 is failed provenance because contiguous row splitting introduced row-order distribution drift. v3.6 corrects that problem with hash-stratified splitting and passes locked real PRM800K step-label ranking validation at zero API cost. The allowed claim is limited to `M_STEP_RANKING` / `M_STEP_RANKING_REAL_PRM800K`; `F_REAL_TASK_SC_FMA`, `F_PRM_TRAINING`, deterministic replay, and causal identification remain future or forbidden claims.

### 0.1 Diagnostic Mainline and Evidence Contract

The diagnostic manuscript mainline is:

```text
FMA reflection utility learning
-> structural necessity diagnostic
-> failed real-task/downstream preliminary test
```

The Chinese framework positions FMA as a process-supervision framework: structure-preserving intervention, Conditional Interventional Utility, counterfactual matching, doubly robust estimation, and distribution-conditioned aggregation can produce reflection utility signals for PRM/filtering. The current repository evidence adds the core diagnostic finding needed to make that story credible: local utility is too broad to serve directly as a supervision weight, because structural necessity is sparse and weakly aligned with local attribution.

Current must-satisfy contract:

- Phase 5-7 are completed diagnostic evidence.
- Historical `outputs/` artifacts remain provenance evidence and are not rewritten.
- Real-task generation/replay is pilot evidence only until readiness gates pass. Separately, v3.6 real PRM800K step-label ranking is passed methodological evidence only and cannot be used as replay validation.
- Current pilot failed and remains frozen; same-pilot tuning cannot upgrade it.
- Fresh manifest/audit is clean for v2, but the first 20-row stochastic smoke failed original generation and the bounded rerun failed with sparse Delta-U signal; full fresh traces, v2 scoring, replay validation, and rank-signal validation have not run. v2.1 has separate package materialization, a passed transport-only canary, an approved API_PREFLIGHT_ONLY rerun that now parses successfully but remains `PREFLIGHT_FAIL_DRIFT` with missing disclosure metadata, a bounded stochastic smoke rerun that was feasible for a pilot-budget request, and a recomputed pilot stochastic artifact whose task/global pilot gates pass. The later v2.1 full stochastic validation and strict engineering retry are failed provenance, not a pass: rank signal is positive, but preregistered quality and GSM8K sparse-signal gates failed, and strict v2.1 full validation is now abandoned as non-viable under the current contract. v2.2 is archived failed exploratory provenance. v3 DELETE and v3.1 REPLACE/masked-span smokes are failed sparse-signal preliminary test only; they do not authorize pilot validation, scoring beyond smoke diagnostics, validation claims, route-pass wording, or downstream PRM/filtering gain claims. v3.6 PRM800K hash-split validation supports only the real step-label ranking methodological claim.
- PRM/filtering is not validated in the current repository; the completed v2.1 mini downstream filtering diagnostic failed and is abandoned.
- Any candidate supervision weight must be structurally calibrated rather than `Normalize(FMA)` alone.

Future application hypothesis:

- A future PRM/filtering experiment may train or apply reflection weights derived from FMA.
- That weight must incorporate structural necessity, bottleneck rarity, redundancy, and compensation diagnostics.
- Any future experiment must compare against vanilla PRM, length-calibrated PRM, token attribution, and heuristic reflection scoring before claiming downstream value.

---

## 1. Research Objective

Develop a lightweight, intervention-based framework for **reflection utility learning** in LLM agents, with Functional Metacognitive Attribution (FMA) as the attribution layer and structural necessity diagnostics as the constraint that prevents naive process supervision.

**Core Question**:  
> Which reflective operations measurably improve downstream task performance under controlled perturbation, which are structurally necessary, and which are too redundant to receive direct supervision weight?

This project integrates:

- Counterfactual attribution,
- Reflection utility estimation,
- Structural necessity diagnostics,
- Process-level reward modeling,
- Lightweight intervention-sensitive analysis,

**without requiring**:

- Large-scale RLHF infrastructure,
- Massive GPU clusters,
- Full agent operating systems.

**Operational Definition**:  
We define a *reflection* as any self-directed cognitive operation **explicitly demarcated** in the model's output stream—e.g., within `<reflection>` tags, `Wait, let me reconsider...` spans, or structured self-critique blocks. We do **not** treat reflection as an implicit latent state.

---

## 2. Research Hypothesis

**Prevailing Assumption (which we challenge)**:  
> More reflection leads to better reasoning.

**Our Framing**:  
> Reflection is a heterogeneous intervention variable; its utility is context-dependent and must be estimated through controlled perturbation, not correlation alone.

**Key Hypothesis**:  
Reflective operations exhibit **heterogeneous functional utility**. Specific reflection types may:

| Positive Effects | Negative Effects |
|-----------------|------------------|
| Improve reasoning trajectories | Waste context budget without performance gain |
| Repair failure states | Amplify existing errors via self-confirmation |
| Reduce hallucinations | Increase reasoning instability |
| Stabilize long-horizon reasoning | Create unnecessary computational overhead |

**Implication**:  
Reflection should be treated as an **observable intervention target** rather than a monolithic capability. The relevant question is not *whether* to reflect, but *which* reflections to retain, modify, suppress, or use as structurally calibrated process-supervision signals.

---

## 3. Novelty Positioning

### 3.1 Gap in Existing Work

Current reflection methods mainly optimize reflection **globally**:

| Method | Focus | Evaluation Granularity |
|--------|-------|----------------------|
| Reflexion | Self-feedback loops | Trajectory-level success |
| Self-Refine | Iterative refinement | Final answer correctness |
| ReAct | Thought-Action interleaving | Task completion rate |
| Process Reward Models (PRM) | Step-level correctness | Intermediate step labels |

**Critical Gap**: Existing work evaluates:
- Final task performance,
- Trajectory success,
- Aggregate reasoning quality,

but **not** the intervention-sensitive utility of *individual* reflection steps.

### 3.2 Our Core Distinction

```text
Existing Work:          "Does reflection help overall?"
This Project:         "Which reflection step helps, harms, or does nothing under controlled perturbation?"
```

### 3.3 Primary Novelty

1. **Counterfactual reflection attribution**: Estimating the functional influence of single reflection operations via deterministic replay,
2. **Intervention-level utility estimation**: Per-step utility scores rather than aggregate metrics,
3. **Structural necessity calibration**: separating widespread local utility from sparse bottlenecks and redundancy before constructing supervision weights,
4. **Replay analysis for metacognition**: a lightweight perturbation testbed for reflective cognition,
5. **Required downstream validation**: future PRM/filtering experiments must test structurally calibrated FMA signals against vanilla and heuristic alternatives.

---

## 4. Reflection Taxonomy

We treat reflection as **heterogeneous** rather than uniform. This taxonomy serves both as an analytical framework and as a labeling schema for the dataset.

### 4.1 Proposed Reflection Types

| Reflection Type | Functional Role | Example Trigger |
|-----------------|-----------------|-----------------|
| **Error-checking** | Detect reasoning mistakes | Discrepancy in intermediate calculation |
| **Verification** | Validate intermediate conclusions | Cross-checking arithmetic or facts |
| **Planning** | Re-plan future reasoning | Subgoal decomposition or strategy shift |
| **Decomposition** | Split complex tasks | Breaking multi-step problems into parts |
| **Self-critique** | Criticize prior reasoning | Identifying logical fallacies or biases |
| **Recovery** | Repair failed trajectories | Backtracking from an incorrect path |
| **Consistency-checking** | Detect logical inconsistency | Ensuring conclusions follow from premises |

### 4.2 Research Questions

- Which reflection type has the highest average functional utility?
- Which types are most token-efficient (utility per token)?
- Which types become harmful under high uncertainty or low model capability?
- Which tasks benefit from which reflection categories?

---

## 5. Core Research Directions

### Direction A — Reflection Utility Attribution (Primary)

**Goal**: Estimate the local functional contribution of individual reflective steps to downstream task success.

**Observable Setup**:
For a trajectory segment:
```
s_t -> a_t -> o_t
        |
   reflection rho_t
        |
s_{t+1} -> a_{t+1} -> Reward
```

**Target Estimand**:  
```
Utility(rho_t) = Reward(tau_with rho_t) - Reward(tau_without rho_t)
```

**Methodology**:
- **Structure-preserving masking**: Replace the reflection span payload with length-matched mask content and re-generate the continuation under **deterministic decoding** (greedy or fixed seed) to estimate intervention-sensitive influence while preserving layout.
- **Reflection masking**: Ablation of specific reflection sub-spans.
- **Trajectory replay with fixed randomness**: Ensure outcome differences are attributable to the reflection intervention, not stochasticity.
- **Intervention-based evaluation**: Compare outcome distributions across intervention conditions.

**Outputs**:
- Per-reflection utility scores (positive / neutral / harmful),
- Utility distribution by reflection type and task domain,
- Harmful reflection detection and qualitative typology.

---

### Direction B — Reflection PRM (Process Reward Modeling)

**Goal**: Design a lightweight reward-modeling validation that scores reflection quality *in situ*, enabling online filtering or generation guidance only after the diagnostic signal is structurally calibrated.

**Standard PRM Limitation**:  
Scores only final answer correctness or terminal state value.

**Our Extension**:  
Scores the **functional utility of intermediate reflective cognition**, but does not treat local utility as a sufficient supervision weight.

**Input**:  
`(reasoning trace, reflection segment rho_t, local state s_t)`

**Output**:  
`u_hat_t = f_theta(s_t, rho_t)` — predicted reflection utility.

For any future downstream application validation, the filtering signal should be:

```text
w_t = g(local utility, structural necessity, bottleneck status, redundancy, compensation)
```

not `Normalize(FMA)` alone.

**Formulations**:
- Scalar regression against counterfactual utility labels,
- Pairwise ranking of reflections by estimated utility,
- Binary utility classification (helpful vs. neutral vs. harmful).

**Novel Supervision Signal**:  
Counterfactual utility labels derived from Direction A's intervention engine, yielding **intervention-derived process rewards** rather than heuristic or human preference labels. The Phase 5-7 finding adds a constraint: labels must be calibrated against sparse structural necessity so that redundant local utility is not over-supervised.

**Current Status**:  
No trained PRM, filtering run, or downstream comparison artifact is currently present. This direction is a required validation layer, not completed evidence.

---

### Direction C — Counterfactual Reflection Replay

**Goal**: Construct a lightweight replay testbed for reflective cognition by replaying trajectories under modified reflection conditions.

**Intervention Types**:

| Intervention | Description | Purpose |
|--------------|-------------|---------|
| **Masking** | Replace reflection payload with length-matched masks and regenerate continuation | Baseline utility estimation |
| **Replacement** | Substitute with alternative reflection content | Test content sensitivity |
| **Injection** | Insert reflection where none occurred | Test necessity of reflection timing |
| **Reordering** | Permute sequence of multiple reflections | Test ordering effects |
| **Corruption** | Introduce noise into reflection content | Test robustness to low-quality reflection |

**Measured Effects**:
- Task success rate delta (Delta Acc),
- Reasoning stability (consistency across intervention conditions),
- Token efficiency (cost-benefit of reflection length vs. accuracy gain),
- Trajectory divergence (structural similarity of continuations).

**Value**:  
This becomes an **intervention-sensitive testbed** for reflective cognition, enabling offline evaluation of reflection policies without online RL risks.

---

## 6. Experimental Protocol

### 6.1 Reflection Insertion Strategy

Standard trajectory format:
```
Question
-> Initial Reasoning (CoT)
-> [Reflection: rho_t]
-> Revised Reasoning
-> Final Answer
```

Reflection can be:
- **Explicitly generated**: Prompted via structured templates,
- **Periodically inserted**: At fixed intervals (e.g., every k reasoning steps),
- **Conditionally triggered**: After uncertainty detection (entropy threshold or verifier signal).

### 6.2 Counterfactual Replay Protocol

**Original**:
```
CoT -> Reflection -> Continue -> Final Answer
```

**Counterfactual (Masking)**:
```
CoT -> [MASK REFLECTION PAYLOAD] -> Continue Generation -> Final Answer
```

**Alternative Interventions**:
- **Replacement**: `CoT -> Alt_Reflection -> Continue`,
- **Corruption**: `CoT -> Corrupted_Reflection -> Continue`,
- **Permutation**: Reorder multiple reflections in multi-step reasoning,
- **Truncation**: Shorten reflection while preserving core content.

**Deterministic Control**:  
All replay conditions use **greedy decoding** (`temperature=0`) or **identical sampling seeds** to ensure that observed outcome differences are attributable to the reflection intervention, not sampling variance.

### 6.3 Reflection Sampling

Reflection candidates can be generated via:
- **Self-reflection prompting**: Direct instruction to critique and revise,
- **Multi-sample reasoning**: Generate N reasoning paths, extract divergent points as reflection triggers,
- **Verifier-triggered critique**: External verifier signals inconsistency,
- **Uncertainty-conditioned prompting**: High entropy states trigger mandatory reflection.

---

## 7. Utility Estimation

### 7.1 Per-Reflection Utility

For a specific reflection rho_t at timestep t in trajectory tau:

```
U(rho_t) = R(tau_with rho_t) - R(tau_without rho_t)
```

where R(.) is a composite reward function.

### 7.2 Composite Reward Definition

```
R = alpha * TaskAccuracy - beta * TokenCost - gamma * ReasoningInstability
```

**Component Definitions**:

| Component | Symbol | Description | Measurement |
|-----------|--------|-------------|-------------|
| TaskAccuracy | Acc | Final correctness | Exact match or semantic equivalence |
| TokenCost | Tok | Reflection overhead | Token count of reflection span |
| ReasoningInstability | Instab | Divergence across reruns | Edit distance between continuations under fixed seeds |
| Consistency | Consist | Logical agreement | Entailment between intermediate and final conclusions |
| RepairSuccess | Repair | Recovery from failures | Accuracy gain from pre- to post-reflection state |

**Marginal Utility Extension**:  
For tasks where reflection is necessary (e.g., hard MATH problems), define **relative utility** against a minimal-reflection baseline to avoid degenerate "any reflection is helpful" conclusions:

```
U_rel(rho_t) = R(tau_with rho_t) - R(tau_with rho_minimal)
```

### 7.3 Task-Conditioned Functional Contrast

Reflection as an observable intervention target:

```
C_R(D) = E[Y | masked or replaced reflection, X in D] - E[Y | original reflection, X in D]
```

**Interpretation**: Distribution-conditioned functional contrast for a specified task distribution D and replay protocol.

**Estimation Strategy**:
Under the deterministic replay protocol, the intervened outcome is measured by structure-preserving masking or replacement and regeneration. This yields an intervention-sensitive contrast, not an identified effect in a formal causal model.

---

## 8. Reflection PRM

This section is the target downstream validation design. It is not a completed repository result. The current completed evidence stops at diagnostic attribution, structural necessity, redundancy, and guarded real-task pilot preparation.

### 8.1 Objective

Train or evaluate a model to predict structurally calibrated reflection utility from local context:

```
f_theta(s_t, rho_t) -> U_hat_struct(rho_t)
```

where:
- s_t = local reasoning state (preceding context),
- rho_t = reflection segment,
- U_hat_struct(rho_t) = estimated utility after accounting for structural necessity, bottleneck status, redundancy, and compensation diagnostics.

The Phase 5-7 diagnostic result changes the supervision rule. The candidate training weight is not raw local FMA:

```text
not: w_t = Normalize(FMA(rho_t; D))
```

The target validation should instead test a structurally calibrated signal:

```text
w_t = Normalize(Calibrate(FMA, structural_necessity, bottleneck, redundancy, compensation))
```

### 8.2 Training Objectives

**Primary (MSE Regression)**:
```
L_MSE = || f_theta(s_t, rho_t) - U(rho_t) ||^2
```

**Alternative Objectives**:
- **Ranking Loss**: `L_rank = max(0, 1 - (f_theta(s, rho^+) - f_theta(s, rho^-)) * sign(U^+ - U^-))`
- **Binary Classification**: Harmful vs. non-harmful reflection detection,
- **Focal Loss**: For imbalanced harmful-reflection detection.

These objectives remain proposed validation designs until real training, filtering, and downstream comparison artifacts exist.

### 8.3 Model Configuration

| Component | Specification |
|-----------|---------------|
| Backbones | Qwen2.5-7B, Llama3-8B, DeepSeek-R1-Distill-7B |
| Training | LoRA (r=64, alpha=128) or QLoRA |
| Framework | TRL + PEFT + Accelerate |
| Compute | 1-2 x A100-40GB or equivalent |
| Duration | ~4 hours per model (3K-5K training examples) |

**Avoid initially**: Distributed PPO, online RL infrastructure, 70B+ models.

---

## 9. Failure Modes

We explicitly study **harmful reflection behavior** as a first-class research object, not merely as a nuisance.

### 9.1 Taxonomy of Harmful Reflection

| Failure Mode | Description | Functional Signature |
|--------------|-------------|----------------|
| **Reflection Amplification** | Reflection strengthens existing hallucinations | U(rho) << 0 with high confidence in incorrect answer |
| **False Confidence** | Incorrect reasoning becomes more confident after reflection | Confidence increase paired with accuracy decrease |
| **Reasoning Drift** | Reflection derails previously valid reasoning | Pre-reflection correct -> Post-reflection incorrect |
| **Overthinking** | Reflection increases computation without accuracy gain | Delta Tok >> 0, Delta Acc ~ 0 |
| **Self-Confirmation** | Reflection repeatedly validates and entrenches errors | Cyclic self-endorsement in multi-turn reflection |
| **Reflection Collapse** | Repeated reflection reduces output diversity | Low variance across multiple reflection samples |

### 9.2 Research Goal

Identify **when** and **why** reflection becomes counterproductive, enabling:
- Early detection of harmful reflection patterns,
- Conditional suppression of low-utility reflections,
- Design guidelines for reflection-triggering policies.

---

## 10. Lightweight Benchmark Philosophy

This project intentionally prioritizes:

| Priority | Rationale |
|----------|-----------|
| Low-cost experimentation | Single-GPU training, offline evaluation |
| Reproducibility | Deterministic protocols, open-source models |
| Offline intervention analysis | No online RL, no API-dependent pipelines |
| Small-model compatibility | 7B-14B parameter models |
| Lightweight iteration | 2-3 week milestones, rapid hypothesis testing |

**This is a deliberate research choice**, not a resource limitation. We trade scale for operational rigor and interpretability.

---

## 11. Benchmarks and Evaluation

### 11.1 Benchmarks

| Tier | Benchmark | Domain | Purpose |
|------|-----------|--------|---------|
| **Primary** | GSM8K | Mathematical reasoning | Core utility estimation |
| **Primary** | MATH | Advanced mathematics | Hard-task marginal utility |
| **Primary** | HotpotQA | Multi-hop reasoning | Long-horizon reflection stability |
| **Primary** | SWE-bench-lite | Code reasoning | Structured output correctness |
| **Optional** | MiniWoB | Web agent tasks | Action-space reflection |
| **Optional** | WebShop | E-commerce simulation | Long-horizon decision making |

### 11.2 Evaluation Metrics

| Metric | Symbol | Purpose | Measurement |
|--------|--------|---------|-------------|
| Accuracy Gain | Delta Acc | Task improvement | Correctness rate delta |
| Token Efficiency | U / Tok | Utility per token | U(rho) / len(rho) |
| Reflection Utility | U(rho) | Local functional contribution | Counterfactual reward difference |
| Stability | sigma_replay | Rerun consistency | Std. dev. of outcomes across fixed seeds |
| Recovery Rate | P(repair) | Failure correction | P(correct_post | incorrect_pre) |
| Harmful Reflection Rate | P(U < -epsilon) | Negative utility frequency | Proportion of harmful reflections |

---

## 12. Minimal Viable Research Plan

### Phase 1 — Reflection Dataset Construction

**Inputs**:  
Existing reasoning datasets (GSM8K, MATH, HotpotQA, SWE-bench-lite).

**Generation Protocol**:  
Prompt models to produce:
1. Initial reasoning attempt,
2. Explicit self-reflection (demarcated via structured tags),
3. Revised reasoning and final answer.

**Storage Schema**:
```json
{
  "task_id": "gsm8k-1234",
  "reasoning_trace": "full token sequence",
  "reflection_spans": [
    {"start": 120, "end": 180, "type": "verification", "content": "..."}
  ],
  "final_answer": "42",
  "correctness": true,
  "model": "qwen2.5-7b"
}
```

**Deliverable**: `data/reflection_traces/` — 5K-10K annotated trajectories.

---

### Phase 2 — Counterfactual Intervention Engine

**Core Operation**:
```python
# Deterministic Replay Protocol
original = generate(task, seed=42, reflection=True, temperature=0)
modified = generate(task, seed=42, reflection=False, temperature=0)  # excised
delta = evaluate(modified) - evaluate(original)
```

**Metrics**: Delta Acc, Delta Tok, consistency delta across seeds.

**Deliverable**: `fma/intervention/` — Excision, replacement, and injection operators.

---

### Phase 3 — Reflection Utility Estimation

**Estimand**: Delta Reward = R_with - R_without

**Label Taxonomy**:
- **Positive utility**: Delta > epsilon
- **Neutral utility**: |Delta| <= epsilon
- **Harmful utility**: Delta < -epsilon

**Deliverable**: `fma/utility/` — 5K+ labeled reflection-utility pairs with significance testing.

---

### Phase 4 — Reflection PRM

**Training Set**: 3K-5K (s_t, rho_t, U_struct(rho_t)) triples from Phase 3 plus structural calibration features from the Phase 6-7 diagnostic layer.

**Training**: LoRA on Qwen2.5-7B or DeepSeek-R1-Distill-7B.

**Deliverable**: `fma/prm/` — trained checkpoint, inference pipeline, and a documented distinction between raw local utility labels and structurally calibrated supervision weights. This deliverable is not present in the current repository.

---

### Phase 5 — Evaluation

**Research Questions**:
1. Does structurally calibrated utility-aware reflection filtering improve aggregate performance?
2. Can the PRM reduce unnecessary or redundant reflection (token efficiency)?
3. Does harmful reflection suppression prevent error amplification?

**Protocol**:
- Baseline: Unfiltered reflection generation,
- Treatment: PRM-filtered reflection (retain structurally calibrated predicted-positive reflections),
- Metrics: Accuracy, token count, F1 on utility prediction.

This phase is a future application experiment and must not be described as completed unless real downstream comparison artifacts exist.

---

## 13. Initial Milestones (3 Weeks)

### Week 1: Infrastructure & Data

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-2 | Build reflection trace generator (prompt templates for Qwen2.5-7B / DeepSeek-R1-Distill) | Generator script |
| 3 | Implement reflection span detector (regex + lightweight classifier) | Detector module |
| 4-5 | Generate 2K raw trajectories on GSM8K + MATH | Raw dataset |
| 6 | **Validation**: Manual audit of 100 samples for boundary accuracy | Audit report |
| 7 | Clean and structure dataset per schema | `reflection_traces_v1.jsonl` |

**Deliverable**: `fma/data/reflection_traces_v1.jsonl`

---

### Week 2: Intervention & Utility

| Day | Task | Deliverable |
|-----|------|-------------|
| 1-2 | Implement deterministic masking protocol (greedy decoding, fixed seed) | Intervention engine |
| 3-4 | Run counterfactual deletion on 1K trajectories | Utility scores |
| 5 | Compute utility distributions by type and domain | Statistics tables |
| 6 | Generate case studies (5 positive, 5 harmful, 5 neutral) | Qualitative analysis |
| 7 | Produce visualizations (utility distribution, type breakdown, length vs. utility) | Figures |

**Deliverable**: `fma/intervention/counterfactual_results.json` + analysis notebook.

---

### Week 3: PRM Prototype & Evaluation

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Construct training set of 3K+ (s, rho, U_struct) triples | Training data |
| 2 | Train Reflection PRM with LoRA (1 GPU, ~4 hours) | Model checkpoint |
| 3 | Evaluate PRM on held-out GSM8K subset | PRM metrics |
| 4-5 | End-to-end evaluation: baseline vs. structurally calibrated PRM-filtered | Comparison report |
| 6 | Measure accuracy gain and token efficiency | Efficiency analysis |
| 7 | Document and package | Final report |

**Deliverable**: `fma/prm/checkpoint/` + evaluation report. Current status: required future validation, not completed evidence.

---

## 14. Publication Strategy

### 14.1 Diagnostic Route

**Targets**:  
- NeurIPS / ICLR / ICML Workshop on Agent Learning or Reasoning,
- ACL / EMNLP Findings,
- AAAI Symposium on Cognitive Systems.

**Focus**:  
Empirical intervention-sensitive analysis of reflection utility, structural necessity diagnostics, and case studies of harmful or redundant reflection.

**Suggested Title**:  
*"Functional Metacognitive Attribution: Which Reflections Improve LLM Reasoning Under Perturbation?"*

### 14.2 Future Application Route

**Extensions**:  
- Structurally calibrated utility-aware adaptive reflection policies,
- Real PRM/filtering validation against vanilla PRM, length-calibrated PRM, token attribution, and heuristic reflection scoring,
- Cross-lingual / cross-domain generalization of reflection utility,
- Reflection scheduling: optimal timing and frequency.

**Targets**:  
- ACL / EMNLP Main Conference,
- ICLR / NeurIPS Main Conference (with substantial empirical and theoretical extension).

Any future application route requires downstream evidence. Phase 5-7 explain why the distinction is necessary; they do not by themselves show downstream robustness or generalization gains for a PRM/filtering system.

---

## 15. Related Work & Positioning

| Work | Focus | Our Differentiation |
|------|-------|-------------------|
| DeepSeek-R1 / o1-style reasoning | Long-chain deliberation | We attribute utility *per reflection*, not aggregate chain quality |
| Process Reward Models (PRM) | Step-level correctness | We separate reflection local utility from structural necessity before proposing supervision weights |
| Self-Correction literature | Iterative refinement | We use structure-preserving perturbation to estimate functional influence, not just correlation |
| Reflexion / Self-Refine | Global reflection optimization | We operate at the intervention level with replay contrasts |
| Cognitive architectures | Agent metacognition | We remain lightweight (7B, offline) rather than system-level |

**Positioning Statement**:  
We are not proposing "better reflection generation." We are proposing **better reflection selection and attribution** as a complementary layer that can be applied to any existing reflection-producing model. The current repository validates the diagnostic layer; the PRM/filtering application still requires a real downstream experiment.

---

## 16. Risk Assessment & Mitigation

| Risk Level | Risk | Mitigation |
|------------|------|------------|
| **Low** | Dataset construction | Automate via prompt templates; use existing benchmarks. |
| **Low** | Utility estimation pipeline | Modular Python; deterministic decoding ensures reproducibility. |
| **Medium** | Reflection span boundary detection | Rule-based segmentation (tag-based) + classifier validation; manual audit on 200-sample subset. |
| **Medium** | Excision-induced coherence collapse | Fallback to "replacement" intervention if removal breaks syntax; report coherence-break rate. |
| **Medium** | Interpretation stability | Report effect sizes across multiple fixed seeds; permutation test for significance. |
| **Medium** | Reflection PRM generalization | Train on diverse task mix; evaluate zero-shot on held-out domains. |
| **High** | Full online RL integration | **Avoid in MVP**. Stay offline and intervention-based. |
| **High** | "Any reflection helps" degeneracy | Use marginal utility U_rel against minimal baseline on hard tasks. |

---

## 17. Final Recommended Scope

**Best balance of novelty, feasibility, publication speed, and low compute cost**:

> **FMA Reflection Utility Learning + Structural Necessity Diagnostics**

with any future extension separated into:

> **Structurally Calibrated Reflection PRM / Filtering Validation**

**Avoid initially**:
- Full RL systems (PPO, GRPO at scale),
- Complex latent-variable graph theory,
- Multi-agent reflection coordination,
- Giant benchmark ecosystems (full SWE-bench, WebShop at scale).

**Closing Argument**:  
The lightweight intervention-analysis framing is already sufficient for a diagnostic paper. The journal claim becomes stronger when paired with downstream PRM/filtering evidence: FMA proposes reflection utility learning, and Phase 5-7 explain why raw local utility must be structurally calibrated before it becomes a supervision or filtering signal.

---

## 18. Real-Task Pilot Readiness Layer

This layer tests whether the framework can move beyond stored synthetic traces without weakening provenance.

### 18.1 Guarded Preflight

- Primary model: `gpt-5.5`, selected only after live Responses API preflight confirms access.
- Fallback order and JSON mode fallback are configured in `configs/real_task_pilot.yaml`.
- Required API metadata: endpoint, structured output mode, reasoning effort, seed, SDK version, API date, service tier, and usage tokens. `system_fingerprint` is logged and disclosed when available; if absent, it is reported separately from schema/tag success.
- Schema gate: first 20 traces must have JSON parse success and `<reflection>` tag extraction success at or above 95 percent.
- Drift gate: the same prompt and seed called three times must have token-level output difference below 5 percent; otherwise non-full determinism is disclosed.
- Cost gate: full pilot cannot run while `user_approved_budget_usd` is unset.

### 18.2 Real-Task Pilot Artifacts

- `outputs/real_task_pilot/api_preflight_report.json`
- `outputs/real_task_pilot/schema_compliance_report.json`
- `outputs/real_task_pilot/determinism_drift_report.json`
- `outputs/real_task_pilot/cost_and_rate_limit_report.json`
- `outputs/real_task_pilot/sample_manifest.json`
- `outputs/real_task_pilot/preflight_traces.jsonl`
- `outputs/real_task_pilot/generation_fallback_report.json`
- `outputs/real_task_pilot/replay_prefixes.jsonl`
- `outputs/real_task_pilot/real_task_delta_u.jsonl`
- `outputs/real_task_pilot/independent_baseline_scores.jsonl`
- `outputs/real_task_pilot/structurally_calibrated_fma_scores.jsonl`
- `outputs/real_task_pilot/rank_signal_report.json`
- `outputs/real_task_pilot/baseline_leakage_audit.json`
- `outputs/real_task_pilot/trajectory_controls_report.json`
- `outputs/real_task_pilot/hygiene_audit.md`
- `outputs/real_task_pilot/readiness_audit.json`

### 18.3 Readiness Rule

The `pilot_pass: true` gate requires preflight pass, at least 300 valid traces, span validity at least 90 percent, replay success at least 85 percent, clean baseline leakage audit, complete cost report, passing tests, and clean hygiene scan. Expansion toward larger evaluation requires task-level Spearman CI lower bound above zero, or pooled CI lower bound above zero plus at least one independently passing task.

Current status: `outputs/real_task_pilot/readiness_audit.json` reports `PILOT_BLOCKED`, with failure codes `PILOT_FAIL_SIGNAL` and `PREFLIGHT_FAIL_DRIFT`. `outputs/real_task_pilot/rank_signal_report.json` now includes a clean 382-row `structurally_calibrated_fma` candidate score, but its pooled and per-task bootstrap CI lower bounds are not above zero, so expansion is blocked. `outputs/real_task_pilot/api_preflight_report.json` reports `status: fail`, so generated traces remain guarded pilot evidence only. The trajectory-controls artifact is readiness-complete as a partial pilot control report, not a completed downstream control validation.

The current failure audit is frozen. No next validation route is active for the diagnostic manuscript. The v2 scorer is frozen by formula hash `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628`. `outputs/s_fma_v2_fresh_holdout/manifest_overlap_audit.json` is currently `MANIFEST_OVERLAP_CLEAN`; `outputs/s_fma_v2_fresh_holdout/api_preflight_report.json` is `PREFLIGHT_FAIL_DRIFT` after a guarded live API preflight-only run with 20 evaluated records. `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_report.json` is `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`: the bounded rerun used 20 smoke samples, produced 60/60 successful replay results, spent `3.14542` USD within the `5` USD ceiling, but had `nonzero_delta_rows: 0` and `next_allowed_step: STOP_OR_REVISE_EVIDENCE_TARGET`. `outputs/s_fma_v2_1_fresh_holdout/manifest_overlap_audit.json` is `MANIFEST_OVERLAP_CLEAN`, `outputs/s_fma_v2_1_fresh_holdout/v2_1_contract_audit.json` is `V2_1_CONTRACT_CLEAN`, and the approved `outputs/s_fma_v2_1_fresh_holdout/api_preflight_report.json` rerun is `PREFLIGHT_FAIL_DRIFT` after 20 records and 23 API attempts, with cost `0.86245`, 20 valid trace rows, JSON/schema/tag/final-answer success `1.0`, and 23/23 non-empty `raw_output` attempts. `outputs/s_fma_v2_1_fresh_holdout/api_preflight_drift_failure_audit.json` records that deterministic replay is blocked by drift. `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_report.json` is `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST`: the latest bounded smoke rerun used 140 API attempts, spent `6.11314` USD within the `8` USD ceiling, reached JSON/schema/tag/final-answer success `1.0`, replay success rate `1.0`, 40 Delta-U rows, and nonzero Delta-U counts of 20 pooled, 7 GSM8K, and 13 HotpotQA. `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_report.json` reports `V2_1_PILOT_STOCHASTIC_PASS` after the single retry, with 700 effective API requests, USD `28.06931`, 100 valid original traces, 600/600 replay success, JSON/schema/tag/final-answer success `1.0`, nonzero Delta-U counts of 96 pooled, 42 GSM8K, and 54 HotpotQA, positive pilot Spearman CIs, and `full_validation_approval_request_allowed: true`. The later full stochastic validation report is `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`, with 396 valid original traces, 2372/2376 successful replay results, positive pooled/GSM8K/HotpotQA rank signal, and `nonzero_delta_u` counts of 158 pooled, 16 GSM8K, and 142 HotpotQA. It fails because exact quality rates are below `1.0` and GSM8K sparse signal is below threshold. The strict engineering retry used 119 incremental retry API calls, still reports `GLOBAL_pass: false`, and hard-stops with `transport_unresolved_and_gsm8k_sparse_signal_below_preregistered_threshold`. `paper/full_validation_route_decision.md` now records strict v2.1 full validation as abandoned and permits only conservative diagnostic/workshop wording. No deterministic replay claim, full validation pass claim, PRM/filtering claim, or status upgrade is allowed; current status remains `PILOT_BLOCKED`.

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Reflection span** | A contiguous token sequence explicitly performing self-critique, verification, or reconsideration. |
| **Deterministic replay** | Regeneration under identical conditions (fixed seed, greedy decoding) after structural modification. |
| **Harmful reflection** | A reflection whose masking or replacement improves downstream reward (U(rho) < -epsilon). |
| **Reflection PRM** | A process reward model trained to predict the functional utility of a reflection given local context. |
| **Functional contrast** | Expected outcome difference between original and intervened observable traces under a fixed task distribution. |
| **Marginal utility** | Utility relative to a minimal-reflection baseline, used on tasks where reflection is necessary. |
| **Coherence collapse** | Failure of the model to produce syntactically or semantically valid output after reflection masking or replacement. |
| **Structurally calibrated supervision weight** | A proposed downstream weight that combines local utility with structural necessity, bottleneck, redundancy, and compensation diagnostics rather than using raw FMA alone. |
| **PRM/filtering validation** | Required future experiment testing downstream process-supervision or reflection-filtering benefit against explicit baselines. |
