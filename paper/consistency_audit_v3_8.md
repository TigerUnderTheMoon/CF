# v3.8 Consistency Audit

Audit date: 2026-06-12
Repository: `D:\CF`
Scope: claim/evidence consistency for v3.6 PRM800K step-ranking, v3.7 PRM800K overlap audit, v3.8 frozen PRM locked scoring, manuscript-facing Markdown, public docs, and the KBS submission package.

## Verdict

Status: **PASS_FINAL_PACKAGE_SOURCE_AND_PDF**.

Root-level status documents are internally consistent with the v3.6/v3.7/v3.8 artifact boundary. The KBS package source files and tracked `paper/kbs_submission/main.pdf` have been synchronized to remove positive GSM8K/HotpotQA downstream filtering claims and to report v3.6/v3.8 PRM800K evidence under the correct boundaries. The final tracked PDF was rebuilt from the synchronized source and passed the claim-safety text scan.

No new experiment, API call, AutoDL run, or claim upgrade was performed for this audit.

## Source of Truth

| Route | Artifact | Status | Allowed claim | Forbidden claim |
|---|---|---|---|---|
| v3.6 PRM800K hash split | `outputs/real_task_v3_6_prm800k_hash/decision_report.json` | `pass` | `M_STEP_RANKING`; `M_STEP_RANKING_REAL_PRM800K` | `F_PRM_TRAINING`; `F_REAL_TASK_SC_FMA`; deterministic replay; causal identification |
| v3.7 PRM baseline audit | `outputs/real_task_v3_7_prm_baseline_comparison/decision_report.json` | `pass_with_in_distribution_limitation` | in-distribution PRM baseline context | external PRM generalization; broad public-PRM superiority; PRM training; GSM8K/HotpotQA replay |
| v3.8 frozen PRM scoring | `outputs/real_task_v3_8_prm_locked_scoring/decision_report.json` | `pass_strong` | `M_BASELINE_COMPARISON_CONTEXT_ONLY` | broad `M_BASELINE_COMPARISON`; `F_PRM_TRAINING`; `F_REAL_TASK_SC_FMA`; external PRM generalization; deterministic replay; causal identification |

Canonical metrics:

| Evidence | Samples | Steps | Primary metric | CI / correction | Cost |
|---|---:|---:|---|---|---:|
| v3.6 `w_struct` vs raw/heuristics | 4417 | 34219 | `w_struct` Spearman `0.6113401179642559`; raw local utility Spearman `-0.07745914322519368` | `w_struct - raw` CI `[0.6732614322543506, 0.7045869106196779]`; Holm pass | USD `0.0` |
| v3.8 `w_struct` vs frozen PRM prefix score | 4417 | 34219 | frozen PRM Spearman `0.2515662235547571`; `w_struct` Spearman `0.6113401179642559` | `w_struct - prm` CI `[0.34499208448462026, 0.3745467544914783]`; Holm pass | USD `0.0` |

The v3.8 PRM score semantics are `prefix_sequence_reward_probability`: step `k` is scored by the sequence reward for the question plus the first `k` steps. It must not be described as token-level PRM logits.

## Scan Scope

Contract sources:

- `paper/claim_registry.md`
- `paper/submission_readiness_audit.md`
- `outputs/real_task_v3_6_prm800k_hash/decision_report.json`
- `outputs/real_task_v3_7_prm_baseline_comparison/decision_report.json`
- `outputs/real_task_v3_8_prm_locked_scoring/decision_report.json`

Manuscript and public surfaces:

- `paper/abstract.md`
- `paper/manuscript.md`
- `paper/introduction.md`
- `paper/experiments.md`
- `paper/results.md`
- `paper/limitations.md`
- `paper/conclusion.md`
- `paper/terminology.md`
- `README.md`
- `PLANS.md`
- `docs/interpretation_and_limitations.md`

KBS package surfaces:

- `paper/kbs_submission/main.tex`
- `paper/kbs_submission/main.pdf`
- `paper/kbs_submission/cover_letter.md`
- `paper/kbs_submission/supplementary_materials.md`
- `paper/kbs_submission/supplementary/supplementary_manifest.md`

## Findings

