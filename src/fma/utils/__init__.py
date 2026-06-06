"""Shared utility interfaces."""

from .benchmark import (
    BenchmarkResult,
    benchmark,
    benchmark_function,
    pyperf_benchmark_function,
    write_benchmark_result,
)
from .cleanup import CleanupReport, cleanup_outputs
from .config import FMAConfig, flatten_config, load_config, validate_config

__all__ = [
    "BenchmarkResult",
    "CleanupReport",
    "FMAConfig",
    "benchmark",
    "benchmark_function",
    "cleanup_outputs",
    "flatten_config",
    "load_config",
    "validate_config",
    "write_benchmark_result",
]
