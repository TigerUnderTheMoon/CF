"""Counterfactual replay helpers for structure-preserving reflection masking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


REFLECTION_RE = re.compile(
    r"<reflection(?:\s+type=[\"'](?P<type>[^\"']+)[\"'])?\s*>"
    r"(?P<content>.*?)"
    r"</reflection>",
    flags=re.IGNORECASE | re.DOTALL,
)
FINAL_ANSWER_RE = re.compile(r"final\s+answer\s*:\s*(?P<answer>.+)", re.IGNORECASE)
MASK_CANDIDATE_STRINGS = (
    "[MASK]",
    "<mask>",
    "<MASK>",
    ".",
    ",",
    ";",
    ":",
    "!",
    "?",
)


@dataclass(frozen=True)
class ReplayConfig:
    max_input_tokens: int
    max_new_tokens: int
    seed: int
    model_name_or_path: str


def build_prompt(template: str, question: str) -> str:
    if "{question}" in template:
        return template.format(question=question)
    return f"{template.rstrip()}\n\nQuestion:\n{question}\n"


def model_input_device(model: AutoModelForCausalLM) -> torch.device:
    return next(model.parameters()).device


def detect_reflection_spans(text: str) -> list[dict[str, Any]]:
    spans = []
    for match in REFLECTION_RE.finditer(text):
        spans.append(
            {
                "start_char": match.start(),
                "end_char": match.end(),
                "content_start_char": match.start("content"),
                "content_end_char": match.end("content"),
                "reflection_type": (match.group("type") or "self-reflection").strip(),
                "content": match.group("content").strip(),
            }
        )
    return spans


def resolve_mask_token_id(tokenizer: AutoTokenizer) -> int:
    """Pick a single-token placeholder that can stand in for masked content.

    We prefer an existing single-token string rather than adding new vocabulary,
    because the goal is to preserve token length with minimal infrastructure.
    """

    candidate_strings = (
        tokenizer.mask_token,
        tokenizer.unk_token,
        tokenizer.pad_token,
        tokenizer.eos_token,
        *MASK_CANDIDATE_STRINGS,
    )
    seen = set()
    for candidate in candidate_strings:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        token_ids = tokenizer.encode(candidate, add_special_tokens=False)
        if len(token_ids) == 1 and token_ids[0] not in tokenizer.all_special_ids:
            return token_ids[0]

    for token, token_id in tokenizer.get_vocab().items():
        if token_id in tokenizer.all_special_ids:
            continue
        if len(tokenizer.encode(token, add_special_tokens=False)) == 1:
            return token_id

    raise ValueError("Could not resolve a single-token mask placeholder for this tokenizer.")


def tokenize_with_offsets(
    text: str,
    tokenizer: AutoTokenizer,
    max_length: int | None = None,
) -> tuple[list[int], list[tuple[int, int]]]:
    try:
        encoding = tokenizer(
            text,
            add_special_tokens=False,
            truncation=max_length is not None,
            max_length=max_length,
            return_offsets_mapping=True,
        )
    except NotImplementedError as exc:
        raise ValueError(
            "Structure-preserving masking requires a fast tokenizer with offset mapping."
        ) from exc
    return list(encoding["input_ids"]), list(encoding["offset_mapping"])


def token_span_for_char_range(
    offsets: list[tuple[int, int]],
    start_char: int,
    end_char: int,
) -> tuple[int, int]:
    start_token = len(offsets)
    end_token = len(offsets)
    for idx, (token_start, token_end) in enumerate(offsets):
        if token_end > start_char and start_token == len(offsets):
            start_token = idx
        if token_start >= end_char:
            end_token = idx
            break
    if start_token == len(offsets):
        start_token = len(offsets)
    if end_token == len(offsets):
        end_token = len(offsets)
    return start_token, end_token


def mask_reflection_content_ids(
    text: str,
    tokenizer: AutoTokenizer,
    mask_token_id: int,
    max_length: int | None = None,
) -> tuple[list[int], list[tuple[int, int]], list[dict[str, Any]]]:
    token_ids, offsets = tokenize_with_offsets(text, tokenizer, max_length=max_length)
    masked_ids = list(token_ids)
    detected_spans = detect_reflection_spans(text)

    masked_spans: list[dict[str, Any]] = []
    for span in detected_spans:
        content_start_token, content_end_token = token_span_for_char_range(
            offsets,
            span["content_start_char"],
            span["content_end_char"],
        )
        token_count = max(0, content_end_token - content_start_token)
        if token_count > 0:
            masked_ids[content_start_token:content_end_token] = [mask_token_id] * token_count
        masked_spans.append(
            {
                **span,
                "start_token": content_start_token,
                "end_token": content_end_token,
                "token_count": token_count,
            }
        )

    return masked_ids, offsets, masked_spans


def extract_final_answer(text: str) -> str:
    matches = list(FINAL_ANSWER_RE.finditer(text))
    if matches:
        return matches[-1].group("answer").strip()
    return ""


def count_tokens(text: str, tokenizer: AutoTokenizer) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))


def generate_continuation_from_ids(
    context_ids: list[int],
    tokenizer: AutoTokenizer,
    model: AutoModelForCausalLM,
    config: ReplayConfig,
) -> tuple[list[int], str]:
    input_ids = torch.tensor([context_ids], dtype=torch.long, device=model_input_device(model))
    attention_mask = torch.ones_like(input_ids)

    # Replay assumption: greedy decoding with fixed model weights/tokenizer gives
    # a deterministic continuation from the intervened observable context.
    with torch.no_grad():
        generated = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=config.max_new_tokens,
            do_sample=False,
            temperature=0.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    new_tokens = generated[0, input_ids.shape[1] :].tolist()
    return new_tokens, tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def build_no_reflection_result(record: dict[str, Any], tokenizer: AutoTokenizer) -> dict[str, Any]:
    original_trace = record.get("reasoning_trace", "")
    original_token_count = count_tokens(original_trace, tokenizer)
    return {
        "task_id": record.get("task_id", ""),
        "status": "no_reflection_found",
        "original_answer": record.get("final_answer") or extract_final_answer(original_trace),
        "counterfactual_answer": None,
        "token_length_difference": None,
        "original_token_count": original_token_count,
        "counterfactual_token_count": None,
        "num_reflection_spans": 0,
    }


def build_truncated_result(record: dict[str, Any], tokenizer: AutoTokenizer) -> dict[str, Any]:
    original_trace = record.get("reasoning_trace", "")
    return {
        "task_id": record.get("task_id", ""),
        "status": "context_too_long",
        "original_answer": record.get("final_answer") or extract_final_answer(original_trace),
        "counterfactual_answer": None,
        "token_length_difference": None,
        "original_token_count": count_tokens(original_trace, tokenizer),
        "counterfactual_token_count": None,
        "num_reflection_spans": len(detect_reflection_spans(original_trace)),
    }


def replay_record(
    record: dict[str, Any],
    prompt_template: str,
    tokenizer: AutoTokenizer,
    model: AutoModelForCausalLM,
    config: ReplayConfig,
) -> dict[str, Any]:
    question = record["question"]
    original_trace = record.get("reasoning_trace", "")
    detected_spans = detect_reflection_spans(original_trace)

    if not detected_spans:
        return build_no_reflection_result(record, tokenizer)

    mask_token_id = resolve_mask_token_id(tokenizer)
    masked_ids, offsets, masked_spans = mask_reflection_content_ids(
        original_trace,
        tokenizer,
        mask_token_id,
        max_length=None,
    )
    _, first_block_end = token_span_for_char_range(
        offsets,
        detected_spans[0]["start_char"],
        detected_spans[0]["end_char"],
    )
    replay_prefix_ids = masked_ids[:first_block_end]

    base_prompt = build_prompt(prompt_template, question)
    prompt_ids = tokenizer.encode(base_prompt, add_special_tokens=True)
    generation_context_ids = prompt_ids + replay_prefix_ids
    if len(generation_context_ids) > config.max_input_tokens:
        return build_truncated_result(record, tokenizer)

    # Intervention logic: the reflection content is replaced with a
    # length-matched placeholder so the trace stays token-aligned. We then
    # replay from the end of the first masked reflection block.
    counterfactual_continuation_ids, counterfactual_continuation = generate_continuation_from_ids(
        generation_context_ids,
        tokenizer,
        model,
        config,
    )
    counterfactual_trace = tokenizer.decode(
        replay_prefix_ids,
        skip_special_tokens=False,
        clean_up_tokenization_spaces=False,
    ).strip()
    if counterfactual_continuation:
        counterfactual_trace = f"{counterfactual_trace}\n{counterfactual_continuation}".strip()

    original_token_count = count_tokens(original_trace, tokenizer)
    counterfactual_token_count = len(replay_prefix_ids) + len(counterfactual_continuation_ids)
    original_answer = record.get("final_answer") or extract_final_answer(original_trace)
    counterfactual_answer = extract_final_answer(counterfactual_trace)

    # Causal limitation: this is an intervention-sensitive contrast, not a
    # globally identifiable causal quantity. The result depends on the prompt,
    # model, tokenizer, context window, and the observable trace prefix.
    return {
        "task_id": record.get("task_id", ""),
        "status": "replayed_with_masking",
        "question": question,
        "original_answer": original_answer,
        "counterfactual_answer": counterfactual_answer,
        "token_length_difference": counterfactual_token_count - original_token_count,
        "original_token_count": original_token_count,
        "counterfactual_token_count": counterfactual_token_count,
        "masked_trace_token_count": len(masked_ids),
        "intervention_preserves_token_count": len(masked_ids) == original_token_count,
        "num_reflection_spans": len(detected_spans),
        "masked_reflection_spans": masked_spans,
        "original_trace": original_trace,
        "masked_trace": tokenizer.decode(
            masked_ids,
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        ).strip(),
        "counterfactual_trace": counterfactual_trace,
        "counterfactual_generation_config": {
            "intervention": "length_preserving_reflection_masking_then_regenerate",
            "intervention_point": "first_reflection_end",
            "temperature": 0.0,
            "do_sample": False,
            "seed": config.seed,
            "max_new_tokens": config.max_new_tokens,
            "max_input_tokens": config.max_input_tokens,
            "model_name_or_path": config.model_name_or_path,
            "mask_token_id": mask_token_id,
        },
    }
