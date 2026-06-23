# Cover Letter

Final Word version: `final_package/cover_letter.docx`.

June 15, 2026

Editorial Office
Information Processing & Management
Elsevier

Dear Editor,

We are pleased to submit our manuscript, "Structurally-Calibrated Functional Attribution for Audit Prioritization in Knowledge-Intensive Reasoning", for consideration as a regular article in Information Processing & Management.

The manuscript presents Structurally-Calibrated Functional Attribution (SC-FMA), a method for auditable verification-step weighting in knowledge-intensive reasoning systems. We believe it fits Information Processing & Management because it treats process supervision as a knowledge-structured decision-support problem within information-intensive processing: verification steps are weighted not only by local utility, but also by graph dependencies, redundancy, and bottleneck roles, supporting audit prioritization under a fixed review budget. The same structurally-calibrated weighting is directly applicable to information-processing workflows familiar to IPM readers: auditing retrieval chains in retrieval-augmented generation, reviewing entity-binding steps in knowledge-graph quality assessment, flagging redundant or bottleneck rules in expert-system rule chains, and prioritizing heterogeneous verification steps in digital libraries and knowledge-management systems.

Concretely, in a retrieval-augmented generation pipeline, SC-FMA's redundancy term flags retrieval steps that surface near-duplicate passages, while its bottleneck term identifies entity-linking steps whose failure would break downstream inference paths. In knowledge-graph quality assessment, the fidelity component maps to triple confidence scores, the necessity component maps to entity-path coverage, and the bottleneck component surfaces rare long-tail entity bindings whose corruption silently alters downstream correctness. These component-level mappings are methodological analogies that connect the SCU objective to audit workflows already studied in the information-science literature; they do not constitute validated deployment in those settings.

The evidence package includes a controlled synthetic benchmark where QP and Ridge are comparable but QP is strongest, locked PRM800K step-label evidence where `w_struct` is the primary real-data signal and Ridge is the closest SC-FMA approximation, a new offline PRM800K audit-prioritization readout for fixed review budgets, and a preliminary audit prioritization demonstration (Section 6) applying SC-FMA to knowledge-intensive process annotation with a fixed-budget comparison table (Table 3) and accompanying artifact at `outputs/kbs_audit_demo/`. The PRM800K stratified readout provides moderate, preliminary real-data support for PRM800K-like audit prioritization. The claim boundary is explicit: the submission does not claim downstream PRM training gains, GSM8K/HotpotQA replay validation, out-of-distribution transfer, or deployed workflow validation.

This work was supported by the National Social Science Fund of China Project (24BSH018) and the Beijing Natural Science Foundation Project (L252145). The authors declared that they have no conflicts of interest to this work. PRM800K is publicly available from its original source; derived reports and reproduction artifacts will be made available by the authors on request.

Correspondence may be directed to Ningning Wang at `wangningning@bistu.edu.cn`. Haoran Ma can be reached at `mahaoran0000@foamail.com`.

Sincerely,

Haoran Ma and Ningning Wang
