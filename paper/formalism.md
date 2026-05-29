# Functional Reflective Attribution: An Operational Framework for Reflective Trace Analysis

## Section 1 - Reflection Units

The basic unit of analysis in this framework is the reflection unit. A reflection unit is an observable segment of a reasoning trace that performs a reflective role, such as checking a prior step, revising an intermediate conclusion, monitoring uncertainty, correcting an error, or adjusting a solution plan. The unit is defined only at the level of the recorded trace. It is not treated as evidence for processes outside the trace or as an explanation of how the model produced the trace.

We denote the set of reflection units in a trace as \(R = \{r_1, r_2, ..., r_n\}\). Each element of \(R\) corresponds to a bounded reflective segment that can be separated from surrounding task reasoning and final-answer content. The segmentation is operational: a unit is included when it can be identified as a distinct reflective component and used as a target for controlled perturbation without redefining the entire trace. The resulting unit set provides a stable interface between trace-level observation and intervention-sensitive evaluation.

Reflection units are separated from general reasoning components by their role in the trace. A direct computation, retrieval step, or answer statement is not automatically a reflection unit. A segment becomes a reflection unit when it evaluates, revises, monitors, critiques, or redirects the reasoning process itself. This distinction matters because the framework studies reflective utility contribution rather than generic step scoring. The object of analysis is not whether every token or sentence is important, but whether identified reflective segments exhibit measurable intervention-sensitive behavior.

Segmentation is designed to support intervention-ready analysis. A unit must be sufficiently local to be perturbed while preserving the surrounding trace structure, and sufficiently meaningful to represent a reflective operation rather than an arbitrary text fragment. The framework therefore treats reflection units as practical analysis targets: they are observable, bounded, and linked to final-output evaluation through a predefined protocol. This is a lightweight operational definition, not a claim about the complete organization of reasoning.

The use of reflection units also keeps the analysis grounded in reproducible artifacts. Since each unit is derived from the observable trace, later measurements can be tied back to explicit segments rather than inferred processes. This preserves the empirical scope of the framework: reflection units are not theoretical primitives or explanatory mechanisms. They are trace-level units that make controlled perturbation and operational attribution possible.

## Section 2 - Utility and Evaluation Scope

Utility is task-dependent and instantiated through predefined evaluation metrics within the experimental protocol. In this document, \(U(Y)\) denotes the measured utility of a trace output \(Y\) under the chosen evaluation procedure. The metric may be exact-match accuracy, semantic correctness, code execution success, verifier score, calibrated task reward, or another documented outcome measure appropriate to the task.

The meaning of \(U(Y)\) is therefore operational. It does not denote universal model quality, general reasoning competence, or a decision-theoretic utility function. It denotes the score assigned by the evaluation protocol to the output produced from an observable trace. Any comparison using \(U\) must be interpreted relative to the task, data split, perturbation rule, evaluator, and normalization procedure used in the experiment.

This utility boundary is important for reproducibility. A reflection unit can receive a high attribution score under one metric and a lower score under another if the metrics reward different aspects of performance. For example, a verification step may improve final answer correctness while increasing token cost, or a planning step may improve execution success without changing a surface-form correctness metric. The framework treats such differences as protocol-dependent empirical results rather than contradictions.

When utility values are normalized, the normalization is part of the evaluation procedure. Normalization enables comparison within a specified experiment, but it does not imply probabilistic semantics or universal comparability across tasks. Reported utility and attribution values should therefore be accompanied by the evaluation definition that produced them.

## Section 3 - Functional Attribution

Functional attribution assigns an operational score to each reflection unit. The attribution operator is written as \(A(r_i)\). A higher value indicates that the unit has greater measured reflective utility contribution under the framework's intervention-sensitive evaluation procedure. \(A(r_i)\) denotes a normalized operational attribution score under the specified evaluation procedure, not a universal property of the text segment.

Attribution is estimated operationally by comparing outcomes for the intact trace and the trace after a controlled perturbation of the target reflection unit. If perturbing a unit produces a larger utility degradation, the unit receives stronger evidence of reflective utility contribution. If perturbing the unit leaves measured utility largely unchanged, the attribution score is lower. The interpretation is empirical and contrastive: \(A(r_i)\) describes how the evaluated trace behaves when \(r_i\) is altered under a documented perturbation protocol.

The phrase functional attribution is used deliberately. The score describes operational contribution, not a stronger explanatory claim. It summarizes intervention-sensitive behavior observed under a fixed evaluation protocol. This makes the quantity useful for comparing reflection units, ranking candidate units for perturbation, and studying the distribution of local utility across traces, while keeping the interpretation bounded to observable trace behavior.