| ID | Priority | Category | Location | Finding | Required action |
|---|---|---|---|---|---|
| CAV38-001 | REMEDIATED | empirical evidence | `paper/kbs_submission/main.tex`; `paper/kbs_submission/main.pdf` | The data-split caption previously said GSM8K and HotpotQA provide "real-data downstream evidence." | Replaced with PRM800K step-ranking evidence and failed/blocked GSM8K/HotpotQA provenance in source and rebuilt PDF. |
| CAV38-002 | REMEDIATED | empirical evidence | `paper/kbs_submission/main.tex`; `paper/kbs_submission/main.pdf` | The package previously reported a positive "Downstream Filtering on Real Data" result with GSM8K filtering accuracy and a calibrated filtering signal. | Replaced the section with PRM800K step-ranking and in-distribution frozen PRM baseline context; rebuilt PDF no longer contains the forbidden section title. |
| CAV38-003 | REMEDIATED | empirical evidence | `paper/kbs_submission/main.tex`; `paper/kbs_submission/main.pdf` | The package previously said the GSM8K filtering result provides positive real-data evidence. | Replaced with the boundary that no passing GSM8K/HotpotQA replay or downstream filtering validation is currently available. |
| CAV38-004 | REMEDIATED | reproducibility / package consistency | `paper/kbs_submission/main.tex`; `paper/kbs_submission/main.pdf` | Data/code availability previously described GSM8K and HotpotQA downstream filtering data as part of the current protocol. | Replaced with v3.6/v3.8 PRM800K artifacts as current real-data evidence; GSM8K/HotpotQA task-specific replay and downstream filtering described as not completed. |
| CAV38-005 | REMEDIATED | package synchronization | `paper/kbs_submission/cover_letter.md` | The cover letter omitted the later v3.6 PRM800K pass and v3.8 overlap-limited PRM baseline context. | Added v3.6/v3.8 strict context-only wording. |
| CAV38-006 | REMEDIATED | supplementary synchronization | `paper/kbs_submission/supplementary_materials.md`; `paper/kbs_submission/supplementary/supplementary_manifest.md` | The supplement omitted v3.6/v3.8 positive PRM800K evidence. | Added v3.6/v3.7/v3.8 evidence entries without upgrading replay/filtering or PRM-training claims. |
| CAV38-007 | REMEDIATED | wording precision | `paper/kbs_submission/main.tex`; `paper/kbs_submission/main.pdf` | "actionable process supervision" and "practical deployment" could be read as downstream validation. | Softened to "process-supervision-oriented analysis" and "auditable implementation" in the KBS package and rebuilt PDF. |
| CAV38-008 | REMEDIATED | terminology | `paper/kbs_submission/main.tex`; `paper/kbs_submission/main.pdf` | "step importance ranking, a downstream task" could be confused with downstream PRM/filtering validation. | Replaced with "an evaluation task" in the KBS package and rebuilt PDF. |
| CAV38-009 | PASS | root status contract | `paper/claim_registry.md`; `paper/submission_readiness_audit.md`; `README.md`; `PLANS.md`; `docs/interpretation_and_limitations.md` | Root status documents consistently state that v3.6 supports real PRM800K step-ranking only and v3.8 supports in-distribution frozen PRM baseline context only. | No immediate change required. |

## Claim Permission Check

The v3.7 and v3.8 `decision_report.json` files both keep the following boundaries:

- `F_PRM_TRAINING: false`
- `F_REAL_TASK_SC_FMA: false`
- `external_generalization_claim_allowed: false`
- `deterministic_replay_claim: false`
- `causal_identification_claim: false`
- `M_BASELINE_COMPARISON: false`
- `M_BASELINE_COMPARISON_CONTEXT_ONLY: true`
- `in_distribution_prm_baseline_context_allowed: true`

The v3.6 `decision_report.json` permits only `M_STEP_RANKING` and `M_STEP_RANKING_REAL_PRM800K`.

## Safe Wording Template

Use this wording for v3.8:

> This PRM comparison is reported as an in-distribution baseline comparison with acknowledged PRM800K overlap risk. It strengthens the baseline context for real PRM800K step-ranking, but does not establish external generalization beyond PRM800K-like process-supervision data.

Use this wording for the synchronized submission package:

> The current positive real-data evidence is limited to PRM800K step-label ranking and an in-distribution frozen PRM baseline comparison. GSM8K/HotpotQA task-specific replay and downstream filtering/training were not completed and are reported only as future validation targets.

## Reviewer Risk Register

