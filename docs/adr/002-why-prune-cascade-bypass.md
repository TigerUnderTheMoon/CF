# ADR 002: Why PRUNE, CASCADE, and BYPASS

Status: accepted

Date: 2026-06-06

## Context

PRUNE (single-node removal, 单节点移除), CASCADE (node-plus-descendant removal, 节点及其后继移除), and BYPASS (remove-and-reconnect intervention, 移除并重连下游结构) are Phase 6 graph interventions. They turn local reflection scores into topology-sensitive diagnostics (拓扑敏感诊断：对图结构变化产生响应的测量方式).

Local attribution (局部归因) asks whether a reflective step has local utility. Structural necessity (结构必要性) asks a different question: whether the reasoning graph still depends on that step when the graph is modified.

## Decision

Use all three interventions as complementary diagnostics rather than choosing one canonical structural metric.

- PRUNE measures direct local removal sensitivity.
- CASCADE measures downstream dependency (下游依赖：节点对其后继节点的影响关系) when descendants are also removed.
- BYPASS measures whether downstream flow can remain connected after the selected node is skipped.

## Rationale

Reflective reasoning can be locally useful but structurally redundant. A single intervention cannot separate all relevant cases:

- PRUNE can miss downstream propagation.
- CASCADE can overstate disruption when a node has many descendants.
- BYPASS can reveal whether a node behaves like a bridge (桥接节点：连接上游和下游的必经之路) or an optional intermediate step (可选中间步骤：可被跳过而不破坏连通性的节点).

Using all three modes makes the mismatch between attribution score and structural necessity visible. This is the core Phase 6 diagnostic: local utility is widespread, while strict structural necessity is sparse.

## Consequences

Positive:

- Reviewers can see whether a result depends on one removal assumption.
- Zero-necessity cases are easier to interpret.
- Bottleneck candidates require stronger evidence across graph behavior.

Negative:

- The terminology is denser than a single-score report.
- The modes are structural diagnostics, not proof of true causal effects.
- Visual and notebook examples are needed for new users.

## Claim Boundary

PRUNE, CASCADE, and BYPASS estimate topology-mediated functional influence in stored graphs. They do not identify a Rubin-style average treatment effect, hidden cognitive state, or universal causal mechanism.
