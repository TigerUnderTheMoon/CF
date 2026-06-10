# ADR 003: Why the Pilot-Blocked Strategy

Status: accepted

Date: 2026-06-06

## Context

`PILOT_BLOCKED` (pilot evidence exists but readiness gates block claim upgrade, 试点证据存在但不能升级结论) is the project status used when a route (验证路线) has useful diagnostic artifacts (诊断产物) but has not satisfied its preregistered pass gates (预注册通过门限：事先规定的数据、成本和信号阈值).

FMA has several real-task and downstream artifacts. Some show useful signals, but strict validation gates failed or remained incomplete. Treating those artifacts as positive validation would overstate the evidence.

## Decision

Keep the pilot-blocked strategy as the default status policy for guarded real-task and downstream routes. A route can move out of `PILOT_BLOCKED` only when the current claim registry (结论注册表) and readiness audit (就绪性审计) identify a passing artifact with the exact required gates.

Failed, abandoned, or request-only artifacts remain provenance. They must not be rewritten into stronger evidence.

## Rationale

The project studies functional attribution under observable traces. That framing requires conservative evidence boundaries:

- A pilot pass is not a full-validation pass.
- A positive rank signal is not enough if quality, sparse-signal, or transport gates fail.
- A downstream mini diagnostic that fails its preregistered downstream filtering gate (下游过滤门限：对下游过滤或过程奖励模型性能的预注册阈值) is evidence against that route, not a PRM/filtering success.
- A transport canary (传输金丝雀：用于检测基础设施连通性的轻量测试) is diagnostic infrastructure evidence, not validation evidence.

`PILOT_BLOCKED` keeps these distinctions visible in README, paper, and audit files.

## Consequences

Positive:

- Claim wording stays reviewer-safe.
- Historical failures remain useful as preliminary tests.
- New routes must preregister data, cost, transport, and pass/fail gates before live execution.

Negative:

- The project may look less complete than a pass/fail benchmark repository.
- Status reporting requires more precision.
- Some promising pilot signals remain non-upgradable.

## Claim Boundary

The current diagnostic manuscript may report Phase 5-7 synthetic diagnostics and guarded pilot failures as evidence about local utility, structural necessity, and validation limits. It must not claim deterministic replay success (确定性重放成功：完全可复现的实验结果), submission readiness (提交就绪性), or PRM/filtering improvement from blocked pilot artifacts.
