"""Pilot API client layer: auditable, resilient LLM backends for FMA."""

from __future__ import annotations

from fma.pilot.api_client import APIResponse, BaseAPIClient, OpenAIClient, VLLMClient
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

__all__ = [
    "APIResponse",
    "BaseAPIClient",
    "OpenAIClient",
    "VLLMClient",
    "APICache",
    "CacheEntry",
    "cache_key",
    "prompt_sha256",
    "CircuitBreaker",
    "CircuitOpenError",
    "CostLimitExceeded",
    "CostTracker",
    "DriftCheckResult",
    "DriftDetector",
    "SchemaDriftError",
    "retry_with_exponential_backoff",
]
