# Phase 6 SRA Delivery Audit

## Reproducibility Commands

```powershell
python scripts\run_structural_attribution.py
python scripts\audit_phase6_delivery.py
python -m pytest -q
```

All Phase 6 computations are deterministic, CPU-only, and do not call LLM inference.

## Inputs

- Traces: `D:\CF\data\traces\synthetic_100x8.json`
- Phase 5 necessity scores: `D:\CF\outputs\necessity_scores.jsonl`

## Core Metrics

- Graphs: `800`
- Nodes: `2400`
- Edges: `2098`
- PRUNE structural faithfulness Pearson: `0.07532678914864946`
- PRUNE mean compression ratio: `0.49333333333333335`

The low structural faithfulness Pearson is interpreted as weak alignment between Phase 5 step scores and topology-sensitive SRA necessity, not as proof of success or failure.

## Required Reports

- `reflection_graph.json`: exists=`True`, nonempty=`True`, bytes=`1549800`
- `structural_node_necessity.jsonl`: exists=`True`, nonempty=`True`, bytes=`699344`
- `structural_edge_necessity.jsonl`: exists=`True`, nonempty=`True`, bytes=`541604`
- `structural_subgraph_necessity.jsonl`: exists=`True`, nonempty=`True`, bytes=`497971`
- `structural_faithfulness.json`: exists=`True`, nonempty=`True`, bytes=`1367`
- `motif_report.json`: exists=`True`, nonempty=`True`, bytes=`404217`
- `reflection_compression_report.json`: exists=`True`, nonempty=`True`, bytes=`951280`

## Required Figures

- `graph_size_distribution.png`: exists=`True`, nonempty=`True`, bytes=`75409`
- `node_necessity_distribution.png`: exists=`True`, nonempty=`True`, bytes=`78273`
- `edge_necessity_distribution.png`: exists=`True`, nonempty=`True`, bytes=`78365`
- `structural_faithfulness_scatter.png`: exists=`True`, nonempty=`True`, bytes=`86081`
- `motif_frequency.png`: exists=`True`, nonempty=`True`, bytes=`163683`
- `compression_curve.png`: exists=`True`, nonempty=`True`, bytes=`85729`
- `structural_influence_distribution.png`: exists=`True`, nonempty=`True`, bytes=`71759`

## JSONL Row Counts

- `structural_node_necessity.jsonl`: `2400` rows
- `structural_edge_necessity.jsonl`: `2098` rows
- `structural_subgraph_necessity.jsonl`: `1618` rows

## Scope From git status --short

- Source code:
  - `?? fma/eval/reflection_compression.py`
  - `?? fma/eval/structural_attribution.py`
  - `?? fma/graph/`
  - `?? fma/visualization/graph_plots.py`
  - `?? scripts/audit_phase6_delivery.py`
  - `?? scripts/run_structural_attribution.py`
- Tests:
  - `?? tests/test_motif_analysis.py`
  - `?? tests/test_reflection_compression.py`
  - `?? tests/test_reflection_graph.py`
  - `?? tests/test_structural_attribution.py`
- Generated outputs:
  - `?? outputs/figures/compression_curve.png`
  - `?? outputs/figures/edge_necessity_distribution.png`
  - `?? outputs/figures/graph_size_distribution.png`
  - `?? outputs/figures/motif_frequency.png`
  - `?? outputs/figures/node_necessity_distribution.png`
  - `?? outputs/figures/structural_faithfulness_scatter.png`
  - `?? outputs/figures/structural_influence_distribution.png`
  - `?? outputs/motif_report.json`
  - `?? outputs/phase6_readme.md`
  - `?? outputs/phase6_sensitivity.json`
  - `?? outputs/reflection_compression_report.json`
  - `?? outputs/reflection_graph.json`
  - `?? outputs/structural_edge_necessity.jsonl`
  - `?? outputs/structural_faithfulness.json`
  - `?? outputs/structural_node_necessity.jsonl`
  - `?? outputs/structural_subgraph_necessity.jsonl`
- Specification:
  - `?? outputs/phase6_spec.md`

## Interpretation Boundaries

- SRA estimates structural process attribution, not a universal causal estimand.
- Source-node reachability is frozen to make edge and bridge interventions topology-sensitive.
- Motifs are hand-designed deterministic templates; automatic motif induction is deferred to a later phase.
- Propagation and edge weights remain heuristic and are not learned in Phase 6.
