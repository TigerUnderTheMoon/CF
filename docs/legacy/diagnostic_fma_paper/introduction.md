# Introduction

Reflective reasoning — where a model checks, diagnoses, revises, or critiques its own intermediate steps — is treated as a natural path to stronger language-model problem solving. The intuition is straightforward: if a reflective step improves final-answer quality, that step should receive more supervision weight. This view motivates process reward models and reflection filtering, but it ignores a structural question: should every locally useful reflection receive high supervision weight, even if the reasoning graph can route around it?

The structural question is especially consequential for knowledge-based systems. In knowledge-intensive tasks—medical diagnostic reasoning, scientific knowledge discovery, expert system verification—reflective steps act as metacognitive monitoring nodes within knowledge inference chains [XX]. Current process supervision suffers a dual inefficiency: redundant local reflections waste computation without tightening the inference, while omitted critical verification steps silently invalidate the reasoning chain. This tension mirrors recognized concerns in knowledge graph reasoning quality control [XX], expert system explanation fidelity [XX], and metacognitive architectures for cognitive agents [XX]. FMA's structural bottleneck identification addresses this directly: by distinguishing topology-sensitive nodes from merely locally useful ones, the framework supports a shift from undifferentiated utility scoring toward targeted allocation of verification resources in knowledge-intensive reasoning.

The answer from prior work is increasingly clear: local utility alone is a poor proxy for structural necessity. Diagnostic studies show that up to 50% of reflective steps with positive local utility have zero measured structural necessity, and alignment between local utility and graph-level necessity is weak (Pearson < 0.10). Compensatory redistribution is limited, and influence is concentrated rather than distributed. Together, these findings imply that naive utility-based supervision would overweight fluent but redundant reflection and underweight rare structurally critical operations.

This paper proposes a methodological solution to that diagnosis. We present **Structurally-Calibrated Functional Attribution (SC-FMA)**, a methodology that transforms raw interventional utility estimates into calibrated, topologically-consistent supervision weights. Rather than treating structural diagnostics as an independent analysis layer, SC-FMA embeds them directly into the weight computation through a convex constrained optimization.

The core of SC-FMA is the **Structurally-Calibrated Utility (SCU) objective**:

```
L(w) = α·||w − c||² + β·||w − n||² + γ·wᵀRw − δ·Σᵢ bᵢ·log(wᵢ)
```

where `c` is normalized CIU, `n` is structural necessity, `R` encodes pair-level redundancy, and `bᵢ` identifies bottleneck nodes. The terms enforce: (1) fidelity to the local utility ranking, (2) consistency with graph-level necessity, (3) a penalty for assigning dissimilar weights to redundant pairs, and (4) a log-barrier that prevents bottleneck nodes from receiving near-zero weight. The objective is strictly convex, guaranteeing a unique global minimizer, and the bottleneck term ensures no structurally critical node is inadvertently zeroed out.

We implement three calibration variants covering a simplicity-power spectrum: **SC-FMA Ridge** (a closed-form linear combination of CIU and necessity, tuned via held-out validation), **SC-FMA QP** (the full quadratic program with redundancy penalty and bottleneck constraints, solved via SLSQP), and **SC-FMA Projection** (a direct topology-constrained projection). All three produce normalized supervision weight vectors that preserve the sum-to-one constraint.

We evaluate SC-FMA on step importance ranking, a downstream task that measures how well predicted weights correlate with oracle step-level correctness labels from annotated reasoning datasets. We compare against six baseline families: (A) Gradient Attribution (Gradient×Input, attention rollout), (C) Monte Carlo Shapley value, (D) Information-Theoretic (surprisal, entropy), (E) Heuristic (random, span length, position), and (F) Oracle (ground-truth step correctness). SC-FMA variants consistently achieve higher Spearman rank correlation with oracle labels than raw CIU or information-theoretic baselines, and the full QP variant with bottleneck protection ranks best.

We provide theoretical guarantees for the SCU objective: **(G1) convexity** ensures a unique global minimizer when any regularization weight is positive, **(G2) monotonicity** guarantees that for non-redundant step pairs, the calibrated weight ordering preserves the joint CIU and necessity ordering, **(G4) variance reduction** proves that SC-FMA weights have strictly lower variance than raw CIU weights for any positive structural regularization, and **(G6) bottleneck protection** guarantees that identified bottleneck nodes receive weight above a configurable floor.

Our contributions are:
1. **SC-FMA**, a structural calibration methodology that transforms raw interventional utility into structurally-consistent supervision weights via convex optimization.
2. The **SCU objective**, with its theoretical guarantees of convexity, monotonicity, variance reduction, and bottleneck protection.
3. A **step importance ranking** evaluation framework comparing SC-FMA against six baseline families across multiple metrics.
4. Empirical evidence that structural calibration improves rank correlation with oracle step labels over raw utility and standard baselines.
5. An **implemented algorithm** with configurable variants (Ridge, QP, Projection) and open-source code.

The remainder of the paper is organized as follows. Section 2 reviews related work in process supervision, attribution, and structural diagnostics. Section 3 presents the SC-FMA methodology and SCU objective. Section 4 describes the experimental setup for step importance ranking. Section 5 reports results including ablation analysis. Section 6 provides theoretical guarantees. Section 7 discusses limitations, and Section 8 concludes.
