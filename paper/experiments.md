# Experiments

The completed experiments use a deterministic synthetic reflection benchmark and stored repository artifacts. The current empirical scope is Phase 5-7. Phase 1-4 supply conceptual and infrastructural foundations, including trace schemas, taxonomy coverage, locality checks, and functional-validity diagnostics, but they are not treated as independent experimental chapters.

The target journal architecture connects FMA to process supervision and reflection filtering, but the current experiments evaluate diagnostic properties of reflective reasoning traces, not completed downstream PRM/filtering performance. It is analysis-oriented, topology-oriented, and diagnostic-oriented; it is not a leaderboard benchmark, model ranking framework, or general evaluation suite.

## Evidence Layers

The experimental story has three layers:

| Layer | Status | Role in the paper |
|---|---|---|
| Diagnostic evidence | Completed Phase 5-7 | Shows why local utility and structural necessity must be separated |
| Real-task replay/pilot | Guarded pilot evidence | Tests whether the pipeline can move beyond stored synthetic traces under preflight and readiness gates |
| PRM/filtering validation | Required future experiment | Must evaluate downstream benefit from structurally calibrated FMA in process supervision or reflection filtering |

Only the first layer is currently complete. The second layer is blocked by readiness gates, and the third layer is not yet present as a repository artifact.

## Data Scale

The benchmark input is `data/traces/synthetic_100x8.json`. It contains 800 traces and 2400 reflective steps. The taxonomy report `outputs/taxonomy_coverage_synthetic.json` records 2400 total reflections and no collapse warnings. The category counts are: BACKTRACKING 284, CONSTRAINT_TRACKING 313, DECOMPOSITION 282, ERROR_CORRECTION 288, PLANNING 313, RETRIEVAL 300, UNCERTAINTY_MONITORING 298, and VERIFICATION 322.

The Phase 6 graph representation contains 800 graphs, 2400 nodes, and 2098 edges. The graph and structural necessity outputs are stored in `outputs/reflection_graph.json`, `outputs/structural_node_necessity.jsonl`, `outputs/structural_edge_necessity.jsonl`, and `outputs/structural_subgraph_necessity.jsonl`.

## Unified Comparison Space

The journal protocol fixes a common step-level evaluation space before held-out scoring. Prediction target: step-level `Delta U(r_i)`. Method output: step-level score vector `s_B(r_i)`. Comparison metrics: ranking correlation, top-k alignment, and high-impact step AUC. Raw token-level, raw attention-level, and unprojected activation-level values are not primary comparison results.

The available Stage 2 run evaluates FMA as a preprojected step-level vector. The projection audit therefore uses identity mappings for `pi_1` through `pi_4`; this is expected behavior for the FMA representation and should be read as a step-level representation audit, not as evidence of nontrivial token-to-step projection robustness.

Required baseline families are random masking, span masking, graph removal, and edge dropout. `outputs/baseline_mapping_table.csv` defines their intended step-level mappings. `outputs/baseline_artifact_audit.md` found no hidden independent Stage 2 baseline score vectors, so `outputs/stage2_baseline_results.json` evaluates the four required rows with frozen conservative non-target proxy rules. All four required rows have `target_leakage_status: clean`.

| Comparison group | Current Stage 2 handling | Primary-result status |
|---|---|---|
| FMA | Evaluated as preprojected step-level `s_B(r_i)` | reported with rank, top-k, AUC, and confidence intervals |
| Structural-free perturbation baselines | random masking and span masking use clean conservative proxy `s_B(r_i)` vectors | required controls integrated |
| Structure controls | graph removal and edge dropout use clean topology-derived proxy `s_B(r_i)` vectors | required controls integrated |
| Optional or unavailable baselines | token dropout, white-box attribution rows, generative feedback systems, and extra structure controls are registered as unavailable or secondary | not primary evidence |
| Oracle/control rows | none available in the current artifacts | not reported |

## Phase 5 Attribution Settings

Phase 5 runs deterministic counterfactual functional attribution through `scripts/run_counterfactual_attribution.py`. It reads `outputs/utility_annotations.jsonl` with 2400 rows and writes `outputs/necessity_scores.jsonl` with 2400 rows. The ablation output `outputs/counterfactual_ablation_results.jsonl` contains 14400 rows: 2400 rows for each of six ablation strategies.

The Phase 5 summary reports mean necessity 0.0636, mean normalized necessity 0.1217, mean compression ratio 0.2858, median compression ratio 0.0000, redundancy ratio 0.1454, and 303 traces with redundancy. These values are consistent with the local utility layer but do not settle structural necessity.

## Phase 6 Structural Diagnostics

Phase 6 runs structural diagnostics through `scripts/run_structural_diagnostics.py`. The intervention modes are PRUNE, CASCADE, and BYPASS. The key diagnostic files are `outputs/structural_diagnostics.json`, `outputs/structural_diagnostics.md`, and `outputs/phase6_sensitivity.json`.

The alignment tests measure the relation between Phase 5 `attribution_score` and Phase 6 `structural_necessity`. Pearson values are weak in all modes: PRUNE 0.0753, CASCADE 0.0523, and BYPASS 0.0917. The zero structural necessity fraction is 67.79 percent, and the positive-attribution zero-necessity fraction is 49.54 percent. These diagnostics establish the attribution-necessity mismatch used in the paper narrative.

