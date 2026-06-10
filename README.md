# Functional Metacognitive Attribution

Functional Metacognitive Attribution (FMA) is a diagnostic and design framework for studying reflective reasoning traces. It separates local functional utility from topology-sensitive structural necessity, then uses failed real-task and downstream routes as preliminary tests for reproducibility governance.

Current package status: `PILOT_BLOCKED`.

## Current Evidence Boundary

The KBS package is a diagnostic submission package, not a downstream performance package.

Allowed current claims:

- Phase 5-7 stored synthetic diagnostics support the distinction between widespread local utility and sparse structural necessity.
- Stage 2 provides a low-magnitude, stratum-dependent held-out diagnostic signal.
- v2.1 full stochastic validation failed preregistered gates and is abandoned under its current contract.
- The v2.1 downstream filtering mini-check failed its filtering-signal gate.
- v3 DELETE smoke failed sparse-signal gates: GSM8K `1/25`, HotpotQA `28/35`.
- v3.1 REPLACE/masked-span smoke failed sparse-signal gates: GSM8K `8/25`, HotpotQA `14/35`.

Blocked current claims:

- locked real-task validation
- downstream PRM/filtering gain
- threshold retuning after failed smoke
- mixing v3 DELETE and v3.1 rows
- any status upgrade beyond `PILOT_BLOCKED`

## Canonical Evidence Paths

The manuscript and Quarto chapter use root-level `outputs/` paths as the canonical evidence surface.

Core diagnostic files:

- `outputs/counterfactual_summary.json`
- `outputs/structural_diagnostics.json`
- `outputs/redundancy_analysis.json`
- `outputs/stage2_holdout_validation.json`
- `outputs/stage2_claim_gating_summary.md`
- `outputs/stage2_stratified_metrics.json`
- `outputs/figures/`

Real-task boundary files:

- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_failure_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_full_validation_abandonment_audit.json`
- `outputs/s_fma_v2_1_fresh_holdout/v2_1_downstream_filtering_report.json`
- `outputs/real_task_v3/qwen36_delete_hotfix_20260607/smoke_report.json`
- `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_report.json`
- `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json`

## Quick Start

```bash
pip install -e .
python -m pytest -q
```

The default test command is intentionally not a coverage gate. Use the separate coverage target when coverage is the goal:

```bash
make coverage
```

## DVC

The DVC pipeline stages are:

| Stage | Input | Output |
|---|---|---|
| `phase5` | `data/synthetic_traces.jsonl` | `outputs/phase5/` |
| `phase6` | `outputs/phase5/` | `outputs/phase6/` |
| `phase7` | `outputs/phase6/` | `outputs/phase7/` |
| `figures` | `outputs/phase7/` | `outputs/figures/` |

For the KBS package, historical Phase 5-7 evidence may be materialized from `outputs/archive/legacy/` into the root `outputs/` surface and phase directories. Do not rewrite historical reports to strengthen claims.

## Paper Package

Primary manuscript files:

- `paper/manuscript.md`
- `paper/kbs_submission/main.tex`
- `paper/kbs_submission/cover_letter.md`
- `paper/submission_readiness_audit.md`
- `paper/claim_registry.md`

Build the KBS PDF from:

```bash
cd paper/kbs_submission
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

## Citation

```bibtex
@misc{fma2026,
  title        = {Functional Metacognitive Attribution},
  author       = {Anonymous},
  year         = {2026},
  note         = {Diagnostic and design framework for local utility and structural necessity in reflective reasoning traces}
}
```
