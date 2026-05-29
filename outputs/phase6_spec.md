# Codex Task — Phase 6: Structural Reflection Attribution (SRA)

## Revised Specification v1.1

---

# Critical Revision Notes (v1.1)

This revision addresses four major theoretical weaknesses identified in v1.0:

1. **Linear additive utility issue**

   * v1.0 utility computation was effectively sequence-additive and did not sufficiently incorporate graph structure.
   * v1.1 introduces:

     * Reachability-Constrained Utility
     * Structural Influence Score
     * Topology-sensitive propagation

2. **Edge necessity degeneracy**

   * In v1.0, deleting edges often had no effect because utility was node-local.
   * v1.1 fixes this by requiring node utility to depend on graph reachability.

3. **DAG vs retry-cycle contradiction**

   * v1.0 referenced "retry cycles" despite enforcing DAG constraints.
   * v1.1 replaces this with:

     * retry cascades
     * iterative retry motifs

4. **Unnecessary graph isomorphism complexity**

   * v1.0 proposed generic graph isomorphism matching.
   * v1.1 replaces this with deterministic template matching specialized to small motifs.

This revision ensures that graph topology materially affects attribution outcomes.

---

# Context

Project root:

```text
D:\CF
```

Completed phases:

* Phase 1: Core attribution engine
* Phase 2: Taxonomy-stratified evaluation
* Phase 3: Stability and intervention analysis
* Phase 4: Functional validity
* Phase 5: Counterfactual Functional Attribution (CFA)

Phase 6 upgrades attribution from:

```text
linear step attribution
```

to:

```text
structural graph attribution
```

---

# Research Goal

Build a Structural Reflection Attribution (SRA) framework that:

1. Represents reflection traces as DAGs
2. Encodes structural dependencies between reflection operations
3. Supports graph-level interventions
4. Computes topology-sensitive operational contribution
5. Detects reusable reasoning motifs
6. Enables minimal sufficient reasoning subgraphs
7. Models structural influence propagation

The system studies:

```text
operational reflective organization
```

NOT literal cognition.

---

# Theoretical Revision — Reachability-Constrained Utility

---

# Problem in v1.0

The original utility definition:

```python
U(G) = sum(node.utility_score)
```

did not meaningfully depend on graph structure.

As a result:

* edge deletion often had zero effect
* topology contributed weakly to attribution
* graph attribution collapsed into node summation

---

# New Utility Definition (v1.1)

A node contributes utility ONLY IF:

```text
it is reachable from at least one source node
```

where:

```text
source node := in_degree == 0
```

Define:

```text
Reachable(G) = {v ∈ V : reachable from at least one source}
```

Then:

U(G)=\sum_{v\in Reachable(G)} SI(v)

This ensures:

* edge deletion can disconnect subgraphs
* graph topology affects utility
* structural interventions become meaningful

---

# Structural Influence Score (NEW)

Each node now has propagated influence:

SI(v)=u(v)+\lambda\sum_{d\in Desc(v)}\gamma^{dist(v,d)}u(d)

Where:

* (u(v)) = local node utility
* (Desc(v)) = descendants of node
* (dist(v,d)) = shortest-path distance
* (\lambda) = propagation coefficient
* (\gamma) = distance decay factor

Recommended defaults:

```python
lambda_propagation = 0.5
gamma_decay = 0.8
```

Interpretation:

* bridge nodes gain importance
* upstream correction nodes gain propagated utility
* deep reasoning structures contribute less via decay
* branching structures become attributionally important

This is the core topology-sensitive upgrade of Phase 6.

---

# Reflection Graph Representation

## File

```text
fma/graph/reflection_graph.py
```

## ReflectionNode

```python
@dataclass
class ReflectionNode:
    node_id: str
    trace_id: str
    step_index: int
    taxonomy_label: str
    utility_score: float
    structural_influence: float
    content: str
```

---

## ReflectionEdge

```python
@dataclass
class ReflectionEdge:
    source: str
    target: str
    edge_type: str
    weight: float = 1.0
```

Supported edge types:

* verifies
* critiques
* corrects
* elaborates
* retries
* decomposes
* summarizes
* revises

---

## ReflectionGraph

Internal invariant:

```text
Graph MUST remain acyclic.
```

Any edge creating a cycle raises:

```python
ValueError
```

Required methods remain identical to v1.0.

---

# Graph Construction

## File

```text
fma/graph/build_reflection_graph.py
```

---

# Deterministic Edge Rules

The priority-ranked heuristic system from v1.0 remains unchanged.

However:

```text
Only one edge may exist between any ordered pair.
```

is now STRICTLY REQUIRED for deterministic topology.

---

# Structural Attribution

## File

```text
fma/eval/structural_attribution.py
```

---

# Utility Computation (UPDATED)

## Reachability-Constrained Utility

```python
def compute_graph_utility(
    graph: ReflectionGraph
) -> float:
```

Algorithm:

1. Find all source nodes
2. Compute all reachable nodes
3. Sum structural influence over reachable nodes only

