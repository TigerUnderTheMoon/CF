"""Thin OpenAI Responses API adapter with explicit preflight guards."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .schema import structured_output_text_format


@dataclass(frozen=True)
class ApiCallResult:
    output_text: str
    model_name: str
    system_fingerprint: str | None
    usage: dict[str, Any]
    raw_response: Any
    request_metadata: dict[str, Any] = field(default_factory=dict)
    response_id: str | None = None
    output_extraction_diagnostics: dict[str, Any] = field(default_factory=dict)


class OpenAIResponsesAdapter:
    """Small adapter so tests can replace API calls with a fake client."""

    def __init__(self) -> None:
        try:
            import openai
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - environment guard
            raise RuntimeError("openai is required for live API pilot stages.") from exc
        self.openai_version = getattr(openai, "__version__", "unknown")
        self.client = OpenAI()

    def create_trace(
        self,
        *,
        prompt: str,
        config: Mapping[str, Any],
        model_name: str,
        json_mode: bool = False,
    ) -> ApiCallResult:
        request = _request_kwargs(prompt=prompt, config=config, model_name=model_name, json_mode=json_mode)
        seed_requested = "extra_body" in request and "seed" in request.get("extra_body", {})
        reasoning_requested = "reasoning" in request
        errors: list[dict[str, str]] = []
        last_error: Exception | None = None
        for retry_label, candidate in _request_candidates(request):
            try:
                response = self.client.responses.create(**candidate)
            except Exception as exc:
                last_error = exc
                errors.append(
                    {
                        "retry_label": retry_label,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue
            request_metadata = {
                "seed_requested": seed_requested,
                "reasoning_requested": reasoning_requested,
                "optional_fields_stripped_on_retry": retry_label != "full",
                "retry_label": retry_label,
                "retry_errors": errors,
                "seed_sent": "extra_body" in candidate and "seed" in candidate.get("extra_body", {}),
                "reasoning_sent": "reasoning" in candidate,
            }
            return _result_from_response(response, request_metadata=request_metadata)
        if last_error is not None:
            raise last_error
        raise RuntimeError("No OpenAI request candidate was attempted.")


def _request_kwargs(
    *,
    prompt: str,
    config: Mapping[str, Any],
    model_name: str,
    json_mode: bool,
) -> dict[str, Any]:
    model_config = config.get("model", {})
    api_config = config.get("api", {})
    experiment = config.get("experiment", {})
    text_format = {"type": "json_object"} if json_mode else structured_output_text_format()
    kwargs: dict[str, Any] = {
        "model": model_name,
        "input": prompt,
        "temperature": float(model_config.get("temperature", 0.0)),
        "top_p": float(model_config.get("top_p", 1.0)),
        "max_output_tokens": int(model_config.get("max_output_tokens", 2048)),
        "service_tier": api_config.get("service_tier", "default"),
        "store": bool(api_config.get("store", False)),
        "text": {"format": text_format},
        "reasoning": {"effort": model_config.get("reasoning", {}).get("effort", "none")},
        "extra_body": {"seed": int(experiment.get("seed", 20260530))},
    }
    timeout_seconds = api_config.get("request_timeout_seconds")
    if timeout_seconds is not None:
        kwargs["timeout"] = float(timeout_seconds)
    return kwargs


def _request_candidates(request: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    candidates = [("full", dict(request))]
    if "reasoning" in request:
        candidates.append(("without_reasoning", _without_keys(request, "reasoning")))
    if "extra_body" in request:
        candidates.append(("without_seed", _without_keys(request, "extra_body")))
    if "reasoning" in request and "extra_body" in request:
        candidates.append(("without_reasoning_and_seed", _without_keys(request, "reasoning", "extra_body")))
    return candidates


def _without_keys(request: dict[str, Any], *keys: str) -> dict[str, Any]:
    retry = dict(request)
    for key in keys:
        retry.pop(key, None)
    return retry


def _result_from_response(response: Any, *, request_metadata: dict[str, Any]) -> ApiCallResult:
    output_text, output_extraction_diagnostics = extract_response_output_text(response)
    usage = getattr(response, "usage", None)
    if hasattr(usage, "model_dump"):
        usage_payload = usage.model_dump()
    elif isinstance(usage, Mapping):
        usage_payload = dict(usage)
    else:
        usage_payload = {}
    response_id = _string_or_none(getattr(response, "id", None))
    output_extraction_diagnostics = dict(output_extraction_diagnostics)
    output_extraction_diagnostics["usage_present"] = bool(usage_payload)
    output_extraction_diagnostics["response_id_present"] = response_id is not None
    return ApiCallResult(
        output_text=str(output_text or ""),
        model_name=str(getattr(response, "model", "")),
        system_fingerprint=getattr(response, "system_fingerprint", None),
        usage=usage_payload,
        raw_response=response,
        request_metadata=request_metadata,
        response_id=response_id,
        output_extraction_diagnostics=output_extraction_diagnostics,
    )


def _extract_output_text(response: Any) -> str:
    return extract_response_output_text(response)[0]


def extract_response_output_text(response: Any) -> tuple[str, dict[str, Any]]:
    """Extract Responses text from output_text, dict payloads, or typed content objects."""

    direct_output = getattr(response, "output_text", None)
    direct_text = str(direct_output) if direct_output else ""
    diagnostics: dict[str, Any] = {
        "output_text_present": bool(direct_text.strip()),
        "fallback_used": not bool(direct_text.strip()),
        "model_dump_available": hasattr(response, "model_dump"),
        "output_item_count": 0,
        "content_item_count": 0,
        "text_segment_count": 1 if direct_text.strip() else 0,
        "content_item_kinds": [],
        "extracted_text_empty": not bool(direct_text.strip()),
        "response_id_present": _string_or_none(getattr(response, "id", None)) is not None,
        "usage_present": getattr(response, "usage", None) is not None,
    }
    if direct_text.strip():
        return direct_text, diagnostics

    payload = _response_payload(response)
    output_items = _as_list(_get_field(payload, "output"))
    if not output_items:
        output_items = _as_list(_get_field(response, "output"))

    texts: list[str] = []
    content_item_kinds: list[str] = []
    content_count = 0
    for output in output_items:
        content_items = _as_list(_get_field(output, "content"))
        content_count += len(content_items)
        for content in content_items:
            content_item_kinds.append(type(content).__name__)
            text = _get_field(content, "text")
            if text is None:
                text = _get_field(content, "output_text")
            if text is None:
                continue
            text_value = str(text)
            if text_value:
                texts.append(text_value)

    extracted = "\n".join(texts)
    diagnostics.update(
        {
            "output_item_count": len(output_items),
            "content_item_count": content_count,
            "text_segment_count": len(texts),
            "content_item_kinds": content_item_kinds,
            "extracted_text_empty": not bool(extracted.strip()),
        }
    )
    return extracted, diagnostics


def _response_payload(response: Any) -> Any:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if isinstance(response, Mapping):
        return dict(response)
    return response


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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def api_metadata(config: Mapping[str, Any], *, sdk_version: str) -> dict[str, Any]:
    return {
        "endpoint": config.get("api", {}).get("endpoint", "/v1/responses"),
        "api_date": _string_or_none(config.get("api", {}).get("api_date")),
        "sdk_version": sdk_version,
        "text_format": "json_schema",
        "reasoning_effort": config.get("model", {}).get("reasoning", {}).get("effort"),
        "seed": config.get("experiment", {}).get("seed"),
        "service_tier": config.get("api", {}).get("service_tier"),
    }


def _string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)
