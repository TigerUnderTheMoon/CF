from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import Mock

import pytest

from fma.pilot.api_client import APIResponse, OpenAIClient, VLLMClient
from fma.pilot.cache import APICache
from fma.pilot.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CostLimitExceeded,
    CostTracker,
    DriftDetector,
    SchemaDriftError,
    retry_with_exponential_backoff,
)
from fma.real_task_pilot.openai_client import OpenAIResponsesAdapter


@dataclass
class _FakeResponsesResponse:
    output_text: str
    model: str = "gpt-test"
    system_fingerprint: str = "fp-test"
    id: str = "resp-test"
    usage: Mapping[str, int] | None = None


def test_api_cache_uses_prompt_model_sampling_key(tmp_path: Path) -> None:
    cache = APICache(tmp_path / "api_cache.sqlite")

    cache.set(
        prompt="same prompt",
        model_name="gpt-test",
        temperature=0.0,
        seed=7,
        top_p=1.0,
        raw_output="cached output",
        metadata={"response_id": "resp-1"},
        cost_usd=0.03,
    )

    hit = cache.get(
        prompt="same prompt",
        model_name="gpt-test",
        temperature=0.0,
        seed=7,
        top_p=1.0,
    )

    assert hit is not None
    assert hit.raw_output == "cached output"
    assert hit.metadata["response_id"] == "resp-1"
    assert hit.cost_usd == 0.03
    assert cache.get(
        prompt="same prompt",
        model_name="gpt-test",
        temperature=0.2,
        seed=7,
        top_p=1.0,
    ) is None


def test_retry_with_exponential_backoff_retries_then_succeeds() -> None:
    attempts = 0
    delays: list[float] = []

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("temporary timeout")
        return "ok"

    result = retry_with_exponential_backoff(
        flaky,
        max_retries=3,
        base_delay=1.0,
        max_delay=10.0,
        sleep=delays.append,
    )

    assert result == "ok"
    assert attempts == 3
    assert delays == [1.0, 2.0]


def test_circuit_breaker_opens_after_five_failures_and_recovers() -> None:
    now = 100.0

    def clock() -> float:
        return now

    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout_seconds=60.0, clock=clock)

    for _index in range(4):
        breaker.before_call()
        breaker.record_failure()

    breaker.before_call()
    breaker.record_failure()

    with pytest.raises(CircuitOpenError):
        breaker.before_call()

    now = 161.0
    breaker.before_call()
    breaker.record_success()
    assert breaker.failure_count == 0


def test_cost_tracker_raises_before_request_when_near_ceiling() -> None:
    tracker = CostTracker(cost_ceiling_usd=1.0, warning_ratio=0.95)
    tracker.record_cost(0.95)

    with pytest.raises(CostLimitExceeded):
        tracker.check_before_request()


def test_openai_client_retries_records_cost_and_uses_cache(tmp_path: Path) -> None:
    responses = Mock()
    responses.create.side_effect = [
        TimeoutError("temporary"),
        _FakeResponsesResponse(
            output_text='{"observable_trace":"A <reflection type=\\"verification\\">check</reflection> Final Answer: 5","final_answer":"5"}',
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        ),
    ]
    sdk_client = Mock(responses=responses)
    delays: list[float] = []
    cache = APICache(tmp_path / "api_cache.sqlite")
    tracker = CostTracker(cost_ceiling_usd=1.0)
    client = OpenAIClient(
        model_name="gpt-test",
        sdk_client=sdk_client,
        cache=cache,
        cost_tracker=tracker,
        pricing={"input_per_million_usd": 10.0, "output_per_million_usd": 20.0},
        sleep=delays.append,
    )

    first = client.chat_complete("prompt", temperature=0.0, seed=7, top_p=1.0)
    second = client.chat_complete("prompt", temperature=0.0, seed=7, top_p=1.0)

    assert first.raw_output.startswith('{"observable_trace"')
    assert first.cached is False
    assert first.cost_usd == pytest.approx(0.002)
    assert second.cached is True
    assert second.raw_output == first.raw_output
    assert responses.create.call_count == 2
    assert delays == [1.0]
    assert tracker.current_cost_usd == pytest.approx(0.002)


def test_vllm_client_posts_openai_compatible_chat_request_and_uses_cache(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, Any], Mapping[str, str], float]] = []

    def transport(
        url: str,
        payload: dict[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        calls.append((url, payload, headers, timeout))
        return {
            "id": "chatcmpl-test",
            "model": payload["model"],
            "choices": [{"message": {"content": '{"final_answer":"5"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    client = VLLMClient(
        base_url="http://127.0.0.1:8000",
        model_name="local-test",
        cache=APICache(tmp_path / "vllm_cache.sqlite"),
        transport=transport,
    )

    first = client.chat_complete("prompt", temperature=0.0, seed=123, top_p=0.9)
    second = client.chat_complete("prompt", temperature=0.0, seed=123, top_p=0.9)

    assert first.raw_output == '{"final_answer":"5"}'
    assert second.cached is True
    assert len(calls) == 1
    assert calls[0][0] == "http://127.0.0.1:8000/v1/chat/completions"
    assert calls[0][1]["seed"] == 123
    assert calls[0][1]["messages"] == [{"role": "user", "content": "prompt"}]


def test_drift_detector_logs_and_raises_on_missing_schema(tmp_path: Path) -> None:
    log_path = tmp_path / "drift_log.jsonl"
    detector = DriftDetector(threshold=0.2, log_path=log_path)

    with pytest.raises(SchemaDriftError):
        detector.validate('{"observable_trace":"No required tag here."}', metadata={"model_name": "bad"})

    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["schema_missing_rate"] > 0.2
    assert "json_field:final_answer" in rows[0]["missing_checks"]
    assert rows[0]["metadata"]["model_name"] == "bad"


def test_openai_responses_adapter_can_use_new_base_client() -> None:
    class FakeBaseClient:
        openai_version = "fake-base-client"

        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def chat_complete(self, prompt: str, **kwargs: Any) -> APIResponse:
            self.calls.append({"prompt": prompt, **kwargs})
            return APIResponse(
                raw_output=(
                    '{"observable_trace":"A <reflection type=\\"verification\\">check</reflection> '
                    'Final Answer: 5","final_answer":"5"}'
                ),
                model_name=str(kwargs["model_name"]),
                metadata={
                    "request_metadata": {"seed_sent": True, "retry_label": "full"},
                    "system_fingerprint": "fp-adapter",
                    "response_id": "resp-adapter",
                    "output_extraction_diagnostics": {"output_text_present": True},
                },
                usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
                cost_usd=0.0,
            )

        def health_check(self) -> bool:
            return True

    base_client = FakeBaseClient()
    adapter = OpenAIResponsesAdapter(api_client=base_client)
    result = adapter.create_trace(
        prompt="prompt",
        config={
            "experiment": {"seed": 7},
            "api": {"endpoint": "/v1/responses"},
            "model": {"temperature": 0.0, "top_p": 1.0, "max_output_tokens": 128},
        },
        model_name="gpt-test",
    )

    assert result.output_text.startswith('{"observable_trace"')
    assert result.request_metadata["seed_sent"] is True
    assert result.system_fingerprint == "fp-adapter"
    assert result.response_id == "resp-adapter"
    assert "request_overrides" in base_client.calls[0]
