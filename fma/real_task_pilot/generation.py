"""Generation orchestration for real-task observable traces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .metrics import score_answer
from .openai_client import ApiCallResult
from .parsing import extract_final_answer, extract_reflection_spans, parse_json_object
from .schema import validate_trace_record


class TraceAdapter(Protocol):
    openai_version: str

    def create_trace(
        self,
        *,
        prompt: str,
        config: Mapping[str, Any],
        model_name: str,
        json_mode: bool = False,
    ) -> ApiCallResult:
        ...


@dataclass(frozen=True)
class GeneratedTraceResult:
    record: dict[str, Any] | None
    raw_output: str
    model_name: str
    structured_output_mode: str
    system_fingerprint: str | None
    usage: dict[str, Any]
    validation_errors: list[str]
    fallback_events: list[dict[str, Any]]
    response_id: str | None = None


def build_generation_prompt(template: str, sample: Mapping[str, Any]) -> str:
    return template.format(
        sample_id=sample.get("sample_id", ""),
        task_type=sample.get("task_type", ""),
        question=sample.get("question", ""),
        reference_answer=sample.get("reference_answer", ""),
        observable_prefix=sample.get("observable_prefix", ""),
    )


def load_prompt_template(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def generate_trace_with_fallback(
    sample: Mapping[str, Any],
    *,
    adapter: TraceAdapter,
    config: Mapping[str, Any],
    prompt_template: str,
) -> GeneratedTraceResult:
    """Generate one trace, trying primary/fallback models and JSON mode."""

    prompt = build_generation_prompt(prompt_template, sample)
    fallback_order = _fallback_order(config)
    events: list[dict[str, Any]] = []
    last_raw = ""
    last_model = fallback_order[0]
    last_usage: dict[str, Any] = {}
    last_fingerprint: str | None = None
    last_errors: list[str] = []
    last_mode = "unavailable"
    for json_mode in (False, True):
        for model_name in fallback_order:
            mode_name = "json_object" if json_mode else "json_schema"
            last_mode = mode_name
            try:
                response = adapter.create_trace(
                    prompt=prompt,
                    config=config,
                    model_name=model_name,
                    json_mode=json_mode,
                )
            except Exception as exc:
                events.append(
                    {
                        "model_name": model_name,
                        "structured_output_mode": mode_name,
                        "status": "api_error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue
            last_raw = response.output_text
            last_model = response.model_name or model_name
            last_usage = response.usage
            last_fingerprint = response.system_fingerprint
            parsed = parse_json_object(response.output_text)
            if parsed is None:
                last_errors = ["<root>: response is not a JSON object"]
            else:
                record = normalize_trace_record(
                    parsed,
                    sample=sample,
                    model_name=last_model,
                    generation_config=_generation_config(
                        config,
                        adapter_version=adapter.openai_version,
                        structured_output_mode=mode_name,
                        api_request_metadata=response.request_metadata,
                        api_response_id=response.response_id,
                    ),
                    system_fingerprint=last_fingerprint,
                    usage=last_usage,
                )
                last_errors = validate_trace_record(record)
                if not last_errors:
                    events.append(
                        {
                            "model_name": model_name,
                            "structured_output_mode": mode_name,
                            "status": "selected",
                            "lower_confidence": json_mode,
                        }
                    )
                    return GeneratedTraceResult(
                        record=record,
                        raw_output=response.output_text,
                        model_name=last_model,
                        structured_output_mode=mode_name,
                        system_fingerprint=last_fingerprint,
                        usage=last_usage,
                        validation_errors=[],
                        fallback_events=events,
                        response_id=response.response_id,
                    )
            events.append(
                {
                    "model_name": model_name,
                    "structured_output_mode": mode_name,
                    "status": "invalid_output",
                    "validation_errors": list(last_errors),
                }
            )
    return GeneratedTraceResult(
        record=None,
        raw_output=last_raw,
        model_name=last_model,
        structured_output_mode=last_mode,
        system_fingerprint=last_fingerprint,
        usage=last_usage,
        validation_errors=last_errors,
        fallback_events=events,
    )


def normalize_trace_record(
    payload: Mapping[str, Any],
    *,
    sample: Mapping[str, Any],
    model_name: str,
    generation_config: Mapping[str, Any],
    system_fingerprint: str | None,
    usage: Mapping[str, Any],
) -> dict[str, Any]:
    trace = str(payload.get("observable_trace") or payload.get("visible_solution_trace") or "")
    spans = extract_reflection_spans(trace)
    generation_config_payload = dict(generation_config)
    reflection_type_normalization = _canonicalize_reflection_span_types(spans)
    if reflection_type_normalization:
        generation_config_payload["reflection_type_normalization"] = reflection_type_normalization
    final_answer = str(payload.get("final_answer") or extract_final_answer(trace))
    task_type = str(sample.get("task_type") or payload.get("task_type") or "")
    reference = str(sample.get("reference_answer") or payload.get("reference_answer") or "")
    aliases = sample.get("aliases") or payload.get("aliases") or []
    score = score_answer(task_type, final_answer, reference, aliases)
    return {
        "sample_id": str(sample.get("sample_id") or payload.get("sample_id") or ""),
        "task_id": str(sample.get("task_id") or payload.get("task_id") or ""),
        "task_type": task_type,
        "question": str(sample.get("question") or payload.get("question") or ""),
        "observable_trace": trace,
        "reflection_spans": spans,
        "final_answer": final_answer,
        "reference_answer": reference,
        "aliases": list(aliases) if isinstance(aliases, list) else [],
        "correctness": bool(score["exact_match"]),
        "model_name": model_name,
        "generation_config": generation_config_payload,
        "system_fingerprint": system_fingerprint,
        "usage": dict(usage),
    }


def build_generation_summary(results: Sequence[GeneratedTraceResult]) -> dict[str, Any]:
    valid = [result for result in results if result.record is not None]
    lower_confidence = [
        result for result in valid if result.structured_output_mode == "json_object"
    ]
    return {
        "records_requested": len(results),
        "valid_records": len(valid),
        "invalid_records": len(results) - len(valid),
        "valid_rate": len(valid) / len(results) if results else 0.0,
        "lower_confidence_records": len(lower_confidence),
        "fallback_events": [
            event
            for result in results
            for event in result.fallback_events
            if event.get("status") != "selected"
        ],
    }


def _fallback_order(config: Mapping[str, Any]) -> list[str]:
    model_config = config.get("model", {})
    order = list(model_config.get("fallback_order") or [])
    primary = str(model_config.get("primary") or "gpt-5.5")
    if primary not in order:
        order.insert(0, primary)
    return order


def _generation_config(
    config: Mapping[str, Any],
    *,
    adapter_version: str,
    structured_output_mode: str,
    api_request_metadata: Mapping[str, Any] | None = None,
    api_response_id: str | None = None,
) -> dict[str, Any]:
    model_config = config.get("model", {})
    api_config = config.get("api", {})
    experiment = config.get("experiment", {})
    return {
        "endpoint": api_config.get("endpoint", "/v1/responses"),
        "api_date": _string_or_none(api_config.get("api_date")),
        "sdk_version": adapter_version,
        "structured_output_mode": structured_output_mode,
        "primary_model": model_config.get("primary"),
        "fallback_order": list(model_config.get("fallback_order") or []),
        "reasoning": dict(model_config.get("reasoning", {})),
        "seed": experiment.get("seed"),
        "service_tier": api_config.get("service_tier"),
        "temperature": model_config.get("temperature", 0.0),
        "max_output_tokens": model_config.get("max_output_tokens"),
        "api_request_metadata": dict(api_request_metadata or {}),
        "response_id": api_response_id,
    }


def _string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _canonicalize_reflection_span_types(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalization_events: list[dict[str, Any]] = []
    aliases = {
        "self_evaluation": "self-evaluation",
        "self_reflection": "self-reflection",
    }
    for span in spans:
        raw_type = str(span.get("operation_type") or "")
        canonical_type = aliases.get(raw_type, raw_type)
        if canonical_type == raw_type:
            continue
        span["operation_type"] = canonical_type
        normalization_events.append(
            {
                "span_index": int(span.get("span_index", 0) or 0),
                "raw_operation_type": raw_type,
                "canonical_operation_type": canonical_type,
            }
        )
    return normalization_events
