"""Run s_FMA_v2.1 API_PREFLIGHT_ONLY with explicit budget and request guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_preflight import attempt_payloads_from_results, select_preflight_records
from fma.real_task_pilot.fresh_preflight_v2_1 import (
    build_v2_1_generation_config,
    build_v2_1_preflight_report,
    estimate_attempt_cost_usd,
    validate_v2_1_preflight_readiness,
)
from fma.real_task_pilot.generation import (
    GeneratedTraceResult,
    build_generation_prompt,
    load_prompt_template,
    normalize_trace_record,
)
from fma.real_task_pilot.openai_client import ApiCallResult, extract_response_output_text
from fma.real_task_pilot.parsing import parse_json_object
from fma.real_task_pilot.schema import structured_output_text_format, validate_trace_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded API preflight-only for the s_FMA_v2.1 fresh holdout."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_1_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-api-preflight-only",
        action="store_true",
        help="Required explicit guard for the v2.1 API preflight-only run.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="User-approved hard budget ceiling for this API_PREFLIGHT_ONLY run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    output_root = Path(config.get("experiment", {}).get("output_dir", "outputs/s_fma_v2_1_fresh_holdout"))
    paths = {
        "manifest": output_root / "fresh_manifest.json",
        "overlap": output_root / "manifest_overlap_audit.json",
        "contract": output_root / "v2_1_contract_audit.json",
        "approval": output_root / "api_preflight_approval_request.json",
        "readiness": Path("outputs") / "real_task_pilot" / "readiness_audit.json",
        "report": output_root / "api_preflight_report.json",
        "attempts": output_root / "api_preflight_attempts.jsonl",
        "traces": output_root / "api_preflight_traces.jsonl",
        "cost": output_root / "logs" / "api_preflight_cost_report.json",
    }
    manifest = _load_required_records(paths["manifest"])
    overlap_audit = _load_required_json(paths["overlap"])
    contract_audit = _load_required_json(paths["contract"])
    approval_request = _load_required_json(paths["approval"])
    current_readiness = _load_required_json(paths["readiness"])
    prompt_file = Path(
        config.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        )
    )
    current_prompt_version = _prompt_version(prompt_file)

    readiness = validate_v2_1_preflight_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=overlap_audit,
        contract_audit=contract_audit,
        approval_request=approval_request,
        current_readiness=current_readiness,
        allow_api_preflight_only=args.allow_api_preflight_only,
        approved_budget_usd=args.approved_budget_usd,
        current_prompt_version=current_prompt_version,
    )
    selected = select_preflight_records(
        manifest,
        samples_per_task=10,
        task_order=["gsm8k", "hotpotqa"],
    )
    live_config = build_v2_1_generation_config(config, readiness=readiness)
    prompt_template = load_prompt_template(live_config["generation"]["prompt_file"])
    adapter = SingleRequestOpenAITraceAdapter()

    preflight_results: list[GeneratedTraceResult] = []
    determinism_results: list[GeneratedTraceResult] = []
    budget_stop_triggered = False
    request_stop_triggered = False

    for sample in selected:
        if _attempt_count(preflight_results, determinism_results) >= readiness["max_api_requests"]:
            request_stop_triggered = True
            break
        preflight_results.append(
            generate_trace_once(
                sample,
                adapter=adapter,
                config=live_config,
                prompt_template=prompt_template,
            )
        )
        _write_live_checkpoint(
            traces_path=paths["traces"],
            attempts_path=paths["attempts"],
            selected_records=selected,
            preflight_results=preflight_results,
            determinism_results=determinism_results,
        )
        if _budget_reached(
            preflight_results=preflight_results,
            determinism_results=determinism_results,
            selected_records=selected,
            config=live_config,
            approved_budget_usd=float(readiness["approved_budget_usd"]),
        ):
            budget_stop_triggered = True
            break

    drift_repeats = int(readiness.get("determinism_probe_repeats", 3))
    if not budget_stop_triggered and not request_stop_triggered and selected:
        probe_sample = selected[0]
        for _index in range(drift_repeats):
            if _attempt_count(preflight_results, determinism_results) >= readiness["max_api_requests"]:
                request_stop_triggered = True
                break
            determinism_results.append(
                generate_trace_once(
                    probe_sample,
                    adapter=adapter,
                    config=live_config,
                    prompt_template=prompt_template,
                )
            )
            _write_live_checkpoint(
                traces_path=paths["traces"],
                attempts_path=paths["attempts"],
                selected_records=selected,
                preflight_results=preflight_results,
                determinism_results=determinism_results,
            )
            if _budget_reached(
                preflight_results=preflight_results,
                determinism_results=determinism_results,
                selected_records=selected,
                config=live_config,
                approved_budget_usd=float(readiness["approved_budget_usd"]),
            ):
                budget_stop_triggered = True
                break

    preflight_attempts = attempt_payloads_from_results(
        preflight_results,
        role="preflight_record",
        samples=selected,
    )
    determinism_attempts = attempt_payloads_from_results(
        determinism_results,
        role="determinism_probe",
        samples=[selected[0]] * len(determinism_results) if selected else [],
    )
    drift_outputs = [
        str(result.record.get("observable_trace"))
        if result.record is not None
        else result.raw_output
        for result in determinism_results
    ]
    report = build_v2_1_preflight_report(
        preflight_attempts,
        selected_records=selected,
        drift_outputs=drift_outputs,
        config=live_config,
        readiness=readiness,
        cost_attempts=preflight_attempts + determinism_attempts,
    )
    report["budget_stop_triggered"] = budget_stop_triggered
    report["request_stop_triggered"] = request_stop_triggered
    report["api_execution_performed"] = True
    _write_json(paths["report"], report)
    _write_json(paths["cost"], report.get("cost_report", {}))
    print(
        json.dumps(
            {
                "status": report["status"],
                "records_evaluated": report["records_evaluated"],
                "api_attempts": report["api_attempts"],
                "cost_used_usd": report.get("cost_used_usd"),
            },
            sort_keys=True,
        )
    )


class SingleRequestOpenAITraceAdapter:
    """Single HTTP-request adapter used to enforce the 25-request preflight cap."""

    def __init__(self) -> None:
        try:
            import openai
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - environment guard
            raise RuntimeError("openai is required for live API preflight stages.") from exc
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
        request = _single_request_kwargs(
            prompt=prompt,
            config=config,
            model_name=model_name,
            json_mode=json_mode,
        )
        response = self.client.responses.create(**request)
        return _api_result_from_response(
            response,
            request_metadata={
                "seed_sent": False,
                "reasoning_sent": False,
                "single_request_preflight": True,
                "retry_errors": [],
            },
        )


def generate_trace_once(
    sample: Mapping[str, Any],
    *,
    adapter: SingleRequestOpenAITraceAdapter,
    config: Mapping[str, Any],
    prompt_template: str,
) -> GeneratedTraceResult:
    """Generate one trace with exactly one adapter call and no retry/fallback."""

    prompt = build_generation_prompt(prompt_template, sample)
    model_name = str(config.get("model", {}).get("primary") or "gpt-5.5")
    mode_name = "json_schema"
    try:
        response = adapter.create_trace(
            prompt=prompt,
            config=config,
            model_name=model_name,
            json_mode=False,
        )
    except Exception as exc:
        return GeneratedTraceResult(
            record=None,
            raw_output="",
            model_name=model_name,
            structured_output_mode=mode_name,
            system_fingerprint=None,
            usage={},
            validation_errors=[f"api_error:{type(exc).__name__}:{exc}"],
            fallback_events=[
                {
                    "model_name": model_name,
                    "structured_output_mode": mode_name,
                    "status": "api_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            ],
            response_id=None,
            output_extraction_diagnostics={},
        )

    parsed = parse_json_object(response.output_text)
    if parsed is None:
        return GeneratedTraceResult(
            record=None,
            raw_output=response.output_text,
            model_name=response.model_name or model_name,
            structured_output_mode=mode_name,
            system_fingerprint=response.system_fingerprint,
            usage=response.usage,
            validation_errors=["<root>: response is not a JSON object"],
            fallback_events=[
                {
                    "model_name": model_name,
                    "structured_output_mode": mode_name,
                    "status": "invalid_output",
                    "validation_errors": ["<root>: response is not a JSON object"],
                }
            ],
            response_id=response.response_id,
            output_extraction_diagnostics=dict(response.output_extraction_diagnostics),
        )

    record = normalize_trace_record(
        parsed,
        sample=sample,
        model_name=response.model_name or model_name,
        generation_config=_generation_config(
            config,
            adapter_version=adapter.openai_version,
            structured_output_mode=mode_name,
            api_request_metadata=response.request_metadata,
            api_response_id=response.response_id,
        ),
        system_fingerprint=response.system_fingerprint,
        usage=response.usage,
    )
    validation_errors = validate_trace_record(record)
    if validation_errors:
        return GeneratedTraceResult(
            record=None,
            raw_output=response.output_text,
            model_name=response.model_name or model_name,
            structured_output_mode=mode_name,
            system_fingerprint=response.system_fingerprint,
            usage=response.usage,
            validation_errors=validation_errors,
            fallback_events=[
                {
                    "model_name": model_name,
                    "structured_output_mode": mode_name,
                    "status": "invalid_output",
                    "validation_errors": list(validation_errors),
                }
            ],
            response_id=response.response_id,
            output_extraction_diagnostics=dict(response.output_extraction_diagnostics),
        )
    return GeneratedTraceResult(
        record=record,
        raw_output=response.output_text,
        model_name=response.model_name or model_name,
        structured_output_mode=mode_name,
        system_fingerprint=response.system_fingerprint,
        usage=response.usage,
        validation_errors=[],
        fallback_events=[
            {
                "model_name": model_name,
                "structured_output_mode": mode_name,
                "status": "selected",
                "lower_confidence": False,
            }
        ],
        response_id=response.response_id,
        output_extraction_diagnostics=dict(response.output_extraction_diagnostics),
    )


def _write_live_checkpoint(
    *,
    traces_path: Path,
    attempts_path: Path,
    selected_records: list[dict[str, Any]],
    preflight_results: list[GeneratedTraceResult],
    determinism_results: list[GeneratedTraceResult],
) -> None:
    valid_records = [result.record for result in preflight_results if result.record is not None]
    attempts = attempt_payloads_from_results(
        preflight_results,
        role="preflight_record",
        samples=selected_records,
    )
    attempts.extend(
        attempt_payloads_from_results(
            determinism_results,
            role="determinism_probe",
            samples=[selected_records[0]] * len(determinism_results) if selected_records else [],
        )
    )
    write_records(valid_records, traces_path)
    write_records(attempts, attempts_path)


def _budget_reached(
    *,
    preflight_results: list[GeneratedTraceResult],
    determinism_results: list[GeneratedTraceResult],
    selected_records: list[dict[str, Any]],
    config: Mapping[str, Any],
    approved_budget_usd: float,
) -> bool:
    attempts = attempt_payloads_from_results(
        preflight_results,
        role="preflight_record",
        samples=selected_records,
    )
    attempts.extend(
        attempt_payloads_from_results(
            determinism_results,
            role="determinism_probe",
            samples=[selected_records[0]] * len(determinism_results) if selected_records else [],
        )
    )
    cost = estimate_attempt_cost_usd(attempts, config=config)
    return cost is not None and cost >= approved_budget_usd


def _attempt_count(
    preflight_results: list[GeneratedTraceResult],
    determinism_results: list[GeneratedTraceResult],
) -> int:
    return len(preflight_results) + len(determinism_results)


def _prompt_version(path: Path) -> str:
    return "prompt-sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _single_request_kwargs(
    *,
    prompt: str,
    config: Mapping[str, Any],
    model_name: str,
    json_mode: bool,
) -> dict[str, Any]:
    model_config = config.get("model", {})
    api_config = config.get("api", {})
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
    }
    timeout_seconds = api_config.get("request_timeout_seconds")
    if timeout_seconds is not None:
        kwargs["timeout"] = float(timeout_seconds)
    return kwargs


def _api_result_from_response(response: Any, *, request_metadata: Mapping[str, Any]) -> ApiCallResult:
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
        request_metadata=dict(request_metadata),
        response_id=response_id,
        output_extraction_diagnostics=output_extraction_diagnostics,
    )


def _extract_output_text(response: Any) -> str:
    return extract_response_output_text(response)[0]


def _generation_config(
    config: Mapping[str, Any],
    *,
    adapter_version: str,
    structured_output_mode: str,
    api_request_metadata: Mapping[str, Any],
    api_response_id: str | None,
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
        "api_request_metadata": dict(api_request_metadata),
        "response_id": api_response_id,
    }


def _load_required_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"required manifest does not exist: {path}")
    return load_records(path)


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required JSON does not exist: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


if __name__ == "__main__":
    main()