\(A(r_i)\) is a local empirical measurement: it is attached to an individual reflection unit, depends on measured utility after perturbation, and is defined by the procedure used to produce it.

The score does not by itself determine whether a reflection unit is necessary for the whole trace, whether similar units behave similarly in other tasks, or whether the model would preserve performance under a different perturbation rule. Such claims require separate group-level or distribution-level measurements. Individual attribution is a starting point for analysis, not the final interpretation of reflective structure.

## Section 4 - Intervention Utility Difference

The core evaluation mechanism is the utility difference between an intact reasoning trace and a perturbed version of that trace. In conceptual form, this is written as \(U(Y) - U(Y \mid I(r_i))\). Here, \(U(Y)\) is the measured utility of the intact trace output, and \(I(r_i)\) is the operational perturbation applied to reflection unit \(r_i\). The expression captures the performance gap associated with altering a specific reflective segment under the specified evaluation procedure.

The intervention notation is descriptive and does not correspond to Pearl-style do-operator semantics. The vertical bar in \(U(Y \mid I(r_i))\) means "utility measured after applying the perturbation \(I(r_i)\)" rather than a probabilistic conditioning statement or a formal intervention calculus. The framework uses intervention notation as compact shorthand for a controlled trace manipulation followed by evaluation.

The perturbation is controlled in the sense that it is applied to an identified unit while retaining the rest of the trace as the comparison context. Depending on the analysis layer, the perturbation may mask, replace, bypass, remove from an abstracted structure, or otherwise alter the target unit according to predefined operational rules. The purpose is to evaluate whether measured utility changes when the reflective segment is no longer available in its original form.

Utility degradation is the central observable signal. If \(U(Y)\) remains close to \(U(Y \mid I(r_i))\), the framework treats the intervened unit as having limited measured contribution under that procedure. If \(U(Y \mid I(r_i))\) is substantially lower, the unit is interpreted as having stronger intervention-sensitive utility. The difference is not treated as a complete explanation of the final output. It is a local operational contrast that enables ranking, aggregation, and structural analysis.

This distinction is central to the methodology. The framework does not present itself as a causal inference framework, does not use formal graphical machinery, and does not recover structure outside the recorded trace. It evaluates how observable trace-level utility changes under specified perturbations. The resulting difference is best understood as an intervention-sensitive utility contrast: a reproducible empirical measurement bounded by the chosen perturbation distribution and utility definition.

The intervention utility difference also separates reflective analysis from generic scoring. A reflection unit is not judged only by its surface form or category label. It is evaluated by how the trace behaves when the unit is modified. This makes the measurement context-sensitive: the same kind of reflective operation may contribute strongly in one trace and weakly in another, depending on surrounding reasoning components, task requirements, and final-output dependence.

## Section 5 - Structural Necessity

Individual attribution does not fully describe how reflection units work together. A trace may contain units whose isolated perturbation produces limited degradation, while a group of related units may jointly support the final output. Structural necessity addresses this group-level dependency. It is written as \(S(C)\), where \(C \subseteq R\). The set \(C\) denotes a cluster, chain, or selected subset of reflection units from the trace.

\(S(C)\) measures operational necessity at the level of reflective structure. The term structure refers to dependency-sensitive organization among observed reflection units, such as a sequence of verification, correction, and revision steps. It is an analysis abstraction over trace segments, not a recovered internal organization. The framework asks whether perturbing a group changes utility in a way that is not visible from isolated attribution alone. This allows the analysis to distinguish local contribution from collective degradation.

Structural necessity is not defined as the sum of individual attribution scores. In particular, \(S(C)\) is not assumed to equal \(\sum_i A(r_i)\). It measures collective degradation behavior under joint perturbation. This distinction is critical: a group can be operationally important even when its members have modest individual scores, and high-scoring individual units can be structurally replaceable when other trace components absorb the perturbation.

The purpose of \(S(C)\) is not to introduce a heavy structural theory. It is compact notation for group-level intervention behavior over reflection units. A cluster or chain may have topology-sensitive dependence when perturbing the group produces utility loss that would not be apparent from isolated perturbations. Conversely, a group may have limited structural necessity when the trace remains robust after the group is perturbed.

Structural dependency is therefore an empirical property of the evaluated trace and intervention procedure. It captures collective degradation under controlled perturbation, not model-internal computation. A group can have high structural necessity if its units jointly preserve answer quality, sustain a revision path, or maintain consistency across later reasoning. A group can have low structural necessity if neighboring units or later reasoning components absorb the perturbation without substantial measured loss.

