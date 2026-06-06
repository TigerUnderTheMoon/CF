"""Auditable LLM API clients for pilot stages."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .cache import APICache
from .resilience import (
    CircuitBreaker,
    CostTracker,
    DriftDetector,
    retry_with_exponential_backoff,
)


@dataclass(frozen=True)
class APIResponse:
    raw_output: str
    model_name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    cached: bool = False
    raw_response: Any = None


class BaseAPIClient(ABC):
    @abstractmethod
    def chat_complete(self, prompt: str, **kwargs: Any) -> APIResponse:
        """Return one model completion for ``prompt``."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether the backend is reachable."""


class OpenAIClient(BaseAPIClient):
    """OpenAI SDK client with cache, retry, circuit breaker, and cost guards."""

    openai_version = "unknown"

    def __init__(
        self,
        *,
        model_name: str,
        sdk_client: Any | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        azure_endpoint: str | None = None,
        azure_deployment: str | None = None,
        api_version: str | None = None,
        endpoint: str = "responses",
        cache: APICache | None = None,
        cache_enabled: bool = True,
        cost_tracker: CostTracker | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        drift_detector: DriftDetector | None = None,
        pricing: Mapping[str, float] | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        sleep: Callable[[float], None] | None = None,
        timeout: float | None = None,
    ) -> None:
        self.model_name = model_name
        self.azure_deployment = azure_deployment
        self.endpoint = endpoint
        self.cache = cache if cache is not None else APICache(enabled=cache_enabled)
        self.cost_tracker = cost_tracker or CostTracker(
            cost_ceiling_usd=_float_env("COST_CEILING_USD")
        )
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.drift_detector = drift_detector
        self.pricing = dict(pricing or {})
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.sleep = sleep
        self.timeout = timeout
        self.client = sdk_client if sdk_client is not None else self._build_sdk_client(
            api_key=api_key,
            base_url=base_url,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
        )

    def chat_complete(self, prompt: str, **kwargs: Any) -> APIResponse:
        model_name = str(kwargs.get("model_name") or self.azure_deployment or self.model_name)
        temperature = float(kwargs.get("temperature", 0.0))
        top_p = float(kwargs.get("top_p", 1.0))
        seed = _optional_int(kwargs.get("seed"))
        max_output_tokens = int(kwargs.get("max_output_tokens", 2048))
        cache_entry = self.cache.get(
            prompt=prompt,
            model_name=model_name,
            temperature=temperature,
            seed=seed,
            top_p=top_p,
        )
        if cache_entry is not None:
            return APIResponse(
                raw_output=cache_entry.raw_output,
                model_name=str(cache_entry.metadata.get("model_name") or model_name),
                metadata=dict(cache_entry.metadata),
                usage=dict(cache_entry.metadata.get("usage") or {}),
                cost_usd=cache_entry.cost_usd,
                cached=True,
            )

        self.cost_tracker.check_before_request()
        request = self._request_payload(
            prompt=prompt,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_output_tokens=max_output_tokens,
            kwargs=kwargs,
        )

        def operation() -> Any:
            self.circuit_breaker.before_call()
            try:
                response = self._create(request=request, use_chat=self._uses_chat_endpoint())
            except Exception:
                self.circuit_breaker.record_failure()
                raise
            self.circuit_breaker.record_success()
            return response

        response = retry_with_exponential_backoff(
            operation,
            max_retries=self.max_retries,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            sleep=self.sleep or _sleep_noop_if_none,
        )
        api_response = self._normalize_response(
            response,
            model_name=model_name,
            request_metadata=dict(kwargs.get("request_metadata") or {}),
        )
        if self.drift_detector is not None:
            self.drift_detector.validate(
                api_response.raw_output,
                metadata={"model_name": api_response.model_name, **api_response.metadata},
            )
        self.cost_tracker.record_cost(api_response.cost_usd)
        self.cache.set(
            prompt=prompt,
            model_name=model_name,
            temperature=temperature,
            seed=seed,
            top_p=top_p,
            raw_output=api_response.raw_output,
            metadata={**api_response.metadata, "model_name": api_response.model_name, "usage": api_response.usage},
            cost_usd=api_response.cost_usd,
        )
        return api_response

    def health_check(self) -> bool:
        try:
            models = getattr(self.client, "models", None)
            if models is not None and hasattr(models, "list"):
                models.list()
                return True
        except Exception:
            return False
        return True

    def _build_sdk_client(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        azure_endpoint: str | None,
        api_version: str | None,
    ) -> Any:
        try:
            import openai
            from openai import AzureOpenAI, OpenAI
        except ImportError as exc:  # pragma: no cover - environment guard
            raise RuntimeError("openai is required for live API pilot stages.") from exc
        self.openai_version = getattr(openai, "__version__", "unknown")
        if azure_endpoint:
            return AzureOpenAI(
                api_key=api_key or os.environ.get("AZURE_OPENAI_API_KEY"),
                azure_endpoint=azure_endpoint,
                api_version=api_version or os.environ.get("AZURE_OPENAI_API_VERSION"),
            )
        return OpenAI(api_key=api_key, base_url=base_url)

    def _request_payload(
        self,
        *,
        prompt: str,
        model_name: str,
        temperature: float,
        top_p: float,
        seed: int | None,
        max_output_tokens: int,
        kwargs: Mapping[str, Any],
    ) -> dict[str, Any]:
        request_overrides = dict(kwargs.get("request_overrides") or {})
        if request_overrides:
            return request_overrides
        if self._uses_chat_endpoint():
            request = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_output_tokens,
            }
            if seed is not None:
                request["seed"] = seed
            if self.timeout is not None:
                request["timeout"] = self.timeout
            return request
        request = {
            "model": model_name,
            "input": prompt,
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
        }
        if seed is not None:
            request["extra_body"] = {"seed": seed}
        if self.timeout is not None:
            request["timeout"] = self.timeout
        return request

    def _uses_chat_endpoint(self) -> bool:
        return self.endpoint in {"chat_completions", "/v1/chat/completions", "chat"}

    def _create(self, *, request: Mapping[str, Any], use_chat: bool) -> Any:
        if use_chat:
            return self.client.chat.completions.create(**dict(request))
        return self.client.responses.create(**dict(request))

    def _normalize_response(
        self,
        response: Any,
        *,
        model_name: str,
        request_metadata: Mapping[str, Any],
    ) -> APIResponse:
        raw_output, extraction_diagnostics = _extract_any_output_text(response)
        usage = _extract_usage(response)
        cost_usd = _estimate_cost_usd(usage, self.pricing)
        response_id = _string_or_none(_get_field(response, "id"))
        metadata = {
            "request_metadata": dict(request_metadata),
            "system_fingerprint": _string_or_none(_get_field(response, "system_fingerprint")),
            "response_id": response_id,
            "output_extraction_diagnostics": extraction_diagnostics,
            "usage": usage,
        }
        return APIResponse(
            raw_output=raw_output,
            model_name=str(_get_field(response, "model") or model_name),
            metadata=metadata,
            usage=usage,
            cost_usd=cost_usd,
            raw_response=response,
        )


