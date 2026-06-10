# Results

## Calibration Quality

SC-FMA variants consistently improve rank correlation with oracle step labels over raw CIU weighting across synthetic and annotated benchmarks. Table 1 reports mean Spearman ρ aggregated across samples.

| Method | Spearman ρ | Kendall τ | NDCG@3 | NDCG@5 |
|---|---|---|---|---|
| SC-FMA QP | **0.654** | 0.482 | 0.711 | 0.743 |
| SC-FMA Ridge | 0.630 | 0.460 | 0.692 | 0.725 |
| SC-FMA Projection | 0.612 | 0.441 | 0.675 | 0.710 |
| Raw CIU | 0.582 | 0.418 | 0.651 | 0.688 |
| Gradient×Input | 0.491 | 0.352 | 0.583 | 0.615 |
| Attention Rollout | 0.468 | 0.331 | 0.557 | 0.592 |
| MC Shapley | 0.524 | 0.378 | 0.612 | 0.642 |
| Token Surprisal | 0.310 | 0.215 | 0.425 | 0.461 |
| Span Length | 0.187 | 0.128 | 0.312 | 0.348 |
| Relative Position | 0.223 | 0.154 | 0.358 | 0.391 |
| Random | 0.002 | 0.001 | 0.331 | 0.333 |
| Oracle | 1.000 | 1.000 | 1.000 | 1.000 |

**SC-FMA QP achieves the best rank correlation among all non-oracle methods**, with a mean Spearman ρ of 0.654, representing a +0.072 improvement over raw CIU (p < 0.01, Wilcoxon signed-rank). The gain is concentrated in traces with non-zero redundancy, where the redundancy penalty term provides the largest differentiation. The Friedman omnibus test rejects the null of equal method performance (χ² = 142.3, p < 0.001).

## Ablation Study

To quantify the contribution of each SCU term, we ablate individual components and measure the change in Spearman ρ:

| Variant | α | β | γ | δ | Spearman ρ | Δ vs full |
|---|---|---|---|---|---|---|
| SC-FMA QP (full) | 1.0 | 0.5 | 0.2 | 0.1 | 0.654 | — |
| − Redundancy (γ=0) | 1.0 | 0.5 | 0.0 | 0.1 | 0.632 | −0.022 |
| − Bottleneck (δ=0) | 1.0 | 0.5 | 0.2 | 0.0 | 0.641 | −0.013 |
| − Structure (β=0) | 1.0 | 0.0 | 0.2 | 0.1 | 0.597 | −0.057 |
| − Fidelity (α=0.1) | 0.1 | 0.5 | 0.2 | 0.1 | 0.582 | −0.072 |

Each structural component contributes meaningfully. The **structure term** (β) has the largest individual impact, consistent with the diagnostic finding that CIU alone is weakly aligned with graph-level necessity. The **redundancy penalty** (γ) provides a smaller but consistent gain, primarily in traces where multiple reflective steps serve overlapping roles. The **bottleneck protection** (δ) prevents degradation in traces with sparse critical nodes; its removal reduces variance across samples.

## Comparison Against Baselines

SC-FMA significantly outperforms all heuristic and information-theoretic baselines. Wilcoxon pairwise tests confirm:

- **SC-FMA QP > Gradient×Input**: p = 0.003
- **SC-FMA QP > MC Shapley**: p = 0.018
- **SC-FMA QP > Token Surprisal**: p < 0.001
- **SC-FMA QP > Span Length**: p < 0.001
- **SC-FMA QP > Random**: p < 0.001

The gradient and Shapley baselines perform better than simple heuristics but remain below SC-FMA. This is expected: gradient methods capture local token importance but miss structural dependencies, while Shapley estimation approximates the value function from the same CIU signal without structural calibration.

## Theoretical Verification

All four theoretical guarantees are verified by the implemented tests:

- **G1 (Convexity)**: The SCU Hessian is numerically verified as positive semidefinite at 50 random initialization points. SLSQP converges to the same solution from different starts (max solution deviation < 1e-6).
- **G2 (Monotonicity)**: Across 200 synthetic trace pairs with controlled CIU and necessity profiles, the calibrated weight ordering preserves the joint CIU-necessity ordering for 100% of non-redundant pairs.
- **G4 (Variance Reduction)**: Over 50 trials with Gaussian-noise-perturbed CIU estimates, SC-FMA variance is 0.0034 vs raw CIU variance 0.0071, a 52% reduction.
- **G6 (Bottleneck Protection)**: All bottleneck nodes in the test set receive weight ≥ 0.01 (the configured floor). No structurally critical node is zeroed out.

## Discussion

The results establish SC-FMA as a viable methodology for producing structural-aware supervision weights from interventional utility signals. The key empirical findings are:

1. **Structural calibration matters**: Every configuration of SC-FMA that includes structural terms outperforms raw CIU, confirming the diagnostic motivation.
2. **The convex QP formulation is practical**: Despite O(k³) worst-case complexity, SLSQP converges reliably for typical reasoning traces (k = 3–8 steps) in under 10ms per trace.
3. **Bottleneck protection is reliable**: The log-barrier constraint achieves its design goal of preventing structural collapses from zero-weighted critical nodes.
4. **The gain is robust**: SC-FMA outperforms baselines across multiple metrics (Spearman, Kendall, NDCG) and statistical tests (Friedman, pairwise Wilcoxon).

The ranking improvements are moderate in absolute magnitude (+0.072 over raw CIU), which is consistent with the diagnostic finding that structural signals are sparse. SC-FMA cannot create structural necessity where none exists; it can only calibrate CIU to respect the structural signals that are available. The improvement is therefore bounded by the information content of the structural diagnostics, but reliably positive.
