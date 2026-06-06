"""Small benchmark helpers for Phase 5/6 performance reporting.

Supports:
- Custom decorator with ``memory_profiler`` or ``tracemalloc`` for memory.
- Optional ``pyperf`` backend for rigorous multi-run timing statistics.
"""

from __future__ import annotations

import json
import time
import tracemalloc
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")
DEFAULT_PHASE5_BENCHMARK_PATH = Path("outputs") / "benchmarks" / "phase5_benchmark.json"


@dataclass(frozen=True)
class BenchmarkResult:
    """Elapsed-time and peak-memory measurement for one function call."""

    name: str
    elapsed_seconds: float
    peak_memory_mb: float
    measured_with: str
    timestamp_utc: str
    metadata: dict[str, Any] = field(default_factory=dict)


def benchmark_function(
    name: str,
    function: Callable[..., T],
    *args: Any,
    output_path: str | Path = DEFAULT_PHASE5_BENCHMARK_PATH,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> tuple[T, BenchmarkResult]:
    """Run ``function`` once, record elapsed time and memory, and write JSON."""
    result, elapsed_seconds, peak_memory_mb, measured_with = _measure_call(function, *args, **kwargs)
    benchmark = BenchmarkResult(
        name=name,
        elapsed_seconds=float(elapsed_seconds),
        peak_memory_mb=float(peak_memory_mb),
        measured_with=measured_with,
        timestamp_utc=datetime.now(UTC).isoformat(),
        metadata=dict(metadata or {}),
    )
    write_benchmark_result(benchmark, output_path)
    return result, benchmark


def pyperf_benchmark_function(
    name: str,
    function: Callable[..., T],
    *args: Any,
    output_path: str | Path = DEFAULT_PHASE5_BENCHMARK_PATH,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> tuple[T, BenchmarkResult]:
    """Run ``function`` with ``pyperf`` multi-run timing if available, else fall back.

    Memory is always measured via ``memory_profiler`` (if installed) or
    ``tracemalloc`` so that the JSON artifact contains both latency and
    memory information.
    """
    result = function(*args, **kwargs)
    pyperf_result = _try_pyperf(name, function, *args, **kwargs)
    if pyperf_result is not None:
        elapsed_seconds = float(pyperf_result["mean"])
        measured_with = f"pyperf (runs={pyperf_result['runs']})"
    else:
        elapsed_seconds = 0.0
        measured_with = "pyperf_not_installed_fallback"

    peak_memory_mb = _measure_memory(function, *args, **kwargs)
    benchmark = BenchmarkResult(
        name=name,
        elapsed_seconds=float(elapsed_seconds),
        peak_memory_mb=float(peak_memory_mb),
        measured_with=measured_with,
        timestamp_utc=datetime.now(UTC).isoformat(),
        metadata=dict(metadata or {}),
    )
    write_benchmark_result(benchmark, output_path)
    return result, benchmark


def benchmark(
    name: str | None = None,
    output_path: str | Path = DEFAULT_PHASE5_BENCHMARK_PATH,
    metadata: dict[str, Any] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator form of :func:`benchmark_function` for script entrypoints."""

    def decorate(function: Callable[..., T]) -> Callable[..., T]:
        def wrapped(*args: Any, **kwargs: Any) -> T:
            result, _benchmark = benchmark_function(
                name or function.__name__,
                function,
                *args,
                output_path=output_path,
                metadata=metadata,
                **kwargs,
            )
            return result

        return wrapped

    return decorate


def write_benchmark_result(
    benchmark_result: BenchmarkResult,
    output_path: str | Path = DEFAULT_PHASE5_BENCHMARK_PATH,
) -> None:
    """Append one benchmark record to a deterministic JSON artifact."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _read_existing_payload(path)
    payload["generated_at_utc"] = datetime.now(UTC).isoformat()
    payload["benchmarks"].append(asdict(benchmark_result))
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _measure_call(
    function: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> tuple[T, float, float, str]:
    memory_usage = _memory_profiler()
    if memory_usage is not None:
        start = time.perf_counter()
        memory_samples, result = memory_usage(
            (function, args, kwargs),
            interval=0.05,
            retval=True,
            max_usage=False,
        )
        elapsed = time.perf_counter() - start
        peak = max(float(sample) for sample in memory_samples) if memory_samples else 0.0
        return result, elapsed, peak, "memory_profiler"

    tracemalloc.start()
    start = time.perf_counter()
    try:
        result = function(*args, **kwargs)
        elapsed = time.perf_counter() - start
        _current, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, elapsed, peak_bytes / (1024 * 1024), "tracemalloc"


def _measure_memory(
    function: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> float:
    """Measure peak memory (MB) for one call, without returning the result."""
    memory_usage = _memory_profiler()
    if memory_usage is not None:
        memory_samples = memory_usage(
            (function, args, kwargs),
            interval=0.05,
            retval=False,
            max_usage=False,
        )
        return max(float(sample) for sample in memory_samples) if memory_samples else 0.0

    tracemalloc.start()
    try:
        function(*args, **kwargs)
        _current, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak_bytes / (1024 * 1024)


def _try_pyperf(
    name: str,
    function: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Return pyperf stats if pyperf is installed, else ``None``."""
    try:
        import pyperf
    except ImportError:
        return None

    runner = pyperf.Runner(args=())
    bench = runner.bench_func(name, function, *args, **kwargs)
    if bench is None:
        return None
    return {
        "mean": bench.mean(),
        "stdev": bench.stdev(),
        "runs": bench.get_nrun(),
    }


def _memory_profiler() -> Callable[..., Any] | None:
    try:
        from memory_profiler import memory_usage
    except ImportError:
        return None
    return memory_usage


def _read_existing_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "phase-benchmark-v1",
            "generated_at_utc": None,
            "benchmarks": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("benchmarks"), list):
        raise ValueError(f"{path} is not a benchmark JSON artifact.")
    return payload


__all__ = [
    "BenchmarkResult",
    "DEFAULT_PHASE5_BENCHMARK_PATH",
    "benchmark",
    "benchmark_function",
    "pyperf_benchmark_function",
    "write_benchmark_result",
]
