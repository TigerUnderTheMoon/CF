"""Resilience and audit helpers for pilot API calls."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when the API circuit breaker is open."""


class CostLimitExceeded(RuntimeError):
    """Raised before an API call would exceed the configured hard cost guard."""


class SchemaDriftError(RuntimeError):
    """Raised when response schema drift exceeds the configured threshold."""


def retry_with_exponential_backoff(
    operation: Callable[[], T],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
    retryable_errors: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Retry an operation with one initial attempt plus ``max_retries`` retries."""

    if max_retries < 0:
        raise ValueError("max_retries must be non-negative.")
    last_error: BaseException | None = None
    for attempt_index in range(max_retries + 1):
        try:
            return operation()
        except retryable_errors as exc:
            last_error = exc
            if attempt_index == max_retries:
                break
            delay = min(max_delay, base_delay * (2 ** attempt_index))
            sleep(delay)
    assert last_error is not None
    raise last_error


class CircuitBreaker:
    """Open after a configurable run of consecutive failures."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.clock = clock
        self.failure_count = 0
        self.opened_at: float | None = None

    def before_call(self) -> None:
        if self.opened_at is None:
            return
        if self.clock() - self.opened_at >= self.recovery_timeout_seconds:
            return
        remaining = self.recovery_timeout_seconds - (self.clock() - self.opened_at)
        raise CircuitOpenError(f"API circuit is open for {remaining:.1f}s more.")

    def record_success(self) -> None:
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold and self.opened_at is None:
            self.opened_at = self.clock()


class CostTracker:
    """Track cumulative live API cost and fail closed near the ceiling."""

    def __init__(self, *, cost_ceiling_usd: float | None = None, warning_ratio: float = 0.95) -> None:
        self.cost_ceiling_usd = cost_ceiling_usd
        self.warning_ratio = warning_ratio
        self.current_cost_usd = 0.0

    def check_before_request(self, *, estimated_cost_usd: float = 0.0) -> None:
        if self.cost_ceiling_usd is None:
            return
        projected = self.current_cost_usd + max(0.0, estimated_cost_usd)
        guardrail = self.cost_ceiling_usd * self.warning_ratio
        if projected >= guardrail:
            raise CostLimitExceeded(
                f"API cost guard reached: projected=${projected:.6f}, "
                f"ceiling=${self.cost_ceiling_usd:.6f}."
            )

    def record_cost(self, cost_usd: float) -> None:
        self.current_cost_usd += max(0.0, float(cost_usd))


@dataclass(frozen=True)
class DriftCheckResult:
    missing_checks: list[str]
    schema_missing_rate: float


class DriftDetector:
    """Validate coarse response format expectations and log drift events."""

    def __init__(
        self,
        *,
        threshold: float = 0.2,
        log_path: str | Path = "outputs/audit/drift_log.jsonl",
    ) -> None:
        self.threshold = threshold
        self.log_path = Path(log_path)

    def validate(self, raw_output: str, *, metadata: Mapping[str, Any] | None = None) -> None:
        result = self.check(raw_output)
        if result.schema_missing_rate <= self.threshold:
            return
        row = {
            "event": "schema_drift",
            "schema_missing_rate": result.schema_missing_rate,
            "threshold": self.threshold,
            "missing_checks": result.missing_checks,
            "metadata": dict(metadata or {}),
            "raw_output_preview": raw_output[:500],
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
        raise SchemaDriftError(
            f"Response schema drift {result.schema_missing_rate:.3f} exceeds threshold {self.threshold:.3f}."
        )

    def check(self, raw_output: str) -> DriftCheckResult:
        checks = [
            "json_parse",
            "json_field:observable_trace",
            "json_field:final_answer",
            "tag_format:reflection",
            "final_answer_format",
        ]
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            return DriftCheckResult(missing_checks=list(checks), schema_missing_rate=1.0)

        missing: list[str] = []
        if not isinstance(payload, Mapping):
            missing.extend(checks[1:])
            return DriftCheckResult(
                missing_checks=missing,
                schema_missing_rate=len(missing) / len(checks),
            )

        trace = str(payload.get("observable_trace") or "")
        final_answer = str(payload.get("final_answer") or "")
        if not trace:
            missing.append("json_field:observable_trace")
        if not final_answer:
            missing.append("json_field:final_answer")
        if not _has_reflection_tag(trace):
            missing.append("tag_format:reflection")
        if not final_answer and not _has_final_answer_line(trace):
            missing.append("final_answer_format")
        return DriftCheckResult(
            missing_checks=missing,
            schema_missing_rate=len(missing) / len(checks),
        )


def _has_reflection_tag(trace: str) -> bool:
    return bool(re.search(r"<reflection\s+type=\"[^\"]+\">.*?</reflection>", trace, flags=re.DOTALL))


def _has_final_answer_line(trace: str) -> bool:
    return bool(re.search(r"final\s+answer\s*:", trace, flags=re.IGNORECASE))


__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "CostLimitExceeded",
    "CostTracker",
    "DriftCheckResult",
    "DriftDetector",
    "SchemaDriftError",
    "retry_with_exponential_backoff",
]
