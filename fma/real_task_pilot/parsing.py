"""Parsing helpers for observable traces and reflection tags."""

from __future__ import annotations

import json
import re
from typing import Any


REFLECTION_RE = re.compile(
    r"<reflection(?:\s+type=[\"'](?P<type>[^\"']+)[\"'])?\s*>"
    r"(?P<content>.*?)"
    r"</reflection>",
    flags=re.IGNORECASE | re.DOTALL,
)
FINAL_ANSWER_RE = re.compile(r"final\s+answer\s*:\s*(?P<answer>.+)", re.IGNORECASE)
TOKEN_RE = re.compile(r"\S+")


def parse_json_object(value: Any) -> dict[str, Any] | None:
    """Parse a JSON object from SDK content, raw text, or fenced JSON."""

    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def proxy_token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def _proxy_token_start(text: str, char_offset: int) -> int:
    return proxy_token_count(text[:char_offset])


def extract_reflection_spans(text: str) -> list[dict[str, Any]]:
    """Extract visible reflection tags with char and proxy-token offsets."""

    spans: list[dict[str, Any]] = []
    for index, match in enumerate(REFLECTION_RE.finditer(text)):
        raw_content = match.group("content")
        leading_chars = len(raw_content) - len(raw_content.lstrip())
        trailing_chars = len(raw_content) - len(raw_content.rstrip())
        content_start = match.start("content") + leading_chars
        content_end = match.end("content") - trailing_chars
        operation_type = (match.group("type") or "self-reflection").strip()
        if operation_type == "error-diagnosis":
            operation_type = "error_diagnosis"
        elif operation_type == "plan-revision":
            operation_type = "plan_revision"
        elif operation_type == "strategy-critique":
            operation_type = "strategy_critique"
        spans.append(
            {
                "span_index": index,
                "start_char": match.start(),
                "end_char": match.end(),
                "content_start_char": content_start,
                "content_end_char": content_end,
                "start_token": _proxy_token_start(text, content_start),
                "end_token": _proxy_token_start(text, content_end),
                "operation_type": operation_type,
                "content": text[content_start:content_end],
            }
        )
    return spans


def extract_final_answer(text: str) -> str:
    matches = list(FINAL_ANSWER_RE.finditer(text))
    return matches[-1].group("answer").strip() if matches else ""
