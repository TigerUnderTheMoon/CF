# PLANS.md — Functional Metacognitive Attribution (FMA)

> **Version**: 2.0  
> **Status**: Research Proposal / Living Document  
> **Last Updated**: 2026-05-28

---

## 1. Research Objective

Develop a lightweight, intervention-based framework for the **causal attribution of reflective cognition** in LLM agents.

**Core Question**:  
> Which reflective operations causally improve downstream task performance, and which are redundant or harmful?

This project integrates:

- Counterfactual attribution,
- Reflection utility estimation,
- Process-level reward modeling,
- Lightweight causal intervention analysis,

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
> Reflection is a heterogeneous intervention variable; its utility is context-dependent and must be attributed causally, not correlationally.

**Key Hypothesis**:  
Reflective operations exhibit **heterogeneous causal utility**. Specific reflection types may:

| Positive Effects | Negative Effects |
|-----------------|------------------|
| Improve reasoning trajectories | Waste context budget without performance gain |
| Repair failure states | Amplify existing errors via self-confirmation |
| Reduce hallucinations | Increase reasoning instability |
| Stabilize long-horizon reasoning | Create unnecessary computational overhead |

**Implication**:  
Reflection should be treated as a **causal intervention** $do(R=r)$ rather than a monolithic capability. The relevant question is not *whether* to reflect, but *which* reflections to retain, modify, or suppress.

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

but **not** the causal utility of *individual* reflection steps.

### 3.2 Our Core Distinction

```text
Existing Work:          "Does reflection help overall?"
This Project:         "Which reflection step causally helps, harms, or does nothing?"
```

### 3.3 Primary Novelty

1. **Counterfactual reflection attribution**: Isolating the causal effect of single reflection operations via deterministic replay,
2. **Intervention-level utility estimation**: Per-step utility scores rather than aggregate metrics,
3. **Reflection-specific reward modeling**: PRMs trained to predict reflection utility, not just step correctness,
4. **Causal replay analysis for metacognition**: A lightweight simulator for reflective cognition.

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

- Which reflection type has the highest average causal utility?
- Which types are most token-efficient (utility per token)?
- Which types become harmful under high uncertainty or low model capability?
- Which tasks benefit from which reflection categories?

---

## 5. Core Research Directions

### Direction A — Reflection Utility Attribution (Primary)

**Goal**: Estimate the causal contribution of individual reflective steps to downstream task success.

**Causal Setup**:  
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
- **Counterfactual deletion**: Excise the reflection span and re-generate the continuation under **deterministic decoding** (greedy or fixed seed) to isolate the reflection effect from sampling variance.
- **Reflection masking**: Ablation of specific reflection sub-spans.
- **Trajectory replay with fixed randomness**: Ensure outcome differences are attributable to the reflection intervention, not stochasticity.
- **Intervention-based evaluation**: Compare outcome distributions across intervention conditions.

**Outputs**:
- Per-reflection utility scores (positive / neutral / harmful),
- Utility distribution by reflection type and task domain,
- Harmful reflection detection and qualitative typology.

---

### Direction B — Reflection PRM (Process Reward Modeling)

**Goal**: Train a lightweight reward model that scores reflection quality *in situ*, enabling online filtering or generation guidance.

**Standard PRM Limitation**:  
Scores only final answer correctness or terminal state value.

**Our Extension**:  
Scores the **functional utility of intermediate reflective cognition**.

**Input**:  
`(reasoning trace, reflection segment rho_t, local state s_t)`

**Output**:  
`u_hat_t = f_theta(s_t, rho_t)` — predicted reflection utility.

**Formulations**:
- Scalar regression against counterfactual utility labels,
- Pairwise ranking of reflections by estimated utility,
- Binary utility classification (helpful vs. neutral vs. harmful).

**Novel Supervision Signal**:  
Counterfactual utility labels derived from Direction A's intervention engine, yielding **intervention-derived process rewards** rather than heuristic or human preference labels.

---

### Direction C — Counterfactual Reflection Replay

**Goal**: Construct a lightweight causal simulator for reflective cognition by replaying trajectories under modified reflection conditions.

**Intervention Types**:

