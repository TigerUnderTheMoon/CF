# Figure Inventory

All paths below refer to existing files under `outputs/figures/`. Captions must describe stored outputs, metrics, perturbation settings, observed trace behavior, or measured pipeline outputs. Captions must not imply causal identification, mechanism recovery, structural explanation, or protocol-independent reasoning.

| Figure path | Phase source | Figure purpose | Paper placement |
|---|---|---|---|
| `outputs/figures/structural_diagnostics_attribution_vs_necessity.png` | Phase 6 diagnostics | 2x2 PRUNE/CASCADE/BYPASS scatter plus pooled density; includes `y=x`, `n=2400`, and zero-inflation annotation. | Main Figure 1, Results: Attribution vs Necessity |
| `outputs/figures/structural_diagnostics_mode_comparison.png` | Phase 6 diagnostics | Summarizes PRUNE, CASCADE, and BYPASS alignment and zero-inflation diagnostics. | Main Figure 2, Results: Structural Diagnostic Summary |
| `outputs/figures/compensation_distribution.png` | Phase 7 redundancy | Reports compensation ratio distribution. | Main Figure 4, Results: Weak Compensation |
| `outputs/figures/rerouting_entropy_vs_attribution.png` | Phase 7 redundancy | Plots rerouting entropy against attribution values. | Appendix or supplementary diagnostics |
| `outputs/figures/redundancy_density_histogram.png` | Phase 7 redundancy | Reports redundancy density distribution. | Main Figure 3, Results: Redundancy |
| `outputs/figures/bottleneck_examples.png` | Phase 7 redundancy | Visualizes sparse bottleneck examples. | Appendix or supplementary diagnostics |
| `outputs/figures/resilience_curves.png` | Phase 7 redundancy | Plots removal-order resilience curves. | Main Figure 5, Results: Resilience |
| `outputs/figures/distributedness_distribution.png` | Phase 7 redundancy | Reports distributedness distribution. | Appendix or supplementary diagnostics |
| `outputs/figures/ablation_strategy_comparison.png` | Phase 5 attribution | Summarizes deterministic ablation strategies. | Methodology or Appendix |
| `outputs/figures/necessity_distribution.png` | Phase 5 attribution | Reports necessity-score distribution. | Appendix |
| `outputs/figures/minimal_subset_curve.png` | Phase 5 attribution | Plots minimal subset compression curve. | Appendix |
| `outputs/figures/redundancy_heatmap.png` | Phase 5 attribution | Visualizes Phase 5 redundancy report structure. | Appendix |
| `outputs/figures/faithfulness_scatter.png` | Phase 5 attribution | Plots Phase 5 attribution faithfulness scatter. | Appendix |
| `outputs/figures/attribution_utility_scatter.png` | Phase 4/5 validity | Plots attribution and utility relation. | Appendix |
| `outputs/figures/utility_distribution.png` | Phase 4 validity | Reports utility distribution. | Appendix |
| `outputs/figures/utility_by_category.png` | Phase 4 validity | Reports utility by taxonomy category. | Appendix |
| `outputs/figures/degradation_heatmap.png` | Phase 4 validity | Visualizes degradation diagnostics. | Appendix |
| `outputs/figures/category_dist.png` | Phase 4 validity | Reports category distribution. | Appendix |
| `outputs/figures/locality_sensitivity.png` | Phase 3 locality | Reports locality sensitivity. | Appendix |
| `outputs/figures/stability_scatter.png` | Phase 2/3 stability | Plots stability scatter. | Appendix |
| `outputs/figures/graph_size_distribution.png` | Phase 6 SRA | Reports graph size distribution. | Appendix or supplementary diagnostics |
| `outputs/figures/node_necessity_distribution.png` | Phase 6 SRA | Reports node structural necessity distribution. | Appendix |
| `outputs/figures/edge_necessity_distribution.png` | Phase 6 SRA | Reports edge structural necessity distribution. | Appendix |
| `outputs/figures/structural_faithfulness_scatter.png` | Phase 6 SRA | Plots structural faithfulness scatter. | Appendix |
| `outputs/figures/motif_frequency.png` | Phase 6 SRA | Reports motif frequency. | Appendix |
| `outputs/figures/compression_curve.png` | Phase 6 SRA | Plots structural compression curve. | Appendix |
| `outputs/figures/structural_influence_distribution.png` | Phase 6 SRA | Reports structural influence distribution. | Appendix |
| `outputs/downstream_comparison_v1/figures/task_comparison.png` | Downstream filtering diagnostics | Compares GSM8K filtering with HotpotQA answer-format sensitivity using 95% bootstrap intervals. | Main downstream filtering figure |
| `outputs/downstream_comparison_v1/figures/prm_comparison.png` | Downstream filtering diagnostics | Compares FMA CIU with perplexity proxies, random, position, and taxonomy baselines using 95% bootstrap intervals. | Main downstream filtering table/figure support |
| `outputs/downstream_comparison_v1/figures/filtering_accuracy_comparison.png` | Downstream filtering diagnostics | Reports GSM8K filtering accuracy by keep ratio with 95% bootstrap intervals. | Supplementary or downstream filtering support |
| `outputs/downstream_comparison_v1/figures/position_stratified.png` | Downstream filtering diagnostics | Reports GSM8K position-stratified filtering checks. | Position-confound support |

No known required Phase 6 or Phase 7 figure is missing. Additional discovered figures are included as appendix or framework support material.
