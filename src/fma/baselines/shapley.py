"""Monte Carlo Shapley value estimation for step-level importance.

Family C: Shapley Value
  - Monte Carlo approximation over reasoning step coalitions
  - Compatible with any outcome evaluator
  - Produces step-level contribution scores
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ShapleyConfig:
    n_samples: int = 200
    seed: int = 42
    normalize: bool = True
    use_antithetic: bool = True


def _evaluate_steps(
    step_subset: set[int],
    all_step_scores: list[float],
) -> float:
    if not step_subset:
        return 0.0
    return float(np.mean([all_step_scores[i] for i in step_subset if 0 <= i < len(all_step_scores)]))


def _generate_coalition(
    n_steps: int,
    rng: np.random.Generator,
    use_antithetic: bool = False,
    exclude_idx: int | None = None,
) -> tuple[set[int], set[int]]:
    coalition = set[int]()
    for i in range(n_steps):
        if exclude_idx is not None and i == exclude_idx:
            continue
        if rng.random() > 0.5:
            coalition.add(i)
    complement = set(range(n_steps)) - coalition
    if exclude_idx is not None:
        complement.discard(exclude_idx)
    return coalition, complement


def compute_shapley_step_scores(
    step_ciu: list[float],
    config: ShapleyConfig | None = None,
) -> list[float]:
    if config is None:
        config = ShapleyConfig()

    n = len(step_ciu)
    if n == 0:
        return []
    if n == 1:
        return [1.0]

    rng = np.random.default_rng(config.seed)
    shapley = np.zeros(n, dtype=float)

    evaluation_fn = step_ciu

    for _ in range(config.n_samples):
        permutation = rng.permutation(n).tolist()
        coalition: set[int] = set()

        for i in permutation:
            val_without = _evaluate_steps(coalition, evaluation_fn)
            coalition.add(i)
            val_with = _evaluate_steps(coalition, evaluation_fn)
            shapley[i] += val_with - val_without

        if config.use_antithetic:
            coalition.clear()
            rev_perm = list(reversed(permutation))
            for i in rev_perm:
                val_without = _evaluate_steps(coalition, evaluation_fn)
                coalition.add(i)
                val_with = _evaluate_steps(coalition, evaluation_fn)
                shapley[i] += val_with - val_without
            shapley /= 2.0

    shapley /= config.n_samples

    if config.normalize:
        total = np.sum(np.abs(shapley))
        if total > 1e-10:
            shapley = shapley / total
        else:
            shapley = np.ones(n) / n

    shapley = np.maximum(shapley, 0.0)
    s = np.sum(shapley)
    if s > 1e-10:
        shapley = shapley / s

    return [float(v) for v in shapley]


def shapley_value_permutation(
    step_scores: list[float],
    n_permutations: int = 50,
    seed: int = 42,
) -> list[float]:
    n = len(step_scores)
    if n == 0:
        return []
    if n == 1:
        return [1.0]

    rng = np.random.default_rng(seed)
    contributions = np.zeros(n)
    count = np.zeros(n)

    for _ in range(n_permutations):
        perm = rng.permutation(n).tolist()
        running = 0.0
        for idx in perm:
            score = step_scores[idx]
            contributions[idx] += score - running
            running = score
            count[idx] += 1

    count = np.maximum(count, 1)
    mean_contrib = contributions / count
    total = np.sum(np.abs(mean_contrib))
    if total > 1e-10:
        mean_contrib = mean_contrib / total
    else:
        mean_contrib = np.ones(n) / n

    mean_contrib = np.maximum(mean_contrib, 0.0)
    return [float(v) for v in mean_contrib / np.sum(mean_contrib)]