| Intervention | Description | Purpose |
|--------------|-------------|---------|
| **Removal** | Excise reflection and regenerate continuation | Baseline utility estimation |
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
This becomes a **causal testbed** for reflective cognition, enabling offline evaluation of reflection policies without online RL risks.

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

**Counterfactual (Deletion)**:
```
CoT -> [EXCISE REFLECTION] -> Continue Generation -> Final Answer
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

### 7.3 Average Treatment Effect (ATE)

Reflection as a binary intervention variable:

```
ATE_R = E[Y | do(R=1), X] - E[Y | do(R=0), X]
```

**Interpretation**: Average causal effect of reflection, conditional on task context X.

**Identification Strategy**:  
Under the deterministic replay protocol, the counterfactual Y_{do(R=0)} is observed directly by excision and regeneration, yielding a **direct causal contrast** without requiring ignorability assumptions—provided the reflection span is well-defined and excision preserves syntactic coherence.

---

## 8. Reflection PRM

### 8.1 Objective

Train a model to predict reflection utility from local context:

```
f_theta(s_t, rho_t) -> U_hat(rho_t)
```

where:
- s_t = local reasoning state (preceding context),
- rho_t = reflection segment,
- U_hat(rho_t) = estimated utility.

### 8.2 Training Objectives

**Primary (MSE Regression)**:
```
L_MSE = || f_theta(s_t, rho_t) - U(rho_t) ||^2
```

**Alternative Objectives**:
- **Ranking Loss**: `L_rank = max(0, 1 - (f_theta(s, rho^+) - f_theta(s, rho^-)) * sign(U^+ - U^-))`
- **Binary Classification**: Harmful vs. non-harmful reflection detection,
- **Focal Loss**: For imbalanced harmful-reflection detection.

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

| Failure Mode | Description | Causal Signature |
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

**This is a deliberate research choice**, not a resource limitation. We trade scale for causal rigor and interpretability.

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
| Reflection Utility | U(rho) | Causal contribution | Counterfactual reward difference |
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

**Training Set**: 3K-5K (s_t, rho_t, U(rho_t)) triples from Phase 3.

**Training**: LoRA on Qwen2.5-7B or DeepSeek-R1-Distill-7B.

**Deliverable**: `fma/prm/` — Trained checkpoint + inference pipeline.

---

### Phase 5 — Evaluation

**Research Questions**:
1. Does utility-aware reflection filtering improve aggregate performance?
2. Can the PRM reduce unnecessary reflection (token efficiency)?
3. Does harmful reflection suppression prevent error amplification?

**Protocol**:
- Baseline: Unfiltered reflection generation,
- Treatment: PRM-filtered reflection (retain predicted-positive reflections),
- Metrics: Accuracy, token count, F1 on utility prediction.

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
| 1-2 | Implement deterministic excision protocol (greedy decoding, fixed seed) | Intervention engine |
| 3-4 | Run counterfactual deletion on 1K trajectories | Utility scores |
| 5 | Compute utility distributions by type and domain | Statistics tables |
| 6 | Generate case studies (5 positive, 5 harmful, 5 neutral) | Qualitative analysis |
| 7 | Produce visualizations (utility distribution, type breakdown, length vs. utility) | Figures |

**Deliverable**: `fma/intervention/counterfactual_results.json` + analysis notebook.

---

### Week 3: PRM Prototype & Evaluation

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Construct training set of 3K+ (s, rho, U) triples | Training data |
| 2 | Train Reflection PRM with LoRA (1 GPU, ~4 hours) | Model checkpoint |
| 3 | Evaluate PRM on held-out GSM8K subset | PRM metrics |
| 4-5 | End-to-end evaluation: baseline vs. PRM-filtered | Comparison report |
| 6 | Measure accuracy gain and token efficiency | Efficiency analysis |
| 7 | Document and package | Final report |

**Deliverable**: `fma/prm/checkpoint/` + evaluation report.

---

## 14. Publication Strategy

### 14.1 Fast-Track Route (Recommended for MVP)

**Targets**:  
- NeurIPS / ICLR / ICML Workshop on Agent Learning or Reasoning,
- ACL / EMNLP Findings,
- AAAI Symposium on Cognitive Systems.

**Focus**:  
Empirical causal analysis of reflection utility; lightweight intervention framework; case studies of harmful reflection.

**Suggested Title**:  
*"Functional Metacognitive Attribution: Which Reflections Causally Improve LLM Reasoning?"*

### 14.2 Strong Follow-Up (Post-MVP)

**Extensions**:  
- Utility-aware adaptive reflection policies (reflect only when predicted utility > threshold),
- Online RL with reflection PRM as reward shaping,
- Cross-lingual / cross-domain generalization of reflection utility,
- Reflection scheduling: optimal timing and frequency.

**Targets**:  
- ACL / EMNLP Main Conference,
- ICLR / NeurIPS Main Conference (with substantial empirical and theoretical extension).

---

## 15. Related Work & Positioning

| Work | Focus | Our Differentiation |
|------|-------|-------------------|
| DeepSeek-R1 / o1-style reasoning | Long-chain deliberation | We attribute utility *per reflection*, not aggregate chain quality |
| Process Reward Models (PRM) | Step-level correctness | We score *reflection functional utility*, not just step correctness |
| Self-Correction literature | Iterative refinement | We use counterfactual deletion to establish causality, not just correlation |
| Reflexion / Self-Refine | Global reflection optimization | We operate at the intervention level with causal contrast |
| Cognitive architectures | Agent metacognition | We remain lightweight (7B, offline) rather than system-level |

**Positioning Statement**:  
We are not proposing "better reflection generation." We are proposing **better reflection selection and attribution**—a complementary layer that can be applied to any existing reflection-producing model.

---

## 16. Risk Assessment & Mitigation

| Risk Level | Risk | Mitigation |
|------------|------|------------|
| **Low** | Dataset construction | Automate via prompt templates; use existing benchmarks. |
| **Low** | Utility estimation pipeline | Modular Python; deterministic decoding ensures reproducibility. |
| **Medium** | Reflection span boundary detection | Rule-based segmentation (tag-based) + classifier validation; manual audit on 200-sample subset. |
| **Medium** | Excision-induced coherence collapse | Fallback to "replacement" intervention if removal breaks syntax; report coherence-break rate. |
| **Medium** | Causal interpretation stability | Report effect sizes across multiple fixed seeds; permutation test for significance. |
| **Medium** | Reflection PRM generalization | Train on diverse task mix; evaluate zero-shot on held-out domains. |
| **High** | Full online RL integration | **Avoid in MVP**. Stay offline and intervention-based. |
| **High** | "Any reflection helps" degeneracy | Use marginal utility U_rel against minimal baseline on hard tasks. |

---

## 17. Final Recommended Scope

**Best balance of novelty, feasibility, publication speed, and low compute cost**:

> **Reflection Utility Attribution + Counterfactual Intervention Analysis**

with optional extension into:

> **Reflection PRM for Online Filtering**

**Avoid initially**:
- Full RL systems (PPO, GRPO at scale),
- Complex causal graph theory (latent variable models),
- Multi-agent reflection coordination,
- Giant benchmark ecosystems (full SWE-bench, WebShop at scale).

**Closing Argument**:  
The lightweight intervention-analysis framing is already sufficiently novel for a strong first paper. The core insight—that reflection utility is heterogeneous and attributable via causal intervention—challenges the implicit "more is better" assumption in current reasoning models and opens a principled path toward token-efficient, error-aware metacognition.

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Reflection span** | A contiguous token sequence explicitly performing self-critique, verification, or reconsideration. |
| **Deterministic replay** | Regeneration under identical conditions (fixed seed, greedy decoding) after structural modification. |
| **Harmful reflection** | A reflection whose excision improves downstream reward (U(rho) < -epsilon). |
| **Reflection PRM** | A process reward model trained to predict the functional utility of a reflection given local context. |
| **ATE** | Average Treatment Effect; expected outcome difference between intervention and control. |
| **Marginal utility** | Utility relative to a minimal-reflection baseline, used on tasks where reflection is necessary. |
| **Coherence collapse** | Failure of the model to produce syntactically or semantically valid output after reflection excision. |
