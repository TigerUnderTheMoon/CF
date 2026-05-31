# Non-Deterministic API Pilot Protocol

Status: `NONDETERMINISTIC_PROTOCOL_PREREGISTERED`

## Blocked Original Route

- Blocked route: `deterministic_seed_controlled_api_pilot`
- Decision: `BLOCKED_BY_API_DETERMINISM`
- Reason: No probed model both accepted seed control and passed the drift gate.

## Replacement Protocol

- Disclosure required: `True`
- Claim level: `pilot_only_until_repeated_replay_ci_passes`
- Original generations per sample: `1`
- Replay repeats per span: `3`
- Key-sample replay repeats per span: `5`
- Bootstrap resamples: `10000`
- Bootstrap confidence level: `0.95`

## Gates

- Minimum schema success rate: `0.95`
- Minimum tag success rate: `0.95`
- Minimum valid traces: `300`
- Minimum span validity rate: `0.9`
- Minimum replay success rate: `0.85`
- Effect gate: `bootstrap_ci_lower_gt_zero_by_task_or_pooled_with_task_pass`

## Required Disclosure

OpenAI API seed transport was not available in preflight; repeated sampling and bootstrap confidence intervals replace deterministic replay claims.
