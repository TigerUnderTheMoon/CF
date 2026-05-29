"""Redundancy-density metrics over reflective node profiles."""

from __future__ import annotations

from typing import Any, Sequence

from fma.eval.redundancy.overlap import (
    NodeProfile,
    hybrid_similarity,
    mean,
    profiles_by_task,
)


def compute_redundancy(
    profiles: Sequence[NodeProfile],
    similarity_threshold: float = 0.75,
) -> dict[str, Any]:
    """Compute deterministic redundancy clusters and node redundancy degrees."""
    cluster_sizes: list[int] = []
    cluster_densities: list[float] = []
    pair_values: list[float] = []
    per_trajectory: dict[str, dict[str, Any]] = {}
    degree_by_node: dict[str, float] = {profile.node_id: 0.0 for profile in profiles}
    clusters_out: list[list[str]] = []

    for task_id, group in profiles_by_task(profiles).items():
        similarities = _pairwise(group)
        pair_values.extend(similarities.values())
        for profile in group:
            values = [
                value
                for (left, right), value in similarities.items()
                if profile.node_id in (left, right)
            ]
            degree_by_node[profile.node_id] = mean(values)

        clusters = _clusters(group, similarities, similarity_threshold)
        trajectory_cluster_sizes = [len(cluster) for cluster in clusters]
        trajectory_density = mean(list(similarities.values()))
        per_trajectory[task_id] = {
            "density": trajectory_density,
            "cluster_sizes": trajectory_cluster_sizes,
            "mean_cluster_size": mean([float(size) for size in trajectory_cluster_sizes]),
        }
        for cluster in clusters:
            cluster_sizes.append(len(cluster))
            cluster_densities.append(_cluster_density(cluster, similarities))
            clusters_out.append(cluster)

    return {
        "density": mean(pair_values),
        "cluster_sizes": cluster_sizes,
        "mean_cluster_size": mean([float(size) for size in cluster_sizes]),
        "average_redundancy_degree": mean(list(degree_by_node.values())),
        "cluster_density": mean(cluster_densities),
        "redundancy_degree_by_node": degree_by_node,
        "per_trajectory": per_trajectory,
        "clusters": clusters_out,
        "similarity_threshold": float(similarity_threshold),
    }


def _pairwise(group: Sequence[NodeProfile]) -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], float] = {}
    for left_index, left in enumerate(group):
        for right in group[left_index + 1 :]:
            values[(left.node_id, right.node_id)] = hybrid_similarity(left, right)
    return values


def _clusters(
    group: Sequence[NodeProfile],
    similarities: dict[tuple[str, str], float],
    threshold: float,
) -> list[list[str]]:
    parent = {profile.node_id: profile.node_id for profile in group}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    for (left, right), value in similarities.items():
        if value >= threshold:
            union(left, right)

    grouped: dict[str, list[str]] = {}
    for profile in group:
        grouped.setdefault(find(profile.node_id), []).append(profile.node_id)
    return [sorted(nodes) for _root, nodes in sorted(grouped.items())]


def _cluster_density(
    cluster: Sequence[str],
    similarities: dict[tuple[str, str], float],
) -> float:
    if len(cluster) < 2:
        return 0.0
    values: list[float] = []
    for left_index, left in enumerate(cluster):
        for right in cluster[left_index + 1 :]:
            values.append(similarities.get((left, right), similarities.get((right, left), 0.0)))
    return mean(values)


__all__ = ["compute_redundancy"]
