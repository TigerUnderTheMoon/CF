# Results

The results consolidate Phase 5-7 into a single hypothesis-refinement narrative. Initial hypothesis: reflection may exhibit distributed compensatory organization. Observed results: compensation and distributedness were weaker than expected. Final interpretation: reflective reasoning contains widespread local utility, but sparse structural necessity. Weak alignment, weak compensation, and low distributedness are informative structural findings, not experimental failure.

## Attribution vs Necessity

The Phase 6 diagnostics report weak alignment between local attribution and topology-sensitive structural necessity. Across 2400 reflective nodes, Pearson alignment is 0.0753 for PRUNE, 0.0523 for CASCADE, and 0.0917 for BYPASS. Spearman alignment remains similarly weak: 0.0596 for PRUNE, 0.0512 for CASCADE, and 0.0623 for BYPASS.

Structural necessity is zero-inflated. In every mode, 67.79 percent of structural necessity values are zero, while only 18.25 percent of samples have both zero attribution and zero structural necessity. The positive-attribution zero-necessity fraction is 49.54 percent. Local attribution signals are much more common than topology-sensitive necessity.

The framework reports that reflective utility signals are substantially more widespread than structural necessity, indicating a mismatch between local utility and topology-sensitive necessity.

This mismatch does not invalidate reflective utility attribution. It indicates that local utility and structural necessity are different operational proxy measurements. Many reflective steps are locally functional in the Phase 5 scoring layer but structurally inert in the Phase 6 graph layer.

The primary Phase 6 figure `outputs/figures/structural_diagnostics_attribution_vs_necessity.png` plots the weak alignment pattern. Mode-comparison and structural-faithfulness figures summarize supplementary diagnostics without changing the main interpretation.

## Stage 2 Confirmatory Check

The Stage 2 held-out validation reports a weak aggregate structural signal. Across 280 held-out traces and 840 held-out steps, FMA has Spearman rho 0.1628 with a 95 percent bootstrap interval of [0.0916, 0.2347]. The interval excludes zero on the full held-out set, but the effect-size label is `small`, so this should be described as low-magnitude aggregate alignment rather than a high-magnitude prediction result.

The projection audit is sign-consistent across `pi_1`, `pi_2`, `pi_3`, and `pi_4`. Because FMA is already a step-level score vector, these projections are identity mappings for FMA and should be interpreted as a step-level representation audit.

The stratum audit is heterogeneous. `S_high` and `S_low` pass the Spearman confidence-interval gate, while `S_mid` fails under part of the projection audit and the overlapping random audit stratum `S_rand` includes zero in its confidence intervals. Because the global Stage 2 gate requires all four strata, the claim table maps C1, C2, and C3 to `stratum_dependent`, not to a confirmation label.

## Baseline Gate

Required baseline families are not integrated. `outputs/stage2_baseline_results.json` registers random masking, span masking, graph removal, and edge dropout, but each is marked `not_evaluated_no_stage2_step_scores`. `outputs/stage2_baseline_leakage_audit.json` marks the same required rows as `missing_artifact`, with no independent held-out score vector `s_B(r_i)` available for comparison to the target `Delta U(r_i)`.

These rows are blockers rather than negative baseline results. No primary comparison table should report fabricated rank, AUC, correlation, or confidence-interval values for these baselines. The current results therefore support a stratum-limited Stage 2 FMA audit only; they do not support a baseline-complete journal claim.

## Redundancy

Phase 7 tests whether weak alignment can be explained by redundancy and compensatory redistribution. Redundancy density is moderate at 0.3842, with mean redundancy cluster size 1.1310 and cluster density 0.0983. This means that some reflective steps have substitutable structural profiles, but the graph is not broadly diffuse.

The primary redundancy figure `outputs/figures/redundancy_density_histogram.png` reports the redundancy distribution. It is consistent with moderate redundancy density rather than a final claim of broad compensatory structure.

The redundancy finding is also consistent with one reason why low alignment can be informative. If a local utility signal is attached to a node that has similar neighbors or overlapping downstream influence, graph removal may not expose high structural necessity. The possible interpretation is that some reflective operations are locally functional but replaceable within the stored topology.

## Weak Compensation

Compensation is weak across intervention modes. Mean compensation ratio is 0.0084 for PRUNE, 0.0000 for CASCADE, and 0.0152 for BYPASS. Median compensation is 0.0000 in the reported distributions. Rerouting entropy is also 0.0000, and mean rerouting depth is 0.0100.

These values are informative structural findings. They report limited redistribution in the stored graph topology. The measured quantity is post-removal redistribution under deterministic graph operations.

Weak compensation is therefore a result, not a failure. It narrows the paper's claim away from broad redistribution and toward sparse topology-sensitive dependence. The compensation distribution is best treated as an appendix or supplementary diagnostic because the decision-relevant main result is the near-zero ratio summary.

## Sparse Bottlenecks and Low Distributedness

The bottleneck analysis identifies 191 sparse bottlenecks among 2400 nodes, for a bottleneck frequency of 0.0796 and rarity of 0.9204. These nodes combine high normalized attribution, high normalized necessity, and low redundancy degree. Their rarity is consistent with the reported interpretation that only a small subset of reflective steps is structurally necessary under the operational proxy.

Distributedness is low. The global distributedness index is 0.2976, indicating concentration rather than broad diffusion of structural influence. Resilience curves reinforce this reading: necessity-first removal has AUC 0.1488, much lower than sequential removal at 0.4840, deterministic random removal at 0.5098, and attribution-first removal at 0.4761. Removing structurally necessary nodes degrades remaining necessity much more sharply than removing nodes by attribution alone.

This result is consistent with the attribution-necessity distinction. Attribution-first removal does not degrade the graph as sharply as necessity-first removal, which means local utility ranking is not a substitute for structural necessity ranking. The selected optional primary figure `outputs/figures/resilience_curves.png` plots the removal-order curves; bottleneck examples and distributedness distributions are supplementary diagnostics.

## Hypothesis Refinement

The empirical pattern refines the initial hypothesis rather than rejecting the framework. The initial hypothesis expected reflection to exhibit distributed compensatory organization. The reported results record weak alignment, weak compensation, low distributedness, and sparse bottlenecks. The final interpretation is more conservative and more consistent with the reported outputs: reflective reasoning exhibits widespread local utility, but only sparse structural necessity.

Empirical observations: weak Pearson alignment, a weak aggregate Stage 2 rank-alignment signal with `stratum_dependent` gating, high zero-necessity rate, moderate redundancy density, low compensation ratios, low distributedness, sparse bottlenecks, and missing required baseline evidence.

Structural interpretation: local utility is substantially more widespread than topology-sensitive dependence, so many reflective steps are locally functional without being structurally necessary under the protocol. Held-out validation supports this relation only in a weak-effect regime and with `stratum_dependent` generalization.

Possible interpretation: future process supervision may motivate future work that tests whether separating local utility scores from sparse bottleneck diagnostics is useful, but this remains a future direction rather than a conclusion drawn from the current deterministic proxy pipeline.
