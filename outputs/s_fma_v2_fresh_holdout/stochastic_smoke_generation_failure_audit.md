# Stochastic Smoke Generation Failure Audit

Status: `STOCHASTIC_SMOKE_FAIL_GENERATION`  
Current project status: `PILOT_BLOCKED`  
Next allowed step: `FIX_SMOKE_GENERATION_PIPELINE`

This audit uses existing checkpoint artifacts only. It does not rerun smoke, replay, scoring, or any API call.

## Sources

- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_report.json`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_original_attempts.jsonl`
- `outputs/s_fma_v2_fresh_holdout/stochastic_smoke_replay_attempts.jsonl`
- `outputs/s_fma_v2_fresh_holdout/fresh_manifest.json`
- `outputs/s_fma_v2_fresh_holdout/api_preflight_report.json`
- configured generation prompt: `prompts/real_task_reflection_generation.txt`
- configured replay prompt: `prompts/real_task_replay.txt`

The requested path `prompts/real_task_generation.txt` does not exist in this repo. The active config points generation to `prompts/real_task_reflection_generation.txt`.

## Observed Failure

| Field | Value |
|---|---:|
| Original generation attempts | 20 |
| Valid original traces | 8 |
| Invalid original attempts | 12 |
| Empty raw outputs among invalid attempts | 12 |
| Partial replay attempts | 10 |
| Partial replay results | 3 |
| Cost used | USD 0.35119 |

All 12 invalid original attempts report:

```text
<root>: response is not a JSON object
```

All 12 invalid original attempts have nonzero usage but empty `raw_output`.

## Preflight vs Smoke

Preflight succeeded on JSON/schema/tag/final-answer checks:

- records evaluated: 20
- API attempts: 23
- JSON parse success rate: 1.0
- schema success rate: 1.0
- tag extraction success rate: 1.0
- final-answer parse success rate: 1.0
- model observed in attempts: `gpt-5.5`
- structured output mode: `json_schema`

Smoke original generation diverged:

- invalid original attempts all ended on `gpt-5.4`
- failed rows have no stored `structured_output_mode`
- failed rows have no stored `fallback_events`
- failed rows have no `response_id`
- failed rows have no sample/task context

## Missing Audit Context

The invalid original attempt rows lack:

| Field | Missing Count |
|---|---:|
| `sample_id` | 12 |
| `task_id` | 12 |
| `task_type` | 12 |
| `question_hash` | 12 |
| `question_preview` | 12 |
| `fallback_events` | 12 |
| `response_id` | 12 |

They do retain `model_name`, `usage`, and `validation_errors`.

Because the invalid rows lack sample identifiers, exact failed samples cannot be proven from the historical checkpoint alone. From the expected balanced selection order and the valid sample IDs, the likely failed originals are the first 10 GSM8K rows plus the first 2 HotpotQA rows, but that is an inference, not direct evidence.

## Root-Cause Hypotheses

1. Smoke original generation hit an output extraction or provider empty-output failure on fallback model `gpt-5.4`.
2. Smoke diverged from the preflight path: preflight remained valid on `gpt-5.5/json_schema`, while failed smoke attempts ended on `gpt-5.4` with empty extracted output.
3. Historical attempt serialization was insufficient for audit because invalid rows lost sample context and fallback telemetry.
4. The historical smoke route allowed partial replay checkpointing after incomplete original generation. Those replay rows are provenance only and are not validation evidence.

## Non-API Fixes Applied

- Invalid attempt serialization now preserves sample context when the caller provides samples: `sample_id`, `task_id`, `task_type`, `question_hash`, and `question_preview`.
- Invalid attempt rows now include `structured_output_mode` and `fallback_events`.
- Failed `GeneratedTraceResult` now retains the last attempted structured-output mode instead of reporting `unavailable`.
- The stochastic smoke runner now passes selected sample context into original checkpoint attempt serialization.
- Checkpoint finalization now suppresses Delta-U rows when original generation is incomplete, while still disclosing partial replay counts.
- Regression tests cover invalid attempt context, early stop before replay, finalize-existing no-API behavior, and claim guard fields.

## Claim Boundary

Partial replay attempts/results are not validation evidence. The current smoke has not passed.

Forbidden next steps:

- API execution without a new explicit approval
- smoke rerun without a new explicit approval
- full generation
- v2 scoring
- replay
- PRM/filtering
- `TASK_SPECIFIC_S_FMA_V2_PASS`
- `GLOBAL_S_FMA_V2_PASS`
- deterministic replay claim
- scale-ready or top-tier-ready wording

The only next allowed step remains `FIX_SMOKE_GENERATION_PIPELINE`. A bounded smoke rerun would require a new explicit approval and must not run automatically.
