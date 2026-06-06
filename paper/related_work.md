# Related Work

## Reflexion, Self-Refine, and Self-Correction

Reflection-oriented methods such as Reflexion (Shinn et al., 2023) and Self-Refine (Madaan et al., 2023) study whether iterative critique, feedback, or revision changes task performance. The conceptual comparison is direct: those methods motivate the study of explicit reflective operations, while this framework asks how individual reflective steps behave under deterministic attribution and structural interventions.

The distinction is threefold. First, this repository separates local utility from structural necessity rather than measuring only final trajectory improvement. Second, it treats reflective steps as observable trace elements, not hidden reasoning states. Third, it interprets weak compensation and low distributedness as informative structural findings rather than as evidence that reflection is absent.

A possible interpretation is that reflection methods and this framework answer complementary questions. Reflection methods ask how to obtain better trajectories; this paper asks how the resulting reflective steps are organized under deterministic intervention proxies. That narrower question makes the manuscript less about improving a reflection policy and more about characterizing the relation between local utility and topology-sensitive dependence.

## Process Reward Models

Process Reward Models (PRMs), exemplified by process supervision for mathematical reasoning in Lightman et al. (2023), provide step-level supervision for reasoning processes. They are relevant because both PRMs and this framework operate below the final-answer level. The Chinese framework positions FMA as a way to derive reflection utility signals for process supervision, but the current repository adds an important constraint: local utility should not be treated as a direct supervision weight without structural calibration.

The comparison has three dimensions. Supervision target: vanilla PRMs often score step correctness or process quality, while this framework distinguishes `attribution_score` from `structural_necessity`. Bias control: length-calibrated PRM variants address length or process-bias effects, while FMA focuses on reflection-level intervention sensitivity and topology-sensitive dependence. Granularity: token-attribution methods operate at token or activation level, while FMA treats explicit metacognitive spans as semantic intervention units.

This distinction also keeps the paper from being framed as a completed reward-model tuning exercise. The empirical observations are stored deterministic outputs, not evidence that a learned PRM has improved downstream performance. A future validation should compare structurally calibrated FMA against vanilla PRM, length-calibrated PRM, token attribution, and heuristic reflection scoring.

The central claim-safe position is therefore narrow: Phase 5-7 explain why attribution-aware process supervision should distinguish local utility from sparse structural necessity. They do not yet establish a downstream advantage for attribution-aware PRM/filtering.

## Counterfactual and Intervention-Based Analysis

Counterfactual and intervention-based analysis methods motivate the use of controlled perturbations to test whether a component changes an output. This paper follows that broad logic but applies it to reflective reasoning traces and then separates functional and structural readings. The framework uses deterministic ablations, graph removal modes, redundancy analysis, and resilience curves as operational proxies.

The key distinction is claim discipline. We do not present the resulting measurements as internal-process decomposition or strong identification. The framework reports empirical observations from stored artifacts, structural interpretations over deterministic trace topology, and possible interpretation only as future direction. This lets the paper compare intervention-sensitive local utility with topology-sensitive structural necessity without overstating what the perturbations establish.

Compared with broader intervention-based interpretability, the paper's unit of analysis is the reflective step in an observable trace. The structural layer is not a claim about internal model mechanisms. It is a reproducible graph abstraction that tests how local attribution signals survive PRUNE, CASCADE, BYPASS, redundancy, compensation, and resilience diagnostics.

## Reproducibility, Benchmark Design, and Data Governance

Reproducibility work in machine learning emphasizes that reported results depend on documented data, code, seeds, variance, and experimental reporting choices (Pineau et al., 2021; Dodge et al., 2019; Bouthillier et al., 2019). This paper follows that conservative reading. The repository treats stored artifacts, prompt locks, manifest audits, and readiness gates as part of the evidence boundary rather than as operational details outside the paper.

Benchmark design work also cautions against reading a single static score as a general capability claim. GLUE and SuperGLUE made standardized comparison useful for language understanding, while Dynabench, HELM, and benchmark-governance critiques highlight benchmark construction, coverage, saturation, and scenario design as first-order concerns (Wang et al., 2018; Wang et al., 2019; Kiela et al., 2021; Liang et al., 2022; Raji et al., 2021). FMA adopts the same caution at the trace level: local utility scores are evaluated only under their task distribution, perturbation protocol, and structural diagnostic layer.

Dataset versioning, contamination, and deduplication studies motivate the real-task governance diagnostics. Hugging Face Datasets supports dataset loading by pinned revision, and the Datasets library documents community dataset sharing and provenance practices (Lhoest et al., 2021; Hugging Face, 2026). Deduplication and web-corpus documentation work show that repeated or poorly documented text can affect language-model training and evaluation (Lee et al., 2022; Dodge et al., 2021). Recent contamination diagnostics further show that benchmark freshness cannot be assumed from dataset names alone, especially when test material can be memorized, rephrased, or consumed across prior artifacts (Golchin and Surdeanu, 2023; Yang et al., 2023; Zhang et al., 2024). The blocked real-task v3 route is therefore reported as a governance diagnostic, not as a failed performance run.