This group-level view is important because reflective utility can be distributed unevenly. Some units may appear locally useful but structurally replaceable. Others may have modest individual attribution but participate in a dependency-sensitive chain.

## Section 6 - Resilience

Resilience describes how measured utility changes under progressive perturbation. It is written as \(\mathcal{R}(k)\), where \(k \in \{1, 2, ..., K\}\). The index \(k\) refers to the number of intervention steps applied in a progressive perturbation sequence. \(\mathcal{R}(k)\) summarizes remaining utility after \(k\) interventions and therefore describes the degradation trajectory of the reflective structure.

\(\mathcal{R}(k)\) is computed by progressively applying perturbations according to a documented ordering rule and measuring cumulative utility degradation. The ordering may be attribution-first, structural-necessity-first, sequential, or another predefined strategy. The ordering rule is part of the experimental protocol and must be reported with the curve or summary index.

This procedure turns attribution into a protocol-specific stress test. If utility declines sharply after the first few interventions, the trace exhibits low resilience under the selected perturbation order. If utility declines gradually, the trace exhibits greater operational robustness under the same procedure.

Resilience also helps evaluate attribution stability. When high-attribution units are perturbed first, the remaining utility trajectory indicates whether the attribution ranking identifies units that are utility-sensitive under cumulative perturbation.

The framework may summarize the trajectory with a resilience index, but such a summary remains empirical and intervention-dependent. It does not certify robustness under all possible perturbations and does not imply that a model can reliably recover from arbitrary reflective disruption. It measures operational robustness under the specific progressive perturbation procedure used in the analysis.

Utility collapse behavior is another use of \(\mathcal{R}(k)\). A trace may remain stable through several perturbations and then degrade abruptly once a key reflective chain is disrupted. Alternatively, it may degrade almost linearly as units are perturbed. These patterns summarize how reflective utility is distributed under controlled stress.

## Section 7 - Notational Scope

The notation in this framework is intentionally modest. \(R\) names the observed set of reflection units. \(A(r_i)\) names an intervention-sensitive attribution score for one unit. \(U(Y)\) names measured utility for a trace output under a specified evaluation procedure. \(I(r_i)\) names an operational perturbation on a unit. \(S(C)\) names group-level operational necessity for a subset of units. \(\mathcal{R}(k)\) names remaining utility behavior under progressive perturbation. These symbols provide compact labels for empirical procedures; they do not define a complete mathematical theory of reasoning.

The notation is descriptive rather than theoretically complete. Its purpose is to provide a compact operational vocabulary for intervention-sensitive reflective analysis over observable reasoning traces. It is not a formal causal model, not a mechanistic account, and not a framework for discovering processes outside the recorded trace. The symbols summarize what is measured, how perturbations are applied, and how utility changes are reported.

This scope boundary is necessary because the framework is empirical and operational. The symbols summarize perturbation procedures over observable traces. They do not assert identifiability, encode graphical assumptions, or provide guarantees about processes outside the recorded trace. Their value is methodological clarity: they let the paper describe reflection units, attribution, utility degradation, topology-sensitive dependence, and resilience without unnecessary symbolic machinery.

The formalism is also not intended as a complete theory of reasoning. It does not explain why a model produced a trace or how a segment was generated. It only organizes observable reflective behavior into an intervention-sensitive analysis framework. This makes the notation suitable for methodology writing: concise enough to be readable, explicit enough to support reproducibility, and limited enough to avoid overclaiming.

## Section 8 - Framework Scope and Reporting

Functional Reflective Attribution is an intervention-sensitive operational analysis framework over observable reasoning traces. Its empirical object is the measured behavior of traces under controlled perturbation. Its main outputs are local attribution scores, group-level operational necessity measurements, progressive resilience curves, and task-conditioned summaries of reflective utility contribution.

The framework is bounded to observable traces, controlled perturbations, utility degradation analysis, and operational attribution. It addresses questions such as which reflection units are utility-sensitive under a given protocol, which groups of units have collective degradation under joint perturbation, and whether utility is concentrated or distributed under progressive stress. These questions are empirical and protocol-dependent.

The framework is not a causal inference framework, a mechanistic interpretability framework, or a cognition discovery framework. It does not claim that perturbation results expose the model's internal operations. It does not generalize beyond the intervention distribution, task distribution, evaluator, and trace segmentation procedure without additional evidence.

Reports using this framework specify the following elements: the trace source, the reflection-unit segmentation rule, the perturbation operators, the utility metric, the normalization procedure, the perturbation ordering for \(\mathcal{R}(k)\), and the aggregation rule for task-level summaries. These details define the operational meaning of the reported quantities. Reported values are protocol-dependent rather than protocol-independent properties of reasoning.

