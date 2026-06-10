"""Perplexity-based PRM proxy using freely available base LMs.

When trained PRMs (Qwen2.5-Math-PRM, Math-Shepherd) are unavailable
due to gated access, this module provides a lightweight substitute:
step-level scoring via perplexity of the step text conditional on the
question and previous steps.

Theory: steps that are "surprising" given the context (high perplexity)
are more likely to be erroneous or out-of-distribution.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import numpy as np

from .registry import PRMModelSpec

logger = logging.getLogger(__name__)

FREELY_AVAILABLE_LMS: dict[str, PRMModelSpec] = {
    "Qwen2.5-0.5B": PRMModelSpec(
        model_name="Qwen2.5-0.5B",
        hf_id="Qwen/Qwen2.5-0.5B",
        model_type="base_lm",
        input_format="chain",
        score_per="step",
        max_seq_length=2048,
    ),
    "Qwen2.5-0.5B-Instruct": PRMModelSpec(
        model_name="Qwen2.5-0.5B-Instruct",
        hf_id="Qwen/Qwen2.5-0.5B-Instruct",
        model_type="base_lm",
        input_format="chain",
        score_per="step",
        max_seq_length=2048,
    ),
}


class PerplexityPRMScorer:
    """Score steps using conditional perplexity from a base LM.

    Lower perplexity = higher quality (the step is predictable given
    the context).  Scores are normalized to [0, 1] with
    1 = lowest perplexity (best step).
    """

    def __init__(
        self,
        model_name: str = "Qwen2.5-0.5B-Instruct",
        device: str = "auto",
        cache_dir: str | None = None,
    ) -> None:
        self.model_name = model_name
        if model_name not in FREELY_AVAILABLE_LMS:
            available = ", ".join(sorted(FREELY_AVAILABLE_LMS))
            raise ValueError(
                f"Unknown free LM {model_name!r}. Available: {available}"
            )
        self.spec = FREELY_AVAILABLE_LMS[model_name]
        self.device = device
        self.cache_dir = cache_dir
        self._model = None
        self._tokenizer = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "Perplexity PRM requires torch and transformers."
            ) from exc

        logger.info("Loading %s for perplexity-based PRM", self.spec.hf_id)
        model_kwargs: dict[str, Any] = {}
        if self.device == "auto":
            model_kwargs["device_map"] = "auto"
            model_kwargs["torch_dtype"] = torch.float16

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.spec.hf_id,
            trust_remote_code=False,
            cache_dir=self.cache_dir,
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        self._model = AutoModelForCausalLM.from_pretrained(
            self.spec.hf_id,
            trust_remote_code=False,
            **model_kwargs,
        )
        self._model.eval()
        logger.info("Perplexity PRM model loaded")

    def score_steps(
        self,
        question: str,
        steps: list[str],
        normalize: str = "invert_sigmoid",
    ) -> list[float]:
        """Score steps via conditional perplexity.

        Args:
            question: Problem statement.
            steps: List of step texts.
            normalize: How to convert perplexity to [0,1] score.

        Returns:
            List of scores in [0, 1] (1 = best).
        """
        self._load_model()

        perplexities = self._compute_step_perplexities(question, steps)
        return self._normalize_perplexities(perplexities, method=normalize)

    def score_trace(
        self,
        question: str,
        full_trace: str,
        spans: list[dict[str, Any]],
        normalize: str = "invert_sigmoid",
    ) -> list[tuple[str, str, float]]:
        """Score spans in a trace via conditional perplexity."""
        self._load_model()

        steps = [str(s.get("content", "")) for s in spans]
        perplexities = self._compute_step_perplexities(question, steps)
        scores = self._normalize_perplexities(perplexities, method=normalize)

        results: list[tuple[str, str, float]] = []
        for idx, span in enumerate(spans):
            score = scores[idx] if idx < len(scores) else 0.5
            content = str(span.get("content", ""))
            op_type = str(span.get("operation_type", "reasoning"))
            results.append((content, op_type, score))

        return results

    def _compute_step_perplexities(
        self,
        question: str,
        steps: list[str],
    ) -> list[float]:
        """Compute perplexity for each step conditioned on prior context."""
        import torch

        if self._tokenizer is None or self._model is None:
            raise RuntimeError("Model not loaded")

        token_re = re.compile(r"\S+")
        perplexities: list[float] = []

        context = question
        for step in steps:
            full_text = context + "\n" + step
            encoded = self._tokenizer(
                full_text,
                return_tensors="pt",
                truncation=True,
                max_length=self.spec.max_seq_length,
            )
            device = next(self._model.parameters()).device
            encoded = {k: v.to(device) for k, v in encoded.items()}

            with torch.no_grad():
                outputs = self._model(**encoded, labels=encoded["input_ids"])

            loss = outputs.loss
            if loss is not None:
                nll = float(loss.item())
                token_count = max(1, len(token_re.findall(step)))
                ppl = np.exp(nll / token_count)
                perplexities.append(ppl)
            else:
                perplexities.append(1.0)

            context = full_text

        return perplexities

    def _normalize_perplexities(
        self,
        perplexities: list[float],
        method: str = "invert_sigmoid",
    ) -> list[float]:
        """Convert perplexity values to [0, 1] quality scores."""
        if not perplexities:
            return []

        if method == "invert_sigmoid":
            scores = [1.0 / (1.0 + np.log1p(p)) for p in perplexities]
        elif method == "invert_minmax":
            min_p = min(perplexities)
            max_p = max(perplexities)
            if max_p == min_p:
                return [0.5] * len(perplexities)
            scores = [
                (max_p - p) / (max_p - min_p) for p in perplexities
            ]
        elif method == "rank":
            ranked = sorted(range(len(perplexities)), key=lambda i: perplexities[i])
            ranks = [0.0] * len(perplexities)
            for rank, idx in enumerate(ranked):
                ranks[idx] = 1.0 - rank / max(1, len(perplexities) - 1)
            return ranks
        else:
            raise ValueError(f"Unknown normalize method: {method!r}")

        return [min(1.0, max(0.0, s)) for s in scores]


__all__ = ["FREELY_AVAILABLE_LMS", "PerplexityPRMScorer"]
