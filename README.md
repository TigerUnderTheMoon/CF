# Functional Metacognitive Attribution

This repository is a research prototype for deterministic structural analysis of reflective reasoning traces.

It is NOT:
- a production reasoning benchmark
- a mechanistic interpretability system
- a hidden-process discovery framework

## Current Manuscript Status

The repository includes a Phase 8 paperization layer under `paper/` for workshop-style manuscript preparation. The canonical research claim is:

Reflective reasoning exhibits widespread local utility, but only sparse structural necessity.

Most reflective steps are neither globally necessary nor strongly compensatory. Weak attribution-necessity alignment does not invalidate reflective utility attribution; it indicates a mismatch between local utility and topology-level indispensability.

## Phase 5-7 Core Findings

The empirical contributions are concentrated in Phase 5-7. Phase 1-4 established conceptual and infrastructural foundations.

- Phase 5 produces deterministic counterfactual functional attribution over 800 traces and 2400 reflective steps.
- Phase 6 reports weak alignment between `attribution_score` and `structural_necessity`: PRUNE 0.0753, CASCADE 0.0523, BYPASS 0.0917.
- Phase 6 also reports a 67.79 percent zero structural necessity rate.
- Phase 7 reports redundancy density 0.3842, distributedness index 0.2976, bottleneck count 191, and weak mean compensation ratios.

The framework evaluates structural properties of reflective reasoning traces, not downstream benchmark performance.

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

The new pilot-only artifacts are stored under `outputs/real_task_pilot/`. They do not rewrite historical synthetic outputs.

## Citation Placeholder

TODO: manual bibliography completion

```bibtex
@misc{fma_placeholder,
  title = {Functional Metacognitive Attribution: Deterministic Structural Analysis of Reflective Reasoning Traces},
  author = {Anonymous},
  year = {2026},
  note = {Workshop submission placeholder}
}
```
