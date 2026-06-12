# real_task_v3.5 PRM800K Real Step-Label Validation

This route is a new offline validation route for the step-importance ranking claim only. It does not revive or upgrade the failed GSM8K/HotpotQA replay routes.

## Claim Scope

- Primary claim candidate: `M_STEP_RANKING_REAL_PRM800K`.
- Existing claim that may cite this artifact after pass: `M_STEP_RANKING`.
- Forbidden upgrades: `F_REAL_TASK_SC_FMA`, `F_PRM_TRAINING`, deterministic replay, causal identification.

## Data

- Source: `openai/prm800k`, `phase2_train.jsonl`.
- Dev rows: 0-999, used only to fit and freeze `w_struct`.
- Locked rows: 3000-4999, used once for validation after the model is frozen.
- The runner streams only the configured row ranges from GitHub media and records selected-row hashes. It does not download or cache the full source file.

## Features

Labels, ratings, ground-truth answers, and any derived label fields are forbidden as features. Prediction features are limited to text, position, length, numeric/equation density, and lexical structural cues.

## Gates

Dev must pass leakage audit, minimum sample/step counts, and 5-fold positive stability. Locked validation must pass minimum sample/step counts, bootstrap CI lower bound for `w_struct - raw_local_utility` above zero, beat heuristic baselines, and Holm-corrected primary tests.

## Cost

No API calls are allowed. The only spend is network bandwidth for streaming a bounded row slice from a public dataset.
