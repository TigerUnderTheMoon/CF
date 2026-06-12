# real_task_v3.6 Hash-Stratified PRM800K Validation

v3.5 failed because a contiguous dev/locked split introduced row-order distribution drift. v3.6 preserves that failure and changes only the split design: a new, previously unused PRM800K phase2 row pool is split by deterministic SHA-256 hash into dev and locked subsets.

## Claim Scope

- Primary claim candidate: `M_STEP_RANKING_REAL_PRM800K`.
- Existing claim that may cite this artifact after pass: `M_STEP_RANKING`.
- Forbidden upgrades: `F_REAL_TASK_SC_FMA`, `F_PRM_TRAINING`, deterministic replay, causal identification.

## Data

- Source: `openai/prm800k`, `phase2_train.jsonl`.
- Pool rows: 5000-16999.
- Split: `sha256(sample_id || salt) mod 100`; values 0-49 are dev, 50-99 are locked.
- Dev labels fit and freeze `w_struct`; locked labels are used only once for validation.

## Gates

Dev must pass leakage audit, minimum counts, and 5-fold positive stability. Locked validation must pass minimum counts, bootstrap CI lower bound for `w_struct - raw_local_utility` above zero, beat heuristic baselines, and Holm-corrected primary tests.

## Cost

No API calls are allowed. The runner streams a bounded public row slice only.
