# v2.1 Full Validation Abandonment Audit

Date: 2026-06-06

This audit records the strict v2.1 full-validation rescue decision after the bounded engineering retry. It does not rewrite the frozen failed full-validation artifact and does not run PRM/filtering.

## Decision

Strict `s_FMA_v2.1` full validation is abandoned as non-viable under the current contract.

Current status remains `PILOT_BLOCKED`.

## Evidence

| Field | Value |
|---|---:|
| Source full status | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS` |
| Engineering retry status | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS` |
| Engineering retry failure codes | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`; `V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL` |
| Source API attempts | 2776 |
| Incremental retry API calls | 119 |
| Cumulative route API calls | 2895 |
| Effective report API attempts | 2794 |
| Cumulative route cost | USD `65.806855` |
| Effective JSON/schema/tag/final-answer success | `0.9917680744452398` |
| Nonzero Delta-U GSM8K | 16 |
| Nonzero Delta-U HotpotQA | 142 |
| Full `TASK_SPECIFIC_pass` | `false` |
| Full `GLOBAL_pass` | `false` |

## Basis

- The strict engineering retry did not clear all transport failures within the bounded retry policy.
- The unresolved transport failures are HotpotQA-side and cannot change GSM8K Delta-U rows.
- GSM8K remains at 16 nonzero Delta-U rows, below the preregistered threshold of 20.
- Therefore no allowed strict v2.1 transport-only retry can produce `GLOBAL_pass`.

## Claim Boundary

Allowed wording:

- The v2.1 pilot stochastic artifact passed pilot gates only.
- The v2.1 full stochastic validation and strict engineering retry failed.
- Strict v2.1 full validation is abandoned as non-viable under the current contract.
- Current status remains `PILOT_BLOCKED`.

Forbidden wording:

- Do not claim full-validation pass.
- Do not claim submission-ready or top-tier-ready status.
- Do not claim deterministic replay evidence.
- Do not claim PRM/filtering execution, improvement, or superiority.
- Do not relax v2.1 gates post hoc.
