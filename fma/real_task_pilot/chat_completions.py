"""Direct Chat Completions adapter for guarded real_task_v3 execution."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .openai_client import ApiCallResult


DEFAULT_CHAT_COMPLETIONS_ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"
DEFAULT_V3_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True)
class ChatCompletionsRequest:
    endpoint: str
    model: str
    prompt: str
    temperature: float
    max_tokens: int
    response_format: dict[str, str]


class ChatCompletionsAdapter:
    """Small direct HTTP adapter for OpenAI-compatible chat completions."""

    openai_version = "chat-completions-direct"

    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_CHAT_COMPLETIONS_ENDPOINT,
        api_key: str | None = None,
        transport: Callable[[str, dict[str, Any], Mapping[str, str], float], Mapping[str, Any]]
        | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.transport = transport or _post_json

    def create_trace(
        self,
        *,
        prompt: str,
        config: Mapping[str, Any],
        model_name: str,
        json_mode: bool = False,
    ) -> ApiCallResult:
        request = _chat_request(prompt=prompt, config=config, model_name=model_name)
        request = ChatCompletionsRequest(
            endpoint=self.endpoint,
            model=request.model,
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            response_format=request.response_format,
        )
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        timeout = float(config.get("api", {}).get("request_timeout_seconds", 90))
        try:
            payload = self.transport(self.endpoint, _request_payload(request), headers, timeout)
        except urllib.error.URLError as exc:
            raise RuntimeError(f"chat_completions_infra_error:{exc}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"chat_completions_infra_error:{exc}") from exc
        return _result_from_chat_payload(payload, request=request)


def _chat_request(
    *,
    prompt: str,
    config: Mapping[str, Any],
    model_name: str,
) -> ChatCompletionsRequest:
    model_config = config.get("model", {}) if isinstance(config.get("model"), Mapping) else {}
    api_config = config.get("api", {}) if isinstance(config.get("api"), Mapping) else {}
    endpoint = str(api_config.get("chat_completions_endpoint") or DEFAULT_CHAT_COMPLETIONS_ENDPOINT)
    return ChatCompletionsRequest(
        endpoint=endpoint,
        model=str(model_name or model_config.get("primary") or DEFAULT_V3_MODEL),
        prompt=prompt,
        temperature=float(model_config.get("temperature", 0.0) or 0.0),
        max_tokens=int(model_config.get("max_output_tokens", 2048) or 2048),
        response_format={"type": "json_object"},
    )


def _request_payload(request: ChatCompletionsRequest) -> dict[str, Any]:
    return {
        "model": request.model,
        "messages": [{"role": "user", "content": request.prompt}],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "response_format": request.response_format,
    }


def _post_json(
    endpoint: str,
    payload: dict[str, Any],
    headers: Mapping[str, str],
    timeout: float,
) -> Mapping[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(endpoint, data=data, headers=dict(headers), method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _result_from_chat_payload(
    payload: Mapping[str, Any],
    *,
    request: ChatCompletionsRequest,
) -> ApiCallResult:
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    first_choice = choices[0] if choices else {}
    message = first_choice.get("message") if isinstance(first_choice, Mapping) else {}
    output_text = ""
    if isinstance(message, Mapping):
        output_text = str(message.get("content") or "")
    usage = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
    return ApiCallResult(
        output_text=output_text,
        model_name=str(payload.get("model") or request.model),
        system_fingerprint=(
            None
            if payload.get("system_fingerprint") is None
            else str(payload.get("system_fingerprint"))
        ),
        usage=dict(usage),
        raw_response=dict(payload),
        request_metadata={
            "adapter": "chat_completions_direct",
            "endpoint": request.endpoint,
            "json_mode_requested": True,
        },
        response_id=None if payload.get("id") is None else str(payload.get("id")),
        output_extraction_diagnostics={
            "output_text_present": bool(output_text.strip()),
            "chat_choices_present": bool(choices),
            "usage_present": bool(usage),
            "response_id_present": payload.get("id") is not None,
        },
    )


__all__ = [
    "ChatCompletionsAdapter",
    "DEFAULT_CHAT_COMPLETIONS_ENDPOINT",
    "DEFAULT_V3_MODEL",
]
