# Methodology

The SC-FMA methodology converts interventional utility estimates into calibrated, structurally-consistent supervision weights for process supervision. It builds on two established diagnostic procedures — Conditional Interventional Utility (CIU) estimation and structural necessity measurement — and adds a novel constrained optimization layer that resolves the tension between local utility signals and global topological constraints.

## Preliminaries: CIU and Structural Necessity

Given a reasoning trace with `k` reflective steps, CIU estimation produces a vector `c ∈ ℝᵏ` where `cᵢ = U(Y_original) − U(Y_intervened_i)`. This measures the drop in task utility when step `i` is masked or perturbed. Higher CIU indicates greater local functional contribution. CIU is normalized to `[0,1]` across steps within each trace.

Structural necessity `n ∈ ℝᵏ` is measured via graph-based ablation over a reflection DAG constructed from the trace. Nodes represent reflective steps; edges encode temporal adjacency and keyword-based topical links (e.g., "corrects," "verifies"). Necessity for node `i` is the utility degradation when that node is removed under PRUNE, CASCADE, or BYPASS graph intervention modes. Redundancy `R ∈ ℝᵏˣᵏ` is a pairwise similarity matrix where `R_{ij}` measures how substitutable step `i` is for step `j`, computed as the average of cosine similarity between node profiles and Jaccard overlap of downstream influence sets. Bottleneck indicators `b ∈ {0,1}ᵏ` mark nodes that combine high normalized CIU, high normalized necessity, and low redundancy degree.

## The SCU Objective

The Structurally-Calibrated Utility (SCU) objective produces supervision weights `w ∈ ℝᵏ` by minimizing:

```
L(w; c, n, R, b) = α·||w − c̃||²₂  (fidelity)
                 + β·||w − ñ||²₂   (structure)
                 + γ·wᵀRw         (redundancy penalty)
                 − δ·Σᵢ bᵢ·log(wᵢ)  (bottleneck protection)

subject to:  w ≥ 0,  Σᵢ wᵢ = 1
```

where `c̃` and `ñ` are `l₂`-normalized CIU and necessity vectors. The first term keeps weights close to the local utility ranking; the second term aligns them with graph-level necessity; the third term penalizes assigning different weights to structurally redundant pairs; the fourth term is a log-barrier preventing bottleneck nodes from receiving near-zero weight.

The objective is strictly convex in `w` because (i) the quadratic fidelity and structure terms are convex and strictly convex when combined with the linear equality constraint, (ii) `R` is positive semidefinite by construction (it is made PSD by eigenvalue floor correction if needed), and (iii) `−log(wᵢ)` is strictly convex on `w > 0`. For any `α, β, γ > 0` and `δ ≥ 0`, the combined objective has a unique global minimum.

## Calibration Variants

We implement three calibration variants spanning the complexity-performance spectrum:

**SC-FMA Ridge** produces weights via a temperature-softmax over a linear combination:
```
w = softmax(α_c · c̃ + α_n · ñ, τ)
```
The weights `α_c` and `α_n` are tuned on a held-out split to maximize Spearman rank correlation with oracle step labels. This variant has O(k) complexity and is trivially parallelizable across traces.

**SC-FMA QP** solves the full SCU objective as a constrained quadratic program using sequential least squares (SLSQP). Bottleneck constraints are enforced as lower bounds `wᵢ ≥ ε` for identified bottleneck indices. The QP variant has O(k³) complexity per trace but produces weights that optimally balance all four structural signals.

**SC-FMA Projection** applies a direct topology-constrained projection:
```
w ∝ (φ·c̃ + ψ·ñ) ⊙ (1 − ρ·r) ⊙ (1 + λ·b)
```
where `r` is the mean redundancy vector, `b` is the bottleneck mask, and elementwise operations provide a fast approximation to the full QP solution.

## Theoretical Properties

The SCU objective provides four formal guarantees:

**G1. Convexity and Uniqueness.** The objective `L(w)` is strictly convex for any `α, β, γ ≥ 0` (with at least one positive). The equality constraint `Σw = 1` is linear. The feasible set is compact. Therefore, a unique global minimizer `w*` exists.

**G2. Monotonicity Preservation.** For any two non-redundant steps `i, j` (i.e., `R_{ik} = R_{jk}` for all `k`), if `cᵢ ≥ cⱼ` and `nᵢ ≥ nⱼ`, then `w*ᵢ ≥ w*ⱼ`. The calibrated weights preserve the joint ordering of CIU and structural necessity for steps that do not share redundancy relationships.

**G4. Variance Reduction.** Let `w_c = softmax(c)` be the raw CIU weight vector. For any `α > 0` and `β > 0`, the structural calibration reduces variance: `Var(w*) ≤ Var(w_c)`. This follows from the ridge regularization effect: the structural terms shrink weights toward the necessity baseline, reducing sensitivity to CIU noise.

**G6. Bottleneck Protection.** For any bottleneck node `i` (where `bᵢ = 1`), the SC-FMA weight satisfies `w*ᵢ ≥ δ / (2α + λ_max(R) + δ/ε)` where `ε` is the floor constraint. This guarantees that structurally critical nodes are never assigned zero weight, regardless of their CIU signal strength.

## Step Importance Ranking

We evaluate SC-FMA on step importance ranking, where predicted supervision weights are compared against oracle step-level correctness labels. For each trace with `k` steps, we compute:

- **Spearman ρ**: rank correlation between predicted weights and oracle labels
- **Kendall τ**: ordinal association strength
- **NDCG@k**: normalized discounted cumulative gain at k = 3, 5, 10
- **Top-k overlap**: fraction of the true top-k steps recovered in the predicted top-k

We report aggregate metrics across all samples, bootstrap confidence intervals (95%, 10k resamples), and statistical significance via Friedman omnibus test and Wilcoxon signed-rank pairwise comparisons.

## Baseline Families

Six families of baseline methods are compared:

| Family | Methods | Description |
|---|---|---|
| FMA | SC-FMA QP, SC-FMA Ridge, SC-FMA Projection, Raw CIU | Core SC-FMA variants and uncalibrated baseline |
| Gradient Attribution | Gradient×Input, Attention Rollout | Token-gradient aggregated to step level |
| Shapley | Monte Carlo Shapley | Coalition-based step contribution |
| Information-Theoretic | Token Surprisal, Step Entropy | Probability-based importance |
| Heuristic | Random, Span Length, Relative Position | Simple structural proxies |
| Oracle | Step Correctness Labels | Ground-truth ceiling |

## Implementation

The SC-FMA calibration module is implemented in `src/fma/calibration/`. The step importance ranking framework is in `src/fma/ranking/`. Both are available as open-source Python packages. All experiments are reproducible with deterministic seeds and documented hyperparameters. The full pipeline script is `scripts/run_downstream_ranking.py`.
