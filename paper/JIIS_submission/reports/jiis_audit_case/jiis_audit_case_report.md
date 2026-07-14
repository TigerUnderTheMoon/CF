# JIIS Countries-KG Impact Coverage Audit Case

- Protocol: fair-v1
- Seed: 20260711
- Traces: 600
- Independent source units: 30
- Budget fraction: 25%
- Label cache: `D:\CF\outputs\countries_kg_label_validation\countries_kg_labels_cached.json`

Impact Coverage@K of Life-Saving First stratified policy vs. flat Top-K baseline (using the shared raw_risk_score as the sole ranking criterion), Greedy Maximum Coverage, degree centrality, random stratified labels, position, random, and one-layer-off ablations.

| Method | Impact Coverage@K | Avg path length | Early truncation | Budget used |
|---|---:|---:|---:|---:|
| Life-Saving First | 0.733 | 0.828 | 0.000 | 1.000 |
| Flat Top-K | 0.733 | 0.828 | 0.000 | 1.000 |
| Greedy Maximum Coverage | 0.733 | 0.828 | 0.000 | 1.000 |
| Degree Centrality | 0.650 | 0.761 | 0.000 | 1.000 |
| Random Stratified | 0.733 | 0.828 | 0.000 | 1.000 |
| Position | 0.000 | 0.000 | 0.000 | 1.000 |
| Random | 0.364 | 0.593 | 0.000 | 1.000 |
| No-Fallback Ablation | 0.733 | 0.878 | 0.000 | 0.950 |
| LSF minus Bottleneck | 0.733 | 0.828 | 0.000 | 1.000 |
| LSF minus Redundancy | 0.733 | 0.828 | 0.000 | 1.000 |
| LSF minus Unique | 0.733 | 0.828 | 0.000 | 1.000 |
