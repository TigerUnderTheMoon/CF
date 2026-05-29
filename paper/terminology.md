# Terminology

This paper uses fixed terminology to avoid drift between attribution analysis, structural analysis, and redundancy analysis. The project studies intervention-based functional attribution for reflective cognition dynamics. It does not claim access to hidden reasoning, semantic understanding, internal mechanisms, or strong identification.

## Canonical Claim

Reflective reasoning exhibits widespread local utility, but only sparse structural necessity.

Weak attribution-necessity alignment does not invalidate reflective utility attribution. Instead, it suggests that many reflective steps are locally functional, few are structurally necessary under the protocol, and compensatory redistribution is limited.

## Core Distinctions

Attribution vs necessity: `attribution_score` measures local functional contribution under deterministic counterfactual scoring. `structural_necessity` measures topology-sensitive dependence after graph intervention. A high `attribution_score` does not imply high `structural_necessity`.

Local vs global: local quantities are defined for an individual reflective step in its observable context. Global summaries aggregate over the fixed task distribution and stored trace topology. No global summary should be read as universal outside that distribution.

Functional vs structural: functional metrics estimate outcome-linked local utility. Structural metrics estimate topology-sensitive sensitivity, redundancy, and concentration. The two families are expected to diverge when a locally functional step is structurally replaceable or structurally inert.

Scope disclaimer: all reported quantities are deterministic operational proxies. They are not protocol-independent effects, hidden reasoning states, internal-process explanations, or universal importance scores.

## Proxy Ontology

All core quantities are operational proxy measurements:

| Quantity | Proxy interpretation |
|---|---|
| `attribution_score` | proxy for local functional contribution |
| `structural_necessity` | proxy for topology-sensitive dependence |
| `compensation_ratio` | proxy for post-removal redistribution |
| `distributedness_index` | proxy for concentration vs diffusion of structural influence |

## Canonical Terms

The following names are locked for all `paper/*.md` files. Use these canonical terms even when a nearby synonym would sound natural.

| Canonical term | Meaning | Avoid |
|---|---|---|
| local utility | Local functional contribution of a reflective step under deterministic attribution scoring. | usefulness |
| structural necessity | Topology-sensitive dependence of the graph on a reflective step. | importance |
| sparse bottleneck | Rare node with high normalized attribution, high normalized necessity, and low redundancy degree. | critical node |
| weak compensation | Limited measured post-removal redistribution. | self-repair |
| structurally inert | Locally present step with zero measured structural necessity. | fake reasoning |
| intervention-sensitive utility | Utility estimated from controlled deterministic interventions. | heuristic reflection score |
| topology-sensitive dependence | Dependence measured through graph removal modes and downstream structure. | mechanistic dependence |
| hypothesis refinement | Revision from expected distributed compensation to observed sparse structural necessity. | experimental failure |

## Claim Hierarchy

Empirical observations are measurements directly reported in `outputs/`, such as Pearson alignment, zero-necessity rates, redundancy density, compensation ratios, distributedness, and resilience AUC.

Structural interpretations explain how those measurements relate to stored trace topology, for example the mismatch between widespread local utility and sparse structural necessity.

Speculative implications must be labeled as possible interpretation, hypothesis, or future direction. They must not be stated as settled conclusions.