---

# Structural Influence Propagation

```python
def compute_structural_influence(
    graph: ReflectionGraph,
    lambda_propagation: float = 0.5,
    gamma_decay: float = 0.8
) -> dict[str, float]:
```

Requirements:

* deterministic
* DAG-safe
* no recursive loops
* topological-order propagation

---

# Node Necessity (UPDATED)

Definition:

Necessity(v)=\frac{U(G)-U(G\setminus v)}{U(G)}

Where:

* (U(G)) uses reachability-constrained utility
* removing nodes may disconnect descendants
* topology now materially affects attribution

---

# Edge Necessity (FIXED)

Definition:

Necessity(e)=\frac{U(G)-U(G\setminus e)}{U(G)}

Important change:

Removing an edge may:

* disconnect descendants
* invalidate reachable paths
* reduce propagated influence

Therefore edge necessity is no longer degenerate.

---

# Removal Semantics

Modes retained:

* PRUNE
* CASCADE
* BYPASS

Default:

```text
PRUNE
```

---

# BYPASS Semantics (Clarified)

When removing node (v):

* connect all parents of (v)
* to all children of (v)
* while preserving DAG constraints

If adding bypass edges would create a cycle:

```text
skip that bypass edge
```

---

# Structural Redundancy (UPDATED)

The term:

```text
retry cycles
```

is REMOVED.

Replace with:

```text
iterative retry cascades
```

because the framework enforces DAGs.

---

# Structural Redundancy Types

1. Interchangeable verifier chains
2. Duplicated correction motifs
3. Iterative retry cascades

---

# Motif Discovery

## File

```text
fma/graph/motif_analysis.py
```

---

# IMPORTANT CHANGE

DO NOT use:

```python
networkx.is_isomorphic
```

for general graph matching.

Instead:

* implement deterministic local topology checks
* specialized per-template matching
* explicit edge-pattern traversal

Reason:

* motifs are tiny
* graph iso is unnecessary complexity
* deterministic traversal is faster and simpler

---

# Motif Templates

Same templates as v1.0:

* critique_revision
* verify_correct
* decompose_retry
* retry_verify
* elaborate_chain
* convergent_verify
* divergent_decompose
* full_correction

---

# Reflection Compression

## File

```text
fma/eval/reflection_compression.py
```

---

# Compression Utility (UPDATED)

Subgraph utility is now:

U(S)=\frac{\sum_{v\in Reachable(S)}SI(v)}{\sum_{v\in Reachable(G)}SI(v)}

NOT raw node utility summation.

This makes compression topology-sensitive.

---

# Compression Algorithm

Greedy deletion remains unchanged.

However:

* necessity MUST be recomputed after every accepted deletion
* structural influence MUST be recomputed after every accepted deletion
* reachable nodes MUST be recomputed after every accepted deletion

This prevents stale topology effects.

---

# Visualization

## File

```text
fma/visualization/graph_plots.py
```

Add NEW figure:

| Figure                            | Filename                                        | Description                            |
| --------------------------------- | ----------------------------------------------- | -------------------------------------- |
| Structural Influence Distribution | `figures/structural_influence_distribution.png` | Histogram of propagated node influence |

All previous figures remain required.

---

# Evaluation Extensions

Add NEW metrics:

| Metric                    | Definition                                                      |
| ------------------------- | --------------------------------------------------------------- |
| structural_influence_mean | Mean propagated influence                                       |
| reachable_ratio           | reachable_nodes / total_nodes                                   |
| influence_depth           | mean descendant distance weighted by utility                    |
| bridge_node_fraction      | fraction of nodes whose removal disconnects reachable subgraphs |

---

# Testing Additions (NEW)

Add the following tests:

---

## Structural Utility Tests

```python
test_edge_removal_disconnects_subgraph
```

Assertion:

* removing critical edge reduces reachable utility

---

```python
test_bridge_node_high_influence
```

Assertion:

* bridge nodes have higher structural influence

---

```python
test_propagation_decay
```

Assertion:

* descendant contribution decays with distance

---

```python
test_reachability_constraint
```

Assertion:

* disconnected nodes do not contribute utility

---

# Desired End State

After Phase 6:

* graph topology materially affects attribution
* edge necessity is meaningful
* compression is topology-sensitive
* propagated influence exists
* structural interventions alter utility flow
* attribution is no longer reducible to linear node scoring

The framework should resemble:

```text
structural process attribution
```

rather than:

```text
graph-shaped sequence scoring
```

---

# Remaining Limitations

1. Propagation remains heuristic
2. Edge weights are not learned
3. Utility aggregation is still simplified
4. DAG restriction removes recursive reasoning
5. Motif templates remain hand-designed

---

# Suggested Phase 7 Directions

* weighted propagation calibration
* learned edge weighting
* automatic motif induction
* graph kernel similarity
* dynamic temporal graphs
* recursive reflection modeling
* influence-flow attribution
* probabilistic structural attribution

---
