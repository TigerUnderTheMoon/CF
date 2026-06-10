"""Frozen public PRM inference wrapper for step-level scoring."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .registry import get_prm_spec
from .scoring import (
    aggregate_step_scores,
    extract_step_boundaries_from_spans,
    format_prm_input,
    normalize_prm_scores,
)

logger = logging.getLogger(__name__)


class FrozenPRMScorer:
    """Use a pre-trained public PRM for step-level scoring (inference only).

    No fine-tuning, no training, no hidden hyperparameter tuning.
    The model weights are loaded from HuggingFace in eval mode and
    never updated.
    """

    def __init__(
        self,
        model_name: str = "Qwen2.5-Math-PRM-1.5B",
        device: str = "auto",
        quantization: str | None = "4bit",
        cache_dir: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.spec = get_prm_spec(model_name)
        self.device = device
        self.quantization = quantization
        self.cache_dir = cache_dir
        self._model = None
        self._tokenizer = None

    def _load_model(self) -> None:
        """Lazily load model and tokenizer on first use."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "PRM inference requires torch and transformers. "
                "Install with: poetry install -E ml"
            ) from exc

        model_kwargs: dict[str, Any] = {}
        if self.quantization == "4bit":
            try:
                from transformers import BitsAndBytesConfig

                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                )
                logger.info("prm_load_quantized_4bit", model=self.model_name)
            except ImportError:
                logger.warning("bitsandbytes_not_available", fallback="fp16")
                if self.device == "auto":
                    model_kwargs["device_map"] = "auto"
                    model_kwargs["torch_dtype"] = torch.float16
        else:
            if self.device == "auto":
                model_kwargs["device_map"] = "auto"
                model_kwargs["torch_dtype"] = torch.float16
            elif self.device != "cpu":
                model_kwargs["device_map"] = self.device

        if self.cache_dir:
            model_kwargs["cache_dir"] = self.cache_dir

        logger.info("prm_load_start", model=self.spec.hf_id)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.spec.hf_id,
            trust_remote_code=True,
            cache_dir=self.cache_dir,
        )
        self._model = AutoModelForTokenClassification.from_pretrained(
            self.spec.hf_id,
            trust_remote_code=True,
            **model_kwargs,
        )
        self._model.eval()
        logger.info("prm_load_complete", model=self.model_name)

    def score_steps(
        self,
        question: str,
        steps: list[str],
        aggregation: str = "mean",
        normalize: str = "sigmoid",
    ) -> list[float]:
        """Score each reasoning step using the frozen PRM.

        Args:
            question: The problem statement.
            steps: List of step texts.
            aggregation: How to aggregate token scores to step scores.
            normalize: Score normalization method.

        Returns:
            List of scores, one per step.
        """
        self._load_model()

        formatted = format_prm_input(question, steps, self.spec)
        step_boundaries = self._compute_step_boundaries(formatted, steps)

        token_scores = self._forward_pass(formatted)
        step_scores = aggregate_step_scores(token_scores, step_boundaries, method=aggregation)

        if normalize:
            step_scores = normalize_prm_scores(step_scores, method=normalize)

        return step_scores

    def score_trace(
        self,
        question: str,
        full_trace: str,
        spans: list[dict[str, Any]],
        aggregation: str = "mean",
        normalize: str = "sigmoid",
    ) -> list[tuple[str, str, float]]:
        """Score spans in a trace using the frozen PRM.

        Args:
            question: The problem statement.
            full_trace: Full reasoning trace text.
            spans: Span dicts with ``start_token``/``end_token``/``content``.
            aggregation: Score aggregation method.
            normalize: Score normalization method.

        Returns:
            List of (span_content, operation_type, score) tuples.
        """
        self._load_model()

        formatted = format_prm_input(question, [s.get("content", "") for s in spans], self.spec)
        token_scores = self._forward_pass(formatted)

        boundaries = extract_step_boundaries_from_spans(spans)
        step_scores = aggregate_step_scores(token_scores, boundaries, method=aggregation)

        if normalize:
            step_scores = normalize_prm_scores(step_scores, method=normalize)

        results: list[tuple[str, str, float]] = []
        for idx, span in enumerate(spans):
            score = step_scores[idx] if idx < len(step_scores) else 0.0
            content = str(span.get("content", ""))
            op_type = str(span.get("operation_type", "reasoning"))
            results.append((content, op_type, score))

        return results

    def _forward_pass(self, formatted_input: str) -> list[float]:
        """Run a single forward pass and extract per-token scores."""
        import torch

        if self._tokenizer is None or self._model is None:
            raise RuntimeError("Model not loaded. Call _load_model() first.")

        inputs = self._tokenizer(
            formatted_input,
            return_tensors="pt",
            truncation=True,
            max_length=self.spec.max_seq_length,
        )

        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with torch.no_grad():
                outputs = self._model(**inputs)

        logits = outputs.logits[0]

        if logits.shape[-1] == 1:
            scores = logits.squeeze(-1).tolist()
        elif logits.shape[-1] == 2:
            probs = torch.softmax(logits, dim=-1)
            scores = probs[:, 1].tolist()
        else:
            scores = logits.max(dim=-1).values.tolist()

        if isinstance(inputs.get("attention_mask"), torch.Tensor):
            mask = inputs["attention_mask"][0].tolist()
            scores = [s for s, m in zip(scores, mask, strict=False) if m]
        else:
            scores = scores[:len(formatted_input.split())]

        return scores

    def _compute_step_boundaries(
        self,
        formatted: str,
        steps: list[str],
    ) -> list[tuple[int, int]]:
        """Compute token-level boundaries for each step in formatted input."""
        import re

        token_re = re.compile(r"\S+")
        boundaries: list[tuple[int, int]] = []
        search_start = 0

        for step_text in steps:
            if len(step_text) >= 20:
                step_start = formatted.find(step_text[:20], search_start)
            else:
                step_start = formatted.find(step_text, search_start)
            if step_start < 0:
                step_start = search_start
            step_end = step_start + len(step_text)

            prefix_tokens = token_re.findall(formatted[:step_start])
            content_tokens = token_re.findall(step_text)
            boundaries.append((len(prefix_tokens), len(prefix_tokens) + len(content_tokens)))

            search_start = step_end

        return boundaries


class CachedPRMScorer:
    """Wrapper around FrozenPRMScorer that caches results to disk."""

    def __init__(
        self,
        scorer: FrozenPRMScorer,
        cache_path: str | Path | None = None,
    ) -> None:
        self.scorer = scorer
        self.cache_path = Path(cache_path) if cache_path else None
        self._cache: dict[str, list[float]] = {}
        if self.cache_path and self.cache_path.exists():
            self._load_cache()

    def score_steps(
        self,
        question: str,
        steps: list[str],
        **kwargs: Any,
    ) -> list[float]:
        cache_key = self._make_key(question, steps)
        if cache_key in self._cache:
            return self._cache[cache_key]
        scores = self.scorer.score_steps(question, steps, **kwargs)
        self._cache[cache_key] = scores
        self._save_cache()
        return scores

    def _make_key(self, question: str, steps: list[str]) -> str:
        import hashlib

        raw = json.dumps({"q": question, "s": steps}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _load_cache(self) -> None:
        if self.cache_path is None:
            return
        try:
            with self.cache_path.open("r", encoding="utf-8") as handle:
                self._cache = json.load(handle)
        except (json.JSONDecodeError, OSError):
            self._cache = {}

    def _save_cache(self) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("w", encoding="utf-8") as handle:
            json.dump(self._cache, handle)


__all__ = ["CachedPRMScorer", "FrozenPRMScorer"]
