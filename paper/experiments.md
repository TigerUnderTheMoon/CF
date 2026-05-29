# Experiments

The experiments use a deterministic synthetic reflection benchmark and stored repository artifacts. The empirical scope is Phase 5-7. Phase 1-4 supply conceptual and infrastructural foundations, including trace schemas, taxonomy coverage, locality checks, and functional-validity diagnostics, but they are not treated as independent experimental chapters.

The framework evaluates structural properties of reflective reasoning traces, not downstream benchmark performance. It is analysis-oriented, topology-oriented, and diagnostic-oriented; it is not a leaderboard benchmark, model ranking framework, or general evaluation suite.

## Data Scale

The benchmark input is `data/traces/synthetic_100x8.json`. It contains 800 traces and 2400 reflective steps. The taxonomy report `outputs/taxonomy_coverage_synthetic.json` records 2400 total reflections and no collapse warnings. The category counts are: BACKTRACKING 284, CONSTRAINT_TRACKING 313, DECOMPOSITION 282, ERROR_CORRECTION 288, PLANNING 313, RETRIEVAL 300, UNCERTAINTY_MONITORING 298, and VERIFICATION 322.

The Phase 6 graph representation contains 800 graphs, 2400 nodes, and 2098 edges. The graph and structural necessity outputs are stored in `outputs/reflection_graph.json`, `outputs/structural_node_necessity.jsonl`, `outputs/structural_edge_necessity.jsonl`, and `outputs/structural_subgraph_necessity.jsonl`.

## Phase 5 Attribution Settings

Phase 5 runs deterministic counterfactual functional attribution through `scripts/run_counterfactual_attribution.py`. It reads `outputs/utility_annotations.jsonl` with 2400 rows and writes `outputs/necessity_scores.jsonl` with 2400 rows. The ablation output `outputs/counterfactual_ablation_results.jsonl` contains 14400 rows: 2400 rows for each of six ablation strategies.

The Phase 5 summary reports mean necessity 0.0636, mean normalized necessity 0.1217, mean compression ratio 0.2858, median compression ratio 0.0000, redundancy ratio 0.1454, and 303 traces with redundancy. These values support the local utility layer but do not settle structural necessity.

## Phase 6 Structural Diagnostics

Phase 6 runs structural diagnostics through `scripts/run_structural_diagnostics.py`. The intervention modes are PRUNE, CASCADE, and BYPASS. The key diagnostic files are `outputs/structural_diagnostics.json`, `outputs/structural_diagnostics.md`, and `outputs/phase6_sensitivity.json`.

The alignment tests compare Phase 5 `attribution_score` with Phase 6 `structural_necessity`. Pearson values are weak in all modes: PRUNE 0.0753, CASCADE 0.0523, and BYPASS 0.0917. The zero structural necessity fraction is 67.79 percent, and the positive-attribution zero-necessity fraction is 49.54 percent. These diagnostics establish the attribution-necessity mismatch used in the paper narrative.

The main Phase 6 figures are `outputs/figures/structural_diagnostics_attribution_vs_necessity.png` and `outputs/figures/structural_diagnostics_mode_comparison.png`. Additional supporting figures include graph size, node necessity, edge necessity, structural faithfulness, motif frequency, compression curve, and structural influence distributions.

## Phase 7 Redundancy Analysis

Phase 7 runs `scripts/run_redundancy_analysis.py` over stored structural artifacts. It reads Phase 6 diagnostics, sensitivity summaries, reflection graphs, necessity scores, and node necessity rows. CASCADE and BYPASS node rows are reconstructed from stored graph traces when explicit per-node rows are absent or incomplete.

The redundancy threshold is 0.75 and the bottleneck threshold is 0.25. The reported redundancy density is 0.3842, mean redundancy cluster size is 1.1310, cluster density is 0.0983, mean rerouting entropy is 0.0000, mean rerouting depth is 0.0100, bottleneck count is 191, bottleneck rarity is 0.9204, and the distributedness index is 0.2976.

Mean compensation ratios are low: PRUNE 0.0084, CASCADE 0.0000, and BYPASS 0.0152. Resilience AUC values are sequential 0.4840, deterministic random 0.5098, attribution-first 0.4761, and necessity-first 0.1488. These values support the final interpretation that structural necessity is sparse and compensatory redistribution is limited.

## Figure Set

The primary paper-level result figures are `outputs/figures/structural_diagnostics_attribution_vs_necessity.png`, `outputs/figures/redundancy_density_histogram.png`, and the optional selected primary figure `outputs/figures/resilience_curves.png`. Other generated figures are supplementary diagnostics and are catalogued in `paper/figure_inventory.md`.

Empirical observations are the stored report values. The structural interpretation is that local utility is more widespread than structural necessity. A possible interpretation for future work is that process supervision should distinguish local utility from sparse bottleneck structure rather than treating all reflective steps as equally indispensable.

Human evaluation, semantic reasoning verification, benchmark superiority, external baseline comparison, and statistical significance testing are not evaluated in the current framework.

No experiment in this phase modifies JSON outputs, regenerates figures as part of writing, or introduces learned models.
