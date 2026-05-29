"""Compensation-ratio metrics for Phase 7 redundancy analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from fma.eval.diagnostics.correlation_metrics import distribution_summary
from fma.eval.redundancy.overlap import MODE_ORDER, NodeProfile, mean, profile_by_node
from fma.eval.structural_attribution import compute_node_necessity
from fma.graph.reflection_graph import ReflectionGraph, RemovalMode


@dataclass(frozen=True)
class AffectedNodeDelta:
    node_id: str
    necessity_pre: float
    necessity_post: float
    necessity_delta: float
    distance: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InterventionDelta:
    task_id: str
    mode: str
    removed_node: str
    affected_nodes: tuple[AffectedNodeDelta, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["affected_nodes"] = [node.to_dict() for node in self.affected_nodes]
        return payload


@dataclass(frozen=True)
class CompensationRecord:
    task_id: str
    mode: str
    removed_node: str
    taxonomy: str
    source_role: str
    step_idx: int
    attribution_score: float
    removed_necessity: float
    compensation_ratio: float
    positive_redistribution: float
    affected_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reconstruct_intervention_deltas(
    graphs: Sequence[ReflectionGraph],
    modes: Sequence[str] = MODE_ORDER,
) -> list[InterventionDelta]:
    """Reconstruct node-level post-removal deltas from stored Phase 6 graphs."""
    deltas: list[InterventionDelta] = []
    for graph in sorted(graphs, key=lambda item: item.graph_id):
        for mode_name in modes:
            mode = RemovalMode(str(mode_name).upper())
            pre_rows = {
                row.node_id: row
                for row in compute_node_necessity(graph, removal_mode=mode)
            }
            for node in graph.sorted_nodes():
                distances = graph.shortest_distances_from(node.node_id)
                downstream = sorted(
                    node_id for node_id in distances if node_id != node.node_id
                )
                if not downstream:
                    deltas.append(
                        InterventionDelta(
                            task_id=graph.graph_id,
                            mode=mode.value,
                            removed_node=node.node_id,
                            affected_nodes=(),
                        )
                    )
                    continue

                ablated = graph.remove_node(node.node_id, mode)
                post_rows = {
                    row.node_id: row
                    for row in compute_node_necessity(ablated, removal_mode=mode)
                }
                affected: list[AffectedNodeDelta] = []
                for downstream_id in downstream:
                    pre = float(pre_rows.get(downstream_id).necessity) if downstream_id in pre_rows else 0.0
                    post = (
                        float(post_rows[downstream_id].necessity)
                        if downstream_id in post_rows
                        else 0.0
                    )
                    affected.append(
                        AffectedNodeDelta(
                            node_id=downstream_id,
                            necessity_pre=pre,
                            necessity_post=post,
                            necessity_delta=post - pre,
                            distance=int(distances[downstream_id]),
                        )
                    )
                deltas.append(
                    InterventionDelta(
                        task_id=graph.graph_id,
                        mode=mode.value,
                        removed_node=node.node_id,
                        affected_nodes=tuple(affected),
                    )
                )
    return deltas


def compute_compensation_records(
    profiles: Sequence[NodeProfile],
    deltas: Sequence[InterventionDelta],
) -> list[CompensationRecord]:
    profiles_by_node_id = profile_by_node(profiles)
    records: list[CompensationRecord] = []
    for delta in deltas:
        profile = profiles_by_node_id.get(delta.removed_node)
        if profile is None:
            continue
        downstream = set(profile.downstream_nodes)
        positive = sum(
            max(0.0, affected.necessity_delta)
            for affected in delta.affected_nodes
            if affected.node_id in downstream
        )
        removed_necessity = profile.necessity(delta.mode)
        ratio = positive / max(0.001, abs(removed_necessity))
        records.append(
            CompensationRecord(
                task_id=delta.task_id,
                mode=str(delta.mode).upper(),
                removed_node=delta.removed_node,
                taxonomy=profile.taxonomy,
                source_role=profile.source_role,
                step_idx=profile.step_idx,
                attribution_score=profile.attribution_score,
                removed_necessity=removed_necessity,
                compensation_ratio=float(ratio),
                positive_redistribution=float(positive),
                affected_count=len(delta.affected_nodes),
            )
        )
    return records


def summarize_compensation(
    records: Sequence[CompensationRecord],
    modes: Sequence[str] = MODE_ORDER,
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for mode in modes:
        mode_key = str(mode).upper()
        mode_records = [record for record in records if record.mode == mode_key]
        ratios = [record.compensation_ratio for record in mode_records]
        summary[mode_key.lower()] = {
            "mean_ratio": mean(ratios),
            "distribution": distribution_summary(ratios),
            "stratified_by_taxonomy": stratify_compensation(mode_records, "taxonomy"),
            "stratified_by_source_role": stratify_compensation(mode_records, "source_role"),
            "stratified_by_step_idx": stratify_compensation(mode_records, "step_idx"),
        }
    return summary


def stratify_compensation(
    records: Sequence[CompensationRecord],
    field_name: str,
) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[float]] = {}
    for record in records:
        value = getattr(record, field_name)
        grouped.setdefault(str(value), []).append(record.compensation_ratio)
    return {
        key: {"count": float(len(values)), "mean_ratio": mean(values)}
        for key, values in sorted(grouped.items())
    }


def deltas_from_records(records: Sequence[Mapping[str, Any]]) -> list[InterventionDelta]:
    deltas: list[InterventionDelta] = []
    for record in records:
        affected = tuple(
            AffectedNodeDelta(
                node_id=str(row.get("node_id")),
                necessity_pre=float(row.get("necessity_pre", 0.0)),
                necessity_post=float(row.get("necessity_post", 0.0)),
                necessity_delta=float(row.get("necessity_delta", 0.0)),
                distance=int(row.get("distance", 0)),
            )
            for row in record.get("affected_nodes", [])
            if isinstance(row, Mapping)
        )
        deltas.append(
            InterventionDelta(
                task_id=str(record.get("task_id", "")),
                mode=str(record.get("mode", "PRUNE")).upper(),
                removed_node=str(record.get("removed_node", "")),
                affected_nodes=affected,
            )
        )
    return deltas


__all__ = [
    "AffectedNodeDelta",
    "CompensationRecord",
    "InterventionDelta",
    "compute_compensation_records",
    "deltas_from_records",
    "reconstruct_intervention_deltas",
    "stratify_compensation",
    "summarize_compensation",
]