class VLLMClient(BaseAPIClient):
    """OpenAI-compatible chat completions client for local vLLM servers."""

    openai_version = "vllm-openai-compatible"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8000",
        model_name: str,
        api_key: str | None = None,
        cache: APICache | None = None,
        cache_enabled: bool = True,
        cost_tracker: CostTracker | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        drift_detector: DriftDetector | None = None,
        transport: Callable[[str, dict[str, Any], Mapping[str, str], float], Mapping[str, Any]] | None = None,
        timeout: float = 90.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("VLLM_API_KEY", "")
        self.cache = cache if cache is not None else APICache(enabled=cache_enabled)
        self.cost_tracker = cost_tracker or CostTracker(cost_ceiling_usd=_float_env("COST_CEILING_USD"))
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.drift_detector = drift_detector
        self.transport = transport or _post_json
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.sleep = sleep

    def chat_complete(self, prompt: str, **kwargs: Any) -> APIResponse:
        model_name = str(kwargs.get("model_name") or self.model_name)
        temperature = float(kwargs.get("temperature", 0.0))
        top_p = float(kwargs.get("top_p", 1.0))
        seed = _optional_int(kwargs.get("seed"))
        cache_entry = self.cache.get(
            prompt=prompt,
            model_name=model_name,
            temperature=temperature,
            seed=seed,
            top_p=top_p,
        )
        if cache_entry is not None:
            return APIResponse(
                raw_output=cache_entry.raw_output,
                model_name=str(cache_entry.metadata.get("model_name") or model_name),
                metadata=dict(cache_entry.metadata),
                usage=dict(cache_entry.metadata.get("usage") or {}),
                cost_usd=cache_entry.cost_usd,
                cached=True,
            )

        self.cost_tracker.check_before_request()
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": int(kwargs.get("max_output_tokens", kwargs.get("max_tokens", 2048))),
        }
        if seed is not None:
            payload["seed"] = seed
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.base_url}/v1/chat/completions"

        def operation() -> Mapping[str, Any]:
            self.circuit_breaker.before_call()
            try:
                response_payload = self.transport(url, payload, headers, self.timeout)
            except Exception:
                self.circuit_breaker.record_failure()
                raise
            self.circuit_breaker.record_success()
            return response_payload

        response_payload = retry_with_exponential_backoff(
            operation,
            max_retries=self.max_retries,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            sleep=self.sleep or _sleep_noop_if_none,
        )
        raw_output = _extract_chat_payload_text(response_payload)
        usage = dict(response_payload.get("usage") or {})
        metadata = {
            "request_metadata": dict(kwargs.get("request_metadata") or {}),
            "response_id": _string_or_none(response_payload.get("id")),
            "system_fingerprint": _string_or_none(response_payload.get("system_fingerprint")),
            "usage": usage,
            "backend": "vllm",
        }
        response = APIResponse(
            raw_output=raw_output,
            model_name=str(response_payload.get("model") or model_name),
            metadata=metadata,
            usage=usage,
            cost_usd=0.0,
            raw_response=dict(response_payload),
        )
        if self.drift_detector is not None:
            self.drift_detector.validate(response.raw_output, metadata=response.metadata)
        self.cache.set(
            prompt=prompt,
            model_name=model_name,
            temperature=temperature,
            seed=seed,
            top_p=top_p,
            raw_output=response.raw_output,
            metadata={**response.metadata, "model_name": response.model_name},
            cost_usd=response.cost_usd,
        )
        return response

    def health_check(self) -> bool:
        try:
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": "health_check"}],
                "temperature": 0.0,
                "max_tokens": 1,
            }
            self.transport(f"{self.base_url}/v1/chat/completions", payload, {"Content-Type": "application/json"}, 5.0)
        except Exception:
            return False
        return True


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: Mapping[str, str],
    timeout: float,
) -> Mapping[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"api_transport_error:{exc}") from exc


