"""Deterministic functional taxonomy for reflection traces."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from fma.types import ReflectionAnnotation, ReflectionCategory, ReflectionTrace


class ReflectionTaxonomizer:
    """Rule-based classifier for functional reflection categories."""

    DEFAULT_KEYWORD_MAP: dict[ReflectionCategory, tuple[str, ...]] = {
        ReflectionCategory.DECOMPOSITION: ("break down", "subproblem"),
        ReflectionCategory.VERIFICATION: ("verify", "check"),
        ReflectionCategory.ERROR_CORRECTION: ("mistake", "correct"),
        ReflectionCategory.BACKTRACKING: ("backtrack", "alternative"),
        ReflectionCategory.UNCERTAINTY_MONITORING: ("uncertain", "not sure"),
        ReflectionCategory.PLANNING: ("plan", "next step"),
        ReflectionCategory.CONSTRAINT_TRACKING: ("constraint", "boundary"),
        ReflectionCategory.RETRIEVAL: ("recall", "remember"),
    }

    def __init__(self, keyword_map: Optional[Dict[str, List[str]]] = None):
        """Initialize with optional custom keyword overrides."""
        self.keyword_map = {
            category: list(keywords)
            for category, keywords in self.DEFAULT_KEYWORD_MAP.items()
        }
        if keyword_map:
            for category_key, keywords in keyword_map.items():
                category = self._coerce_category(category_key)
                if category is ReflectionCategory.OTHER:
                    continue
                self.keyword_map[category] = list(keywords)

    def classify(self, trace: ReflectionTrace) -> ReflectionAnnotation:
        """Return a deterministic functional category annotation."""
        text = trace.reflection_text.strip()
        if not text:
            return ReflectionAnnotation(
                category=ReflectionCategory.OTHER,
                confidence=0.0,
                rationale="empty trace",
            )

        scored: list[tuple[float, int, ReflectionCategory, list[str]]] = []
        for category in ReflectionCategory:
            if category is ReflectionCategory.OTHER:
                continue
            keywords = self.keyword_map.get(category, [])
            if not keywords:
                continue
            matched = [keyword for keyword in keywords if self._keyword_matches(text, keyword)]
            score = len(matched) / len(keywords)
            scored.append((score, category.value, category, matched))

        if not scored:
            return ReflectionAnnotation(
                category=ReflectionCategory.OTHER,
                confidence=0.0,
                rationale="no strong match",
            )

        scored.sort(key=lambda item: (-item[0], item[1]))
        confidence, _, category, matched = scored[0]
        confidence = min(1.0, max(0.0, float(confidence)))

        if confidence < 0.5:
            return ReflectionAnnotation(
                category=ReflectionCategory.OTHER,
                confidence=confidence,
                rationale="no strong match",
            )

        rationale = self._rationale(category, matched)
        return ReflectionAnnotation(category=category, confidence=confidence, rationale=rationale)

    @staticmethod
    def _coerce_category(category_key: str | ReflectionCategory) -> ReflectionCategory:
        if isinstance(category_key, ReflectionCategory):
            return category_key
        normalized = str(category_key).strip().upper()
        try:
            return ReflectionCategory[normalized]
        except KeyError as exc:
            raise ValueError(f"Unknown reflection category {category_key!r}.") from exc

    @staticmethod
    def _keyword_matches(text: str, keyword: str) -> bool:
        pattern = ReflectionTaxonomizer._literal_keyword_pattern(keyword)
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    @staticmethod
    def _literal_keyword_pattern(keyword: str) -> str:
        escaped_parts = [re.escape(part) for part in keyword.strip().split()]
        escaped = r"\s+".join(escaped_parts)
        prefix = r"(?<![A-Za-z0-9_])" if keyword[:1].isalnum() else ""
        suffix = r"(?![A-Za-z0-9_])" if keyword[-1:].isalnum() else ""
        return f"{prefix}{escaped}{suffix}"

    @staticmethod
    def _rationale(category: ReflectionCategory, matched: Iterable[str]) -> str:
        cues = ", ".join(f"'{keyword}'" for keyword in matched)
        rationale = f"matched {category.name.lower()} cue(s): {cues}"
        return rationale[:200]
