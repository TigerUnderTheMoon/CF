# PRM800K Audit-Prioritization Summary

This report is an offline audit-prioritization readout on the locked PRM800K split. It is not PRM training evidence, not filtering superiority evidence, and not GSM8K/HotpotQA replay validation.

- Claim boundary: `real_prm800k_audit_prioritization_only`
- Samples: 4417
- Steps: 34219

| Method | Top-1 max-label hit | Label mass@25% | Label mass@50% | NDCG@25% | NDCG@50% | Claim permission |
|---|---:|---:|---:|---:|---:|---|
| w_struct | 0.9169 | 0.3809 | 0.6854 | 0.9506 | 0.9593 | `audit_prioritization_context_only` |
| SC-FMA Ridge | 0.9054 | 0.3796 | 0.6837 | 0.9460 | 0.9554 | `audit_prioritization_context_only` |
| SC-FMA QP | 0.9033 | 0.3790 | 0.6774 | 0.9439 | 0.9487 | `audit_prioritization_context_only` |
| Frozen PRM prefix score | 0.7775 | 0.3419 | 0.6193 | 0.8465 | 0.8627 | `audit_prioritization_context_only` |
| random | 0.7329 | 0.3065 | 0.5523 | 0.7757 | 0.7844 | `audit_prioritization_context_only` |
| span_length | 0.7055 | 0.2969 | 0.5498 | 0.7526 | 0.7759 | `audit_prioritization_context_only` |

Operational note: w_struct and SC-FMA Ridge concentrate high-rated PRM800K process steps better than the best simple control under the 25% review budget. This remains a locked-split step-ranking use case, not downstream PRM training or task replay validation.
