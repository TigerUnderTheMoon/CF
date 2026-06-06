"""Parallel Phase 5 attribution engines.

The engines in this module keep the existing deterministic Phase 5 scoring
semantics and only change orchestration: strategy-level work is parallelized,
and large trace sets can be checkpointed by chunk.
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from joblib import Parallel, delayed
from tqdm.auto import tqdm

from fma.eval.counterfactual_attribution import (
    ABLATION_STRATEGIES,
    CounterfactualAblationResult,
    ablate_step,
    attribution_score_for_annotation,
    compute_trace_utility,
    group_annotations_by_trace,
    strategy_order,
)
from fma.eval.utility_annotation import UtilityAnnotation
from fma.utils.common import trace_id_for_record
from fma.utils.logging_config import get_logger

logger = get_logger("fma.attribution.engine")

ParallelBackend = Literal["loky", "threading"]


class ParallelAttributionEngine:
    """Run Phase 5 single-step ablations in deterministic parallel chunks."""

    def __init__(
        self,
        seed: int = 42,
        chunk_size: int = 100,
        n_jobs: int = -1,
        backend: ParallelBackend = "loky",
        show_progress: bool = True,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        if backend not in {"loky", "threading"}:
            raise ValueError("backend must be 'loky' or 'threading'.")
        self.seed = int(seed)
        self.chunk_size = int(chunk_size)
        self.n_jobs = int(n_jobs)
        self.backend: ParallelBackend = backend
        self.show_progress = bool(show_progress)

    def run_single_step_ablations(
        self,
        traces: Sequence[Mapping[str, Any]],
        annotations: Sequence[UtilityAnnotation],
        strategies: Sequence[str] = ABLATION_STRATEGIES,
    ) -> list[CounterfactualAblationResult]:
        """Run ablation strategies in parallel while preserving serial output order.

        Traces are partitioned into fixed-size chunks; each (chunk,
        strategy) pair becomes an independent task submitted to a
        ``joblib.Parallel`` worker pool.  Results are gathered and
        re-sorted by a stable sort key so the output is deterministic
        and ordering-equivalent to a serial run.

        Complexity:
            Let T = number of traces, C = chunk_size, S = max steps
            per trace, K = |strategies|, and J = n_jobs.

            *Work* (total CPU): O(T × S² × K), same as the serial
             algorithm, because the chunking does not reduce the
             total number of ablation evaluations.
            *Span* (wall-clock with J workers): O((⌈T/C⌉ × K) ×
             (C × S²) / J), which is O(T × S² × K / J) when the
             chunk-level work distributes evenly.
            *Space*: O(T × S × K) for the aggregated result list
             plus O(C × S) per-chunk working memory.

            The sorting step at the end is O(R log R) where
            R = T × S × K, but this is dominated by the ablation work.
        """
        _set_seed(self.seed)
        strategy_values = tuple(str(strategy) for strategy in strategies)
        chunks = _trace_chunks(traces, annotations, self.chunk_size)
        if not chunks or not strategy_values:
            logger.warning("no_chunks_or_strategies", chunk_count=len(chunks), strategy_count=len(strategy_values))
            return []

        logger.info(
            "ablation_start",
            chunk_count=len(chunks),
            strategy_count=len(strategy_values),
            total_tasks=len(chunks) * len(strategy_values),
        )
        tasks = [
            (
                chunk_index,
                strategy_index,
                strategy,
                chunk_traces,
                chunk_annotations,
                self.seed,
            )
            for chunk_index, (chunk_traces, chunk_annotations) in enumerate(chunks)
            for strategy_index, strategy in enumerate(strategy_values)
        ]
        task_iter = tqdm(
            tasks,
            total=len(tasks),
            desc="Phase 5 ablation chunks",
            disable=not self.show_progress or not sys.stdout.isatty(),
        )
        parallel = Parallel(n_jobs=self.n_jobs, backend=self.backend)
        rows = parallel(delayed(_run_ablation_strategy_chunk)(*task) for task in task_iter)

        ordered: list[tuple[tuple[int, int, int, int], CounterfactualAblationResult]] = []
        for chunk_rows in rows:
            ordered.extend(chunk_rows)
        ordered.sort(key=lambda item: item[0])
        result_count = len(ordered)
        logger.info("ablation_complete", result_count=result_count)
        return [row for _sort_key, row in ordered]


class IncrementalAttributionEngine:
    """Checkpoint Phase 5 chunk outputs for large trace sets and resume later."""

    def __init__(
        self,
        output_dir: str | Path = Path("outputs") / "phase5" / "chunks",
        seed: int = 42,
        chunk_size: int = 100,
        n_jobs: int = -1,
        backend: ParallelBackend = "loky",
        show_progress: bool = True,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        self.output_dir = Path(output_dir)
        self.seed = int(seed)
        self.chunk_size = int(chunk_size)
        self.n_jobs = int(n_jobs)
        self.backend: ParallelBackend = backend
        self.show_progress = bool(show_progress)

    def run(
        self,
        traces: Sequence[Mapping[str, Any]],
        annotations: Sequence[UtilityAnnotation],
        strategies: Sequence[str] = ABLATION_STRATEGIES,
        resume: bool = True,
    ) -> list[CounterfactualAblationResult]:
        """Run all chunks, reusing existing chunk files when ``resume`` is true.

        Each chunk is processed independently with the same parallel
        engine used by ``ParallelAttributionEngine``.  Completed chunk
        results are persisted to disk (JSONL) so that interrupted runs
        can skip already-finished chunks on the next invocation.

        I/O Complexity:
            *Writes*:  Each chunk produces a JSONL file on disk.
             Total data written = O(R) records, where
             R = T × S × K (T = traces, S = steps, K = strategies).
             Each record is ≈200 bytes → roughly R/5 KiB on disk.

            *Reads*:  On resume, only uncompleted chunks are recomputed.
             In the worst case (no prior progress) no files are read; in
             the best case (all chunks complete) the entire result is
             read back from disk at O(R) read cost with zero recomputation.
             Reads are sequential line-by-line JSON parsing, O(R) total.

            *Space*:  O(R) for the accumulated in-memory result list.
             Per-chunk disk files are independent and can be cleaned up
             after the final aggregation.

        The underlying per-chunk computational complexity follows
        ``ParallelAttributionEngine.run_single_step_ablations``
        (O(C × S² × K) work per chunk).
        """
        _set_seed(self.seed)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        chunks = _trace_chunks(traces, annotations, self.chunk_size)
        all_results: list[CounterfactualAblationResult] = []
        completed: list[int] = []

        logger.info(
            "incremental_start",
            chunk_count=len(chunks),
            output_dir=str(self.output_dir),
            resume=resume,
        )
        chunk_iter = tqdm(
            list(enumerate(chunks)),
            total=len(chunks),
            desc="Phase 5 incremental chunks",
            disable=not self.show_progress or not sys.stdout.isatty(),
        )
        for chunk_index, (chunk_traces, chunk_annotations) in chunk_iter:
            chunk_path = self._chunk_path(chunk_index)
            if resume and chunk_path.exists():
                logger.debug("chunk_resumed", chunk_index=chunk_index, path=str(chunk_path))
                chunk_results = _read_chunk_results(chunk_path)
            else:
                logger.debug(
                    "chunk_processing",
                    chunk_index=chunk_index,
                    trace_count=len(chunk_traces),
                    annotation_count=len(chunk_annotations),
                )
                engine = ParallelAttributionEngine(
                    seed=self.seed,
                    chunk_size=self.chunk_size,
                    n_jobs=self.n_jobs,
                    backend=self.backend,
                    show_progress=False,
                )
                chunk_results = engine.run_single_step_ablations(
                    chunk_traces,
                    chunk_annotations,
                    strategies=strategies,
                )
                _write_chunk_results(chunk_path, chunk_results)
                logger.debug("chunk_complete", chunk_index=chunk_index, result_count=len(chunk_results))
            all_results.extend(chunk_results)
            completed.append(chunk_index)

        self._write_checkpoint(completed_chunks=completed, total_chunks=len(chunks))
        logger.info(
            "incremental_complete",
            total_results=len(all_results),
            completed_chunks=len(completed),
            total_chunks=len(chunks),
        )
        return all_results

    def _chunk_path(self, chunk_index: int) -> Path:
        return self.output_dir / f"chunk_{chunk_index:05d}.jsonl"

    def _write_checkpoint(self, completed_chunks: list[int], total_chunks: int) -> None:
        checkpoint = {
            "schema_version": "phase5-incremental-v1",
            "seed": self.seed,
            "chunk_size": self.chunk_size,
            "completed_chunks": completed_chunks,
            "total_chunks": total_chunks,
            "output_dir": str(self.output_dir),
        }
        _write_json(self.output_dir / "checkpoint.json", checkpoint)


def _run_ablation_strategy_chunk(
    chunk_index: int,
    strategy_index: int,
    strategy: str,
    traces: Sequence[Mapping[str, Any]],
    annotations: Sequence[UtilityAnnotation],
    seed: int,
) -> list[tuple[tuple[int, int, int, int], CounterfactualAblationResult]]:
    _set_seed(seed)
    trace_by_id = {trace_id_for_record(trace, index): trace for index, trace in enumerate(traces)}
    grouped = group_annotations_by_trace(annotations)
    rows: list[tuple[tuple[int, int, int, int], CounterfactualAblationResult]] = []

    for trace_order, (trace_id, group) in enumerate(grouped.items()):
        original_utility = compute_trace_utility(group)
        annotations_by_idx = {annotation.reflection_idx: annotation for annotation in group}
        trace = trace_by_id.get(trace_id)
        ordered_steps = strategy_order(group, strategy, seed=seed, trace_id=trace_id)
        for step_order, step_idx in enumerate(ordered_steps):
            if trace is not None:
                ablate_step(trace, step_idx)
            remaining = [step for step in group if step.reflection_idx != step_idx]
            ablated_utility = compute_trace_utility(remaining)
            annotation = annotations_by_idx[step_idx]
            rows.append(
                (
                    (chunk_index, trace_order, strategy_index, step_order),
                    CounterfactualAblationResult(
                        trace_id=trace_id,
                        strategy=strategy,
                        removed_step_idx=step_idx,
                        original_utility=original_utility,
                        ablated_utility=ablated_utility,
                        delta_utility=float(original_utility - ablated_utility),
                        attribution_score_of_removed=attribution_score_for_annotation(annotation),
                    ),
                )
            )
    return rows


def _trace_chunks(
    traces: Sequence[Mapping[str, Any]],
    annotations: Sequence[UtilityAnnotation],
    chunk_size: int,
) -> list[tuple[list[Mapping[str, Any]], list[UtilityAnnotation]]]:
    grouped = group_annotations_by_trace(annotations)
    trace_by_id = {trace_id_for_record(trace, index): trace for index, trace in enumerate(traces)}
    trace_ids = list(grouped)
    for trace_id in trace_by_id:
        if trace_id not in grouped:
            trace_ids.append(trace_id)

    chunks: list[tuple[list[Mapping[str, Any]], list[UtilityAnnotation]]] = []
    for start in range(0, len(trace_ids), chunk_size):
        chunk_ids = trace_ids[start : start + chunk_size]
        chunk_traces = [trace_by_id[trace_id] for trace_id in chunk_ids if trace_id in trace_by_id]
        chunk_annotations = [
            annotation
            for trace_id in chunk_ids
            for annotation in grouped.get(trace_id, [])
        ]
        chunks.append((chunk_traces, chunk_annotations))
    return chunks


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _write_chunk_results(path: Path, results: Sequence[CounterfactualAblationResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for index, result in enumerate(results):
            record = {"_result_order": index, **asdict(result)}
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _read_chunk_results(path: Path) -> list[CounterfactualAblationResult]:
    rows: list[tuple[int, CounterfactualAblationResult]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            rows.append(
                (
                    int(record.get("_result_order", index)),
                    CounterfactualAblationResult(
                        trace_id=str(record["trace_id"]),
                        strategy=str(record["strategy"]),
                        removed_step_idx=int(record["removed_step_idx"]),
                        original_utility=float(record["original_utility"]),
                        ablated_utility=float(record["ablated_utility"]),
                        delta_utility=float(record["delta_utility"]),
                        attribution_score_of_removed=float(record["attribution_score_of_removed"]),
                    ),
                )
            )
    rows.sort(key=lambda item: item[0])
    return [row for _order, row in rows]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "IncrementalAttributionEngine",
    "ParallelAttributionEngine",
]
