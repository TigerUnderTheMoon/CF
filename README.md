# Functional Metacognitive Attribution

This repository is a research prototype for Functional Metacognitive Attribution (FMA): an intervention-based framework for learning reflection utility signals that may later support attribution-aware process supervision and PRM/filtering.

It is NOT:
- a production reasoning benchmark
- a mechanistic interpretability system
- a hidden-process discovery framework

## Current Manuscript Status

Status source rule: current readiness is derived from `outputs/real_task_pilot/readiness_audit.json`, `paper/submission_readiness_audit.md`, and `paper/claim_registry.md`. Proposal text is not evidence.

The repository includes a Phase 8 paperization layer under `paper/`. The target journal storyline follows the Chinese framework in `D:/Desktop/论文框架_中文版.pdf`: FMA is proposed as a reflection utility learning framework for process supervision, while the current repository evidence supplies the diagnostic core that prevents naive supervision weighting.

Current completed evidence supports this claim:

Reflective reasoning exhibits widespread local utility, but only sparse structural necessity.

The key manuscript turn is that local FMA-style utility cannot be used directly as a PRM supervision weight. Phase 5-7 show that many locally useful reflective steps are structurally redundant or structurally inert, so downstream supervision/filtering must be constrained by structural necessity, sparse bottlenecks, redundancy, and weak compensation diagnostics.

The current state is not a completed top-tier PRM/filtering result. Real-task replay is still pilot evidence, readiness is `PILOT_BLOCKED`, and attribution-aware PRM/filtering remains a required downstream validation experiment.

The current real-task pilot failed the primary rank-signal gate and is frozen as a development failure audit. `s_FMA_v2` remains a fresh-holdout validation route, but the guarded live API preflight-only run reports `PREFLIGHT_FAIL_DRIFT`, the first approved 20-row stochastic smoke reported `STOCHASTIC_SMOKE_FAIL_GENERATION`, and the bounded rerun reports `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`. The smoke generation failure audit is stored at `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_generation_failure_audit.md` and `.json`; the approved rerun consumed `3.14542` USD within the `5` USD ceiling, produced 60/60 successful replay results, but had `nonzero_delta_rows: 0`. The approved `s_FMA_v2.1` API_PREFLIGHT_ONLY rerun at `outputs/s_fma_v2_1_fresh_holdout/api_preflight_report.json` remains failed: status `PREFLIGHT_FAIL_DRIFT`, 20 records, 23 API attempts, cost `0.86245`, JSON/schema/tag/final-answer success rates all `1.0`, 20 valid trace rows, and 23/23 non-empty `raw_output` attempts. The active preflight blockers are drift and missing metadata, not empty extracted output or schema transport. The latest bounded v2.1 stochastic smoke rerun at `outputs/s_fma_v2_1_fresh_holdout/stochastic_smoke_report.json` reports `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST`: JSON/schema/tag/final-answer success rates are all `1.0`, replay success rate is `1.0`, and nonzero Delta-U counts are 20 pooled, 7 GSM8K, and 13 HotpotQA. This permits only a request-only pilot stochastic budget package. It is not validation evidence, rank-signal evidence, a task/global pass, deterministic replay evidence, or a PRM/filtering result. Current status remains `PILOT_BLOCKED`.

The request-only v2.1 pilot stochastic budget package is now stored at `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_approval_request.md` and `.json`. It requests `V2_1_PILOT_STOCHASTIC_VALIDATION_ONLY` with 100 total records, GSM8K 50 plus HotpotQA 50, 3 stochastic repeats per eligible span, a USD 40 budget ceiling recommendation, and a 700-request cap, but it remains `REQUEST_ONLY_NOT_APPROVED` and authorizes no API, pilot run, replay, scoring, full validation, pass wording, or PRM/filtering.

## Phase 5-7 Core Findings

The empirical contributions currently completed are concentrated in Phase 5-7. Phase 1-4 established conceptual and infrastructural foundations.

- Phase 5 produces deterministic counterfactual functional attribution over 800 traces and 2400 reflective steps.
- Phase 6 reports weak alignment between `attribution_score` and `structural_necessity`: PRUNE 0.0753, CASCADE 0.0523, BYPASS 0.0917.
- Phase 6 also reports a 67.79 percent zero structural necessity rate.
- Phase 7 reports redundancy density 0.3842, distributedness index 0.2976, bottleneck count 191, and weak mean compensation ratios.

