# Methodology

The framework studies intervention-based functional attribution for reflective cognition dynamics. In the target journal architecture, FMA is a reflection utility learning framework that can supply candidate signals for process supervision and reflection filtering. In the current repository, the implemented evidence estimates local utility and topology-sensitive dependence over observable reasoning traces, then consolidates those estimates into structural diagnostics. The framework estimates operational proxies, not internal-process explanations.

The empirical contributions and deterministic validation presented in this paper are concentrated in Phase 5-7, for which complete implementations, deterministic tests, and reproducible outputs are available in the repository. PRM/filtering validation is part of the target architecture, but it is not a completed experiment in the current artifact set.

Phase 1-4 established the conceptual framework and pipeline architecture.

## Inputs and Outputs

The input is a set of reflective reasoning traces. Each trace contains a `sample_id`, `task_id`, `task_type`, question text, reasoning trace text, reflection spans, final answer, reference answer, correctness flag, model metadata when available, and generation configuration. In the current deterministic benchmark, `data/traces/synthetic_100x8.json` provides 800 synthetic traces with 2400 reflective steps.

The trace contract is deliberately explicit. Reflection is represented by observable spans with token boundaries, taxonomy labels, and step indices. The framework does not infer hidden reflective states. This lets each later phase join records by stable identifiers rather than by approximate text matching. It also makes failure cases easier to audit: missing rows, zero-valued necessity, and reconstructed graph records remain visible in the output files.

The primary Phase 5 outputs are `outputs/necessity_scores.jsonl`, `outputs/counterfactual_ablation_results.jsonl`, `outputs/faithfulness_report.json`, and `outputs/counterfactual_summary.json`. The primary Phase 6 outputs are `outputs/reflection_graph.json`, `outputs/structural_node_necessity.jsonl`, `outputs/structural_edge_necessity.jsonl`, `outputs/structural_subgraph_necessity.jsonl`, `outputs/structural_diagnostics.json`, and `outputs/phase6_sensitivity.json`. The primary Phase 7 outputs are `outputs/redundancy_analysis.json`, `outputs/redundancy_analysis.md`, and the Phase 7 figures under `outputs/figures/`.

All quantities are operational proxy measurements over observable trace-level perturbations. They do not provide mechanistic identification of internal computation, hidden reasoning, semantic understanding, or protocol-independent recovery.

```text
attribution_score:
  proxy for local functional contribution

structural_necessity:
  proxy for topology-sensitive dependence

compensation_ratio:
  proxy for post-removal redistribution

distributedness_index:
  proxy for concentration vs diffusion
  of structural influence
```

The output contract is similarly conservative. A paper-level row can include sample identity, task type, local utility, structural necessity, intervention mode, operation type, context length, and trajectory length. Aggregate reports must preserve task distribution information and should not pool results into a universal score without noting the fixed benchmark distribution. This scope keeps methodology readable while preserving direct reproducibility from stored artifacts.

For manuscript writing, the same contract controls terminology. Tables should report `attribution_score`, `structural_necessity`, `compensation_ratio`, and `distributedness_index` by their canonical names. Figures should be cited by the stored path in `outputs/figures/` until venue formatting converts them into numbered manuscript figures. This keeps the paper layer auditable against the repository.

All manuscript claims should remain traceable to these files.

## FMA Target Architecture

The target architecture follows the Chinese framework. Given an observable reflective trace, structure-preserving interventions estimate Conditional Interventional Utility for a metacognitive span in its local context. FMA then aggregates those local utilities under a task distribution. Counterfactual matching and doubly robust estimation are the intended controls for trajectory length, task difficulty, reasoning depth, reflection density, and step index.

In manuscript terms, this architecture supports a reflection utility learning story:

```text
observable reflection span
-> structure-preserving intervention
-> local utility estimate
-> distribution-conditioned FMA
-> candidate process-supervision or filtering signal
```

The implemented Phase 5-7 evidence adds a necessary diagnostic layer:

```text
candidate local utility signal
-> structural necessity, redundancy, bottleneck, compensation diagnostics
-> structurally calibrated supervision/filtering signal
```

This second arrow is central. The current results show that local utility alone is too broad for direct supervision weighting.

## Phase 5: Counterfactual Functional Attribution

Phase 5 estimates local utility for reflective steps using deterministic counterfactual ablation over stored traces and annotations. The runner `scripts/run_counterfactual_attribution.py` reads `data/traces/synthetic_100x8.json` and `outputs/utility_annotations.jsonl`, computes necessity scores, runs single-step ablations, and writes summary reports. The ablation strategies are `ATTRIBUTION_TOP_K`, `ATTRIBUTION_BOTTOM_K`, `CATEGORY_MATCHED_RANDOM`, `POSITIONAL_FIRST_K`, `POSITIONAL_LAST_K`, and `RANDOM_K`.

The Phase 5 metric family is functional rather than structural. It asks whether a local reflective step contributes to the measured outcome under deterministic attribution scoring. The output `attribution_score` is reported as local utility, not structural necessity. The summary report contains 800 traces, 2400 ablation units, mean normalized necessity 0.1217, and a redundancy ratio of 0.1454.

The local utility calculation is intervention-sensitive. It identifies reflective steps that have measurable local contribution under the fixed scoring procedure. It is not sufficient for identifying sparse bottlenecks, because a step can contribute locally while still being replaceable in the stored structure.

