# Limitations

This repository is a research prototype for deterministic structural analysis of reflective reasoning traces. The framework does not provide strong identification guarantees, mechanism-level guarantees, hidden-reasoning access, semantic understanding, or protocol-independent recovery. Its quantities are operational proxies over observable traces and stored trace topology.

The non-causal framing is central. `attribution_score` is a proxy for local functional contribution, and `structural_necessity` is a proxy for topology-sensitive dependence. A high or low value should not be read as a hidden reasoning fact. The framework studies deterministic intervention sensitivity, not internal-process explanation.

The deterministic proxy design also has limits. The benchmark is synthetic, and the current traces are generated under fixed templates and seeds. Determinism increases reproducibility, but it does not guarantee external validity on open-ended reasoning tasks, model-generated reflection under deployment conditions, or human-authored rationales.

Topology approximation is another limitation. Reflection graphs are deterministic approximations constructed from observable trace structure. Edges, source nodes, influence propagation, PRUNE, CASCADE, and BYPASS modes provide structural diagnostics, but they do not prove semantic dependence or hidden reasoning mechanisms.

Intervention coverage is sparse relative to the full space of possible reflective operations. Phase 5-7 cover local ablations, graph removal modes, redundancy profiles, compensation ratios, rerouting, resilience, and distributedness. They do not cover learned policies, hidden-state models, discovery-style claims, or semantic reasoning verification.

Stage 2 evidence is also limited. The held-out FMA signal is positive and its aggregate confidence interval excludes zero, but the effect size is small. This supports weak alignment, not a high-magnitude prediction result. Stratified generalization is not globally confirmed: the `S_mid` and `S_rand` confidence intervals include zero, so C1, C2, and C3 must be described as `stratum_dependent` rather than globally confirmed.

Baseline integration is conservative. The repository contains clean held-out step-level proxy scores for random masking, span masking, graph removal, and edge dropout, but these are frozen non-target controls rather than independently rerun perturbation-response experiments. They close the missing-artifact gate without supporting high-magnitude or superiority claims.

Observed redistribution should not be interpreted as intentional adaptation. Compensation and rerouting are descriptive structural measurements of post-removal redistribution in a deterministic graph. They are not evidence of deliberate replanning, agentic recovery, or semantic recovery.

Empirical observations are bounded by the stored outputs. Structural interpretations should remain tied to those outputs. A possible interpretation is that future benchmarks could test whether the same local-utility and sparse-necessity pattern holds under larger, non-synthetic, or human-reviewed trace collections.

Finally, the manuscript is limited by citation status. Related work uses placeholders until bibliographic metadata is manually completed. This is intentional citation safety: conceptual comparison is preferable to unverified author, year, venue, or title claims.
