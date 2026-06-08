# v3.1 REPLACE Preregistration and Result

## Purpose

This document preregisters and freezes the v3.1 REPLACE fallback route after the v3 DELETE smoke failed sparse-signal gates. The route is not a post-hoc pass attempt. It tests whether a stronger reflection-span intervention can create sufficient Delta-U variation on GSM8K and HotpotQA while preserving the same claim boundary.

Current project status remains `PILOT_BLOCKED`.

## v3 DELETE Trigger

The v3 DELETE smoke artifact is:

- `outputs/real_task_v3/qwen36_delete_hotfix_20260607/smoke_report.json`

Stored result:

| Metric | Observed | Gate |
|---|---:|---:|
| Valid traces | 199 total; GSM8K 100; HotpotQA 99 | 95 per task |
| Eligible spans | 597 | 150 pooled |
| GSM8K nonzero Delta-U | 1 | 25 |
| HotpotQA nonzero Delta-U | 28 | 35 |
| Transport success rate | 0.9964947421131698 | 0.95 |

The DELETE smoke passed transport and trace-count gates, but failed both sparse-signal gates. DELETE evidence is failure provenance only and cannot be mixed with v3.1 evidence.

## v3.1 Hypothesis

The v3.1 route tests a REPLACE-style intervention: reflection-span content is replaced with `[REASONING_MASK]` and replay instructs the model to continue without the masked information. The intended contract is stronger than DELETE while retaining span position and structure.

Preregistered constraints:

- Use only `qwen3.6-plus` data for this route.
- Keep smoke gates fixed: 95 valid traces per task, 25 GSM8K nonzero Delta-U, 35 HotpotQA nonzero Delta-U, and 150 pooled eligible spans.
- Do not tune thresholds after seeing smoke results.
- Do not pool DELETE and REPLACE rows.
- Do not use smoke failure data for `w_struct` fitting, locked validation, or downstream PRM/filtering claims.

## Required Artifacts

| Artifact | Path |
|---|---|
| Preregistration plan | `paper/real_task_v3_1_preregistration_plan.md` |
| Config | `configs/real_task_v3_1_validation.yaml` |
| Smoke runner | `scripts/run_real_task_v3_1_smoke.py` |
| Replay prompt | `prompts/real_task_v3_1_replay.txt` |
| Smoke output directory | `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/` |
| Smoke report | `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_report.json` |
| Delta-U rows | `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/smoke_delta_u.jsonl` |
| Companion consistency audit | `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json` |

## Decision Tree

```text
v3.1 REPLACE smoke
  FAIL transport or trace-count gates
    -> STOP_AND_FIX_GENERATION
  FAIL sparse signal in GSM8K or HotpotQA
    -> STOP. Neither DELETE nor REPLACE produces sufficient signal under
       the current model/protocol. Manuscript reports negative boundary
       evidence. No further intervention tuning is allowed under this
       preregistration.
  PASS all smoke gates
    -> Request separately approved dev calibration and locked validation.
```

## Execution Result

The v3.1 smoke output directory is:

- `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/`

Stored result:

| Metric | v3 DELETE | v3.1 REPLACE | Gate | Pass |
|---|---:|---:|---:|---|
| Valid traces | 199 total; GSM8K 100; HotpotQA 99 | 196 total; GSM8K 99; HotpotQA 97 | 95 per task | true |
| Eligible spans | 597 | 588 | 150 pooled | true |
| GSM8K nonzero Delta-U | 1 | 8 | 25 | false |
| HotpotQA nonzero Delta-U | 28 | 14 | 35 | false |
| Transport success rate | 0.9964947421131698 | 0.9979633401221996 | 0.95 | true |

Raw v3.1 smoke status: `V3_1_SMOKE_FAIL_SPARSE_SIGNAL_GSM8K`.

Audited status summary: `V3_1_SMOKE_FAIL_SPARSE_SIGNAL_GSM8K_AND_HOTPOTQA`.

## Consistency Audit

The companion audit records three claim-relevant inconsistencies in the raw v3.1 smoke report:

- The report records `intervention_type=REPLACE` but `intervention_implementation=length_preserving_masked_delete`; the smoke metadata contract records `reasoning_mask_replacement`.
- Both GSM8K and HotpotQA sparse-signal gates failed, but the raw status string names only GSM8K.
- The raw `next_allowed_step` repeats `REQUEST_V3_1_REPLACE_PREREGISTRATION`, which is stale after the v3.1 smoke has already run and failed.

The companion audit is:

- `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.json`
- `outputs/real_task_v3_1/qwen36_replace_smoke_20260608/v3_1_replace_smoke_consistency_audit.md`

## Frozen Claim Boundary

Allowed wording:

- v3 DELETE and v3.1 REPLACE/masked-span smokes both failed sparse-signal gates.
- The negative result is boundary evidence: coarse reflection-span interventions do not produce sufficient Delta-U variation on GSM8K and HotpotQA with the current model/protocol.
- Phase 5-7 remain the only positive diagnostic empirical core for the KBS package.

Blocked wording:

- validation pass or partial pass
- downstream PRM/filtering evidence
- threshold retuning
- mixing DELETE and REPLACE evidence
- any v3.2 or further intervention route under the current preregistration

Audited next allowed step: `STOP_NO_FURTHER_INTERVENTION_TUNING_UNDER_CURRENT_PREREGISTRATION`.