## Phase 6: Structural Reflection Attribution

Phase 6 constructs graph representations of reflective traces and evaluates topology-sensitive dependence. The graph layer links reflective steps into deterministic structures with source nodes, downstream edges, and structural influence propagation. The core question changes from local contribution to topology-sensitive dependence: does removing or changing the role of a reflective node alter the structural necessity profile?

The implemented intervention modes are PRUNE, CASCADE, and BYPASS. PRUNE removes the selected node while preserving the rest of the graph. CASCADE removes the selected node and descendants, making it sensitive to propagation. BYPASS reroutes through the graph to test dependence under a bypassed reflective node. These are deterministic graph interventions, not semantic interventions and not learned models.

Phase 6 reports `structural_necessity` for 2400 nodes, edge necessity for 2098 edges, and subgraph necessity for 1618 subgraphs. It also computes alignment diagnostics between Phase 5 `attribution_score` and Phase 6 `structural_necessity`. The diagnostic report uses low alignment as a boundary between local attribution and topology-sensitive necessity, not as proof that either signal is invalid.

The structural diagnostic uses Pearson, Spearman, Kendall tau, top-k overlap, scatter summaries, zero-inflation analysis, and stratified correlations by taxonomy, step index, and source role. These statistics are descriptive. They help determine whether local utility and structural necessity move together, but they do not authorize a stronger interpretation than the stored graph abstraction allows.

## Phase 7: Redundancy, Compensation, and Distributedness

Phase 7 is a research consolidation layer over stored Phase 6 outputs. It does not rerun attribution experiments, introduce learned models, or add an experiment phase. The runner `scripts/run_redundancy_analysis.py` reads `outputs/structural_diagnostics.json`, `outputs/phase6_sensitivity.json`, `outputs/reflection_graph.json`, `outputs/necessity_scores.jsonl`, and `outputs/structural_node_necessity.jsonl`.

Redundancy is estimated using hybrid similarity: scalar profile cosine similarity plus downstream-influence Jaccard overlap. Compensation is estimated as positive downstream necessity delta after node removal, divided by removed-node necessity with a small denominator floor. Rerouting measures breadth, depth, and entropy of downstream redistribution. Bottlenecks are nodes with high normalized attribution, high normalized necessity, and low redundancy degree. Resilience curves measure remaining total necessity under deterministic removal sequences. Distributedness summarizes whether structural influence is concentrated or diffuse.

These metrics are linked but not interchangeable. Redundancy asks whether nodes have substitutable profiles. Compensation asks whether downstream necessity increases after removal. Rerouting asks whether redistribution has breadth, depth, or entropy. Distributedness asks whether structural influence is concentrated across nodes. Bottlenecks combine local and structural criteria to identify sparse bottlenecks.

The initial hypothesis was that reflection may exhibit distributed compensatory organization. The observed results refine this hypothesis: compensation and distributedness were weaker than expected. This is an empirical hypothesis refinement, not experimental failure.

## Supervision Implication

The methodology distinguishes three signals that should not be collapsed:

| Signal | Current status | Supervision implication |
|---|---|---|
| Local attribution signal | Implemented in Phase 5 as `attribution_score` | Candidate evidence that a reflection is locally functional |
| Structural necessity signal | Implemented in Phase 6-7 as `structural_necessity`, bottlenecks, redundancy, compensation, and distributedness | Constraint on whether local utility should receive high supervision or filtering weight |
| PRM/filtering weight | Required future validation | Must be learned or computed from structurally calibrated attribution, not raw FMA alone |

The direct rule `w_k = Normalize(FMA(m_k; D))` is therefore only a target-architecture starting point from the original framework, not a claim supported by the current diagnostics. The claim-safe formulation is:

```text
w_k = Normalize(Calibrate(FMA, structural_necessity, bottleneck, redundancy, compensation))
```

The repository has not yet trained a PRM, run a filtering comparison, or produced downstream task-success evidence for this calibrated signal. The current methodology explains why such validation is needed.

## Pipeline Overview

The deterministic pipeline can be read as a sequence of progressively stricter questions. Phase 1-4 establish trace schemas, taxonomy coverage, locality diagnostics, and functional-validity infrastructure. Phase 5 asks which reflective steps have local utility. Phase 6 asks whether those steps are topology-sensitive. Phase 7 asks whether low alignment can be explained by redundancy, compensation, bottlenecks, resilience, and distributedness. The next required validation asks whether structurally calibrated signals benefit PRM/filtering behavior on real downstream tasks.

The claim hierarchy is fixed. Empirical observations are values stored in JSON, JSONL, Markdown reports, and PNG figures. Structural interpretations describe how local utility and structural necessity diverge. Process supervision and reflection filtering are target applications that require downstream validation, not settled conclusions.

The methodology therefore fits a compact manuscript structure. FMA supplies the reflection utility learning architecture. Phase 5 supplies local attribution evidence. Phase 6 supplies topology-sensitive necessity evidence. Phase 7 supplies the refinement that compensation and distributedness are limited. The final current claim is not that reflection is absent or that local utility is invalid. The final current claim is that reflective reasoning exhibits widespread local utility, but only sparse structural necessity; the top-tier claim still requires real PRM/filtering validation.
