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

The current real-task pilot failed the primary rank-signal gate and is frozen as a development failure audit. `s_FMA_v2` is planned as a fresh-holdout route only; fresh holdout required before any v2 claim upgrade, and no PRM claim yet is allowed.

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

The frozen failure audit is `outputs/real_task_pilot/primary_signal_failure_audit.md` with structured companion `outputs/real_task_pilot/primary_signal_failure_audit.json`. The planned `s_FMA_v2` route is documented in `paper/s_fma_v2_fresh_holdout_plan.md` and `configs/s_fma_v2_fresh_holdout.yaml`; it must use fresh non-overlapping GSM8K and HotpotQA holdouts with formula hash `sha256:6971b23562be690e5fd58dc4dfbbcf972d2137c719b1b68a440d9ec4a216b628`. A task-specific pass permits only task-specific or heterogeneous wording. Scale expansion is not allowed until `GLOBAL_S_FMA_V2_PASS`, and PRM/filtering superiority is not allowed until a later separate downstream validation.

## Reference Anchors

- Reflexion: Shinn et al. (2023), "Reflexion: Language Agents with Verbal Reinforcement Learning."
- Self-Refine: Madaan et al. (2023), "Self-Refine: Iterative Refinement with Self-Feedback."
- Process supervision / PRM: Lightman et al. (2023), "Let's Verify Step by Step."
