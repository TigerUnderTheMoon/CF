# JIIS Countries-KG Impact Coverage Audit Case

- Seed: 20260711
- Traces: 600
- Budget fraction: 25%
- Label cache: `outputs\countries_kg_label_validation\countries_kg_labels_cached.json`

Impact Coverage@K of Life-Saving First stratified policy vs. flat Top-K baseline (using the shared raw_risk_score as the sole ranking criterion), degree centrality, random stratified labels, position, random, and no-fallback ablation.

| Method | Impact Coverage@K | Avg path length | Early truncation | Budget used |
|---|---:|---:|---:|---:|
| Life-Saving First | 1.000 | 1.000 | 0.000 | 1.000 |
| Flat Top-K | 0.733 | 0.828 | 0.000 | 1.000 |
| Degree Centrality | 0.650 | 0.761 | 0.000 | 1.000 |
| Random Stratified | 0.544 | 0.656 | 0.000 | 1.000 |
| Position | 0.000 | 0.000 | 0.000 | 1.000 |
| Random | 0.333 | 0.622 | 0.000 | 1.000 |
| No-Fallback Ablation | 1.000 | 1.000 | 0.000 | 1.000 |
