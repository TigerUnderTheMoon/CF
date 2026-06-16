# Conclusion

This paper presented Structurally-Calibrated Functional Attribution (SC-FMA), a methodology that converts local functional attribution signals into structurally calibrated supervision weights. The SCU objective combines utility fidelity, graph-level necessity, redundancy reduction, and bottleneck protection in a convex optimization problem with auditable inputs and deterministic variants.

The evidence is route-specific. On the controlled synthetic benchmark, QP is the strongest SC-FMA variant and reaches Spearman rho = 0.608 against controlled proxy labels. On PRM800K real process-supervision annotations, w_struct is the main positive step-ranking result at rho = 0.611; Ridge closely preserves it at rho = 0.604, while QP and Projection underperform and must not be described as PRM800K winners.

The current package keeps failed and unvalidated routes outside the main claims. GSM8K/HotpotQA replay and filtering remain failed or blocked, downstream PRM training is not validated, and KBS integration remains methodological rather than deployed workflow evidence. With those boundaries, SC-FMA contributes a reproducible calibration method for auditable verification-step weighting and a clear path for future task-specific and KBS deployment validation.
