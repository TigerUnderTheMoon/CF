# Baseline Artifact Audit

Protocol version: `journal_step_impact_v2_3`
Stage 2 protocol version: `fma_v1_2_stage2_confirmatory`

## Result

Scanned files: 54
Independent Stage 2 baseline score vectors found: `false`

No experiment was rerun by this audit. Known protocol, mapping, leakage, and summary artifacts are not treated as independent score-vector evidence.

## Candidate Files

| Path | Decision | Markers |
|---|---|---|
| `outputs/baseline_artifact_audit.md` | not_independent_stage2_vector | step_scores, score_vector, prediction_vector, s_b(r_i), random masking, span masking, graph removal, edge dropout |
| `outputs/baseline_completion_blockers.md` | not_independent_stage2_vector | step_scores, random masking, span masking, graph removal, edge dropout |
| `outputs/baseline_integration_summary.md` | not_independent_stage2_vector | s_b(r_i), random masking, span masking, graph removal, edge dropout |
| `outputs/baseline_mapping_table.csv` | not_independent_stage2_vector | s_b(r_i), random masking, span masking, graph removal, edge dropout |
| `outputs/experiment_matrix.json` | not_independent_stage2_vector | step_scores, s_b(r_i) |
| `outputs/fma_scores.jsonl` | not_independent_stage2_vector | none |
| `outputs/necessity_scores.jsonl` | not_independent_stage2_vector | none |
| `outputs/projection_robustness.json` | not_independent_stage2_vector | score_vector |
| `outputs/reflection_graph.json` | not_independent_stage2_vector | none |
| `outputs/stage2_baseline_leakage_audit.json` | not_independent_stage2_vector | step_scores, prediction_vector, s_b(r_i), random masking, span masking, graph removal, edge dropout |
| `outputs/stage2_baseline_results.json` | not_independent_stage2_vector | none |
| `outputs/stage2_claim_gating_summary.md` | not_independent_stage2_vector | none |
| `outputs/stage2_frozen_protocol.json` | not_independent_stage2_vector | score_vector, s_b(r_i), random masking, span masking, graph removal, edge dropout |
| `outputs/stage2_holdout_validation.json` | not_independent_stage2_vector | none |
| `outputs/stage2_leakage_audit.json` | not_independent_stage2_vector | step_scores, s_b(r_i), random masking, span masking, graph removal, edge dropout |
| `outputs/stage2_projection_audit.json` | not_independent_stage2_vector | step_scores, prediction_vector, random masking, span masking, graph removal, edge dropout |
| `outputs/stage2_split_manifest.json` | not_independent_stage2_vector | none |
| `outputs/stage2_stratified_metrics.json` | not_independent_stage2_vector | none |
| `outputs/structural_edge_necessity.jsonl` | not_independent_stage2_vector | none |
| `outputs/structural_subgraph_necessity.jsonl` | not_independent_stage2_vector | none |
| `outputs/structure_degradation_curves.json` | not_independent_stage2_vector | edge dropout |
| `outputs/submission_consistency_verification.md` | not_independent_stage2_vector | prediction_vector, random masking, span masking, graph removal, edge dropout |

## Fallback Policy

If no independent Stage 2 baseline score vector is found, evaluate required baselines using frozen conservative non-target proxy rules.
