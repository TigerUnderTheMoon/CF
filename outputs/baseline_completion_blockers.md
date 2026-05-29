# Baseline Completion Blockers

Submission status: `blocked`

The required baseline families do not have existing Stage 2 held-out step-level prediction vectors and metrics. Missing values were not inferred from FMA results, structural necessity artifacts, or narrative text.

## Blocking Evidence

Artifacts checked:

- `outputs/stage2_baseline_results.json`
- `outputs/stage2_baseline_leakage_audit.json`
- `outputs/baseline_mapping_table.csv`
- `outputs/structure_degradation_curves.json`
- `outputs/projection_robustness.json`

`outputs/stage2_baseline_results.json` is present, but it reports `evaluated_baselines: 0` and `not_evaluated_baselines: 13`. `outputs/stage2_baseline_leakage_audit.json` marks all required baseline rows as `missing_artifact`.

## Missing Required Evidence

| Baseline / Control | Required artifact evidence | Current Stage 2 status | target_leakage_status |
|---|---|---|---|
| random masking | held-out step-level `s_B(r_i)` vector plus metrics against `Delta U(r_i)` | `not_evaluated_no_stage2_step_scores` | `missing_artifact` |
| span masking | held-out step-level `s_B(r_i)` vector plus metrics against `Delta U(r_i)` | `not_evaluated_no_stage2_step_scores` | `missing_artifact` |
| graph removal | held-out structure-control step-level vector plus metrics against `Delta U(r_i)` | `not_evaluated_no_stage2_step_scores` | `missing_artifact` |
| edge dropout | held-out structure-control step-level vector plus metrics against `Delta U(r_i)` | `not_evaluated_no_stage2_step_scores` | `missing_artifact` |

## Required Before Ready Status

1. Materialize baseline result rows in `outputs/stage2_baseline_results.json` or an equivalent explicitly referenced Stage 2 artifact.
2. Include one row per required baseline family.
3. Verify every baseline emits step-level predictions `s_B(r_i)`.
4. Verify metrics use the same target, step-level `Delta U(r_i)`.
5. Report rank, AUC, correlation, and confidence intervals when available.
6. Mark any target-reusing baseline as `target_leaking` and exclude it from primary comparison unless explicitly labeled as oracle/control.

Until these are present, `baseline_status` remains `blocked_missing_baselines` and `submission_status` remains `blocked`.
