"""Trajectory-control definitions for separate reporting."""

from __future__ import annotations


TRAJECTORY_CONTROLS = {
    "no_reflection": {
        "definition": "Answer directly without visible reflection tags.",
        "mix_with_span_attribution": False,
    },
    "tagged_reflection": {
        "definition": "Use one or more visible <reflection> tags in a single-pass solution.",
        "mix_with_span_attribution": False,
    },
    "self_refine_style": {
        "definition": "Visible draft, feedback, and revision for the same question.",
        "mix_with_span_attribution": False,
    },
    "reflexion_style": {
        "definition": "Visible verbal reflection after failure or uncertainty, then retry.",
        "mix_with_span_attribution": False,
    },
}


def control_report_skeleton() -> dict[str, dict[str, object]]:
    return {
        name: {
            **definition,
            "metrics": {
                "accuracy": None,
                "tokens": None,
                "validity": None,
                "reflection_count": None,
                "cost": None,
            },
        }
        for name, definition in TRAJECTORY_CONTROLS.items()
    }
