# Cover Letter

**Subject**: Submission of Regular Article: "Structurally-Calibrated Functional Attribution: A Methodology for Process Supervision Weighting in Reflective Reasoning"

Dear Editor,

Please consider the manuscript "Structurally-Calibrated Functional Attribution: A Methodology for Process Supervision Weighting in Reflective Reasoning" as a Regular Article for Knowledge-Based Systems. The manuscript introduces Structurally-Calibrated Functional Attribution (SC-FMA), a methodology that turns interventional utility estimates and graph-level structural diagnostics into calibrated supervision weights through a convex Structurally-Calibrated Utility objective. The paper is positioned as a methodological contribution for auditable process supervision in knowledge-intensive reasoning systems, not as a downstream PRM-training or deployed-system validation study.

The paper explicitly addresses three primary methodological concerns: (1) the CIU signal is trace-coarse (all spans in a trace share the same binary outcome), limiting per-span attribution precision; (2) structural necessity depends on a keyword-heuristic graph construction whose topology may not capture semantic or logical reasoning dependence; (3) the CIU protocol exhibits substantial direction noise (54.3% misattribution rate, 7.9% directional alignment accuracy). These limitations are acknowledged as central qualifications, not incidental caveats. The paper interprets the observed divergence as a protocol-bound descriptive observation rather than an unconditional claim about reflective reasoning structure.

The manuscript also reports negative preliminary test results for reproducible reflection-utility evaluation. The v2.1 full stochastic route failed its preregistered quality and sparse-signal gates, and a one-shot downstream filtering mini-validation failed its filtering-signal gate. The later real-task v3 DELETE smoke and v3.1 REPLACE/masked-span smoke both passed transport and trace-count gates but failed sparse-signal gates. These findings are reported as preliminary tests, not as validation or downstream support.

The synchronized submission package separates those failed replay/filtering routes from the current positive real-data evidence. The v3.6 PRM800K hash-split locked validation supports real PRM800K step-label ranking only: 4,417 locked samples and 34,219 labeled steps, with SC-FMA structural weights reaching Spearman 0.6113401179642559 against PRM800K labels. The v3.8 frozen PRM comparison is reported only as an in-distribution, overlap-limited baseline context: the frozen PRM prefix-sequence reward score reaches Spearman 0.2515662235547571, while the paired bootstrap interval for the SC-FMA minus frozen-PRM comparison is [0.34499208448462026, 0.3745467544914783] with Holm correction passing. These results do not support downstream training, GSM8K/HotpotQA replay-pass wording, downstream filtering, mechanism recovery, or claims beyond PRM800K-like process-supervision data.

The paper is a fit for Knowledge-Based Systems because it addresses evaluation design for knowledge-oriented reflective agents and process-supervision systems. SC-FMA frames reflection utility as an auditable calibration signal over observable traces, while the failed route audits identify benchmark-design constraints required for reliable future validation. The current evidence provides protocol-bound diagnostic observations, real PRM800K step-ranking support, and measurement-channel concerns that future process-supervision and reflection-filtering systems should consider before treating reflective utility as a structurally grounded supervision target.

The evidence package separates the primary empirical core from preliminary tests. The primary empirical core is the Phase 5-7 synthetic diagnostic suite plus the v3.6/v3.8 PRM800K step-ranking and frozen-baseline context evidence. Preliminary tests include the v2.1 failed validation route, the failed downstream mini-check, the v3 DELETE smoke failure, and the v3.1 REPLACE/masked-span smoke failure plus companion consistency audit.

We request that the manuscript be considered for review. Suitable reviewers would have expertise in process supervision, reflective agents, reproducibility and benchmark design, interpretability, or evaluation methodology for language-model systems.

Sincerely,

The authors
