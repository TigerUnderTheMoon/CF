# Paper Outline

Target format: 6-8 page workshop-style manuscript, with a concise appendix and reproducibility notes. Primary target venues are NeurIPS, ICLR, and ICML workshops; fallback venues are ACL or EMNLP Findings.

## 1. Introduction

Section purpose: motivate the question of whether reflective reasoning steps that show local utility also exhibit structural necessity.

Key claim: reflective reasoning exhibits widespread local utility, but only sparse structural necessity.

Required figures: none in the first page unless layout permits a small framework schematic generated later.

Referenced outputs: `outputs/counterfactual_summary.json`, `outputs/structural_diagnostics.json`, `outputs/redundancy_analysis.json`.

## 2. Related Work

Section purpose: position the framework against Reflexion or Self-Refine style methods, Process Reward Models, and counterfactual or intervention-based analysis.

Key claim: prior work usually evaluates trajectory-level improvement, step labels, or local perturbation results, while this paper separates local utility from topology-sensitive structural necessity.

Required figures: none.

Referenced outputs: none; citation placeholders remain until manual bibliography completion.

## 3. Framework Overview

Section purpose: define reflective traces, step-level attribution records, graph construction, and the operational proxy stance.

Key claim: the framework estimates local utility and topology-sensitive dependence proxies, not internal-process explanations.

Required figures: `outputs/figures/graph_size_distribution.png`, `outputs/figures/taxonomy_distribution.png`.

Referenced outputs: `data/traces/synthetic_100x8.json`, `outputs/taxonomy_coverage_synthetic.json`, `outputs/reflection_graph.json`.

## 4. Attribution Methodology

Section purpose: summarize Phase 5 counterfactual functional attribution and its deterministic ablation strategies.

Key claim: Phase 5 produces local utility and necessity-score records that serve as local signals but do not settle topology-sensitive necessity.

Required figures: `outputs/figures/ablation_strategy_comparison.png`, `outputs/figures/necessity_distribution.png`, `outputs/figures/minimal_subset_curve.png`.

Referenced outputs: `outputs/necessity_scores.jsonl`, `outputs/counterfactual_ablation_results.jsonl`, `outputs/faithfulness_report.json`, `outputs/counterfactual_summary.json`.

## 5. Intervention & Structural Analysis

Section purpose: describe Phase 6 graph construction, PRUNE, CASCADE, and BYPASS intervention modes, and alignment diagnostics.

Key claim: structural necessity is zero-inflated and weakly aligned with local attribution across all intervention modes.

Interpretation should remain bounded to joint perturbation sensitivity under the evaluation protocol, not explicit compositional structure in the model.

Required figures: `outputs/figures/structural_diagnostics_attribution_vs_necessity.png`.

Referenced outputs: `outputs/structural_diagnostics.json`, `outputs/structural_diagnostics.md`, `outputs/structural_node_necessity.jsonl`, `outputs/phase6_sensitivity.json`. Supporting figures such as `outputs/figures/structural_diagnostics_mode_comparison.png` and `outputs/figures/structural_faithfulness_scatter.png` belong in appendix or supplementary diagnostics.

## 6. Redundancy & Compensation

Section purpose: explain Phase 7 redundancy density, weak compensation, rerouting, sparse bottlenecks, resilience, and distributedness.

Key claim: the initial hypothesis that reflection may exhibit distributed compensatory organization is empirically refined into limited redistribution and sparse structural necessity.

Resilience and compensation should be read as ordering- and protocol-dependent diagnostics rather than intrinsic robustness properties.

Required figures: `outputs/figures/redundancy_density_histogram.png`. Optional primary figure: `outputs/figures/resilience_curves.png`. Supporting figures such as compensation, rerouting, bottleneck examples, and distributedness distributions belong in appendix or supplementary diagnostics.

Referenced outputs: `outputs/redundancy_analysis.json`, `outputs/redundancy_analysis.md`, `outputs/reflection_graph.json`, `outputs/necessity_scores.jsonl`.

## 7. Results

Section purpose: consolidate the Phase 5-7 empirical pattern into the final narrative.

Key claim: weak alignment, weak compensation, and low distributedness are informative structural findings, not experimental failure.

Figures should summarize measured outputs rather than structural explanation.

Required figures: `outputs/figures/structural_diagnostics_attribution_vs_necessity.png` and `outputs/figures/redundancy_density_histogram.png`. Optional primary figure selected for the main text: `outputs/figures/resilience_curves.png`.

Referenced outputs: `outputs/structural_diagnostics.json`, `outputs/redundancy_analysis.json`, `outputs/counterfactual_summary.json`.

## 8. Limitations

Section purpose: bound the claims and prevent over-interpretation.

Key claim: observed redistribution should not be interpreted as intentional adaptation, and deterministic proxy measurements do not provide internal-process guarantees.

Required figures: none.

Referenced outputs: `docs/interpretation_and_limitations.md`, `outputs/redundancy_analysis.md`.

## 9. Reproducibility

Section purpose: specify environment assumptions, deterministic guarantees, commands, and expected outputs.

Key claim: the empirical core is reproducible from stored artifacts and deterministic runners without external APIs.

Required figures: inventory reference only.

Referenced outputs: `outputs/phase6_readme.md`, `outputs/phase6_sensitivity.json`, `outputs/redundancy_analysis.json`, `outputs/figures/`.

## 10. Conclusion

Section purpose: state the final paper claim compactly and identify future directions.

Key claim: reflective reasoning contains widespread local utility, but sparse structural necessity; possible interpretation should focus on better structural diagnostics, not broader explanatory claims.

Required figures: none.

Referenced outputs: same core outputs as Results.
