from __future__ import annotations

import re

import torch

from fma.replay.counterfactual import (
    ReplayConfig,
    build_prompt,
    detect_reflection_spans,
    is_correct,
    mask_reflection_content_ids,
    normalize_answer,
    replay_record,
    resolve_mask_token_id,
    tokenize_with_offsets,
    token_span_for_char_range,
)


class FakeTokenizer:
    mask_token = "[MASK]"
    unk_token = None
    pad_token = None
    eos_token = "<EOS>"
    eos_token_id = 0
    all_special_ids: list[int] = []

    def __init__(self) -> None:
        self._token_to_id = {self.eos_token: self.eos_token_id}
        self._id_to_token = {self.eos_token_id: self.eos_token}

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        ids = [self._id_for(token) for token, _, _ in self._tokenize(text)]
        if add_special_tokens:
            return [self.eos_token_id, *ids]
        return ids

    def decode(
        self,
        token_ids: list[int],
        skip_special_tokens: bool = False,
        clean_up_tokenization_spaces: bool = False,
    ) -> str:
        tokens = []
        for token_id in token_ids:
            if skip_special_tokens and token_id == self.eos_token_id:
                continue
            tokens.append(self._id_to_token[token_id])
        return " ".join(tokens)

    def __call__(
        self,
        text: str,
        add_special_tokens: bool = False,
        truncation: bool = False,
        max_length: int | None = None,
        return_offsets_mapping: bool = False,
    ) -> dict[str, list]:
        tokenized = self._tokenize(text)
        input_ids = [self._id_for(token) for token, _, _ in tokenized]
        offsets = [(start, end) for _, start, end in tokenized]
        if truncation and max_length is not None:
            input_ids = input_ids[:max_length]
            offsets = offsets[:max_length]
        return {"input_ids": input_ids, "offset_mapping": offsets}

    def get_vocab(self) -> dict[str, int]:
        return dict(self._token_to_id)

    def _id_for(self, token: str) -> int:
        if token not in self._token_to_id:
            token_id = len(self._token_to_id)
            self._token_to_id[token] = token_id
            self._id_to_token[token_id] = token
        return self._token_to_id[token]

    @staticmethod
    def _tokenize(text: str) -> list[tuple[str, int, int]]:
        return [
            (match.group(), match.start(), match.end())
            for match in re.finditer(r"<[^>]+>|[^\s<]+", text)
        ]


class FakeModel:
    def __init__(self, continuation_ids: list[int]) -> None:
        self.continuation_ids = continuation_ids
        self._parameter = torch.nn.Parameter(torch.empty(0))

    def parameters(self):
        return iter([self._parameter])

    def generate(self, input_ids, **kwargs):
        continuation = torch.tensor(
            [self.continuation_ids], dtype=torch.long, device=input_ids.device
        )
        return torch.cat([input_ids, continuation], dim=1)


def test_mask_reflection_content_preserves_token_count_and_marks_span() -> None:
    tokenizer = FakeTokenizer()
    trace = "Work <reflection type='verification'>check arithmetic carefully</reflection> Final Answer: 42"
    original_ids = tokenizer.encode(trace, add_special_tokens=False)

    masked_ids, offsets, spans = mask_reflection_content_ids(
        trace,
        tokenizer,
        resolve_mask_token_id(tokenizer),
    )

    assert len(masked_ids) == len(original_ids)
    assert len(offsets) == len(original_ids)
    assert len(spans) == 1
    assert spans[0]["reflection_type"] == "verification"
    assert spans[0]["content"] == "check arithmetic carefully"
    assert spans[0]["start_token"] == 2
    assert spans[0]["end_token"] == 5
    assert spans[0]["token_count"] == 3


