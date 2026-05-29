# Appendix

This appendix provides compact reference material. It summarizes formulas, schemas, intervention examples, taxonomy definitions, edge-case handling, and normalization policy. For detailed implementation contracts, see `AGENTS.md`. For broader interpretation boundaries, see `docs/interpretation_and_limitations.md`.

## Metric Formulas

Local utility proxy:

```latex
\text{local utility}(m_k) = Y(\tau) - Y(\tau_{\setminus m_k})
```

Structural necessity proxy:

```latex
\text{structural necessity}(v) =
\max(0, U(G) - U(G \setminus v))
```

Compensation ratio:

```latex
\text{compensation ratio}(v) =
\frac{\sum_{u \in D(v)} \max(0, N_u^{\text{after}} - N_u^{\text{before}})}
{\max(N_v^{\text{removed}}, \epsilon)}
```

Distributedness index:

```latex
\text{distributedness}(G) = 1 - \text{concentration}(\{N_v : v \in G\})
```

The exact implementation uses the repository functions in `fma/eval/redundancy/` and `fma/eval/diagnostics/`.

## Schema Examples

Trace records follow `schemas/reflection_trace.schema.json` and include `sample_id`, `task_id`, `task_type`, `question`, `reasoning_trace`, `reflection_spans`, `final_answer`, `reference_answer`, `correctness`, `model_name`, and `generation_config`.

Paper-level output records should use fields such as `sample_id`, `task`, `task_type`, `ciu`, `fma`, `matched`, `propensity`, `intervention_type`, `operation_type`, `context_length`, and `trajectory_length` when running the earlier CIU/FMA pipeline.

## Intervention Examples

PRUNE removes a reflective node from the graph and recomputes structural necessity over the remaining topology.

CASCADE removes the selected node and descendants, making the result sensitive to downstream propagation.

BYPASS reroutes through available graph structure to estimate whether downstream dependence remains after bypassing a reflective node.

These are deterministic structural interventions. They are not semantic reasoning verification.

## Taxonomy Definitions

The synthetic taxonomy contains BACKTRACKING, CONSTRAINT_TRACKING, DECOMPOSITION, ERROR_CORRECTION, PLANNING, RETRIEVAL, UNCERTAINTY_MONITORING, and VERIFICATION. The taxonomy report stores counts and normalized coverage in `outputs/taxonomy_coverage_synthetic.json`.

## Additional Tables

Core Phase 6 alignment:

| Mode | Pearson | Zero structural necessity | Positive attribution and zero necessity |
|---|---:|---:|---:|
| PRUNE | 0.0753 | 67.79% | 49.54% |
| CASCADE | 0.0523 | 67.79% | 49.54% |
| BYPASS | 0.0917 | 67.79% | 49.54% |

Core Phase 7 metrics:

| Metric | Value |
|---|---:|
| Redundancy density | 0.3842 |
| Distributedness index | 0.2976 |
| Bottleneck count | 191 |
| PRUNE compensation ratio | 0.0084 |
| CASCADE compensation ratio | 0.0000 |
| BYPASS compensation ratio | 0.0152 |

## Edge-Case Handling

Zero structural necessity is preserved rather than smoothed away. Source-node reachability is frozen in Phase 6 structural analysis. CASCADE and BYPASS node rows can be reconstructed from stored `reflection_graph.json` when explicit rows are absent or incomplete. Compensation uses a denominator floor to avoid unstable division when removed-node necessity is near zero.

## Normalization Policy

Scores are normalized only when required by the implemented diagnostic. Bottleneck scores combine normalized attribution, normalized necessity, and normalized redundancy degree. Redundancy uses a fixed similarity threshold of 0.75 in the current Phase 7 run. Resilience curves use normalized removal progress before AUC computation.

Claim hierarchy: empirical observations are table values from stored outputs; structural interpretations explain their stored trace-topology meaning; possible interpretation should be reserved for future direction.
