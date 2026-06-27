"""Text similarity for reflection graph edge construction.

Provides TF-IDF, Jaccard, and optional embedding similarity backends.
TF-IDF is fitted on a corpus of all reflection step texts for meaningful
IDF weighting, then used for pairwise comparisons within individual
traces.  The embedding backend is optional and fail-closed: callers must
handle missing dependencies or model files explicitly rather than silently
falling back to lexical similarity.
"""

from __future__ import annotations

import math
import re
import hashlib
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

    def __init__(
        self,
        method: str = "tfidf",
        *,
        embedding_backend: str = "sentence-transformers",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        allow_embedding_download: bool = False,
    ) -> None:
        allowed = {"tfidf", "jaccard", "embedding"}
        if method not in allowed:
            raise ValueError(f"method must be one of {allowed}, got {method!r}")
        if embedding_backend not in {"sentence-transformers", "fixture", "blocked"}:
            raise ValueError(
                "embedding_backend must be one of "
                "{'sentence-transformers', 'fixture', 'blocked'}"
            )
        self.method = method
        self.embedding_backend = embedding_backend
        self.embedding_model = embedding_model
        self.allow_embedding_download = bool(allow_embedding_download)
        self._idf: dict[str, float] = {}
        self._vocab: list[str] = []
        self._vocab_index: dict[str, int] = {}
        self._embedding_vectors: dict[str, np.ndarray] = {}
        self._embedding_dimension = 384
        self._embedding_version = "fixture" if embedding_backend == "fixture" else "unknown"
        self._embedding_cache_path = ""
        self._embedding_download_status = "not_applicable"
        self._fitted = False

    def fit_corpus(self, texts: Sequence[str]) -> "TextSimilarity":
        if self.method == "embedding":
            return self._fit_embedding_corpus(texts)

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
        if self.method == "embedding":
            return self._embedding_cosine(text_a, text_b)
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

    def metadata(self) -> dict[str, object]:
        """Return backend metadata suitable for reproducibility reports."""
        payload: dict[str, object] = {"method": self.method, "status": "ok"}
        if self.method == "embedding":
            payload.update(
                {
                    "embedding_backend": self.embedding_backend,
                    "embedding_model": self.embedding_model,
                    "embedding_dimension": int(self._embedding_dimension),
                    "embedding_package_version": self._embedding_version,
                    "embedding_cache_path": self._embedding_cache_path,
                    "embedding_download_status": self._embedding_download_status,
                    "allow_embedding_download": self.allow_embedding_download,
                }
            )
        return payload

    def _fit_embedding_corpus(self, texts: Sequence[str]) -> "TextSimilarity":
        unique_texts = [text for text in dict.fromkeys(str(text) for text in texts) if text.strip()]
        if self.embedding_backend == "blocked":
            raise RuntimeError("embedding backend was explicitly blocked; lexical substitutes were not used")
        if self.embedding_backend == "fixture":
            self._embedding_dimension = 384
            self._embedding_version = "fixture"
            self._embedding_cache_path = "fixture-hashed-embedding"
            self._embedding_download_status = "fixture_local"
            self.embedding_model = "fixture-hashed-embedding"
            self._embedding_vectors = {
                text: _fixture_embedding(text, self._embedding_dimension)
                for text in unique_texts
            }
            self._fitted = True
            return self

        try:
            import sentence_transformers  # type: ignore[import-not-found]
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - depends on optional local env
            raise RuntimeError(
                "sentence-transformers is required for embedding_topical; "
                "install the optional ML dependency or run with --embedding-backend fixture"
            ) from exc

        model_kwargs = {}
        if not self.allow_embedding_download:
            model_kwargs["local_files_only"] = True
        model = SentenceTransformer(self.embedding_model, **model_kwargs)
        embeddings = model.encode(
            unique_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        self._embedding_dimension = int(embeddings.shape[1]) if embeddings.ndim == 2 else 0
        self._embedding_version = str(getattr(sentence_transformers, "__version__", "unknown"))
        cache_folder = getattr(model, "cache_folder", None)
        self._embedding_cache_path = str(cache_folder or _resolve_hf_cache_path(self.embedding_model))
        self._embedding_download_status = (
            "download_allowed_or_cache_hit" if self.allow_embedding_download else "local_cache_only"
        )
        self._embedding_vectors = {
            text: np.asarray(vector, dtype=float)
            for text, vector in zip(unique_texts, embeddings, strict=False)
        }
        self._fitted = True
        return self

    def _embedding_cosine(self, text_a: str, text_b: str) -> float:
        vec_a = self._embedding_vectors.get(text_a)
        vec_b = self._embedding_vectors.get(text_b)
        if vec_a is None:
            vec_a = _fixture_embedding(text_a, self._embedding_dimension)
        if vec_b is None:
            vec_b = _fixture_embedding(text_b, self._embedding_dimension)
        dot = float(np.dot(vec_a, vec_b))
        norm_a = float(np.linalg.norm(vec_a))
        norm_b = float(np.linalg.norm(vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.clip(dot / (norm_a * norm_b), 0.0, 1.0))


def _fixture_embedding(text: str, dimension: int) -> np.ndarray:
    """Deterministic local embedding for fixture tests, not paper evidence."""
    vector = np.zeros(dimension, dtype=float)
    tokens = tokenize(text) or [str(text)]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


def _resolve_hf_cache_path(model_name: str) -> str:
    try:
        from huggingface_hub import try_to_load_from_cache  # type: ignore[import-not-found]

        path = try_to_load_from_cache(model_name, "config.json")
        if isinstance(path, str) and path:
            return path
    except Exception:
        pass
    return ""


__all__ = [
    "TextSimilarity",
    "jaccard_similarity",
    "tokenize",
]