def _extract_any_output_text(response: Any) -> tuple[str, dict[str, Any]]:
    direct_output = _get_field(response, "output_text")
    direct_text = str(direct_output) if direct_output else ""
    diagnostics: dict[str, Any] = {
        "output_text_present": bool(direct_text.strip()),
        "fallback_used": not bool(direct_text.strip()),
        "output_item_count": 0,
        "content_item_count": 0,
        "text_segment_count": 1 if direct_text.strip() else 0,
        "extracted_text_empty": not bool(direct_text.strip()),
    }
    if direct_text.strip():
        return direct_text, diagnostics

    payload = _model_dump_or_mapping(response)
    chat_text = _extract_chat_payload_text(payload) if isinstance(payload, Mapping) else ""
    if chat_text:
        diagnostics.update({"text_segment_count": 1, "extracted_text_empty": False})
        return chat_text, diagnostics

    output_items = _as_list(_get_field(payload, "output")) or _as_list(_get_field(response, "output"))
    texts: list[str] = []
    content_count = 0
    for output in output_items:
        content_items = _as_list(_get_field(output, "content"))
        content_count += len(content_items)
        for content in content_items:
            text = _get_field(content, "text")
            if text is None:
                text = _get_field(content, "output_text")
            if text:
                texts.append(str(text))
    extracted = "\n".join(texts)
    diagnostics.update(
        {
            "output_item_count": len(output_items),
            "content_item_count": content_count,
            "text_segment_count": len(texts),
            "extracted_text_empty": not bool(extracted.strip()),
        }
    )
    return extracted, diagnostics


def _extract_chat_payload_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    if not choices:
        return ""
    first = choices[0]
    if not isinstance(first, Mapping):
        return ""
    message = first.get("message")
    if isinstance(message, Mapping):
        return str(message.get("content") or "")
    text = first.get("text")
    return "" if text is None else str(text)


def _extract_usage(response: Any) -> dict[str, Any]:
    usage = _get_field(response, "usage")
    if hasattr(usage, "model_dump"):
        payload = usage.model_dump()
        return dict(payload) if isinstance(payload, Mapping) else {}
    if isinstance(usage, Mapping):
        return dict(usage)
    return {}


def _estimate_cost_usd(usage: Mapping[str, Any], pricing: Mapping[str, float]) -> float:
    input_tokens = float(usage.get("input_tokens") or usage.get("prompt_tokens") or 0.0)
    output_tokens = float(usage.get("output_tokens") or usage.get("completion_tokens") or 0.0)
    input_rate = float(pricing.get("input_per_million_usd") or pricing.get("prompt_per_million_usd") or 0.0)
    output_rate = float(pricing.get("output_per_million_usd") or pricing.get("completion_per_million_usd") or 0.0)
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def _get_field(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    if hasattr(value, key):
        return getattr(value, key)
    if hasattr(value, "model_dump"):
        payload = value.model_dump()
        if isinstance(payload, Mapping):
            return payload.get(key)
    return None


def _model_dump_or_mapping(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _float_env(name: str) -> float | None:
    value = os.environ.get(name)
    if not value:
        return None
    return float(value)


def _sleep_noop_if_none(seconds: float) -> None:
    time_sleep = __import__("time").sleep
    time_sleep(seconds)


__all__ = ["APIResponse", "BaseAPIClient", "OpenAIClient", "VLLMClient"]
