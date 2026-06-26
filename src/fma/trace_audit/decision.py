"""Dataset decision for the trace-audit experiment."""

from __future__ import annotations

from typing import Any


def compare_datasets() -> dict[str, dict[str, float | str]]:
    """Return the final GrailQA/WebQSP audit-suitability comparison.

    Scores are ordinal engineering judgments for this repository's goal:
    lower risk/cost is better, higher suitability/reproducibility is better.
    They intentionally ignore KGQA leaderboard performance.
    """

    return {
        "WebQSP": {
            "reasoning_trace_audit_suitability": 0.78,
            "risk_of_kgqa_interpretation": 0.28,
            "replay_verification_feasibility": 0.86,
            "engineering_complexity": 0.34,
            "reproducibility": 0.82,
            "kbs_reviewer_fit": 0.76,
            "summary": (
                "Best fit for a bounded trace-audit route: executable parses, "
                "manageable local KG slices, and low pressure to report KGQA "
                "leaderboard comparisons."
            ),
        },
        "GrailQA": {
            "reasoning_trace_audit_suitability": 0.84,
            "risk_of_kgqa_interpretation": 0.72,
            "replay_verification_feasibility": 0.58,
            "engineering_complexity": 0.76,
            "reproducibility": 0.66,
            "kbs_reviewer_fit": 0.70,
            "summary": (
                "Strong KGQA dataset, but its compositional and zero-shot focus "
                "invites semantic-parsing and KGQA-generalization expectations."
            ),
        },
    }


def final_dataset_decision() -> dict[str, Any]:
    """Return the non-revisitable final dataset choice for this route."""

    return {
        "recommended_dataset": "WebQSP",
        "rejected_dataset": "GrailQA",
        "rationale": (
            "WebQSP is final because it is sufficient for executable reasoning "
            "trace auditing while keeping the experiment clearly outside KGQA "
            "benchmarking, semantic parsing optimization, and model comparison."
        ),
        "rejected_dataset_rationale": (
            "GrailQA is less suitable for this audit methodology paper because "
            "its benchmark identity is KGQA compositional generalization. Using "
            "it would raise engineering cost and reviewer pressure to discuss "
            "KGQA performance rather than SC-FMA trace audit behavior."
        ),
    }
