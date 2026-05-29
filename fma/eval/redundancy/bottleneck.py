"""Bottleneck detection for rare high-utility, low-redundancy nodes."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from fma.eval.redundancy.overlap import (
    NodeProfile,
    min_max_normalize,
    overall_necessity,
)


def compute_bottlenecks(
    profiles: Sequence[NodeProfile],
    redundancy_degree_by_node: Mapping[str, float],
    threshold: float = 0.25,
) -> dict[str, Any]:
    """Return bottleneck scores and thresholded candidate summaries."""
    if not profiles:
        return {
            "bottleneck_count": 0,
            "frequency": 0.0,
            "rarity": 0.0,
            "taxonomy_distribution": {},
            "examples": [],
            "scores_by_node": {},
            "threshold": float(threshold),
        }

    attr_norm = min_max_normalize([profile.attribution_score for profile in profiles])
    nec_norm = min_max_normalize([overall_necessity(profile) for profile in profiles])
    red_norm = min_max_normalize(
        [float(redundancy_degree_by_node.get(profile.node_id, 0.0)) for profile in profiles]
    )

    scores: dict[str, dict[str, float | str | int]] = {}
    candidates: list[tuple[float, NodeProfile]] = []
    for profile, attr, nec, red in zip(profiles, attr_norm, nec_norm, red_norm):
        score = float(attr * nec * (1.0 - red))
        scores[profile.node_id] = {
            "bottleneck_score": score,
            "normalized_attribution": float(attr),
            "normalized_necessity": float(nec),
            "normalized_redundancy_degree": float(red),
            "taxonomy": profile.taxonomy,
            "step_idx": profile.step_idx,
        }
        if score >= threshold and attr > 0.0 and nec > 0.0:
            candidates.append((score, profile))

    candidates = sorted(
        candidates,
        key=lambda item: (-item[0], item[1].task_id, item[1].step_idx, item[1].node_id),
    )
    taxonomy_counts = Counter(profile.taxonomy for _score, profile in candidates)
    frequency = len(candidates) / len(profiles)
    return {
        "bottleneck_count": len(candidates),
        "frequency": float(frequency),
        "rarity": float(1.0 - frequency),
        "taxonomy_distribution": dict(sorted(taxonomy_counts.items())),
        "examples": [
            {
                "node_id": profile.node_id,
                "task_id": profile.task_id,
                "step_idx": profile.step_idx,
                "taxonomy": profile.taxonomy,
                "bottleneck_score": score,
            }
            for score, profile in candidates[:10]
        ],
        "scores_by_node": scores,
        "threshold": float(threshold),
    }


__all__ = ["compute_bottlenecks"]