These diagnostics explain why the target architecture must distinguish local utility from structural necessity. They do not establish downstream task gains for attribution-aware PRM/filtering.

## Target Storyline

The intended journal narrative has three layers:

1. FMA proposes a structure-preserving, distribution-conditioned way to estimate reflection utility from observable reasoning traces.
2. Phase 5-7 reveal the central diagnostic finding: local utility is widespread, but sparse structural necessity is the safer constraint for supervision and filtering.
3. A top-tier version must add real PRM/filtering validation testing structurally calibrated attribution signals against vanilla PRM, length-calibrated PRM, token attribution, and heuristic reflection scoring baselines.

Until that final layer exists as real artifacts, PRM/filtering claims remain future validation requirements rather than completed evidence.

## Paper Directory

- `paper/abstract.md`
- `paper/introduction.md`
- `paper/related_work.md`
- `paper/methodology.md`
- `paper/experiments.md`
- `paper/results.md`
- `paper/limitations.md`
- `paper/conclusion.md`
- `paper/appendix.md`
- `paper/reproducibility.md`
- `paper/terminology.md`
- `paper/figure_inventory.md`
- `paper/paper_outline.md`
- `paper/claim_registry.md`
- `paper/submission_readiness_audit.md`
- `paper/s_fma_v2_fresh_holdout_plan.md`
- `paper/s_fma_v2_1_evidence_target_revision.md`

## Reproduction Commands

Run tests:

```powershell
python -m pytest -q
```

Run the guarded real-task pilot checks without live API spend:

```powershell
python scripts/run_real_task_pilot.py --stage hygiene
python scripts/run_real_task_pilot.py --stage preflight-eval --input tests/fixtures/real_task_traces.jsonl
python scripts/run_real_task_pilot.py --stage replay-prefixes --input tests/fixtures/real_task_traces.jsonl
python scripts/run_real_task_pilot.py --stage delta-u --input tests/fixtures/real_task_traces.jsonl --intervened-input tests/fixtures/intervened_traces.jsonl
python scripts/run_real_task_pilot.py --stage baselines --input tests/fixtures/real_task_traces.jsonl
python scripts/run_real_task_pilot.py --stage controls --input tests/fixtures/real_task_traces.jsonl
python scripts/run_real_task_pilot.py --stage readiness --input tests/fixtures/real_task_traces.jsonl --tests-passed
```

Live API preflight and pilot execution are intentionally guarded and must use a real-data manifest, not fixtures:

```powershell
python scripts/run_real_task_pilot.py --stage export-data
python scripts/run_real_task_pilot.py --stage manifest --gsm8k-input data/real_task_pilot/gsm8k_test.jsonl --hotpotqa-input data/real_task_pilot/hotpotqa_validation.jsonl
python scripts/run_real_task_pilot.py --stage api-preflight --input outputs/real_task_pilot/sample_manifest.json --allow-api
python scripts/run_real_task_pilot.py --stage seed-probe --input outputs/real_task_pilot/sample_manifest.json --allow-api
python scripts/run_real_task_pilot.py --stage protocol-revision --input outputs/real_task_pilot/sample_manifest.json
python scripts/run_real_task_pilot.py --stage api-pilot --input outputs/real_task_pilot/sample_manifest.json --allow-api
```

The deterministic 400-trace pilot must not start until `outputs/real_task_pilot/api_preflight_report.json` has `status: pass`. If seed transport is unavailable, `protocol-revision` writes `api_determinism_blocker.json` and a preregistered non-deterministic repeated-estimation protocol; that protocol permits trace generation only as pilot evidence and requires repeated replay plus bootstrap confidence intervals before any utility claim is upgraded.

Regenerate structural diagnostics:

```powershell
python scripts/run_structural_diagnostics.py
```

Regenerate redundancy and compensation analysis:

```powershell
python scripts/run_redundancy_analysis.py
```

## Expected Outputs

Primary outputs are stored in `outputs/`, with figures under `outputs/figures/`. The main paper evidence comes from `outputs/counterfactual_summary.json`, `outputs/structural_diagnostics.json`, `outputs/structural_diagnostics.md`, `outputs/redundancy_analysis.json`, and `outputs/redundancy_analysis.md`.

