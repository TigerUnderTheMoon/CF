"""Deterministic template pools for category-diverse reflections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Sequence


class ReflectionStyle(Enum):
    DECOMPOSITION = "decomposition"
    VERIFICATION = "verification"
    ERROR_CORRECTION = "error_correction"
    BACKTRACKING = "backtracking"
    PLANNING = "planning"
    CONSTRAINT_TRACKING = "constraint_tracking"
    UNCERTAINTY_MONITORING = "uncertainty_monitoring"
    RETRIEVAL = "retrieval"


@dataclass(frozen=True)
class ReflectionTemplate:
    category: ReflectionStyle
    template: str
    weight: float


TEMPLATE_POOLS: Mapping[ReflectionStyle, tuple[ReflectionTemplate, ...]] = MappingProxyType(
    {
        ReflectionStyle.DECOMPOSITION: (
            ReflectionTemplate(
                ReflectionStyle.DECOMPOSITION,
                "Let's break down the problem into smaller parts.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.DECOMPOSITION,
                "First solve the subproblem, then combine the result.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.DECOMPOSITION,
                "Separate the given information into the pieces that matter.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.DECOMPOSITION,
                "Reduce the task to one smaller step before continuing.",
                1.0,
            ),
        ),
        ReflectionStyle.VERIFICATION: (
            ReflectionTemplate(
                ReflectionStyle.VERIFICATION,
                "Check the arithmetic carefully before accepting the result.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.VERIFICATION,
                "Verify the previous conclusion against the problem statement.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.VERIFICATION,
                "Check whether each intermediate value is consistent.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.VERIFICATION,
                "Verify the answer by substituting it back into the conditions.",
                1.0,
            ),
        ),
        ReflectionStyle.ERROR_CORRECTION: (
            ReflectionTemplate(
                ReflectionStyle.ERROR_CORRECTION,
                "There may be a mistake, so correct the earlier calculation.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.ERROR_CORRECTION,
                "Correct the inconsistent step before moving on.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.ERROR_CORRECTION,
                "Identify the mistake and repair the reasoning path.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.ERROR_CORRECTION,
                "Revise the flawed step instead of carrying the error forward.",
                1.0,
            ),
        ),
        ReflectionStyle.BACKTRACKING: (
            ReflectionTemplate(
                ReflectionStyle.BACKTRACKING,
                "Backtrack to the point where the assumption entered.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.BACKTRACKING,
                "The earlier assumption may be incorrect, so consider an alternative.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.BACKTRACKING,
                "Let's reconsider the previous step before proceeding.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.BACKTRACKING,
                "Return to the last reliable conclusion and branch from there.",
                1.0,
            ),
        ),
        ReflectionStyle.PLANNING: (
            ReflectionTemplate(
                ReflectionStyle.PLANNING,
                "Plan the next step before doing the calculation.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.PLANNING,
                "First choose a strategy, then execute it in order.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.PLANNING,
                "Set the next step so the solution path stays organized.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.PLANNING,
                "Decide which operation should come next.",
                1.0,
            ),
        ),
        ReflectionStyle.CONSTRAINT_TRACKING: (
            ReflectionTemplate(
                ReflectionStyle.CONSTRAINT_TRACKING,
                "Track every constraint before drawing the conclusion.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.CONSTRAINT_TRACKING,
                "Need to satisfy both conditions at the same time.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.CONSTRAINT_TRACKING,
                "Keep the boundary condition visible while reasoning.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.CONSTRAINT_TRACKING,
                "Check that no constraint has been dropped from the argument.",
                1.0,
            ),
        ),
        ReflectionStyle.UNCERTAINTY_MONITORING: (
            ReflectionTemplate(
                ReflectionStyle.UNCERTAINTY_MONITORING,
                "This step is uncertain, so do not overcommit yet.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.UNCERTAINTY_MONITORING,
                "The evidence is incomplete and needs another check.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.UNCERTAINTY_MONITORING,
                "I am not sure this inference is supported.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.UNCERTAINTY_MONITORING,
                "Mark the uncertain part before continuing.",
                1.0,
            ),
        ),
        ReflectionStyle.RETRIEVAL: (
            ReflectionTemplate(
                ReflectionStyle.RETRIEVAL,
                "Recall the earlier definition before applying it.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.RETRIEVAL,
                "Use the previously established fact here.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.RETRIEVAL,
                "Remember the relevant rule from the setup.",
                1.0,
            ),
            ReflectionTemplate(
                ReflectionStyle.RETRIEVAL,
                "Retrieve the known relation and plug it into this step.",
                1.0,
            ),
        ),
    }
)


def templates_for(category: ReflectionStyle) -> tuple[ReflectionTemplate, ...]:
    """Return templates for one reflection category."""
    return TEMPLATE_POOLS[category]


def validate_template_pools(
    template_pools: Mapping[ReflectionStyle, Sequence[ReflectionTemplate]] = TEMPLATE_POOLS,
    min_templates: int = 3,
) -> None:
    """Validate that every style has enough deterministic templates."""
    missing = [
        style.name
        for style in ReflectionStyle
        if len(tuple(template_pools.get(style, ()))) < min_templates
    ]
    if missing:
        raise ValueError(f"Template pool is underspecified for: {', '.join(missing)}")


validate_template_pools()


__all__ = [
    "ReflectionStyle",
    "ReflectionTemplate",
    "TEMPLATE_POOLS",
    "templates_for",
    "validate_template_pools",
]
