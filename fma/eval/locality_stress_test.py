"""Locality stress diagnostics for synthetic reflection chains."""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Optional, Sequence

from fma.generation import ReflectionChain, ReflectionStyle
from fma.intervention import InterventionType, StructuralInterventionEngine


def compute_trace_utility(trace: ReflectionChain) -> float:
    """
    Heuristic proxy for reflection-chain quality.

    This score measures perturbation response only. It is not a claim about
    hidden reasoning states or universal functional value.
    """
    categories = trace.categories()
    if not categories:
        return 0.0

    has_contradiction = any(category == "CONTRADICTION" for category in categories)
    non_contradiction = [category for category in categories if category != "CONTRADICTION"]
    counts = Counter(non_contradiction)
    total = sum(counts.values())
    if total == 0:
        diversity_score = 0.0
    else:
        entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
        diversity_score = entropy / math.log2(len(ReflectionStyle))

    length = len(categories)
    if 2 <= length <= 5:
        length_score = 1.0
    elif length == 1:
        length_score = 0.75
    else:
        length_score = max(0.0, 1.0 - 0.15 * abs(length - 5))

    utility = 0.75 * diversity_score + 0.25 * length_score
    if has_contradiction:
        utility -= 1.0
    return min(1.0, max(0.0, float(utility)))


@dataclass(frozen=True)
class LocalityStressResult:
    trace_id: str
    edit_distance: float
    utility_before: float
    utility_after: float
    utility_shift: float
    locality_ratio: float
    intervention_type: str

    def to_dict(self) -> dict[str, float | str]:
        return {
            "trace_id": self.trace_id,
            "edit_distance": self.edit_distance,
            "utility_before": self.utility_before,
            "utility_after": self.utility_after,
            "utility_shift": self.utility_shift,
            "locality_ratio": self.locality_ratio,
            "intervention_type": self.intervention_type,
        }


class LocalityStressTester:
    """Evaluate local instability under seeded structural interventions."""

    def evaluate(
        self,
        trace: ReflectionChain,
        intervention_engine: StructuralInterventionEngine,
        seed: int,
        intervention_type: Optional[InterventionType] = None,
        target_index: Optional[int] = None,
    ) -> LocalityStressResult:
        rng = random.Random(seed)
        selected_type = intervention_type or rng.choice(list(InterventionType))
        intervened, _metadata = intervention_engine.apply(
            trace,
            intervention_type=selected_type,
            seed=seed,
            target_index=target_index,
        )
        utility_before = compute_trace_utility(trace)
        utility_after = compute_trace_utility(intervened)
        edit_distance = normalized_levenshtein_on_category_sequence(
            trace.categories(),
            intervened.categories(),
        )
        utility_shift = abs(utility_after - utility_before)
        locality_ratio = utility_shift / (edit_distance + 1e-6)
        return LocalityStressResult(
            trace_id=trace.trace_id,
            edit_distance=edit_distance,
            utility_before=utility_before,
            utility_after=utility_after,
            utility_shift=utility_shift,
            locality_ratio=locality_ratio,
            intervention_type=selected_type.value,
        )


def normalized_levenshtein_on_category_sequence(
    before: Sequence[str],
    after: Sequence[str],
) -> float:
    denominator = max(len(before), len(after), 1)
    distance = levenshtein_distance(before, after)
    return min(1.0, max(0.0, distance / denominator))


def levenshtein_distance(left: Sequence[str], right: Sequence[str]) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            insertion = current[right_index - 1] + 1
            deletion = previous[right_index] + 1
            substitution = previous[right_index - 1] + (0 if left_value == right_value else 1)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


__all__ = [
    "LocalityStressResult",
    "LocalityStressTester",
    "compute_trace_utility",
    "levenshtein_distance",
    "normalized_levenshtein_on_category_sequence",
]
