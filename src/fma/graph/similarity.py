"""Text similarity for reflection graph edge construction.

Provides TF-IDF-based and Jaccard similarity backends. TF-IDF is fitted
on a corpus of all reflection step texts for meaningful IDF weighting,
then used for pairwise comparisons within individual traces.

All computation is pure Python + numpy (no sklearn dependency).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

import numpy as np

_TOKEN_PATTERN = re.compile(r"(?u)\b\w+\b")

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
        "to", "was", "were", "will", "with",
    }
)


def tokenize(text: str) -> list[str]:
    """Return lowercase word tokens, filtering stop words."""
    return [
        token
        for token in _TOKEN_PATTERN.findall(text.lower())
        if token not in _STOP_WORDS
    ]


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity on token sets (stop words excluded)."""
    tokens_a = set(_TOKEN_PATTERN.findall(text_a.lower())) - _STOP_WORDS
    tokens_b = set(_TOKEN_PATTERN.findall(text_b.lower())) - _STOP_WORDS
    if not tokens_a or not tokens_b:
        return 0.0
    return float(len(tokens_a & tokens_b) / len(tokens_a | tokens_b))


class TextSimilarity:
    """Corpus-fitted text similarity for reflection graph edges.

    Usage::

        sim = TextSimilarity(method="tfidf")
        sim.fit_corpus(all_step_texts)
        score = sim.pairwise(text_a, text_b)
    """

    def __init__(self, method: str = "tfidf") -> None:
        allowed = {"tfidf", "jaccard"}
        if method not in allowed:
            raise ValueError(f"method must be one of {allowed}, got {method!r}")
        self.method = method
        self._idf: dict[str, float] = {}
        self._vocab: list[str] = []
        self._vocab_index: dict[str, int] = {}
        self._fitted = False

    def fit_corpus(self, texts: Sequence[str]) -> "TextSimilarity":
        n = len(texts)
        if n < 3 or self.method == "jaccard":
            self._fitted = True
            return self

        df: Counter[str] = Counter()
        tokenized_docs: list[set[str]] = []
        for text in texts:
            tokens = set(tokenize(text))
            tokenized_docs.append(tokens)
            df.update(tokens)

        self._vocab = sorted(token for token, count in df.items() if count >= 2)
        self._vocab_index = {term: idx for idx, term in enumerate(self._vocab)}

        for term in self._vocab:
            self._idf[term] = math.log((n + 1) / (df[term] + 1)) + 1.0

        self._fitted = True
        return self

    def pairwise(self, text_a: str, text_b: str) -> float:
        if not text_a.strip() or not text_b.strip():
            return 0.0
        if text_a == text_b:
            return 1.0
        if self.method == "tfidf" and self._vocab:
            return self._tfidf_cosine(text_a, text_b)
        return jaccard_similarity(text_a, text_b)

    def _tfidf_cosine(self, text_a: str, text_b: str) -> float:
        vec_a = self._tfidf_vector(text_a)
        vec_b = self._tfidf_vector(text_b)
        dot = float(np.dot(vec_a, vec_b))
        norm_a = float(np.linalg.norm(vec_a))
        norm_b = float(np.linalg.norm(vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.clip(dot / (norm_a * norm_b), 0.0, 1.0))

    def _tfidf_vector(self, text: str) -> np.ndarray:
        tokens = tokenize(text)
        if not tokens or not self._vocab:
            return np.zeros(len(self._vocab), dtype=float)
        tf = Counter(tokens)
        vec = np.zeros(len(self._vocab), dtype=float)
        for term, count in tf.items():
            idx = self._vocab_index.get(term)
            if idx is not None:
                vec[idx] = count * self._idf.get(term, 1.0)
        return vec

    def similarity_matrix(self, texts: Sequence[str]) -> np.ndarray:
        """Compute pairwise similarity matrix for a sequence of texts."""
        n = len(texts)
        matrix = np.eye(n, dtype=float)
        for i in range(n):
            for j in range(i + 1, n):
                sim = self.pairwise(texts[i], texts[j])
                matrix[i, j] = sim
                matrix[j, i] = sim
        return matrix


__all__ = [
    "TextSimilarity",
    "jaccard_similarity",
    "tokenize",
]
