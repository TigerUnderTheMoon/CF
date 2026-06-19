# Diagnostic FMA Paper (ARCHIVED — SUPERSEDED)

**This is NOT the active submission source.** These files are an archived diagnostic draft of the original FMA paper ("Functional Metacognitive Attribution: A Diagnostic and Design Framework with Reproducibility Constraints for Reflection Utility Evaluation").

The canonical KBS submission source is:

```
paper/kbs_submission/final_source/manuscript.tex
```

The canonical upload package is:

```
paper/kbs_submission/final_package/
```

These archived files are retained for provenance only. They must not be referenced as active paper entrypoints, used to construct claims, or cited as the current manuscript version. The active claim registry is `paper/claim_registry.md`; the active submission readiness audit is `paper/submission_lock_audit.md`.

## What changed

The original diagnostic paper framed FMA as a framework for showing that local utility ≠ structural necessity. The KBS submission reframes the contribution as **Structurally-Calibrated Functional Attribution (SC-FMA)**: a methodology that converts interventional utility estimates into structurally-consistent supervision weights via convex constrained optimization (the SCU objective).

Key differences:
- Title changed from "Functional Metacognitive Attribution: A Diagnostic and Design Framework..." to "Structurally-Calibrated Functional Attribution for Audit Prioritization in Knowledge-Intensive Reasoning"
- Core contribution shifted from diagnostic analysis to structural calibration methodology
- Added SCU objective with 4 formal guarantees (convexity, monotonicity, variance reduction, bottleneck protection)
- Added KBS positioning section with application scenarios and adapter pseudocode
- Added PRM800K real-data step-ranking evidence and audit-prioritization readout
- Added Countries KG ontology-aware edge construction pilot
