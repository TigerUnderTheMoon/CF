# Interpretation and Limitations

## Scope

This repository studies intervention-based functional attribution for reflective cognition dynamics. Phase 6 adds Structural Reflection Attribution (SRA), which studies topology-mediated functional influence over reflection dependency graphs.

The framework does NOT claim true causal identification. Its claims are operational and framework-relative: given observable reflection traces, deterministic graph construction, and structure-sensitive interventions, SRA estimates topology-sensitive necessity.

## Local Attribution vs Structural Necessity

Phase 5 `attribution_score` is a local reflective attribution signal. It summarizes step-level reflective contribution using local annotation and attribution evidence.

Phase 6 structural `necessity` is a graph-intervention signal. It asks how much reachable structural utility changes when a node is removed under a specified removal mode.

These signals can disagree for principled reasons:

- A locally useful reflection step may be structurally redundant.
- A low-scoring local step may be a bridge for downstream reflection.
- A source-adjacent node can have high topology-sensitive necessity even when its local attribution is modest.
- A later verification step can have high local attribution but little structural effect if no downstream dependency relies on it.

The intended interpretation is weak structural alignment or local-to-structural mismatch, not close correspondence.

## Why Pearson Is Low

Current Phase 6 diagnostics observe weak Pearson alignment between Phase 5 `attribution_score` and Phase 6 structural `necessity` across PRUNE, CASCADE, and BYPASS.

This is expected because Pearson measures linear association between two scalar vectors, while SRA introduces graph topology, reachability, downstream propagation, and removal-mode semantics. The comparison therefore measures cross-stage alignment, not self-consistency.

Low Pearson should be read as evidence of structural dependency divergence: local reflective attribution is not a strong linear predictor of topology-sensitive necessity.

## Nonlinear Topology Effects

Topology-sensitive intervention analysis is inherently nonlinear. Removing a node may:

- disconnect descendants from frozen source nodes
- change reachable structural utility
- collapse a downstream chain
- preserve utility through alternate paths
- reconnect parents and children under BYPASS

These effects are not additive local score changes. They depend on graph position, edge direction, descendant sets, and source reachability. Pearson can understate such relationships because it does not model threshold effects, bottlenecks, or dependency cascades.

## Zero-Inflated Necessity Distributions

Structural necessity can be zero for many nodes. A zero value does not mean the local reflection was useless; it means that under the current topology and removal mode, deleting that node did not reduce the measured structural utility.

The most important mismatch statistic is:

> `attribution_score > 0` and `structural necessity == 0`

This identifies locally attributed steps that are structurally redundant under the graph intervention. A high fraction of these cases naturally lowers Pearson and is useful evidence for local-to-structural mismatch.

## CASCADE Propagation Sensitivity

CASCADE removes a selected node and its descendants. It is therefore more sensitive to downstream dependency structure than PRUNE, which removes only the selected node, or BYPASS, which attempts to preserve parent-child connectivity.

CASCADE can produce lower linear alignment because it amplifies topology effects:

- early bridge nodes affect larger subgraphs
- descendant removal makes local scores less directly comparable
- source-adjacent structure can dominate later local attribution

This behavior is not a metric tuning problem. It is part of what the CASCADE diagnostic is meant to reveal.

## Why Weak Alignment Is Not Attribution Failure

Weak structural alignment is not necessarily attribution failure. The two measurements answer different questions.

Phase 5 asks:

> Which local reflective steps appear useful under step-level attribution evidence?

Phase 6 asks:

> Which graph nodes are necessary for preserving topology-mediated functional utility?

If these always closely matched, SRA would add little beyond local scoring. Weak alignment indicates that structural reflective necessity carries information that local attribution alone does not capture.

## Terminology Guidance

Preferred terms:

- weak structural alignment
- local-to-structural mismatch
- topology-sensitive necessity
- structural dependency divergence
- topology-mediated functional influence

Avoid terms that imply the diagnostic confirms a prior score or proves correctness. Do not describe the result as Phase 5 confirmation, close correspondence, correctness proof, or faithful recovery of local attribution.

Use "functional influence" and "structural necessity" rather than causal-effect language.

## Methodological Limitations

SRA depends on several design choices:

- graph construction heuristics
- edge type semantics
- frozen source-node reachability
- utility propagation parameters
- node removal mode
- observable reflection traces

The framework conditions only on observable trace structure. It does not observe latent cognitive state, and graph edges are deterministic approximations of reflective dependencies.

The diagnostics are also limited:

- Pearson captures only linear association.
- Spearman and Kendall Tau capture rank structure but not all graph effects.
- Top-k overlap depends on the chosen k.
- Zero-inflation statistics expose redundancy but do not explain every mismatch.
- Taxonomy-stratified correlations can be unstable for small groups.

## Future Directions

Future work can extend this layer without changing the current deterministic Phase 6 semantics:

- learn topology-aware attribution weights
- compare graph construction policies
- add nonlinear dependency diagnostics
- evaluate bridge-node and source-node sensitivity
- compare PRUNE, CASCADE, and BYPASS against external task outcomes
- study whether structural necessity improves downstream process supervision

These directions should preserve the distinction between local reflective attribution and structural reflective necessity.

## Section 8 - Phase 7: Redundancy and Compensation

Phase 7 adds a deterministic redundancy and compensation analysis layer over the stored Phase 6 graph outputs. It does not rerun attribution experiments, introduce learned models, tune correlations, or claim mechanistic faithfulness.

The current Phase 7 run analyzed 2,400 reflective nodes across 800 stored graphs and 2,098 edges. The headline descriptive results are:

- redundancy density: `0.3842`
- global distributedness index: `0.2976`
- bottleneck count: `191`
- bottleneck rarity: `0.9204`
- mean compensation ratio: PRUNE `0.0084`, CASCADE `0.0000`, BYPASS `0.0152`
- resilience AUC: sequential `0.4840`, deterministic random `0.5098`, attribution-first `0.4761`, necessity-first `0.1488`

Weak necessity alignment does not imply attribution invalidity. Instead, it suggests distributed and compensatory reflective organization.

The redundancy findings support the interpretation that many locally attributed reflective steps have substitutes or overlapping downstream influence sets. This helps explain why local attribution can be positive even when structural necessity is zero under a given graph intervention.

The distributedness index should be read as a topology summary. A higher value indicates diffuse reflective organization; a lower value indicates concentration around candidate structural anchors. The current value suggests that necessity is not uniformly diffuse and that sparse bottlenecks remain relevant.

The compensation ratios measure structural redistribution and functional displacement after node removal. PRUNE and BYPASS show small but nonzero redistribution, while CASCADE is near zero because descendant removal leaves fewer downstream candidates for redistribution. These values describe stored topology behavior, not adaptive intent.

Here, compensatory behavior means non-agentic functional redistribution in the measured graph, with possible reflective substitution among downstream steps.

Observed redistribution patterns should not be interpreted as intentional or agentic adaptation.

Updated limitations:

- Phase 7 depends on Phase 6 graph construction and stored node necessity rows.
- Missing CASCADE and BYPASS per-node rows are reconstructed from stored reflection graph traces for Phase 7 summaries.
- Compensation and rerouting are descriptive graph-state metrics.
- Bottleneck scores identify candidates, not proven irreplaceable mechanisms.
- Resilience curves use stored node necessity profiles and do not rerun intervention experiments.
