"""Real-task pilot governance and API call utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from fma.pilot.api_client import APIResponse, BaseAPIClient, OpenAIClient, VLLMClient
from fma.pilot.audit import AuditEvent, AuditLogger, FailureAudit
from fma.pilot.cache import APICache, CacheEntry, cache_key, prompt_sha256
from fma.pilot.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CostLimitExceeded,
    CostTracker,
    DriftCheckResult,
    DriftDetector,
    SchemaDriftError,
    retry_with_exponential_backoff,
)


@dataclass(frozen=True)
class PilotRunConfig:
    """Minimal public pilot run config used by the project skeleton API."""

    config_name: str = "pilot/v2_1"
    output_root: Path | None = None
    overrides: Sequence[str] = ()


def run_pilot(
    config: PilotRunConfig | None = None, *, timestamp: str | None = None
) -> dict[str, Any]:
    """Compose a guarded pilot config and create its run directory."""
    from fma.cli import run_cli

    config = config or PilotRunConfig()
    argv = ["run-pilot", f"--config-name={config.config_name}", *config.overrides]
    if config.output_root is not None:
        argv.append(f"paths.output_root={config.output_root.as_posix()}")
    result = run_cli(argv, timestamp=timestamp)
    if not isinstance(result, dict):
        raise TypeError("run-pilot returned a non-mapping result")
    return result


__all__ = [
    "APIResponse",
    "APICache",
    "AuditEvent",
    "AuditLogger",
    "BaseAPIClient",
    "CacheEntry",
    "CircuitBreaker",
    "CircuitOpenError",
    "CostLimitExceeded",
    "CostTracker",
    "DriftCheckResult",
    "DriftDetector",
    "FailureAudit",
    "OpenAIClient",
    "PilotRunConfig",
    "SchemaDriftError",
    "VLLMClient",
    "cache_key",
    "prompt_sha256",
    "retry_with_exponential_backoff",
    "run_pilot",
]
