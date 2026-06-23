# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Functional Metacognitive Attribution (FMA) / SC-FMA: a research package studying reflective reasoning traces via intervention-based *functional attribution* (not causal identification). The active contribution is **SC-FMA** — a structural-calibration methodology that turns local interventional utility (CIU) into supervision weights via convex constrained optimization.

**Framing rule:** describe work as "intervention-based functional attribution for reflective cognition dynamics." Never frame as full causal identification, generic PRM tuning, token attribution, or heuristic reflection scoring. See `AGENTS.md` §1, §6.4 for forbidden terminology.

## Commands

```bash
# Install (poetry is the canonical env manager; pip install -e . also works)
poetry install                # or: pip install -e .
poetry install --extras ml    # torch/transformers/datasets/openai for pilot + PRM scoring

# Tests — default run is NOT a coverage gate (skips slow + regression markers)
python -m pytest -q
poetry run pytest -m "not slow"          # CI's exact invocation
python -m pytest tests/test_ranking.py   # single file
python -m pytest tests/test_ranking.py::test_name   # single test
python -m pytest -m regression           # historical hash/snapshot tests (CI-only)
python -m pytest -m slow                 # live-API/expensive tests, skipped by default

# Coverage gates
make coverage                             # overall, fails under 80%
poetry run coverage report --include="src/fma/graph/*" --fail-under=90   # CI graph gate

# Lint / format / type
python -m ruff check .
python -m black --check .
python -m mypy

# DVC pipeline (synthetic Phase 5→6→7→figures)
dvc repro                  # or individual stages: dvc repro phase5

# Build the KBS PDF
cd paper/kbs_submission/final_source && latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
```

`pytest.ini` sets `pythonpath = src, .` and `addopts = -m "not slow and not regression"`. `tests/_archived/` is excluded from collection. Configs are Hydra/OmegaConf-style under `configs/` (composed via `fma run` / `fma run-pilot`); pipeline stages live in `configs/phase{5,6,7}/`.

## The claim-governance system (read before editing prose, paper, or outputs)

This repo enforces a **claim registry contract** — the most important non-obvious convention. Claims about what the evidence shows are gated by status labels, and a scanner enforces them in CI.

- **`paper/claim_registry.md`** is the source of truth for every claim, its status (`supported`, `stratum_dependent`, `pilot_blocked`, `failed_validation`, `archived`, `future_validation`), the artifact that owns it, and explicitly listed *allowed* vs *blocked* wording. Status can only change via documented Upgrade Rules in that file.
- **`scripts/check_claim_boundaries.py`** (tested by `tests/test_claim_boundaries.py`) scans active `.md`/`.tex`/`.yml` files plus root `README.md`/`AGENTS.md`/`dvc.*` for `FORBIDDEN_PATTERNS` (e.g. "true causal effect", "external generalization", "deployed KBS validation"). Negated uses are allowed; positive assertions are blocked. There is a separate GitHub workflow `.github/workflows/audit-check.yml`.
- **Current evidence boundary** (see README §"Current Evidence Boundary"): only PRM800K real step-label ranking (v3.6, `M_STEP_RANKING`) and in-distribution frozen-PRM baseline context (v3.8, `M_BASELINE_COMPARISON_CONTEXT_ONLY`) pass. All GSM8K/HotpotQA real-task routes (v2, v2.1, v2.2, v3, v3.1) failed or are `PILOT_BLOCKED`. **Do not** rewrite historical reports to strengthen claims, upgrade a route's status without new passing evidence, or describe PRM800K step-ranking as GSM8K/HotpotQA replay validation.
- `paper/manuscript.md` is a **superseded pointer**, not the active manuscript. The active manuscript is `paper/kbs_submission/final_source/manuscript.tex`.

When editing any markdown/latex/yaml in the repo, assume the boundary scanner will run on it.

## Code architecture

Source lives under `src/fma/` (import path `fma.*`, configured in `pyproject.toml`). **AGENTS.md is the authoritative architecture doc** — it documents both the implemented modules and, critically, the gap between the *planned ABC interface architecture* (Sections 3–4) and the *actual running pipeline*. Key points:

- The **planned ABC contracts** (`Intervention`, `ConditionalDistribution`, `UtilityEstimator`, `Matcher`, `DoublyRobustEstimator`, `FMAAggregator`) are largely **not implemented** — see AGENTS.md §2.2/§2.4 for the gap table. `fma/conditional/`, `fma/matching/`, `fma/dr/` do not exist. Do not describe these as completed evidence. Replacement currently uses random template swap (a labeled proxy deviation), and CIU is a raw outcome difference, not DR-corrected.
- The **actual operational pipeline** is deterministic scripts, not the ABCs (AGENTS.md §2.3):
  - Phase 5: `scripts/run_counterfactual_attribution.py` → `fma/eval/counterfactual_attribution.py`
  - Phase 6: `scripts/run_structural_attribution.py` → `fma/graph/`
  - Phase 7: `scripts/run_redundancy_analysis.py` → `fma/eval/redundancy/`
  - Real-task pilot / validation: `scripts/run_real_task_v3_*.py`, `scripts/run_s_fma_v2_*.py` → `fma/real_task_pilot/`, `fma/pilot/`
- Implemented subsystems that AGENTS.md once marked "planned": `fma/data/` (PRM800K, ProcessBench, GSM8K CoT loaders + normalizer), `fma/prm/` (frozen Qwen2.5-Math-PRM / Math-Shepherd / RLVR-PRM inference only), `fma/utility/` (filtering A/B + FMA-vs-PRM-vs-baseline comparison), `fma/calibration/` (the SC-FMA convex optimizer — the core methodological contribution; tested by `tests/test_calibration_guarantees.py`).
- CLI entry points (pyproject `[tool.poetry.scripts]`): `fma` → `fma.cli:main` (subcommands `run`, `run-pilot`, `run-phase5`, `run-phase6`, `clean-outputs`, `audit`), and `fma-structural-diagnostics` → `fma.graph.diagnostics:main`.
- All experiments are config-driven (OmegaConf/Hydra). See AGENTS.md §5 for the schema. Interventions must preserve token length, positional structure, and autoregressive consistency (AGENTS.md §6.1) — never naive span deletion.

## Output layout & data provenance

- **`outputs/`** is the canonical evidence surface (root-level paths are referenced by the manuscript and Quarto chapter). `outputs/archive/legacy/` holds historical Phase 5–7 synthetic evidence that may be materialized into root `outputs/` but must not be rewritten. Failed pilot routes live under `outputs/archive/s_fma_v2_*/`.
- `fma clean-outputs` archives legacy/failed outputs (preserves `outputs/phase{5,6,7}` with `--keep-core`).
- Data is DVC-tracked (`data/`, `data.dvc`). The current KBS calibration benchmark uses **200 synthetic traces / 1,027 steps**; earlier Phase 5–7 synthetic diagnostics (800 traces / 2,400 steps) are retained as *historical* evidence and must not be merged into current ranking-benchmark counts.
- Every run should save config snapshot, git hash, seed, model version, intervention/matching/DR stats (AGENTS.md §8).