| ID | Priority | Category | Reviewer concern | Evidence | Severity | Probability | Fix effort | Recommended action |
|---|---|---|---|---|---|---|---|---|
| RSK-001 | remediated | empirical evidence | Reviewer could say the paper claims positive GSM8K filtering even though current artifacts say downstream filtering failed. | CAV38-001 to CAV38-004 | fatal before fix | low after fix | completed | KBS source and PDF now report GSM8K/HotpotQA task-specific replay/filtering as not completed; PRM800K step-ranking and frozen PRM baseline are presented as positive evidence. |
| RSK-002 | remediated | reproducibility | Reviewer could say the submitted LaTeX package and root claim registry disagree on what the real-data evidence supports. | KBS package vs `paper/submission_readiness_audit.md` | fatal before fix | low after fix | completed | KBS source, PDF, cover letter, and supplement now use the v3.6/v3.8 evidence boundary. |
| RSK-003 | remediated | clarity | Reviewer could read "actionable process supervision" as a PRM training or deployment claim. | CAV38-007 | medium before fix | low after fix | completed | KBS wording was softened. |
| RSK-004 | remediated | package completeness | Reviewer could miss the v3.6/v3.8 positive PRM800K evidence because supplementary package only lists failed routes. | CAV38-005 and CAV38-006 | medium before fix | low after fix | completed | Supplementary package metadata now includes v3.6/v3.8 context-only evidence. |

## Final Package State

The tracked KBS PDF has been updated from the synchronized source. The final package synchronization completed these required actions:

1. Removed or rewrote the positive GSM8K downstream filtering section.
2. Added v3.6 PRM800K step-ranking evidence.
3. Added v3.8 in-distribution frozen PRM baseline context evidence.
4. Kept PRM training, GSM8K/HotpotQA replay, deterministic replay, and external PRM generalization explicitly forbidden.
5. Rebuilt and verified the tracked LaTeX PDF after text synchronization.

## Package Sync Result

Sync date: 2026-06-12

Status: **P0 remediated in KBS source package and tracked PDF**.

Source changes:

- `paper/kbs_submission/main.tex`: removed the positive "Downstream Filtering on Real Data" section, removed the GSM8K filtering accuracy table and figure reference, added v3.6 PRM800K step-ranking evidence, added v3.8 in-distribution frozen PRM baseline context, and described GSM8K/HotpotQA task-specific replay plus downstream filtering as not completed.
- `paper/kbs_submission/cover_letter.md`: added the v3.6/v3.8 evidence boundary and explicitly excluded PRM training, replay validation, downstream filtering, causal identification, and claims beyond PRM800K-like process-supervision data.
- `paper/kbs_submission/supplementary_materials.md` and `paper/kbs_submission/supplementary/supplementary_manifest.md`: added PRM800K evidence entries while preserving v2/v3 failed-route provenance.
- LaTeX auxiliary caches under `paper/kbs_submission/` were refreshed by the final tracked PDF build so directory-level claim scans no longer report stale cached downstream claims.

Resolved findings:

- CAV38-001: resolved in `main.tex` data composition caption and rows.
- CAV38-002: resolved by replacing the downstream filtering subsection with PRM800K step-ranking and frozen PRM baseline context.
- CAV38-003: resolved in Discussion and Scope/Limitations.
- CAV38-004: resolved in Data and code availability.
- CAV38-005: resolved in the cover letter.
- CAV38-006: resolved in supplementary materials and manifest.

Remaining item:

- No P0/P1 claim-boundary blocker remains in the KBS source package or tracked PDF. Production color-space requirements for retained PNG assets remain a separate format-check item.

Verification results:

- Claim scan: no matches in `paper/kbs_submission` source/PDF for forbidden positive downstream wording; remaining matches are only historical/forbidden-boundary text in this audit report.
- Claim permission check: `permission_check_ok` for v3.7 and v3.8 decision artifacts.
- Targeted regression: `10 passed in 10.98s`.
- Full regression: `477 passed, 1 deselected in 65.94s`.
- Final tracked PDF build: `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` passed with TeX Live, output `paper/kbs_submission/main.pdf` (37 pages, 630071 bytes).
- PDF text scan: no forbidden positive downstream/replay/PRM-training/generalization wording found; PRM800K step-ranking and frozen PRM baseline context wording is present.
- Hygiene: `git diff --check` passed; Git reported CRLF conversion warnings only.

No API calls, AutoDL runs, or new experiments were performed.