The new pilot-only artifacts are stored under `outputs/real_task_pilot/`. They do not rewrite historical synthetic outputs. As of the current readiness audit, `outputs/real_task_pilot/readiness_audit.json` reports `PILOT_BLOCKED`, and `outputs/real_task_pilot/api_preflight_report.json` reports `PREFLIGHT_FAIL_DRIFT`.

The current pilot blockers are that the primary signal is available but failed the rank-signal gate, and API determinism drift remains. Replay, Delta-U, rank-signal coverage, baseline leakage, and readiness-level trajectory-control gates now pass; the real-task candidate score remains pilot diagnostic evidence, not scale-ready support or PRM/filtering validation.

The frozen failure audit is `outputs/real_task_pilot/primary_signal_failure_audit.md` with structured companion `outputs/real_task_pilot/primary_signal_failure_audit.json`. The planned `s_FMA_v2` route is documented in `paper/s_fma_v2_fresh_holdout_plan.md` and `configs/s_fma_v2_fresh_holdout.yaml`; `outputs/s_fma_v2_fresh_holdout/manifest_overlap_audit.json` reports `MANIFEST_OVERLAP_CLEAN`, the fresh-holdout live API preflight-only report reports `PREFLIGHT_FAIL_DRIFT` after 20 evaluated records, and the first approved smoke produced the generation failure audit at `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_generation_failure_audit.md` and `.json`. The bounded rerun approval package is stored at `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_rerun_approval_request.md` and `.json`; the approved rerun updated `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_report.json` to `STOCHASTIC_SMOKE_FAIL_SPARSE_SIGNAL`, with 20 smoke samples, 60/60 successful replay results, `nonzero_delta_rows: 0`, and `cost_used_usd: 3.14542`. The planned `s_FMA_v2.1` revision is documented in `paper/s_fma_v2_1_evidence_target_revision.md` and `configs/s_fma_v2_1_fresh_holdout.yaml`; the regenerated package under `outputs/s_fma_v2_1_fresh_holdout/` contains 400 fresh selected rows, `MANIFEST_OVERLAP_CLEAN` with zero selected overlap on all six required keys, `V2_1_CONTRACT_CLEAN`, and request-only API preflight approval files locked to prompt hash `prompt-sha256:e5ac816bc586ee33a2800fbd0c373523154e0c4eeef74cdd349fa70271054a4b`. The approved v2.1 API_PREFLIGHT_ONLY rerun rewrote only `api_preflight_report.json`, `api_preflight_attempts.jsonl`, `api_preflight_traces.jsonl`, and `logs/api_preflight_cost_report.json`; it remains `PREFLIGHT_FAIL_DRIFT` after 20 evaluated records and 23 attempts, with cost `0.86245`, JSON/schema/tag/final-answer success `1.0`, 20 valid trace rows, and 23/23 non-empty `raw_output` attempts. The latest bounded v2.1 stochastic smoke rerun wrote the smoke artifacts under `outputs/s_fma_v2_1_fresh_holdout/` and reports `V2_1_STOCHASTIC_SMOKE_FEASIBLE_FOR_PILOT_REQUEST`, with 140 API attempts, cost `6.11314`, JSON/schema/tag/final-answer success `1.0`, replay success rate `1.0`, 40 Delta-U rows, and nonzero Delta-U counts of 20 pooled, 7 GSM8K, and 13 HotpotQA. These are smoke diagnostics only and permit only a request-only pilot stochastic budget package. No full generation, no 400 fresh validation, no rank-signal validation, no task/global pass, no deterministic replay claim, no v2.1 pilot execution, no full validation, and no PRM claim are allowed from these results. Current status remains `PILOT_BLOCKED`.

The corresponding request-only v2.1 pilot stochastic budget artifacts are `outputs/s_fma_v2_1_fresh_holdout/v2_1_pilot_stochastic_approval_request.md` and `.json`; they are not execution artifacts and leave `PILOT_BLOCKED` unchanged.

## Reference Anchors

- Reflexion: Shinn et al. (2023), "Reflexion: Language Agents with Verbal Reinforcement Learning."
- Self-Refine: Madaan et al. (2023), "Self-Refine: Iterative Refinement with Self-Feedback."
- Process supervision / PRM: Lightman et al. (2023), "Let's Verify Step by Step."
