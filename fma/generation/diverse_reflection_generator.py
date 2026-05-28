"""Seeded reflection-chain generation from deterministic template pools."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from fma.generation.reflection_templates import (
    TEMPLATE_POOLS,
    ReflectionStyle,
    ReflectionTemplate,
    validate_template_pools,
)


@dataclass(frozen=True)
class ReflectionStep:
    category: str
    text: str
    attribution_type: str | None = None
    expected_intervention: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, str | float | None]:
        return {
            "category": self.category,
            "text": self.text,
            "attribution_type": self.attribution_type,
            "expected_intervention": self.expected_intervention,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ReflectionChain:
    trace_id: str
    reflection_chain: tuple[ReflectionStep, ...]

    def __iter__(self):
        return iter(self.reflection_chain)

    def __len__(self) -> int:
        return len(self.reflection_chain)

    def categories(self) -> list[str]:
        return [step.category for step in self.reflection_chain]

    def texts(self) -> list[str]:
        return [step.text for step in self.reflection_chain]

    def chain_text(self) -> str:
        return " ".join(self.texts())

    def to_dict(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "reflection_chain": [step.to_dict() for step in self.reflection_chain],
        }


ReflectionTrace = ReflectionChain


class DiverseReflectionGenerator:
    """Generate reproducible single-category and mixed-category reflection chains."""

    def __init__(
        self,
        template_pools: Mapping[ReflectionStyle, Sequence[ReflectionTemplate]] | None = None,
        category_weights: Mapping[ReflectionStyle | str, float] | None = None,
    ):
        self.template_pools = {
            style: tuple(templates)
            for style, templates in (template_pools or TEMPLATE_POOLS).items()
        }
        validate_template_pools(self.template_pools)
        self.category_weights = self._normalize_category_weights(category_weights)

    def generate(
        self,
        category: ReflectionStyle,
        seed: int,
        n: int = 1,
    ) -> list[ReflectionTrace]:
        """Generate n one-step traces from a single reflection category."""
        return self.generate_chain([category], seed=seed, n=n)

    def generate_chain(
        self,
        categories: Sequence[ReflectionStyle | str],
        seed: int,
        n: int = 1,
    ) -> list[ReflectionTrace]:
        """Generate n traces with an explicit ordered category sequence."""
        if n < 0:
            raise ValueError("n must be non-negative.")
        styles = [self._coerce_style(category) for category in categories]
        rng = random.Random(seed)
        return [
            self._build_chain(styles, seed=seed, trace_index=index, rng=rng)
            for index in range(n)
        ]

    def generate_mixed(
        self,
        seed: int,
        n: int = 1,
        chain_length: int = 3,
        category_sequence: Sequence[ReflectionStyle | str] | None = None,
    ) -> list[ReflectionTrace]:
        """Generate mixed-category traces, or repeat a provided sequence."""
        if category_sequence is not None:
            return self.generate_chain(category_sequence, seed=seed, n=n)
        if chain_length <= 0:
            raise ValueError("chain_length must be positive.")
        rng = random.Random(seed)
        chains: list[ReflectionTrace] = []
        for trace_index in range(n):
            styles = [self._sample_category(rng) for _ in range(chain_length)]
            chains.append(self._build_chain(styles, seed=seed, trace_index=trace_index, rng=rng))
        return chains

    def generate_balanced(
        self,
        n_per_category: int,
        seed: int,
        chain_length: int = 1,
    ) -> list[ReflectionTrace]:
        """Generate traces whose first reflection category is balanced by style."""
        if n_per_category < 0:
            raise ValueError("n_per_category must be non-negative.")
        if chain_length <= 0:
            raise ValueError("chain_length must be positive.")

        rng = random.Random(seed)
        chains: list[ReflectionTrace] = []
        for primary_style in ReflectionStyle:
            for _ in range(n_per_category):
                styles = [primary_style]
                styles.extend(self._sample_category(rng) for _ in range(chain_length - 1))
                chains.append(
                    self._build_chain(
                        styles,
                        seed=seed,
                        trace_index=len(chains),
                        rng=rng,
                    )
                )
        return chains

    def _build_chain(
        self,
        styles: Sequence[ReflectionStyle],
        seed: int,
        trace_index: int,
        rng: random.Random,
    ) -> ReflectionTrace:
        steps = tuple(self._build_step(style, rng) for style in styles)
        trace_id = self._trace_id(seed, trace_index, steps)
        return ReflectionChain(trace_id=trace_id, reflection_chain=steps)

    def _build_step(self, style: ReflectionStyle, rng: random.Random) -> ReflectionStep:
        template = self._sample_template(style, rng)
        return ReflectionStep(
            category=style.name,
            text=template.template,
            attribution_type=template.attribution_type,
            expected_intervention=template.expected_intervention,
            confidence=template.confidence,
        )

    def _sample_category(self, rng: random.Random) -> ReflectionStyle:
        styles = list(ReflectionStyle)
        weights = [self.category_weights[style] for style in styles]
        return rng.choices(styles, weights=weights, k=1)[0]

    def _sample_template(
        self,
        style: ReflectionStyle,
        rng: random.Random,
    ) -> ReflectionTemplate:
        templates = self.template_pools[style]
        weights = [template.weight for template in templates]
        if any(weight < 0.0 for weight in weights) or sum(weights) <= 0.0:
            raise ValueError(f"Invalid template weights for {style.name}.")
        return rng.choices(list(templates), weights=weights, k=1)[0]

    @staticmethod
    def _trace_id(seed: int, trace_index: int, steps: Iterable[ReflectionStep]) -> str:
        payload = "|".join(f"{step.category}:{step.text}" for step in steps)
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fma:{seed}:{trace_index}:{payload}"))

    @staticmethod
    def _coerce_style(category: ReflectionStyle | str) -> ReflectionStyle:
        if isinstance(category, ReflectionStyle):
            return category
        normalized = str(category).strip().upper().replace("-", "_")
        try:
            return ReflectionStyle[normalized]
        except KeyError:
            for style in ReflectionStyle:
                if style.value == str(category).strip().lower():
                    return style
            raise ValueError(f"Unknown reflection style {category!r}.")

    @classmethod
    def _normalize_category_weights(
        cls,
        category_weights: Mapping[ReflectionStyle | str, float] | None,
    ) -> dict[ReflectionStyle, float]:
        weights = {style: 1.0 for style in ReflectionStyle}
        if category_weights:
            for key, value in category_weights.items():
                style = cls._coerce_style(key)
                weight = float(value)
                if weight < 0.0:
                    raise ValueError("category weights must be non-negative.")
                weights[style] = weight
        if sum(weights.values()) <= 0.0:
            raise ValueError("at least one category weight must be positive.")
        return weights


__all__ = [
    "DiverseReflectionGenerator",
    "ReflectionChain",
    "ReflectionStep",
    "ReflectionTrace",
]
