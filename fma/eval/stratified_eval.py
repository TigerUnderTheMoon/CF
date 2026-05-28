"""Stratified evaluation for taxonomy-driven reflection attribution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from fma.eval.stability import StabilityAnalyzer, bounded_stability
from fma.types import AttributionRecord, ReflectionAnnotation, ReflectionCategory, ReflectionTrace, StratifiedInput


LOGGER = logging.getLogger(__name__)
MIN_BUCKET_SIZE = 5
MIN_UTILITY_BUCKET_SIZE = 5
DIMENSION_BUCKETS: dict[str, tuple[str, ...]] = {
    "category": tuple(category.name for category in ReflectionCategory),
    "difficulty": ("low", "medium", "high"),
    "intervention": ("weak", "moderate", "strong"),
    "locality": ("local", "mixed", "global"),
    "trace_length": ("short", "medium", "long"),
    "necessity": ("q1", "q2", "q3", "q4"),
    "redundancy": ("t1", "t2", "t3"),
    "faithfulness": tuple(f"d{index:02d}" for index in range(1, 11)),
}


@dataclass(frozen=True)
class StratifiedBucket:
    dimension: str
    bucket_name: str
    indices: List[int]
    n_samples: int


@dataclass(frozen=True)
class BucketMetrics:
    mean_utility_delta: float
    utility_variance: float
    mean_attribution_score: float
    attribution_stability: float
    intervention_sensitivity: float
    n_samples: int
    status: str = "ok"
    utility_status: str = "ok"
    necessity_status: str = "ok"
    redundancy_status: str = "ok"
    faithfulness_status: str = "ok"
    required: int = MIN_BUCKET_SIZE
    utility_required: int = MIN_UTILITY_BUCKET_SIZE


@dataclass(frozen=True)
class _EvalRow:
    index: int
    record: AttributionRecord
    annotation: ReflectionAnnotation
    trace: ReflectionTrace | None


class StratifiedEvaluator:
    def __init__(self, random_seed: int = 42):
        self.rng = np.random.default_rng(random_seed)
        self.stability_analyzer = StabilityAnalyzer(random_seed=random_seed)

    def evaluate(self, inputs: StratifiedInput) -> Dict[str, Dict[str, BucketMetrics]]:
        """
        Returns nested dict: {dimension: {bucket_name: BucketMetrics}}
        """
        rows = self._valid_rows(inputs)
        if not rows:
            raise ValueError("no valid evaluation data")

        results: dict[str, dict[str, BucketMetrics]] = {}
        has_non_empty_bucket = False
        for dimension in DIMENSION_BUCKETS:
            buckets = self._build_buckets(rows, dimension)
            results[dimension] = {}
            for bucket in buckets:
                bucket_rows = [row for row in rows if row.index in set(bucket.indices)]
                if bucket.n_samples > 0:
                    has_non_empty_bucket = True
                results[dimension][bucket.bucket_name] = self._bucket_metrics(bucket_rows, rows)

        if not has_non_empty_bucket:
            raise ValueError("no valid evaluation data")
        return results

    def get_instability_cases(
        self,
        inputs: StratifiedInput,
        threshold: float = 0.2,
    ) -> List[Dict[str, Any]]:
        """
        Return records where |attribution_score - mean(attribution_score in bucket)| > threshold.
        """
        rows = self._valid_rows(inputs)
        by_category: dict[ReflectionCategory, list[_EvalRow]] = {}
        for row in rows:
            by_category.setdefault(row.annotation.category, []).append(row)

        cases: list[dict[str, Any]] = []
        for category, category_rows in by_category.items():
            mean_score = float(np.mean([row.record.attribution_score for row in category_rows]))
            for row in category_rows:
                score = row.record.attribution_score
                deviation = abs(float(score) - mean_score)
                if deviation > threshold:
                    cases.append(
                        {
                            "trace_id": row.record.trace_id,
                            "bucket": f"category:{category.name}",
                            "deviation": deviation,
                            "explanation": (
                                f"attribution score {score:.2f} deviates significantly "
                                f"from bucket mean {mean_score:.2f}"
                            ),
                        }
                    )
        return sorted(cases, key=lambda item: (item["bucket"], item["trace_id"]))

    def _valid_rows(self, inputs: StratifiedInput) -> list[_EvalRow]:
        traces = inputs.traces or {}
        rows: list[_EvalRow] = []
        for index, record in enumerate(inputs.records):
            annotation = inputs.annotations.get(record.trace_id)
            if annotation is None:
                LOGGER.warning("Skipping trace_id=%s because annotation is missing.", record.trace_id)
                continue
            trace = traces.get(record.trace_id)
            if trace is None:
                LOGGER.warning("Trace metadata missing for trace_id=%s.", record.trace_id)
            rows.append(_EvalRow(index=index, record=record, annotation=annotation, trace=trace))
        return rows

    def _build_buckets(self, rows: list[_EvalRow], dimension: str) -> list[StratifiedBucket]:
        if dimension in {"necessity", "redundancy", "faithfulness"}:
            return self._build_dynamic_buckets(rows, dimension)

        bucket_indices: dict[str, list[int]] = {name: [] for name in DIMENSION_BUCKETS[dimension]}
        for row in rows:
            bucket_name = self._bucket_name(row, dimension)
            if bucket_name is None:
                continue
            bucket_indices[bucket_name].append(row.index)

        return [
            StratifiedBucket(
                dimension=dimension,
                bucket_name=bucket_name,
                indices=indices,
                n_samples=len(indices),
            )
            for bucket_name, indices in bucket_indices.items()
        ]

    def _bucket_metrics(self, rows: list[_EvalRow], all_rows: list[_EvalRow]) -> BucketMetrics:
        if len(rows) < MIN_BUCKET_SIZE:
            return BucketMetrics(
                mean_utility_delta=float("nan"),
                utility_variance=float("nan"),
                mean_attribution_score=float("nan"),
                attribution_stability=float("nan"),
                intervention_sensitivity=float("nan"),
                n_samples=len(rows),
                status="insufficient_samples",
                utility_status="insufficient_samples",
                necessity_status="insufficient_samples",
                redundancy_status="insufficient_samples",
                faithfulness_status="insufficient_samples",
                required=MIN_BUCKET_SIZE,
                utility_required=MIN_UTILITY_BUCKET_SIZE,
            )

        utility_deltas = np.asarray([row.record.utility_delta for row in rows], dtype=float)
        utility_status = "ok" if len(utility_deltas) >= MIN_UTILITY_BUCKET_SIZE else "insufficient_samples"
        attribution_scores = np.asarray([row.record.attribution_score for row in rows], dtype=float)
        mean_attribution = float(np.mean(attribution_scores))
        attribution_stability = bounded_stability(attribution_scores)
        _perturbation_stability = self.stability_analyzer.compute_stability(
            attribution_scores,
            lambda scores: np.asarray([np.mean(scores)], dtype=float),
        )

        return BucketMetrics(
            mean_utility_delta=float(np.mean(utility_deltas)),
            utility_variance=float(np.var(utility_deltas, ddof=1)),
            mean_attribution_score=mean_attribution,
            attribution_stability=attribution_stability,
            intervention_sensitivity=self._intervention_sensitivity(rows, all_rows),
            n_samples=len(rows),
            utility_status=utility_status,
            necessity_status=self._field_status(rows, "necessity_score"),
            redundancy_status=self._field_status(rows, "redundancy_ratio"),
            faithfulness_status="ok" if len(attribution_scores) >= MIN_BUCKET_SIZE else "insufficient_samples",
        )

    def _build_dynamic_buckets(self, rows: list[_EvalRow], dimension: str) -> list[StratifiedBucket]:
        bucket_names = DIMENSION_BUCKETS[dimension]
        bucket_indices: dict[str, list[int]] = {name: [] for name in bucket_names}
        values: list[tuple[_EvalRow, float]] = []
        for row in rows:
            value = self._dynamic_value(row, dimension)
            if value is None:
                continue
            values.append((row, value))

        values.sort(key=lambda item: (item[1], item[0].index))
        if values:
            for rank, (row, _value) in enumerate(values):
                bucket_index = min(
                    len(bucket_names) - 1,
                    int(rank * len(bucket_names) / len(values)),
                )
                bucket_indices[bucket_names[bucket_index]].append(row.index)

        return [
            StratifiedBucket(
                dimension=dimension,
                bucket_name=bucket_name,
                indices=indices,
                n_samples=len(indices),
            )
            for bucket_name, indices in bucket_indices.items()
        ]

    @staticmethod
    def _intervention_sensitivity(rows: list[_EvalRow], all_rows: list[_EvalRow]) -> float:
        weak = [
            row.record.utility_delta
            for row in rows
            if row.trace is not None and row.trace.intervention_magnitude < 0.3
        ]
        strong = [
            row.record.utility_delta
            for row in rows
            if row.trace is not None and row.trace.intervention_magnitude > 0.7
        ]
        if not weak or not strong:
            return float("nan")

        all_utility_deltas = np.asarray([row.record.utility_delta for row in all_rows], dtype=float)
        denominator = float(np.std(all_utility_deltas)) + 1e-6
        return float(abs(np.mean(strong) - np.mean(weak)) / denominator)

    @staticmethod
    def _bucket_name(row: _EvalRow, dimension: str) -> str | None:
        if dimension == "category":
            return row.annotation.category.name
        if dimension == "difficulty":
            if row.trace is None:
                return None
            return StratifiedEvaluator._difficulty_bucket(row.trace.task_difficulty)
        if dimension == "intervention":
            if row.trace is None:
                return None
            return StratifiedEvaluator._intervention_bucket(row.trace.intervention_magnitude)
        if dimension == "locality":
            if row.trace is None:
                return "local" if row.record.is_local else "global"
            return StratifiedEvaluator._locality_bucket(row.trace.locality_score)
        if dimension == "trace_length":
            if row.trace is None:
                return None
            return StratifiedEvaluator._trace_length_bucket(len(row.trace.reflection_text))
        raise ValueError(f"Unsupported stratification dimension {dimension!r}.")

    @staticmethod
    def _dynamic_value(row: _EvalRow, dimension: str) -> float | None:
        if dimension == "necessity":
            return StratifiedEvaluator._finite_or_none(row.record.necessity_score)
        if dimension == "redundancy":
            return StratifiedEvaluator._finite_or_none(row.record.redundancy_ratio)
        if dimension == "faithfulness":
            return StratifiedEvaluator._finite_or_none(row.record.attribution_score)
        raise ValueError(f"Unsupported dynamic stratification dimension {dimension!r}.")

    @staticmethod
    def _field_status(rows: list[_EvalRow], field_name: str) -> str:
        count = sum(
            1
            for row in rows
            if StratifiedEvaluator._finite_or_none(getattr(row.record, field_name)) is not None
        )
        return "ok" if count >= MIN_BUCKET_SIZE else "insufficient_samples"

    @staticmethod
    def _finite_or_none(value: float | None) -> float | None:
        if value is None:
            return None
        number = float(value)
        if not np.isfinite(number):
            return None
        return number

    @staticmethod
    def _difficulty_bucket(task_difficulty: int) -> str:
        if task_difficulty <= 2:
            return "low"
        if task_difficulty == 3:
            return "medium"
        return "high"

    @staticmethod
    def _intervention_bucket(intervention_magnitude: float) -> str:
        if intervention_magnitude < 0.3:
            return "weak"
        if intervention_magnitude <= 0.7:
            return "moderate"
        return "strong"

    @staticmethod
    def _locality_bucket(locality_score: float) -> str:
        if locality_score >= 0.8:
            return "local"
        if locality_score >= 0.4:
            return "mixed"
        return "global"

    @staticmethod
    def _trace_length_bucket(trace_length: int) -> str:
        if trace_length < 50:
            return "short"
        if trace_length <= 200:
            return "medium"
        return "long"
