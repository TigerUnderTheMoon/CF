# real_task_v3.7 PRM Baseline Contamination Audit

v3.7 is an offline audit route for a future frozen-PRM baseline comparison on the v3.6 PRM800K hash split. It does not run PRM inference, train PRMs, validate GSM8K/HotpotQA replay, or upgrade causal claims.

## Claim Scope

- Allowed: in-distribution PRM baseline context for `M_BASELINE_COMPARISON`.
- Existing positive evidence remains governed by v3.6: `M_STEP_RANKING` / `M_STEP_RANKING_REAL_PRM800K`.
- Forbidden upgrades: `F_REAL_TASK_SC_FMA`, `F_PRM_TRAINING`, deterministic replay, external PRM generalization, and causal identification.

Required wording if overlap or unknown overlap is present:

> This PRM comparison is reported as an in-distribution baseline comparison with acknowledged PRM800K overlap risk. It strengthens the baseline context for real PRM800K step-ranking, but does not establish external generalization beyond PRM800K-like process-supervision data.

## Bidirectional Contamination Audit

The route writes `training_overlap_audit.json` and `reverse_prm800k_usage_scan.csv`.

The audit checks two directions:

- Candidate-to-dataset: whether the PRM baseline under comparison used PRM800K.
- Dataset-to-ecosystem: whether PRM800K appears in public PRM or process-supervision model/benchmark provenance.

Decision rules:

- `known_yes` or `unknown` PRM800K usage blocks external-generalization language.
- `known_no` is accepted only with a primary-source URL from a model card, paper, official repo, or dataset card.
- Blog posts may provide secondary context, but they cannot independently clear overlap risk.
- Math-Shepherd is a P2 appendix candidate and does not block the v3.7 main timeline.

## Data Boundary

- Target dataset: `openai/prm800k`, `phase2_train.jsonl`.
- Source rows: v3.6 pool rows 5000-16999.
- Split: v3.6 hash-locked split.
- Labels: selected completion ratings mapped by `clip((rating + 1) / 2, 0, 1)`.
- Labels and ground-truth fields remain target-only and must not enter model features or PRM scorer input.

## Cost

No API calls or model inference are allowed in this audit route. Estimated API cost is USD `0.0`.

## Required Verification

- `python -m pytest tests/test_real_task_v3_7_prm_baseline_comparison.py -q`
- `python scripts/run_real_task_v3_7_prm_baseline_comparison.py --stage all`

The generated decision report must keep `external_generalization_claim_allowed: false` and `in_distribution_prm_baseline_context_allowed: true` whenever Qwen PRM800K or unknown-overlap PRMs are included.
