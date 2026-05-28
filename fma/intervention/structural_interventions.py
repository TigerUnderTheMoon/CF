"""Structural perturbations for synthetic reflection chains."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from fma.generation import ReflectionChain, ReflectionStep, ReflectionStyle, templates_for


class InterventionType(Enum):
    DELETE = "delete"
    SHUFFLE = "shuffle"
    REPLACE = "replace"
    TRUNCATE = "truncate"
    CONTRADICT = "contradict"


@dataclass(frozen=True)
class InterventionMetadata:
    intervention_type: str
    target_index: Optional[int]
    seed: int
    before_hash: str
    after_hash: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intervention_type": self.intervention_type,
            "target_index": self.target_index,
            "seed": self.seed,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "details": self.details,
        }


CONTRADICTION_TEMPLATES: tuple[str, ...] = (
    "The previous reasoning may be invalid.",
    "This conclusion conflicts with the earlier condition.",
    "The selected path contradicts the stated requirement.",
    "Treat the last step as suspect before using it.",
)


class StructuralInterventionEngine:
    """Apply deterministic chain-level perturbations without mutating inputs."""

    def apply(
        self,
        trace: ReflectionChain,
        intervention_type: InterventionType,
        seed: int,
        target_index: Optional[int] = None,
    ) -> tuple[ReflectionChain, InterventionMetadata]:
        rng = random.Random(seed)
        before_hash = trace_hash(trace)

        if intervention_type is InterventionType.SHUFFLE:
            new_trace, details, resolved_index = self._shuffle(trace, rng)
        else:
            resolved_index = self._resolve_target_index(trace, target_index, rng)
            if intervention_type is InterventionType.DELETE:
                new_trace, details = self._delete(trace, resolved_index)
            elif intervention_type is InterventionType.REPLACE:
                new_trace, details = self._replace(trace, resolved_index, rng)
            elif intervention_type is InterventionType.TRUNCATE:
                new_trace, details = self._truncate(trace, resolved_index)
            elif intervention_type is InterventionType.CONTRADICT:
                new_trace, details = self._contradict(trace, resolved_index, rng)
            else:
                raise ValueError(f"Unsupported intervention type {intervention_type!r}.")

        after_hash = trace_hash(new_trace)
        metadata = InterventionMetadata(
            intervention_type=intervention_type.value,
            target_index=resolved_index,
            seed=seed,
            before_hash=before_hash,
            after_hash=after_hash,
            details=details,
        )
        return new_trace, metadata

    @staticmethod
    def _delete(
        trace: ReflectionChain,
        target_index: int,
    ) -> tuple[ReflectionChain, dict[str, Any]]:
        steps = list(trace.reflection_chain)
        removed = steps.pop(target_index)
        return _with_steps(trace, steps), {"removed_category": removed.category}

    @staticmethod
    def _shuffle(
        trace: ReflectionChain,
        rng: random.Random,
    ) -> tuple[ReflectionChain, dict[str, Any], Optional[int]]:
        steps = list(trace.reflection_chain)
        before_order = [step.category for step in steps]
        rng.shuffle(steps)
        after_order = [step.category for step in steps]
        return _with_steps(trace, steps), {"before_order": before_order, "after_order": after_order}, None

    @staticmethod
    def _replace(
        trace: ReflectionChain,
        target_index: int,
        rng: random.Random,
    ) -> tuple[ReflectionChain, dict[str, Any]]:
        steps = list(trace.reflection_chain)
        original = steps[target_index]
        current = original.category.strip().upper()
        candidates = [
            style
            for style in ReflectionStyle
            if style.name != current and style.value.upper() != current
        ]
        replacement_style = rng.choice(candidates)
        templates = templates_for(replacement_style)
        replacement_template = rng.choice(templates)
        steps[target_index] = ReflectionStep(
            category=replacement_style.name,
            text=replacement_template.template,
        )
        return _with_steps(trace, steps), {
            "removed_category": original.category,
            "replacement_category": replacement_style.name,
        }

    @staticmethod
    def _truncate(
        trace: ReflectionChain,
        target_index: int,
    ) -> tuple[ReflectionChain, dict[str, Any]]:
        # Exclusive policy: keep the target step and remove later reflections.
        steps = list(trace.reflection_chain[: target_index + 1])
        return _with_steps(trace, steps), {"truncate_policy": "exclusive_keep_target"}

    @staticmethod
    def _contradict(
        trace: ReflectionChain,
        target_index: int,
        rng: random.Random,
    ) -> tuple[ReflectionChain, dict[str, Any]]:
        steps = list(trace.reflection_chain)
        cue = rng.choice(CONTRADICTION_TEMPLATES)
        steps.insert(target_index + 1, ReflectionStep(category="CONTRADICTION", text=cue))
        return _with_steps(trace, steps), {"inserted_category": "CONTRADICTION"}

    @staticmethod
    def _resolve_target_index(
        trace: ReflectionChain,
        target_index: Optional[int],
        rng: random.Random,
    ) -> int:
        if len(trace) == 0:
            raise ValueError("Cannot apply a targeted intervention to an empty reflection chain.")
        if target_index is None:
            return rng.randrange(len(trace))
        if target_index < 0 or target_index >= len(trace):
            raise IndexError(f"target_index {target_index} out of range for chain length {len(trace)}.")
        return int(target_index)


def trace_hash(trace: ReflectionChain) -> str:
    payload = json.dumps(trace.to_dict(), ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _with_steps(trace: ReflectionChain, steps: list[ReflectionStep]) -> ReflectionChain:
    return ReflectionChain(trace_id=trace.trace_id, reflection_chain=tuple(steps))


__all__ = [
    "CONTRADICTION_TEMPLATES",
    "InterventionMetadata",
    "InterventionType",
    "StructuralInterventionEngine",
    "trace_hash",
]
