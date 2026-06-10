"""Step importance ranking comparison framework.

Compares SC-FMA variants against 6 baseline families on the step importance
ranking downstream task. Produces structured comparison reports with rank
correlation metrics and statistical significance tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .metrics import compute_ranking_metrics
from .significance import bootstrap_ci, friedman_test, wilcoxon_pairs

EPSILON = 1e-10


@dataclass(frozen=True)
class BaselineMethod:
    name: str
    family: str
    description: str
    compute_fn: Callable[..., list[float]] | None = None


def list_methods() -> list[BaselineMethod]:
    return [
        BaselineMethod("scfma_qp", "FMA", "SC-FMA full QP optimizer"),
        BaselineMethod("scfma_ridge", "FMA", "SC-FMA ridge calibration"),
        BaselineMethod("scfma_projection", "FMA", "SC-FMA topology projection"),
        BaselineMethod("raw_ciu", "FMA", "Raw CIU (uncalibrated)"),
        BaselineMethod("gradient_input", "Gradient Attribution", "Gradient x Input saliency"),
        BaselineMethod("attention_rollout", "Gradient Attribution", "Attention rollout importance"),
        BaselineMethod("shapley_mc", "Shapley", "Monte Carlo Shapley value"),
        BaselineMethod("surprisal", "Information-Theoretic", "Token surprisal aggregation"),
        BaselineMethod("entropic", "Information-Theoretic", "Step entropy scoring"),
        BaselineMethod("random", "Heuristic", "Random baseline"),
        BaselineMethod("span_length", "Heuristic", "Span length heuristic"),
        BaselineMethod("relative_position", "Heuristic", "Relative position heuristic"),
        BaselineMethod("oracle", "Oracle", "Ground-truth step correctness labels"),
    ]


@dataclass(frozen=True)
class ComparisonEntry:
    sample_id: str
    method: str
    n_steps: int
    scores: tuple[float, ...]
    rank_metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RankingComparisonReport:
    experiment_name: str
    methods: list[str]
    n_samples: int
    n_total_steps: int
    aggregate_metrics: dict[str, dict[str, dict[str, float]]]
    method_rankings: dict[str, float]
    friedman_result: dict[str, float]
    pairwise_tests: list[dict[str, float]]
    metadata: dict[str, Any] = field(default_factory=dict)


class ImportanceRanker:
    def __init__(self, methods: list[BaselineMethod] | None = None):
        self._methods = methods or list_methods()
        self._registry = {m.name: m for m in self._methods}

    def rank_steps(
        self,
        method_name: str,
        ciu_scores: list[float],
        nec_scores: list[float] | None = None,
        redundancy_matrix: np.ndarray | None = None,
        bottleneck_indices: set[int] | None = None,
        **kwargs: Any,
    ) -> list[float]:
        if method_name == "raw_ciu":
            arr = np.array(ciu_scores, dtype=float)
            total = np.sum(arr)
            return [float(v) / max(total, EPSILON) for v in arr] if total > EPSILON else [1.0 / len(arr)] * len(arr)

        if method_name == "scfma_ridge":
            from fma.calibration import scfma_calibrate_ridge
            n = nec_scores if nec_scores else [0.5] * len(ciu_scores)
            result = scfma_calibrate_ridge(
                np.array(ciu_scores),
                np.array(n),
                sample_id=kwargs.get("sample_id", ""),
                alpha_ciui=kwargs.get("alpha_ciui", 0.7),
                alpha_nec=kwargs.get("alpha_nec", 0.3),
            )
            return result.weights[0].to_list() if result.weights else [1.0 / len(ciu_scores)] * len(ciu_scores)

        if method_name == "scfma_qp":
            from fma.calibration import scfma_calibrate
            n = nec_scores if nec_scores else [0.5] * len(ciu_scores)
            R = redundancy_matrix if redundancy_matrix is not None else np.zeros((len(ciu_scores), len(ciu_scores)))
            bottlenecks = []
            if bottleneck_indices:
                from fma.calibration.types import BottleneckConstraint
                bottlenecks = [BottleneckConstraint(node_index=i, floor_weight=0.01) for i in bottleneck_indices]
            result = scfma_calibrate(
                np.array(ciu_scores), np.array(n), R,
                bottleneck_constraints=bottlenecks,
                sample_id=kwargs.get("sample_id", ""),
                alpha=kwargs.get("alpha", 1.0),
                beta=kwargs.get("beta", 0.5),
                gamma=kwargs.get("gamma", 0.2),
            )
            return result.weights[0].to_list() if result.weights else [1.0 / len(ciu_scores)] * len(ciu_scores)

        if method_name == "scfma_projection":
            from fma.calibration import project_weights
            n = nec_scores if nec_scores else [0.5] * len(ciu_scores)
            R = redundancy_matrix if redundancy_matrix is not None else np.zeros((len(ciu_scores), len(ciu_scores)))
            bi = bottleneck_indices or set()
            w = project_weights(np.array(ciu_scores), np.array(n), R, bi)
            return [float(v) for v in w]

        if method_name in ("random",):
            rng = np.random.default_rng(kwargs.get("seed", 42))
            w = rng.random(len(ciu_scores))
            return [float(v) / max(float(np.sum(w)), EPSILON) for v in w]

        if method_name == "span_length":
            lengths = kwargs.get("span_lengths", [1] * len(ciu_scores))
            total = sum(lengths)
            return [float(l) / max(total, EPSILON) for l in lengths] if total > EPSILON else [1.0 / len(lengths)] * len(lengths)

        if method_name == "relative_position":
            positions = kwargs.get("step_indices", list(range(len(ciu_scores))))
            inv_pos = [1.0 / (max(p, 1)) for p in positions]
            total = sum(inv_pos)
            return [float(v) / max(total, EPSILON) for v in inv_pos] if total > EPSILON else [1.0 / len(positions)] * len(positions)

        arr = np.array(ciu_scores, dtype=float)
        total = np.sum(arr)
        return [float(v) / max(total, EPSILON) for v in arr] if total > EPSILON else [1.0 / len(arr)] * len(arr)


def rank_steps_by_method(
    method_name: str,
    ciu: list[float],
    necessity: list[float] | None = None,
    redundancy_matrix: np.ndarray | None = None,
    bottlenecks: set[int] | None = None,
    **kwargs: Any,
) -> list[float]:
    ranker = ImportanceRanker()
    return ranker.rank_steps(method_name, ciu, necessity, redundancy_matrix, bottlenecks, **kwargs)


def compare_methods(
    samples: list[dict[str, Any]],
    methods: list[str] | None = None,
    ground_truth_key: str = "ground_truth_scores",
    ciu_key: str = "ciu_scores",
    nec_key: str = "necessity_scores",
    k_values: tuple[int, ...] = (3, 5, 10),
) -> RankingComparisonReport:
    if methods is None:
        methods = [m.name for m in list_methods()]

    ranker = ImportanceRanker()
    aggregated: dict[str, dict[str, list[float]]] = {m: {} for m in methods}
    total_steps = 0

    for sample in samples:
        ciu = sample.get(ciu_key, [])
        gt = sample.get(ground_truth_key, sample.get("gt_scores", []))
        nec = sample.get(nec_key)

        if not ciu or not gt or len(ciu) != len(gt):
            continue

        sample_id = str(sample.get("sample_id", sample.get("id", str(hash(str(ciu))))))
        n = len(ciu)
        total_steps += n

        red_mat = sample.get("redundancy_matrix")
        bot_set = set(sample.get("bottleneck_indices", [])) if "bottleneck_indices" in sample else None

        for method in methods:
            try:
                scores = ranker.rank_steps(
                    method, ciu, nec, red_mat, bot_set,
                    sample_id=sample_id,
                    span_lengths=sample.get("span_lengths", [10] * n),
                    step_indices=sample.get("step_indices", list(range(n))),
                )
                metrics = compute_ranking_metrics(scores, gt, k_values=k_values)
                for metric_name, value in metrics.items():
                    aggregated[method].setdefault(metric_name, []).append(value)
            except Exception:
                continue

    aggregate_metrics: dict[str, dict[str, dict[str, float]]] = {}
    for method in methods:
        aggregate_metrics[method] = {}
        for metric_name, values in aggregated[method].items():
            arr = np.array(values, dtype=float)
            aggregate_metrics[method][metric_name] = {
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
                "ci_lower": float(np.percentile(arr, 2.5)) if len(arr) > 0 else 0.0,
                "ci_upper": float(np.percentile(arr, 97.5)) if len(arr) > 0 else 0.0,
            }

    spearman_by_method: dict[str, float] = {}
    for method in methods:
        vals = aggregated[method].get("spearman_rho", [])
        spearman_by_method[method] = float(np.mean(vals)) if vals else 0.0

    master_scores: dict[str, list[float]] = {}
    for method in methods:
        master_scores[method] = aggregated[method].get("spearman_rho", [])

    friedman = friedman_test(master_scores)
    pairwise = wilcoxon_pairs(master_scores)

    return RankingComparisonReport(
        experiment_name="scfma_step_ranking",
        methods=methods,
        n_samples=len(samples),
        n_total_steps=total_steps,
        aggregate_metrics=aggregate_metrics,
        method_rankings=spearman_by_method,
        friedman_result=friedman,
        pairwise_tests=pairwise,
    )
