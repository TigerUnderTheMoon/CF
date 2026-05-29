# Structural Diagnostics

This report compares Phase 5 `attribution_score` with Phase 6 topology-sensitive necessity. It is an interpretation diagnostic, not a new attribution algorithm.

The expected reading is weak structural alignment: local reflective attribution and structural reflective necessity are related but distinct signals.

## Overall Correlation

| Mode | Pearson | Spearman | Kendall Tau | Top-10 overlap | Zero necessity | Attribution > 0 and necessity = 0 |
|---|---:|---:|---:|---:|---:|---:|
| PRUNE | 0.0753 | 0.0596 | 0.0527 | 0.2000 | 67.79% | 49.54% |
| CASCADE | 0.0523 | 0.0512 | 0.0455 | 0.2000 | 67.79% | 49.54% |
| BYPASS | 0.0917 | 0.0623 | 0.0545 | 0.2000 | 67.79% | 49.54% |

## Scatter Summaries

| Mode | Samples | Mean attribution | Mean necessity | Median necessity | Positive necessity |
|---|---:|---:|---:|---:|---:|
| PRUNE | 2400 | 0.5361 | 0.2746 | 0.0000 | 32.21% |
| CASCADE | 2400 | 0.5361 | 0.2939 | 0.0000 | 32.21% |
| BYPASS | 2400 | 0.5361 | 0.2571 | 0.0000 | 32.21% |

## Stratified Diagnostics

Per-group correlations help identify local-to-structural mismatch rather than masking it with one global linear statistic.

### PRUNE

#### taxonomy

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| BACKTRACKING | 284 | 0.1408 | 0.1032 |
| CONSTRAINT_TRACKING | 313 | 0.1376 | 0.1261 |
| DECOMPOSITION | 282 | 0.1102 | 0.1201 |
| ERROR_CORRECTION | 288 | -0.0000 | 0.0000 |
| PLANNING | 313 | 0.0486 | 0.0463 |
| RETRIEVAL | 300 | 0.0000 | 0.0000 |
| UNCERTAINTY_MONITORING | 298 | -0.0177 | -0.0231 |
| VERIFICATION | 322 | 0.0778 | 0.0839 |

#### step_idx

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| 0 | 800 | -0.0457 | -0.0125 |
| 1 | 800 | 0.1202 | 0.0672 |
| 2 | 800 | 0.2136 | 0.1540 |

#### source_role

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| non_source_node | 1600 | 0.1608 | 0.1033 |
| source_node | 800 | -0.0457 | -0.0125 |


### CASCADE

#### taxonomy

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| BACKTRACKING | 284 | 0.0729 | 0.0758 |
| CONSTRAINT_TRACKING | 313 | 0.0992 | 0.1080 |
| DECOMPOSITION | 282 | 0.0904 | 0.1134 |
| ERROR_CORRECTION | 288 | 0.0000 | 0.0000 |
| PLANNING | 313 | 0.0426 | 0.0457 |
| RETRIEVAL | 300 | 0.0000 | 0.0000 |
| UNCERTAINTY_MONITORING | 298 | -0.0363 | -0.0337 |
| VERIFICATION | 322 | 0.0869 | 0.0862 |

#### step_idx

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| 0 | 800 | -0.0457 | -0.0125 |
| 1 | 800 | 0.0434 | 0.0418 |
| 2 | 800 | 0.2136 | 0.1540 |

#### source_role

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| non_source_node | 1600 | 0.1127 | 0.0884 |
| source_node | 800 | -0.0457 | -0.0125 |


### BYPASS

#### taxonomy

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| BACKTRACKING | 284 | 0.1984 | 0.1265 |
| CONSTRAINT_TRACKING | 313 | 0.1649 | 0.1376 |
| DECOMPOSITION | 282 | 0.1094 | 0.1168 |
| ERROR_CORRECTION | 288 | 0.0000 | 0.0000 |
| PLANNING | 313 | 0.0981 | 0.0673 |
| RETRIEVAL | 300 | 0.0000 | 0.0000 |
| UNCERTAINTY_MONITORING | 298 | -0.0171 | -0.0247 |
| VERIFICATION | 322 | 0.0630 | 0.0821 |

#### step_idx

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| 0 | 800 | -0.0457 | -0.0125 |
| 1 | 800 | 0.1924 | 0.0823 |
| 2 | 800 | 0.2136 | 0.1540 |

#### source_role

| Group | Samples | Pearson | Spearman |
|---|---:|---:|---:|
| non_source_node | 1600 | 0.2027 | 0.1114 |
| source_node | 800 | -0.0457 | -0.0125 |


## Interpretation

- Low Pearson values indicate weak structural alignment; they do not confirm Phase 5 scores or prove attribution correctness.
- Structural necessity is topology-sensitive: bridge nodes, source reachability, and downstream dependencies can dominate local scalar scores.
- Zero-inflated necessity distributions make linear correlation conservative because many positive local scores have no structural removal effect.
- CASCADE is especially sensitive to propagation because it removes descendants as well as the selected node.
- The framework does not claim true causal identification; Phase 6 studies topology-mediated functional influence under deterministic graph interventions.
