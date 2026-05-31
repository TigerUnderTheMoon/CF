# Related Work

TODO: manual bibliography completion. Citation placeholders are used where bibliographic metadata has not been manually verified.

## Reflexion, Self-Refine, and Self-Correction

Reflection-oriented methods such as Reflexion [REFLEXION_PLACEHOLDER] and Self-Refine [SELF_REFINE_PLACEHOLDER] study whether iterative critique, feedback, or revision changes task performance. The conceptual comparison is direct: those methods motivate the study of explicit reflective operations, while this framework asks how individual reflective steps behave under deterministic attribution and structural interventions.

The distinction is threefold. First, this repository separates local utility from structural necessity rather than measuring only final trajectory improvement. Second, it treats reflective steps as observable trace elements, not hidden reasoning states. Third, it interprets weak compensation and low distributedness as informative structural findings rather than as evidence that reflection is absent.

A possible interpretation is that reflection methods and this framework answer complementary questions. Reflection methods ask how to obtain better trajectories; this paper asks how the resulting reflective steps are organized under deterministic intervention proxies. That narrower question makes the manuscript less about improving a reflection policy and more about characterizing the relation between local utility and topology-sensitive dependence.

## Process Reward Models

Process Reward Models (PRMs) [PRM_PLACEHOLDER] provide step-level supervision for reasoning processes. They are relevant because both PRMs and this framework operate below the final-answer level. The distinction is that PRM-style work usually trains or evaluates a reward signal for intermediate steps, while this paper analyzes deterministic intervention outputs and topology-sensitive dependence.

The comparison has three dimensions. Supervision target: PRMs often score step correctness or process quality, while this framework reports `attribution_score` and `structural_necessity` proxies. Training status: this paper does not introduce a learned model. Claim scope: PRM scores can guide downstream systems, but they do not by themselves establish sparse bottlenecks, weak compensation, or topology-sensitive dependence.

This distinction also keeps the paper from being framed as a reward-model tuning exercise. The empirical observations are stored deterministic outputs, not labels for a new reward model. A future direction could use the proxy quantities as supervision signals, but that would be a separate modeling contribution.

## Counterfactual and Intervention-Based Analysis

Counterfactual and intervention-based analysis methods motivate the use of controlled perturbations to test whether a component changes an output. This paper follows that broad logic but applies it to reflective reasoning traces and then separates functional and structural readings. The framework uses deterministic ablations, graph removal modes, redundancy analysis, and resilience curves as operational proxies.

The key distinction is claim discipline. We do not present the resulting measurements as internal-process decomposition or strong identification. The framework reports empirical observations from stored artifacts, structural interpretations over deterministic trace topology, and possible interpretation only as future direction. This lets the paper compare intervention-sensitive local utility with topology-sensitive structural necessity without overstating what the perturbations establish.

Compared with broader intervention-based interpretability, the paper's unit of analysis is the reflective step in an observable trace. The structural layer is not a claim about internal model mechanisms. It is a reproducible graph abstraction that tests how local attribution signals survive PRUNE, CASCADE, BYPASS, redundancy, compensation, and resilience diagnostics.
