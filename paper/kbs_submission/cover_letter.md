# Cover Letter

**Subject**: Submission of Regular Article: "Functional Metacognitive Attribution: A Diagnostic and Design Framework with Reproducibility Constraints for Reflection Utility Evaluation"

Dear Editor,

Please consider the manuscript "Functional Metacognitive Attribution: A Diagnostic and Design Framework with Reproducibility Constraints for Reflection Utility Evaluation" as a Regular Article for Knowledge-Based Systems. The manuscript introduces Functional Metacognitive Attribution (FMA), a diagnostic protocol that separates local utility from structural necessity in reflective reasoning traces. Across 800 synthetic traces and 2400 reflective steps from a single model under fixed prompts, the stored diagnostics show widespread local attribution but weak alignment with topology-sensitive structural necessity under a keyword-heuristic graph construction: Pearson correlations are approximately 0.05--0.09 across structural modes, and 67.79% of node-level structural necessity values are zero.

The paper explicitly addresses three primary methodological concerns: (1) the CIU signal is trace-coarse (all spans in a trace share the same binary outcome), limiting per-span attribution precision; (2) structural necessity depends on a keyword-heuristic graph construction whose topology may not capture semantic or logical reasoning dependence; (3) the CIU protocol exhibits substantial direction noise (54.3% misattribution rate, 7.9% directional alignment accuracy). These limitations are acknowledged as central qualifications, not incidental caveats. The paper interprets the observed divergence as a protocol-bound descriptive observation rather than an unconditional claim about reflective reasoning structure.

The manuscript also reports negative preliminary test results for reproducible reflection-utility evaluation. The v2.1 full stochastic route failed its preregistered quality and sparse-signal gates, and a one-shot downstream filtering mini-validation failed its filtering-signal gate. The later real-task v3 DELETE smoke and v3.1 REPLACE/masked-span smoke both passed transport and trace-count gates but failed sparse-signal gates. These findings are reported as preliminary tests, not as validation or downstream support.

The paper is a fit for Knowledge-Based Systems because it addresses evaluation design for knowledge-oriented reflective agents and process-supervision systems. FMA frames reflection utility as an auditable diagnostic signal over observable traces, while the failed route audits identify benchmark-design constraints required for reliable future validation. The current evidence provides protocol-bound diagnostic observations and measurement-channel concerns that future process-supervision and reflection-filtering systems should consider before treating reflective utility as a structurally grounded supervision target.

The evidence package separates the primary empirical core from preliminary tests. The primary empirical core is the Phase 5-7 synthetic diagnostic suite. Preliminary tests include the v2.1 failed validation route, the failed downstream mini-check, the v3 DELETE smoke failure, and the v3.1 REPLACE/masked-span smoke failure plus companion consistency audit.

We request that the manuscript be considered for review. Suitable reviewers would have expertise in process supervision, reflective agents, reproducibility and benchmark design, interpretability, or evaluation methodology for language-model systems.

Sincerely,

The authors