The main Phase 6 figures are `outputs/figures/structural_diagnostics_attribution_vs_necessity.png` and `outputs/figures/structural_diagnostics_mode_comparison.png`. Additional supplementary figures report graph size, node necessity, edge necessity, structural faithfulness, motif frequency, compression curve, and structural influence distributions.

## Phase 7 Redundancy Analysis

Phase 7 runs `scripts/run_redundancy_analysis.py` over stored structural artifacts. It reads Phase 6 diagnostics, sensitivity summaries, reflection graphs, necessity scores, and node necessity rows. CASCADE and BYPASS node rows are reconstructed from stored graph traces when explicit per-node rows are absent or incomplete.

The redundancy threshold is 0.75 and the bottleneck threshold is 0.25. The reported redundancy density is 0.3842, mean redundancy cluster size is 1.1310, cluster density is 0.0983, mean rerouting entropy is 0.0000, mean rerouting depth is 0.0100, bottleneck count is 191, bottleneck rarity is 0.9204, and the distributedness index is 0.2976.

Mean compensation ratios are low: PRUNE 0.0084, CASCADE 0.0000, and BYPASS 0.0152. Resilience AUC values are sequential 0.4840, deterministic random 0.5098, attribution-first 0.4761, and necessity-first 0.1488. These values are consistent with the final interpretation that structural necessity is sparse and compensatory redistribution is limited.

## Stage 2 Held-Out Validation

Stage 2 is a confirmatory consistency check over stored artifacts, not a new experiment phase or method update. The verified split contains 520 Stage 1 traces and 280 Stage 2 traces. `S_high`, `S_mid`, and `S_low` form a mutually exclusive partition of Stage 2; `S_rand` is an overlapping non-adaptive audit layer.

The full Stage 2 FMA alignment is positive but low magnitude: Spearman rho is 0.1628 with a 95 percent bootstrap interval of [0.0916, 0.2347]. The effect-size label is `small`. Projection signs are positive for `pi_1` through `pi_4`, but the global claim gate requires all four strata; C1 and C2 are therefore `stratum_dependent`, not confirmed across all required strata.

Stratified generalization is not globally confirmed. C3 is `stratum_dependent` because the Stage 2 stratum audit reports confidence intervals including zero in `S_mid` and `S_rand`. This heterogeneity is reported as variation across unseen distributions, not as evidence that FMA is stronger than the low-magnitude aggregate suggests.

## Real-Task Pilot Status

The real-task pilot is a guarded extension rather than a replacement for historical Phase 5-7 evidence. The current readiness audit reports `PILOT_BLOCKED`, with failure codes `PILOT_FAIL_CONTROLS`, `PILOT_FAIL_COVERAGE`, `PILOT_FAIL_REPLAY`, `PILOT_FAIL_SIGNAL`, and `PREFLIGHT_FAIL_DRIFT`. The API preflight report has `status: fail` due to drift. Any generated GSM8K/HotpotQA pilot traces should therefore be treated as pilot evidence only, not as validated real-task support for utility claims.

The nondeterministic protocol permits trace generation only under guarded pilot framing. It requires repeated replay and bootstrap confidence intervals before any utility claim is upgraded. The trajectory-control artifact is currently marked as unmeasured skeleton output, not a completed control experiment. No manuscript section should describe the real-task pilot as top-tier-ready while these gates remain unresolved.

## Required PRM/Filtering Validation

The top-tier version must add a downstream experiment that tests whether structurally calibrated FMA signals improve process supervision or reflection filtering. The key comparison should separate:

| Method family | Required role |
|---|---|
| Vanilla PRM | Uniform or standard step-supervision baseline |
| Length-calibrated PRM | Control for length and process-bias effects |
| Token attribution | Tests whether semantic reflection-level attribution adds value beyond token-level signals |
| Heuristic reflection scoring | Tests against length, confidence, or self-consistency heuristics |
| Structurally calibrated FMA | Candidate method combining local utility with structural necessity diagnostics |

This validation is not completed in the current repository. Phase 5-7 justify the need for the experiment by showing that raw local utility can overrepresent redundant reflection.

## Figure Set

The primary paper-level result figures are `outputs/figures/structural_diagnostics_attribution_vs_necessity.png`, `outputs/figures/redundancy_density_histogram.png`, and the optional selected primary figure `outputs/figures/resilience_curves.png`. Other generated figures summarize supplementary diagnostics and are catalogued in `paper/figure_inventory.md`.

Empirical observations are the stored report values. The structural interpretation is that local utility is more widespread than structural necessity. The process-supervision implication is a required validation hypothesis: future PRM/filtering work should compare structurally calibrated attribution signals against raw local utility and heuristic reflection scores.

Human evaluation, semantic reasoning verification, benchmark superiority, external PRM/filtering comparison, and downstream statistical significance testing are not evaluated in the current framework.

No experiment in this phase modifies JSON outputs, regenerates figures as part of writing, or introduces learned models.