Terminology discipline is part of reporting. Section 9.1 summarizes the preferred vocabulary for keeping the framework aligned with its intended role: a lightweight empirical framework for analyzing how reflective trace components contribute to measured task outcomes under controlled perturbation.

### Section 8.1 - Experimental Instantiation

In experiments, the framework is instantiated through observable trace artifacts and documented perturbation procedures. The abstract reflection unit becomes a bounded reflective span in a recorded trace. Perturbation becomes a predefined trace or structure modification, such as masking, span removal under a preservation rule, structure-level removal, or bypass. Utility becomes the task evaluation metric selected before analysis. Attribution becomes normalized utility degradation under the chosen perturbation. Structural necessity becomes grouped perturbation analysis over selected units, and resilience becomes a cumulative perturbation trajectory under a reported ordering rule.

| Framework Concept | Experimental Realization |
| --- | --- |
| Reflection unit | Reflective trace span |
| Perturbation | Masking, removal, or bypass under a documented rule |
| Utility | Task evaluation metric |
| Attribution | Normalized utility degradation |
| Structural necessity | Grouped perturbation analysis |
| Resilience | Cumulative perturbation trajectory |

This mapping is implementation-facing rather than theoretical. It specifies what must be recorded for an experiment to be reproducible: the trace source, span boundaries, perturbation operator, utility metric, normalization procedure, and perturbation order where resilience is reported. It does not add another layer of formalism. Its purpose is to keep the methodology tied to executable artifacts and to prevent terms such as attribution, necessity, and resilience from drifting away from the measurements that produce them.

## Section 9 - Assumptions, Validity Boundaries, and Limitations

### A. Observable-Trace Limitation

The framework evaluates only observable reasoning traces and the reflective units identified within those traces. It does not recover hidden reasoning, infer latent processes, or claim access to internal model states. Any statement about reflection is limited to recorded trace behavior under the specified protocol. The absence of an identified reflection unit is not evidence about unrecorded model behavior.

### B. Segmentation Dependence

Reflection-unit segmentation is operational and should not be treated as unique. Different span-boundary rules, annotation procedures, or extraction conventions may produce different unit sets and different attribution results. Reports should describe the segmentation procedure clearly enough that readers can see what was included, excluded, or merged. Sensitivity to segmentation is part of the protocol, not a defect to be hidden.

### C. Perturbation Dependence

Attribution depends on the perturbation operators used to alter reflection units. Masking, removal, replacement, bypass, and grouped perturbation can expose different sensitivities because each changes the trace or structure in a different way. The framework does not claim perturbation-invariant attribution. When multiple operators are used, their results should be reported as related protocol views rather than collapsed into an operator-free claim.

### D. Utility-Metric Dependence

Attribution is evaluator-dependent. A unit may appear more or less important depending on whether utility is measured through exact correctness, semantic equivalence, code execution, verifier score, token cost, or another documented metric. Different utility metrics may therefore yield different rankings without implying a contradiction. Metric choice should be treated as a substantive design decision in the reported experiment.

### E. Ordering Dependence in Resilience

Resilience trajectories depend on the order in which perturbations are applied. Attribution-first, structural-necessity-first, sequential, and other protocol-defined orders answer different stress-test questions. A reported resilience curve is paired with its ordering rule, not treated as an order-free property of the trace. Comparisons between curves are most interpretable when the ordering protocol is held fixed.

### F. No Causal Identifiability

The framework does not identify causal effects. Intervention notation is operational shorthand for trace modification followed by evaluation; no SCM or Pearl-style semantics are assumed. The reported quantities describe measured degradation under controlled perturbation, not identified effects in a causal model.

### G. External Validity Limitation

Results may not transfer across tasks, models, domains, prompting regimes, or evaluation settings. Attribution measurements are protocol-dependent and should be reported with enough experimental detail to make their scope visible. Generalization beyond the observed setting requires additional evidence rather than stronger interpretation of the same measurements. Weak transfer should be treated as an empirical boundary, not as a reason to broaden the claim.

### Section 9.1 - Preferred Terminology

The preferred vocabulary keeps the framework operational, trace-level, and empirically restrained. Reports should use the terms on the left and avoid the stronger readings on the right unless a separate method explicitly warrants them.

| Preferred | Avoid |
| --- | --- |
| Intervention-sensitive | Causal |
| Operational contribution | Mechanistic importance |
| Observable trace | Latent cognition |
| Perturbation | Intervention effect |
| Structural dependency | Computational graph |
| Reflective utility | Reasoning capability |
| Measured degradation | Identified effect |
| Protocol-dependent result | Universal finding |