def test_replay_record_masks_first_reflection_and_scores_counterfactual() -> None:
    tokenizer = FakeTokenizer()
    continuation_ids = tokenizer.encode("Then finish. Final Answer: 42", add_special_tokens=False)
    model = FakeModel(continuation_ids)
    record = {
        "sample_id": "gsm8k-1",
        "task_id": "task-1",
        "task_type": "gsm8k",
        "question": "What is 40 + 2?",
        "reasoning_trace": (
            "Compute 40 + 2. "
            "<reflection type='verification'>check arithmetic carefully</reflection> "
            "Final Answer: 42"
        ),
        "final_answer": "42",
        "reference_answer": "#### 42",
    }

    result = replay_record(
        record,
        "Solve:\n{question}",
        tokenizer,
        model,
        ReplayConfig(max_input_tokens=100, max_new_tokens=8, seed=7, model_name_or_path="fake"),
    )

    assert result["status"] == "replayed_with_masking"
    assert result["intervention_preserves_token_count"] is True
    assert result["counterfactual_answer"] == "42"
    assert result["counterfactual_correctness"] is True
    assert result["num_reflection_spans"] == 1
    assert result["masked_reflection_spans"][0]["token_count"] == 3
    assert (
        result["counterfactual_generation_config"]["intervention_point"] == "first_reflection_end"
    )


def test_replay_record_reports_no_reflection_and_truncated_context() -> None:
    tokenizer = FakeTokenizer()
    model = FakeModel(tokenizer.encode("Final Answer: 0", add_special_tokens=False))
    config = ReplayConfig(max_input_tokens=1, max_new_tokens=4, seed=3, model_name_or_path="fake")

    no_reflection = replay_record(
        {
            "sample_id": "plain",
            "question": "No tags?",
            "reasoning_trace": "Reason directly. Final Answer: 5",
            "reference_answer": "5",
        },
        "Template",
        tokenizer,
        model,
        config,
    )
    truncated = replay_record(
        {
            "sample_id": "long",
            "question": "Too long?",
            "reasoning_trace": "<reflection>check</reflection> Final Answer: 1",
            "reference_answer": "1",
        },
        "Template",
        tokenizer,
        model,
        config,
    )

    assert no_reflection["status"] == "no_reflection_found"
    assert no_reflection["original_answer"] == "5"
    assert truncated["status"] == "context_too_long"
    assert truncated["num_reflection_spans"] == 1


def test_prompt_span_and_answer_helpers_cover_default_paths() -> None:
    assert build_prompt("Question: {question}", "2+2?") == "Question: 2+2?"
    assert build_prompt("Solve this", "2+2?") == "Solve this\n\nQuestion:\n2+2?\n"
    assert (
        detect_reflection_spans("<reflection>plain</reflection>")[0]["reflection_type"]
        == "self-reflection"
    )
    assert token_span_for_char_range([(0, 1), (2, 3)], 10, 12) == (2, 2)
    assert normalize_answer("No numeric answer") == "no numeric answer"
    assert is_correct("Final Answer: 1,234", "#### 1234") is True
    assert is_correct("", "#### 1234") is False
    assert is_correct("anything", None) is None


def test_tokenizer_fallback_and_offset_errors_are_explicit() -> None:
    class VocabOnlyTokenizer(FakeTokenizer):
        mask_token = None
        eos_token = None

        def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
            if text == "fallback":
                return super().encode(text, add_special_tokens=add_special_tokens)
            token_id = self._id_for(text)
            piece_id = self._id_for(f"{text}-piece")
            return [token_id, piece_id]

    class NoUsableTokenTokenizer(VocabOnlyTokenizer):
        all_special_ids = [0, 1]

        def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
            return [0, 1]

        def get_vocab(self) -> dict[str, int]:
            return {"<EOS>": 0, "only-special": 1}

    class SlowTokenizer(FakeTokenizer):
        def __call__(self, *args, **kwargs):
            raise NotImplementedError("slow tokenizer")

    vocab_tokenizer = VocabOnlyTokenizer()
    vocab_tokenizer.encode("fallback", add_special_tokens=False)
    assert resolve_mask_token_id(vocab_tokenizer) == vocab_tokenizer.get_vocab()["fallback"]

    try:
        resolve_mask_token_id(NoUsableTokenTokenizer())
    except ValueError as exc:
        assert "single-token mask placeholder" in str(exc)
    else:
        raise AssertionError("resolve_mask_token_id should fail without a usable token")

    try:
        tokenize_with_offsets("text", SlowTokenizer())
    except ValueError as exc:
        assert "fast tokenizer" in str(exc)
    else:
        raise AssertionError("tokenize_with_offsets should require offset mapping")
