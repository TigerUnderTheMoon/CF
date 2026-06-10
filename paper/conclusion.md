# Conclusion

This paper presented Structurally-Calibrated Functional Attribution (SC-FMA), a methodology that converts interventional utility estimates into structurally-consistent supervision weights for reflective reasoning traces. The core contribution is the SCU objective — a convex, constrained optimization that jointly enforces fidelity to local utility, consistency with graph-level necessity, redundancy reduction, and bottleneck protection.

We showed that SC-FMA's convex formulation provides formal guarantees: unique solutions, monotonicity for non-redundant step pairs, variance reduction over raw CIU weighting, and guaranteed bottleneck protection. These guarantees are verified by both analytical proof and implemented tests.

Empirically, SC-FMA variants achieve higher rank correlation with oracle step importance labels than raw CIU and six families of baseline methods on step importance ranking. The full QP variant with all structural terms activated ranks best, and ablation confirms that each constraint contributes independently to ranking quality. The improvement is robust across metrics and statistical tests.

SC-FMA addresses a specific practical need in process supervision: the conversion of intervention-based utility signals into credible, deployable supervision weights. The convex formulation makes it computationally predictable; the structural calibration makes it empirically superior to uncalibrated alternatives; and the theoretical guarantees make it analyzable.

This work transforms the FMA framework from a diagnostic instrument into a methodological contribution. Where prior work established that local utility is weakly aligned with structural necessity, we provide the calibration mechanism that resolves that tension. The methodology is open-source and reproducible, with configurable variants supporting deployment across different compute budgets and structural fidelity requirements.
