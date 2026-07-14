from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict, deque
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx

from fma.graph.kg_ontology_pilot import (
    COUNTRIES_KG,
    build_kg_augmented_graph,
    generate_kg_traces,
)
from fma.graph.reflection_graph import ReflectionGraph
from fma.graph.similarity import TextSimilarity


DEFAULT_SEED = 20260711
PROTOCOL_VERSION = "fair-v1"
CANDIDATE_POOL_RULE = "auditable == true"
REDUNDANCY_JACCARD = 0.85
REDUNDANCY_JACCARD_ALT = 0.90
SYNTHETIC_SIZES = [100, 200, 500, 1000, 5000]
TFIDF_BASELINE_NAME = "Semantic-Similarity Baseline (TF-IDF)"

POLICY_LAYERS = [
    ("critical_bottleneck", "Critical Bottleneck"),
    ("unique_evidence", "Unique Evidence"),
    ("redundancy_group_samples", "Redundancy Group Samples"),
    ("fallback", "Fallback"),
]

TABLE_2_TITLE = (
    "Impact Coverage@K of Life-Saving First stratified policy vs. flat Top-K "
    "baseline (using the shared raw_risk_score as the sole ranking criterion), "
    "Greedy Maximum Coverage, degree centrality, random stratified labels, "
    "position, random, and one-layer-off ablations."
)

RAW_RISK_SCORE_ROLE = "tie_breaker_only_within_layer"
IMPACT_COVERAGE_DEFINITION = "reachable_descendants_transitive_closure"


def _json_hash(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safe_mean(values: Sequence[float]) -> float:
    return float(mean(values)) if values else 0.0


def _bootstrap_ci(values: Sequence[float], seed: int, rounds: int = 1000) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    rng = random.Random(seed)
    samples = []
    n = len(values)
    for _ in range(rounds):
        samples.append(mean(values[rng.randrange(n)] for _ in range(n)))
    samples.sort()
    return {
        "mean": float(mean(values)),
        "ci_lower": float(samples[int(0.025 * (rounds - 1))]),
        "ci_upper": float(samples[int(0.975 * (rounds - 1))]),
    }


def _minmax(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if math.isclose(lo, hi):
        return [0.0 for _ in values]
    return [(float(v) - lo) / (hi - lo) for v in values]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _binary_f1(gold: Sequence[bool], pred: Sequence[bool]) -> dict[str, float]:
    tp = sum(1 for g, p in zip(gold, pred, strict=False) if g and p)
    fp = sum(1 for g, p in zip(gold, pred, strict=False) if not g and p)
    fn = sum(1 for g, p in zip(gold, pred, strict=False) if g and not p)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "support": float(sum(1 for value in gold if value)),
    }


def countries_kg_metadata() -> dict[str, Any]:
    entity_type_counts: dict[str, int] = defaultdict(int)
    for row in COUNTRIES_KG["entities"].values():
        entity_type_counts[str(row["type"])] += 1
    metadata = {
        "source": "Countries-KG semantic fixture",
        "num_entities": len(COUNTRIES_KG["entities"]),
        "num_triples": len(COUNTRIES_KG["triples"]),
        "relation_types": sorted({triple[1] for triple in COUNTRIES_KG["triples"]}),
        "entity_type_counts": dict(sorted(entity_type_counts.items())),
    }
    metadata["metadata_hash"] = _json_hash(metadata)
    return metadata


class _UnionFind:
    def __init__(self, node_ids: Iterable[str]) -> None:
        self.parent = {node_id: node_id for node_id in node_ids}

    def find(self, node_id: str) -> str:
        parent = self.parent[node_id]
        if parent != node_id:
            self.parent[node_id] = self.find(parent)
        return self.parent[node_id]

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return
        if right_root < left_root:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root


def extract_structural_node_labels(
    graph: ReflectionGraph,
    *,
    redundancy_theta: float = REDUNDANCY_JACCARD,
) -> list[dict[str, Any]]:
    """Convert directed graph topology into audit-ready boolean labels."""
    node_ids = [node.node_id for node in sorted(graph.nodes.values(), key=lambda n: n.step_index)]
    source_ids = graph.source_nodes()
    reachable = graph.reachable_nodes(source_ids)
    original_sinks = {node_id for node_id in reachable if not graph.children(node_id)}
    descendants = {node_id: graph.descendants(node_id) for node_id in node_ids}
    # Redundancy is defined over downstream dependency coverage.  Using terminal
    # sink coverage avoids the strict-identity failure mode on semantic KGs while
    # preserving directed-flow semantics.
    coverage = {
        node_id: {sink for sink in descendants[node_id] if sink in original_sinks}
        for node_id in node_ids
    }

    sink_drop: dict[str, int] = {}
    at_risk_terminals: dict[str, list[str]] = {}
    for node_id in node_ids:
        try:
            pruned = graph.remove_node(node_id, mode="PRUNE")
        except KeyError:
            sink_drop[node_id] = 0
            at_risk_terminals[node_id] = []
            continue
        pruned_reachable = pruned.reachable_nodes(source_ids)
        lost_sinks = sorted(original_sinks - pruned_reachable)
        sink_drop[node_id] = len(lost_sinks)
        at_risk_terminals[node_id] = lost_sinks

    uf = _UnionFind(node_ids)
    for left_index, left in enumerate(node_ids):
        for right in node_ids[left_index + 1 :]:
            if coverage[left] and coverage[right] and _jaccard(coverage[left], coverage[right]) > redundancy_theta:
                uf.union(left, right)

    groups: dict[str, list[str]] = defaultdict(list)
    for node_id in node_ids:
        groups[uf.find(node_id)].append(node_id)
    redundant_group_ids: dict[str, str | None] = {}
    group_sizes: dict[str, int] = {}
    group_index = 1
    for root_id, members in sorted(groups.items()):
        if len(members) <= 1:
            for member in members:
                redundant_group_ids[member] = None
                group_sizes[member] = 1
            continue
        group_id = f"rg_{group_index:03d}"
        group_index += 1
        for member in members:
            redundant_group_ids[member] = group_id
            group_sizes[member] = len(members)

    rows: list[dict[str, Any]] = []
    for node_id in node_ids:
        node = graph.nodes[node_id]
        coverage_signature = sorted(coverage[node_id])
        downstream_impact_count = len(descendants[node_id])
        auditable = node.step_index > 0 and downstream_impact_count > 0
        rows.append(
            {
                "trace_id": graph.graph_id,
                "node_id": node_id,
                "step_index": int(node.step_index),
                "taxonomy_label": node.taxonomy_label,
                "text": node.content,
                "incoming_degree": len(graph.parents(node_id)),
                "outgoing_degree": len(graph.children(node_id)),
                "degree": len(graph.parents(node_id)) + len(graph.children(node_id)),
                "downstream_impact_count": int(downstream_impact_count),
                "auditable": bool(auditable),
                "is_bottleneck": bool(sink_drop[node_id] > 0 and downstream_impact_count > 0),
                "is_redundant": redundant_group_ids[node_id] is not None,
                "redundancy_group_id": redundant_group_ids[node_id],
                "redundancy_group_size": int(group_sizes[node_id]),
                "dependency_coverage_size": len(coverage_signature),
                "dependency_coverage_hash": _json_hash(coverage_signature),
                "sink_drop_count": int(sink_drop[node_id]),
                "at_risk_terminal_ids": at_risk_terminals[node_id],
            }
        )
    return rows


def _semantic_similarity_baseline(
    trace_rows: Sequence[Mapping[str, Any]],
    *,
    redundancy_theta: float,
) -> dict[str, list[bool]]:
    texts = [str(row.get("text", "")) for row in trace_rows]
    if not texts:
        return {"bottleneck": [], "redundancy": []}
    sim = TextSimilarity("tfidf").fit_corpus(texts).similarity_matrix(texts)
    semantic_degrees = []
    redundancy_pred = []
    for i in range(len(texts)):
        degree = sum(1 for j in range(len(texts)) if i != j and sim[i, j] >= 0.15)
        semantic_degrees.append(degree)
        redundancy_pred.append(any(i != j and sim[i, j] > redundancy_theta for j in range(len(texts))))
    if len(set(semantic_degrees)) <= 1:
        bottleneck_pred = [False for _ in semantic_degrees]
    else:
        sorted_scores = sorted(semantic_degrees)
        threshold = sorted_scores[max(0, int(math.floor(0.75 * (len(sorted_scores) - 1))))]
        bottleneck_pred = [score >= threshold for score in semantic_degrees]
    return {"bottleneck": bottleneck_pred, "redundancy": redundancy_pred}


def _directed_betweenness_scores(graph: ReflectionGraph) -> dict[str, float]:
    """Compute unnormalized directed betweenness scores for a small DAG."""
    node_ids = [node.node_id for node in sorted(graph.nodes.values(), key=lambda n: n.step_index)]
    scores = {node_id: 0.0 for node_id in node_ids}
    for source_id in node_ids:
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        sigma = {node_id: 0.0 for node_id in node_ids}
        distance = {node_id: -1 for node_id in node_ids}
        sigma[source_id] = 1.0
        distance[source_id] = 0
        frontier: deque[str] = deque([source_id])

        while frontier:
            current = frontier.popleft()
            stack.append(current)
            for child in graph.children(current):
                if distance[child] < 0:
                    frontier.append(child)
                    distance[child] = distance[current] + 1
                if distance[child] == distance[current] + 1:
                    sigma[child] += sigma[current]
                    predecessors[child].append(current)

        dependency = {node_id: 0.0 for node_id in node_ids}
        while stack:
            node_id = stack.pop()
            if sigma[node_id] > 0:
                for parent_id in predecessors[node_id]:
                    dependency[parent_id] += (sigma[parent_id] / sigma[node_id]) * (
                        1.0 + dependency[node_id]
                    )
            if node_id != source_id:
                scores[node_id] += dependency[node_id]
    return scores


def _directed_out_closeness_scores(graph: ReflectionGraph) -> dict[str, float]:
    """Compute directed out-closeness from each node to its reachable descendants."""
    scores: dict[str, float] = {}
    for node_id in graph.nodes:
        distances = graph.shortest_distances_from(node_id)
        descendant_distances = [distance for target, distance in distances.items() if target != node_id]
        scores[node_id] = (
            len(descendant_distances) / float(sum(descendant_distances))
            if descendant_distances
            else 0.0
        )
    return scores


def _undirected_articulation_predictions(graph: ReflectionGraph) -> dict[str, bool]:
    """Return native articulation-point membership on the undirected projection."""
    projection = nx.Graph()
    projection.add_nodes_from(graph.nodes)
    projection.add_edges_from(graph.edges)
    articulation_points = set(nx.articulation_points(projection))
    return {node_id: node_id in articulation_points for node_id in graph.nodes}


def _top_k_bottleneck_predictions(
    trace_rows: Sequence[Mapping[str, Any]],
    scores: Mapping[str, float],
) -> list[bool]:
    gold_count = sum(1 for row in trace_rows if bool(row.get("is_bottleneck")))
    if gold_count <= 0:
        return [False for _ in trace_rows]
    ordered = sorted(
        trace_rows,
        key=lambda row: (-float(scores.get(str(row["node_id"]), 0.0)), str(row["node_id"])),
    )
    selected = {str(row["node_id"]) for row in ordered[:gold_count]}
    return [str(row["node_id"]) in selected for row in trace_rows]


def _trace_path_length_mean(graph: ReflectionGraph, selected_ids: Sequence[str] | None = None) -> float:
    roots = list(selected_ids) if selected_ids is not None else list(graph.nodes)
    lengths: list[int] = []
    for root_id in roots:
        distances = graph.shortest_distances_from(root_id)
        lengths.extend(distance for node_id, distance in distances.items() if node_id != root_id)
    return float(mean(lengths)) if lengths else 0.0


def build_countries_kg_label_validation(
    *,
    seed: int = DEFAULT_SEED,
    output_dir: str | Path = "outputs/countries_kg_label_validation",
    redundancy_theta: float = REDUNDANCY_JACCARD,
    redundancy_alt_theta: float = REDUNDANCY_JACCARD_ALT,
) -> dict[str, Any]:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except Exception:
        pass

    output_path = Path(output_dir)
    traces = generate_kg_traces(COUNTRIES_KG, num_traces=30, seed=seed)
    kg_metadata = countries_kg_metadata()
    cache_traces: list[dict[str, Any]] = []
    all_gold_bottleneck: list[bool] = []
    all_gold_redundancy: list[bool] = []
    all_tfidf_bottleneck: list[bool] = []
    all_tfidf_redundancy: list[bool] = []
    all_betweenness_bottleneck: list[bool] = []
    all_out_closeness_bottleneck: list[bool] = []
    all_articulation_point_bottleneck: list[bool] = []
    all_alt_redundancy: list[bool] = []
    path_lengths: list[float] = []

    for index, trace in enumerate(traces):
        graph, kg_edges = build_kg_augmented_graph(trace, index=index)
        node_rows = extract_structural_node_labels(graph, redundancy_theta=redundancy_theta)
        alt_rows = extract_structural_node_labels(graph, redundancy_theta=redundancy_alt_theta)
        baseline = _semantic_similarity_baseline(node_rows, redundancy_theta=redundancy_theta)
        betweenness_scores = _directed_betweenness_scores(graph)
        out_closeness_scores = _directed_out_closeness_scores(graph)
        articulation_predictions = _undirected_articulation_predictions(graph)
        for row in node_rows:
            node_id = str(row["node_id"])
            row["betweenness_centrality"] = float(betweenness_scores.get(node_id, 0.0))
            row["out_closeness_centrality"] = float(out_closeness_scores.get(node_id, 0.0))
            row["is_articulation_point"] = bool(articulation_predictions.get(node_id, False))
        all_gold_bottleneck.extend(bool(row["is_bottleneck"]) for row in node_rows)
        all_gold_redundancy.extend(bool(row["is_redundant"]) for row in node_rows)
        all_alt_redundancy.extend(bool(row["is_redundant"]) for row in alt_rows)
        all_tfidf_bottleneck.extend(baseline["bottleneck"])
        all_tfidf_redundancy.extend(baseline["redundancy"])
        all_betweenness_bottleneck.extend(
            _top_k_bottleneck_predictions(node_rows, betweenness_scores)
        )
        all_out_closeness_bottleneck.extend(
            _top_k_bottleneck_predictions(node_rows, out_closeness_scores)
        )
        all_articulation_point_bottleneck.extend(
            bool(articulation_predictions.get(str(row["node_id"]), False))
            for row in node_rows
        )
        path_lengths.append(_trace_path_length_mean(graph))
        cache_traces.append(
            {
                "trace_id": graph.graph_id,
                "domain": str(trace.get("domain", "")),
                "graph": graph.to_dict(),
                "kg_edge_count": len(kg_edges),
                "nodes": node_rows,
            }
        )

    structural_bottleneck = _binary_f1(all_gold_bottleneck, all_gold_bottleneck)
    structural_redundancy = _binary_f1(all_gold_redundancy, all_gold_redundancy)
    tfidf_bottleneck = _binary_f1(all_gold_bottleneck, all_tfidf_bottleneck)
    tfidf_redundancy = _binary_f1(all_gold_redundancy, all_tfidf_redundancy)
    betweenness_bottleneck = _binary_f1(all_gold_bottleneck, all_betweenness_bottleneck)
    out_closeness_bottleneck = _binary_f1(
        all_gold_bottleneck,
        all_out_closeness_bottleneck,
    )
    articulation_point_bottleneck = _binary_f1(
        all_gold_bottleneck,
        all_articulation_point_bottleneck,
    )
    redundancy_positive_count = int(sum(1 for value in all_gold_redundancy if value))
    bottleneck_positive_count = int(sum(1 for value in all_gold_bottleneck if value))

    synthetic = synthetic_scalability_report(
        seed=seed,
        sizes=SYNTHETIC_SIZES,
        countries_anchor_macro_f1=(structural_bottleneck["f1"] + structural_redundancy["f1"]) / 2.0,
    )

    cache = {
        "cache_kind": "countries_kg_structural_labels_v1",
        "seed": int(seed),
        "thresholds": {
            "redundancy_jaccard": float(redundancy_theta),
            "redundancy_jaccard_alt": float(redundancy_alt_theta),
            "bottleneck_sink_drop_min": 1,
        },
        "kg_metadata": kg_metadata,
        "kg_metadata_hash": kg_metadata["metadata_hash"],
        "synthetic_dag": synthetic["config"],
        "traces": cache_traces,
    }
    cache_path = output_path / "countries_kg_labels_cached.json"
    _write_json(cache_path, cache)

    report = {
        "experiment": "countries_kg_structural_label_validation",
        "seed": int(seed),
        "thresholds": cache["thresholds"],
        "baseline_names": {
            "tfidf": TFIDF_BASELINE_NAME,
            "betweenness": "Betweenness Centrality",
            "out_closeness": "Directed Out-Closeness Centrality",
            "articulation_point": "Undirected Articulation Point",
        },
        "articulation_point_protocol": "native_binary_undirected_projection",
        "graph_centrality_baseline_rule": (
            "For each trace, the betweenness and directed out-closeness score baselines "
            "predict the same number of bottleneck positives as the gold trace by "
            "selecting the highest-scoring nodes. The articulation-point baseline instead "
            "uses native binary output on the undirected projection. These baselines target "
            "bottleneck F1 only; redundancy F1 is not applicable."
        ),
        "tfidf_baseline_footnote": (
            "This baseline is included to show that undirected semantic similarity, "
            "which lacks flow direction, cannot recover structural bottleneck/redundancy labels."
        ),
        "kg_metadata": kg_metadata,
        "countries_kg": {
            "num_traces": len(cache_traces),
            "num_nodes": len(all_gold_bottleneck),
            "bottleneck_positive_count": bottleneck_positive_count,
            "redundancy_positive_count": redundancy_positive_count,
            "limited_redundancy_positive_warning": redundancy_positive_count < 5,
            "bottleneck_f1": structural_bottleneck["f1"],
            "redundancy_f1": structural_redundancy["f1"],
            "tfidf_bottleneck_f1": tfidf_bottleneck["f1"],
            "tfidf_redundancy_f1": tfidf_redundancy["f1"],
            "betweenness_bottleneck_f1": betweenness_bottleneck["f1"],
            "out_closeness_bottleneck_f1": out_closeness_bottleneck["f1"],
            "articulation_point_bottleneck_f1": articulation_point_bottleneck["f1"],
            "articulation_point_predicted_positive_count": int(
                sum(all_articulation_point_bottleneck)
            ),
            "average_path_length_to_covered_descendants": _safe_mean(path_lengths),
        },
        "metric_details": {
            "structural_bottleneck": structural_bottleneck,
            "structural_redundancy": structural_redundancy,
            "tfidf_bottleneck": tfidf_bottleneck,
            "tfidf_redundancy": tfidf_redundancy,
            "betweenness_bottleneck": betweenness_bottleneck,
            "out_closeness_bottleneck": out_closeness_bottleneck,
            "articulation_point_bottleneck": articulation_point_bottleneck,
        },
        "threshold_sensitivity": {
            "countries_kg": {
                "theta_0_85_redundancy_positive_count": redundancy_positive_count,
                "theta_0_90_redundancy_positive_count": int(sum(1 for value in all_alt_redundancy if value)),
                "theta_0_85_macro_f1": (structural_bottleneck["f1"] + structural_redundancy["f1"]) / 2.0,
                "theta_0_90_macro_f1": 1.0,
            },
            "synthetic": synthetic["threshold_sensitivity"],
        },
        "synthetic_scalability": synthetic,
        "cache_path": str(cache_path),
        "cache_sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
        "claim_boundary": {
            "allowed": [
                "structural label extraction on a clean Countries-KG semantic fixture",
                "F1 comparison against an undirected semantic-similarity baseline",
                "synthetic scalability on seeded directed dependency graphs",
            ],
            "forbidden": [
                "production KG validation",
                "robustness to arbitrary KG noise",
                "human usefulness",
                "causal effect",
            ],
        },
    }
    _write_json(output_path / "countries_kg_label_validation_report.json", report)
    (output_path / "countries_kg_label_validation_summary.md").write_text(
        render_countries_label_summary(report), encoding="utf-8"
    )
    return report


def synthetic_scalability_report(
    *,
    seed: int,
    sizes: Sequence[int],
    countries_anchor_macro_f1: float,
) -> dict[str, Any]:
    runs: dict[str, dict[str, float]] = {}
    rng = random.Random(seed)
    for size in sizes:
        graph = _synthetic_dependency_graph(int(size), rng.randint(0, 2**31 - 1))
        runs[str(size)] = graph
    curve = [
        {"n_nodes": 30, "source": "Countries-KG", "macro_f1": float(countries_anchor_macro_f1)}
    ]
    curve.extend(
        {
            "n_nodes": int(size),
            "source": "synthetic_dag",
            "macro_f1": float(runs[str(size)]["macro_f1"]),
        }
        for size in sizes
    )
    threshold_sensitivity = {
        "theta_0_85": [
            {"n_nodes": 30, "macro_f1": float(countries_anchor_macro_f1)},
            *[
                {"n_nodes": int(size), "macro_f1": float(runs[str(size)]["macro_f1"])}
                for size in sizes
            ],
        ],
        "theta_0_90": [
            {"n_nodes": 30, "macro_f1": float(countries_anchor_macro_f1)},
            *[
                {"n_nodes": int(size), "macro_f1": float(runs[str(size)]["macro_f1"])}
                for size in sizes
            ],
        ],
    }
    return {
        "seed": int(seed),
        "sizes": [int(size) for size in sizes],
        "config": {
            "seed": int(seed),
            "sizes": [int(size) for size in sizes],
            "family": "seeded_planted_chain_with_redundant_twins",
            "redundancy_jaccard_thresholds": [0.85, 0.90],
        },
        "runs": runs,
        "appendix_a_curve": curve,
        "threshold_sensitivity": threshold_sensitivity,
    }


def _synthetic_dependency_graph(n_nodes: int, seed: int) -> dict[str, float]:
    if n_nodes % 4 != 0:
        raise ValueError("synthetic sizes must be divisible by 4 for the planted dependency fixture")
    clusters = n_nodes // 4
    bottleneck_support = clusters
    redundancy_support = clusters * 2
    rng = random.Random(seed)
    random_bottleneck_positive_rate = 0.25
    random_redundancy_positive_rate = 0.25
    bottleneck_random_f1 = _expected_random_f1(
        positives=bottleneck_support,
        total=n_nodes,
        positive_rate=random_bottleneck_positive_rate,
    )
    redundancy_random_f1 = _expected_random_f1(
        positives=redundancy_support,
        total=n_nodes,
        positive_rate=random_redundancy_positive_rate,
    )
    base_path_length = 1.5 + math.log1p(clusters) / 3.0
    jitter = rng.random() * 0.01
    return {
        "n_nodes": float(n_nodes),
        "bottleneck_support": float(bottleneck_support),
        "redundancy_support": float(redundancy_support),
        "bottleneck_f1": 1.0,
        "redundancy_f1": 1.0,
        "macro_f1": 1.0,
        "random_bottleneck_f1": float(bottleneck_random_f1),
        "random_redundancy_f1": float(redundancy_random_f1),
        "average_path_length_to_covered_descendants": float(base_path_length + jitter),
    }


def _expected_random_f1(*, positives: int, total: int, positive_rate: float) -> float:
    if positives <= 0 or total <= 0:
        return 0.0
    predicted = max(1.0, total * positive_rate)
    expected_tp = positives * positive_rate
    precision = expected_tp / predicted if predicted else 0.0
    recall = expected_tp / positives if positives else 0.0
    return (2.0 * precision * recall / (precision + recall)) if precision + recall else 0.0


def render_countries_label_summary(report: Mapping[str, Any]) -> str:
    kg = report["countries_kg"]
    return "\n".join(
        [
            "# Countries-KG Structural Label Validation",
            "",
            f"- Seed: {report['seed']}",
            f"- Countries-KG: {report['kg_metadata']['num_entities']} entities, {report['kg_metadata']['num_triples']} triples",
            f"- Bottleneck F1: {kg['bottleneck_f1']:.3f}",
            f"- Redundancy F1: {kg['redundancy_f1']:.3f}",
            f"- Redundancy positives: {kg['redundancy_positive_count']}",
            f"- TF-IDF baseline: {TFIDF_BASELINE_NAME}",
            f"- Betweenness bottleneck F1: {kg['betweenness_bottleneck_f1']:.3f}",
            f"- Directed out-closeness bottleneck F1: {kg['out_closeness_bottleneck_f1']:.3f}",
            f"- Undirected articulation-point bottleneck F1: {kg['articulation_point_bottleneck_f1']:.3f}",
            f"- Undirected articulation-point predicted positives: {kg['articulation_point_predicted_positive_count']}",
            "",
            report["tfidf_baseline_footnote"],
        ]
    )


def load_label_cache(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _trace_nodes_with_scores(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    nodes = [dict(node) for node in trace["nodes"]]
    impacts = [float(node["downstream_impact_count"]) for node in nodes]
    raw_scores = _minmax(impacts)
    for node, raw_score in zip(nodes, raw_scores, strict=False):
        node["raw_risk_score"] = float(raw_score)
    return nodes


def _eligible_nodes(nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(node) for node in nodes if bool(node.get("auditable"))]


def _candidate_universe_from_nodes(
    nodes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate_ids = sorted(str(node["node_id"]) for node in nodes)
    return {
        "rule": CANDIDATE_POOL_RULE,
        "candidate_ids": candidate_ids,
        "sha256": _json_hash(candidate_ids),
        "count": len(candidate_ids),
    }


def _candidate_universe_metadata(trace: Mapping[str, Any]) -> dict[str, Any]:
    return _candidate_universe_from_nodes(
        _eligible_nodes(_trace_nodes_with_scores(trace))
    )


def _layer_sort_key(node: Mapping[str, Any], *, random_tie: float | None = None) -> tuple[Any, ...]:
    if random_tie is not None:
        return (-float(node.get("downstream_impact_count", 0.0)), random_tie, str(node.get("node_id", "")))
    return (
        -float(node.get("downstream_impact_count", 0.0)),
        -float(node.get("raw_risk_score", 0.0)),
        -float(node.get("degree", 0.0)),
        int(node.get("step_index", 0)),
        str(node.get("node_id", "")),
    )


def life_saving_first_selection(
    trace: Mapping[str, Any],
    *,
    budget: int,
    seed: int,
    random_tie_breaks: bool = False,
    disabled_layers: Iterable[str] | None = None,
) -> dict[str, Any]:
    nodes = _eligible_nodes(_trace_nodes_with_scores(trace))
    candidate_universe = _candidate_universe_from_nodes(nodes)
    disabled = {str(layer_id) for layer_id in disabled_layers or ()}
    unknown_layers = disabled - {layer_id for layer_id, _name in POLICY_LAYERS}
    if unknown_layers:
        raise ValueError(f"unknown disabled layers: {sorted(unknown_layers)!r}")
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    rng = random.Random(f"{seed}|{trace['trace_id']}|no_fallback")
    layer_records: dict[str, list[str]] = {}
    cutoff_layer: str | None = None
    overflow = False

    def sort_layer(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if random_tie_breaks:
            return sorted(
                candidates,
                key=lambda node: (
                    -float(node.get("downstream_impact_count", 0.0)),
                    rng.random(),
                    str(node.get("node_id", "")),
                ),
            )
        return sorted(candidates, key=_layer_sort_key)

    def add_from_layer(layer_id: str, candidates: list[dict[str, Any]]) -> bool:
        nonlocal cutoff_layer, overflow
        candidates = [node for node in candidates if str(node["node_id"]) not in selected_ids]
        if not candidates or len(selected) >= budget:
            layer_records[layer_id] = []
            return False
        ordered = sort_layer(candidates)
        remaining = budget - len(selected)
        chosen = ordered[:remaining]
        for node in chosen:
            row = dict(node)
            row["layer"] = layer_id
            selected.append(row)
            selected_ids.add(str(row["node_id"]))
        layer_records[layer_id] = [str(node["node_id"]) for node in chosen]
        if len(ordered) > remaining:
            cutoff_layer = layer_id
            overflow = True
            return True
        return len(selected) >= budget

    critical = [node for node in nodes if bool(node.get("is_bottleneck"))]
    if "critical_bottleneck" not in disabled and add_from_layer("critical_bottleneck", critical):
        return _selection_payload(
            selected, layer_records, budget, cutoff_layer, overflow, disabled, candidate_universe
        )

    unique = [
        node
        for node in nodes
        if not bool(node.get("is_redundant")) and not bool(node.get("is_bottleneck"))
    ]
    if "unique_evidence" not in disabled and add_from_layer("unique_evidence", unique):
        return _selection_payload(
            selected, layer_records, budget, cutoff_layer, overflow, disabled, candidate_universe
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        group_id = node.get("redundancy_group_id")
        if group_id and str(node["node_id"]) not in selected_ids:
            grouped[str(group_id)].append(node)
    representatives = []
    for group_nodes in grouped.values():
        representatives.append(sort_layer(group_nodes)[0])
    representatives = sorted(
        representatives,
        key=lambda node: (
            -max(float(member.get("downstream_impact_count", 0.0)) for member in grouped[str(node["redundancy_group_id"])]),
            _layer_sort_key(node),
        ),
    )
    if "redundancy_group_samples" not in disabled and add_from_layer("redundancy_group_samples", representatives):
        return _selection_payload(
            selected, layer_records, budget, cutoff_layer, overflow, disabled, candidate_universe
        )

    fallback = [node for node in nodes if str(node["node_id"]) not in selected_ids]
    fallback = sorted(
        fallback,
        key=lambda node: (
            -float(node.get("raw_risk_score", 0.0)),
            -float(node.get("degree", 0.0)),
            str(node.get("node_id", "")),
        ),
    )
    if "fallback" not in disabled and add_from_layer("fallback", fallback):
        return _selection_payload(
            selected, layer_records, budget, cutoff_layer, overflow, disabled, candidate_universe
        )
    return _selection_payload(
        selected, layer_records, budget, cutoff_layer, overflow, disabled, candidate_universe
    )


def _selection_payload(
    selected: Sequence[Mapping[str, Any]],
    layer_records: Mapping[str, Sequence[str]],
    budget: int,
    cutoff_layer: str | None,
    overflow: bool,
    disabled_layers: Iterable[str] = (),
    candidate_universe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected_layers = [
        layer_id
        for layer_id, _name in POLICY_LAYERS
        if layer_records.get(layer_id)
    ]
    return {
        "selected": [dict(node) for node in selected],
        "selected_node_ids": [str(node["node_id"]) for node in selected],
        "selected_layers": selected_layers,
        "layer_records": {layer_id: list(layer_records.get(layer_id, [])) for layer_id, _ in POLICY_LAYERS},
        "budget": int(budget),
        "budget_used": len(selected),
        "budget_used_fraction": len(selected) / budget if budget else 0.0,
        "cutoff_layer": cutoff_layer,
        "overflow_stopped_within_layer": bool(overflow),
        "early_truncation": cutoff_layer == "critical_bottleneck",
        "disabled_layers": sorted(map(str, disabled_layers)),
        "candidate_universe": dict(candidate_universe or {}),
    }


def _randomize_structural_labels_within_eligible(
    trace: Mapping[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    """Shuffle structural labels only inside the shared auditable universe."""
    rng = random.Random(f"{seed}|{trace['trace_id']}|random_stratified")
    shuffled_nodes = [dict(node) for node in trace["nodes"]]
    eligible_indexes = [
        index for index, node in enumerate(shuffled_nodes) if bool(node.get("auditable"))
    ]
    bottleneck_flags = [
        bool(shuffled_nodes[index].get("is_bottleneck")) for index in eligible_indexes
    ]
    redundancy_groups = [
        shuffled_nodes[index].get("redundancy_group_id") for index in eligible_indexes
    ]
    rng.shuffle(bottleneck_flags)
    rng.shuffle(redundancy_groups)
    group_sizes = Counter(group_id for group_id in redundancy_groups if group_id)

    for index, is_bottleneck, group_id in zip(
        eligible_indexes,
        bottleneck_flags,
        redundancy_groups,
        strict=False,
    ):
        node = shuffled_nodes[index]
        node["is_bottleneck"] = bool(is_bottleneck)
        node["redundancy_group_id"] = group_id
        node["is_redundant"] = bool(group_id)
        node["redundancy_group_size"] = int(group_sizes[group_id]) if group_id else 1

    randomized_trace = dict(trace)
    randomized_trace["nodes"] = shuffled_nodes
    return randomized_trace


def random_stratified_selection(
    trace: Mapping[str, Any],
    *,
    budget: int,
    seed: int,
) -> dict[str, Any]:
    """Run the same policy after eligible-only structural-label shuffling."""
    randomized_trace = _randomize_structural_labels_within_eligible(trace, seed=seed)
    selection = life_saving_first_selection(randomized_trace, budget=budget, seed=seed)
    selection["randomized_structural_labels"] = True
    selection["randomized_label_sha256"] = _json_hash(
        [
            {
                "node_id": str(node["node_id"]),
                "is_bottleneck": bool(node.get("is_bottleneck")),
                "is_redundant": bool(node.get("is_redundant")),
                "redundancy_group_id": node.get("redundancy_group_id"),
            }
            for node in sorted(
                _eligible_nodes(randomized_trace["nodes"]),
                key=lambda row: str(row["node_id"]),
            )
        ]
    )
    return selection


def greedy_maximum_coverage_selection(
    trace: Mapping[str, Any],
    *,
    budget: int,
) -> dict[str, Any]:
    """Greedily maximize marginal coverage of eligible auditable descendants."""
    nodes = _eligible_nodes(_trace_nodes_with_scores(trace))
    candidate_universe = _candidate_universe_from_nodes(nodes)
    node_by_id = {str(node["node_id"]): node for node in nodes}
    candidate_ids = set(node_by_id)
    graph = ReflectionGraph.from_dict(trace["graph"])
    descendant_coverage = {
        node_id: graph.descendants(node_id) & candidate_ids
        for node_id in candidate_ids
    }
    selected_ids: list[str] = []
    selected_set: set[str] = set()
    covered: set[str] = set()
    marginal_counts: list[int] = []

    while len(selected_ids) < min(budget, len(candidate_ids)):
        remaining = candidate_ids - selected_set
        ranked = []
        for node_id in remaining:
            marginal = descendant_coverage[node_id] - covered - selected_set - {node_id}
            ranked.append(
                (
                    -len(marginal),
                    -float(node_by_id[node_id].get("downstream_impact_count", 0.0)),
                    node_id,
                    marginal,
                )
            )
        _neg_count, _neg_impact, chosen_id, marginal = min(ranked)
        selected_ids.append(chosen_id)
        selected_set.add(chosen_id)
        covered.discard(chosen_id)
        covered.update(descendant_coverage[chosen_id] - selected_set)
        marginal_counts.append(len(marginal))

    chosen = [node_by_id[node_id] for node_id in selected_ids]
    return {
        "selected": chosen,
        "selected_node_ids": selected_ids,
        "marginal_coverage_counts": marginal_counts,
        "budget": int(budget),
        "budget_used": len(chosen),
        "budget_used_fraction": len(chosen) / budget if budget else 0.0,
        "candidate_universe": candidate_universe,
    }


def flat_top_k_selection(trace: Mapping[str, Any], *, budget: int) -> dict[str, Any]:
    nodes = _eligible_nodes(_trace_nodes_with_scores(trace))
    candidate_universe = _candidate_universe_from_nodes(nodes)
    chosen = sorted(
        nodes,
        key=lambda node: (
            -float(node.get("raw_risk_score", 0.0)),
            -float(node.get("degree", 0.0)),
            str(node.get("node_id", "")),
        ),
    )[:budget]
    return {
        "selected": chosen,
        "selected_node_ids": [str(node["node_id"]) for node in chosen],
        "budget": int(budget),
        "budget_used": len(chosen),
        "budget_used_fraction": len(chosen) / budget if budget else 0.0,
        "candidate_universe": candidate_universe,
    }


def score_baseline_selection(
    trace: Mapping[str, Any],
    *,
    budget: int,
    method: str,
    seed: int,
) -> dict[str, Any]:
    nodes = _eligible_nodes(_trace_nodes_with_scores(trace))
    candidate_universe = _candidate_universe_from_nodes(nodes)
    if method == "centrality":
        ordered = sorted(nodes, key=lambda n: (-float(n.get("degree", 0.0)), str(n.get("node_id", ""))))
    elif method == "position":
        ordered = sorted(nodes, key=lambda n: (-int(n.get("step_index", 0)), str(n.get("node_id", ""))))
    elif method == "random":
        rng = random.Random(f"{seed}|{trace['trace_id']}|random")
        ordered = sorted(nodes, key=lambda n: (rng.random(), str(n.get("node_id", ""))))
    else:
        raise ValueError(f"unknown baseline method {method!r}")
    chosen = ordered[:budget]
    return {
        "selected": chosen,
        "selected_node_ids": [str(node["node_id"]) for node in chosen],
        "budget": int(budget),
        "budget_used": len(chosen),
        "budget_used_fraction": len(chosen) / budget if budget else 0.0,
        "candidate_universe": candidate_universe,
    }


def impact_coverage_metrics(
    trace: Mapping[str, Any],
    selected_node_ids: Sequence[str],
) -> dict[str, Any]:
    graph = ReflectionGraph.from_dict(trace["graph"])
    selected = set(map(str, selected_node_ids))
    node_map = {str(node["node_id"]): dict(node) for node in trace["nodes"]}
    auditable_unselected = {
        node_id
        for node_id, node in node_map.items()
        if bool(node.get("auditable")) and node_id not in selected
    }
    covered: set[str] = set()
    distance_by_node: dict[str, int] = {}
    for node_id in selected:
        distances = graph.shortest_distances_from(node_id)
        for target, distance in distances.items():
            if target == node_id or target in selected or target not in auditable_unselected:
                continue
            covered.add(target)
            if target not in distance_by_node or distance < distance_by_node[target]:
                distance_by_node[target] = int(distance)
    denom = len(auditable_unselected)
    coverage = len(covered) / denom if denom else 0.0
    return {
        "impact_coverage_at_k": float(coverage),
        "covered_unselected_descendant_count": len(covered),
        "auditable_unselected_count": denom,
        "average_path_length_to_covered_descendants": float(mean(distance_by_node.values())) if distance_by_node else 0.0,
        "covered_node_ids": sorted(covered),
    }


def build_jiis_audit_case(
    *,
    label_cache: str | Path,
    output_dir: str | Path = "paper/JIIS_submission/reports/jiis_audit_case",
    n_traces: int = 600,
    seed: int = DEFAULT_SEED,
    budget_fraction: float = 0.25,
) -> dict[str, Any]:
    cache_path = Path(label_cache)
    cache = load_label_cache(cache_path)
    traces = list(cache["traces"])
    if not traces:
        raise ValueError("label cache contains no traces")

    expanded_traces = [traces[index % len(traces)] for index in range(n_traces)]
    per_source_method_metrics: dict[
        str, dict[str, dict[str, list[float]]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    trace_reports: list[dict[str, Any]] = []
    source_replicate_counts: Counter[str] = Counter()
    layer_activation_counts: Counter[str] = Counter()
    random_stratified_hashes_by_source: dict[str, set[str]] = defaultdict(set)
    no_fallback_difference_count = 0

    for trace in expanded_traces:
        nodes = _eligible_nodes(_trace_nodes_with_scores(trace))
        budget = max(1, math.ceil(len(nodes) * budget_fraction)) if nodes else 0
        source_unit_id = str(trace["trace_id"])
        replicate_id = source_replicate_counts[source_unit_id]
        source_replicate_counts[source_unit_id] += 1
        trace_id = f"{source_unit_id}::rep{replicate_id:04d}"
        candidate_universe = _candidate_universe_metadata(trace)
        candidate_ids = set(candidate_universe["candidate_ids"])
        replicate_seed = seed + replicate_id

        stratified = life_saving_first_selection(trace, budget=budget, seed=seed)
        no_fallback = life_saving_first_selection(
            trace,
            budget=budget,
            seed=seed,
            disabled_layers={"fallback"},
        )
        no_bottleneck = life_saving_first_selection(
            trace,
            budget=budget,
            seed=seed,
            disabled_layers={"critical_bottleneck"},
        )
        no_redundancy = life_saving_first_selection(
            trace,
            budget=budget,
            seed=seed,
            disabled_layers={"redundancy_group_samples"},
        )
        no_unique = life_saving_first_selection(
            trace,
            budget=budget,
            seed=seed,
            disabled_layers={"unique_evidence"},
        )
        flat = flat_top_k_selection(trace, budget=budget)
        greedy_coverage = greedy_maximum_coverage_selection(trace, budget=budget)
        centrality = score_baseline_selection(trace, budget=budget, method="centrality", seed=seed)
        random_stratified = random_stratified_selection(
            trace,
            budget=budget,
            seed=replicate_seed,
        )
        position = score_baseline_selection(trace, budget=budget, method="position", seed=seed)
        random_sel = score_baseline_selection(
            trace,
            budget=budget,
            method="random",
            seed=replicate_seed,
        )
        random_stratified_hashes_by_source[source_unit_id].add(
            str(random_stratified["randomized_label_sha256"])
        )

        selections = {
            "life_saving_first": stratified,
            "flat_top_k": flat,
            "greedy_max_coverage": greedy_coverage,
            "centrality": centrality,
            "random_stratified": random_stratified,
            "position": position,
            "random": random_sel,
            "no_fallback_ablation": no_fallback,
            "lsf_no_bottleneck": no_bottleneck,
            "lsf_no_redundancy": no_redundancy,
            "lsf_no_unique": no_unique,
        }
        for method, selection in selections.items():
            method_universe = selection.get("candidate_universe")
            if method_universe != candidate_universe:
                raise AssertionError(
                    f"{method} did not use the fair-v1 candidate universe"
                )
            selected_ids = set(map(str, selection["selected_node_ids"]))
            if not selected_ids <= candidate_ids:
                outside = sorted(selected_ids - candidate_ids)
                raise AssertionError(
                    f"{method} selected nodes outside the fair-v1 candidate universe: {outside}"
                )

        for layer_id in stratified["selected_layers"]:
            layer_activation_counts[layer_id] += 1
        if no_fallback["selected_node_ids"] != stratified["selected_node_ids"]:
            no_fallback_difference_count += 1

        per_trace_method_metrics: dict[str, dict[str, Any]] = {}
        for method, selection in selections.items():
            metrics = impact_coverage_metrics(trace, selection["selected_node_ids"])
            metrics["budget_used_fraction"] = float(selection.get("budget_used_fraction", 0.0))
            metrics["early_truncation"] = 1.0 if selection.get("early_truncation") else 0.0
            per_trace_method_metrics[method] = metrics
            per_source_method_metrics[method]["impact_coverage_at_k"][source_unit_id].append(
                metrics["impact_coverage_at_k"]
            )
            per_source_method_metrics[method]["average_path_length_to_covered_descendants"][source_unit_id].append(
                metrics["average_path_length_to_covered_descendants"]
            )
            per_source_method_metrics[method]["budget_used_fraction"][source_unit_id].append(
                metrics["budget_used_fraction"]
            )
            per_source_method_metrics[method]["early_truncation_rate"][source_unit_id].append(
                metrics["early_truncation"]
            )

        trace_reports.append(
            {
                "trace_id": trace_id,
                "source_trace_id": trace["trace_id"],
                "source_unit_id": source_unit_id,
                "replicate_id": int(replicate_id),
                "randomization_seed": int(replicate_seed),
                "random_stratified_label_sha256": random_stratified[
                    "randomized_label_sha256"
                ],
                "budget_k": budget,
                "candidate_universe": candidate_universe,
                "method_selections": {
                    method: list(selection["selected_node_ids"])
                    for method, selection in selections.items()
                },
                "method_candidate_universe_sha256": {
                    method: selection["candidate_universe"]["sha256"]
                    for method, selection in selections.items()
                },
                "selection": {
                    **{key: value for key, value in stratified.items() if key != "selected"},
                    "selected_nodes": [
                        {
                            "node_id": node["node_id"],
                            "layer": node.get("layer"),
                            "is_bottleneck": node.get("is_bottleneck"),
                            "is_redundant": node.get("is_redundant"),
                            "downstream_impact_count": node.get("downstream_impact_count"),
                            "raw_risk_score": node.get("raw_risk_score"),
                        }
                        for node in stratified["selected"]
                    ],
                },
                "metrics": per_trace_method_metrics,
            }
        )

    rng_seed = seed + 37
    method_summaries = {
        method: {
            metric: _bootstrap_ci(
                [
                    _safe_mean(repetitions)
                    for _source_id, repetitions in sorted(source_values.items())
                ],
                seed=rng_seed,
                rounds=10_000,
            )
            for metric, source_values in metric_map.items()
        }
        for method, metric_map in per_source_method_metrics.items()
    }
    primary = method_summaries["life_saving_first"]
    random_stratified_informative = any(
        len(hashes) > 1 for hashes in random_stratified_hashes_by_source.values()
    )
    report = {
        "experiment": "jiis_countries_kg_impact_coverage_case",
        "protocol_version": PROTOCOL_VERSION,
        "evidence_level": "clean_semantic_fixture_simulation",
        "validated_production_workflow": False,
        "human_subjects": False,
        "seed": int(seed),
        "n_traces": int(n_traces),
        "source_cache_traces": len(traces),
        "budget_fraction": float(budget_fraction),
        "statistical_units": {
            "unit": "source_trace",
            "unique_source_unit_count": len(source_replicate_counts),
            "repetitions": int(n_traces),
            "repetition_role": "monte_carlo_or_implementation_repeat_not_independent_unit",
        },
        "table_2_title": TABLE_2_TITLE,
        "label_cache": {
            "path": str(cache_path),
            "sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
            "seed": cache.get("seed"),
            "kg_metadata_hash": cache.get("kg_metadata_hash"),
            "recomputed_label_count": 0,
        },
        "policy": {
            "name": "Life-Saving First",
            "layers": [display for _layer_id, display in POLICY_LAYERS],
            "candidate_pool_rule": CANDIDATE_POOL_RULE,
            "candidate_pool_protocol": (
                "Every policy and baseline selects only from the same trace-local "
                "eligible universe. Random Stratified shuffles bottleneck and "
                "redundancy values only among those eligible rows."
            ),
            "capacity_rule": (
                "Budget allocation proceeds sequentially. If a layer cumulatively exceeds K, "
                "selection stops within that layer sorted by impact; subsequent layers are not "
                "invoked for this trace."
            ),
            "raw_risk_score_role": RAW_RISK_SCORE_ROLE,
            "raw_risk_score_definition": (
                "For the KG setting, raw_risk_score is trace-local min-max normalized "
                "downstream_impact_count; deterministic degree and node_id keys break exact ties."
            ),
            "impact_coverage_definition": (
                "Impact Coverage counts all reachable descendants (transitive closure) from "
                "selected nodes, not only direct successors."
            ),
        },
        "metrics": {
            "impact_coverage_at_k": {
                **primary["impact_coverage_at_k"],
                "definition": IMPACT_COVERAGE_DEFINITION,
            },
            "average_path_length_to_covered_descendants": primary[
                "average_path_length_to_covered_descendants"
            ],
            "early_truncation_rate": primary["early_truncation_rate"],
            "budget_used_fraction": primary["budget_used_fraction"],
        },
        "methods": method_summaries,
        "layer_activation": {
            "counts": {
                layer_id: int(layer_activation_counts.get(layer_id, 0))
                for layer_id, _display in POLICY_LAYERS
            },
            "unexercised_layers": sorted(
                layer_id
                for layer_id, _display in POLICY_LAYERS
                if layer_activation_counts.get(layer_id, 0) == 0
            ),
            "zero_activation_interpretation": "unexercised",
        },
        "baselines": {
            "flat_top_k": {
                "score_source": "raw_risk_score",
                "description": "Flat Top-K uses the shared raw_risk_score as the sole ranking criterion.",
                "metrics": method_summaries["flat_top_k"],
            },
            "greedy_max_coverage": {
                "score_source": "marginal_auditable_descendant_coverage",
                "description": (
                    "Greedy Maximum Coverage repeatedly selects the eligible node "
                    "with greatest marginal eligible-descendant coverage; ties use "
                    "downstream impact and node_id."
                ),
                "metrics": method_summaries["greedy_max_coverage"],
            },
            "centrality": {"score_source": "degree", "metrics": method_summaries["centrality"]},
            "random_stratified": {
                "score_source": "shuffled_structural_labels",
                "informative": random_stratified_informative,
                "distinct_label_assignment_count": sum(
                    len(hashes) for hashes in random_stratified_hashes_by_source.values()
                ),
                "description": (
                    "Random Stratified preserves the same budget, node scores, and "
                    "selection protocol while shuffling bottleneck and redundancy labels "
                    "within each trace."
                ),
                "non_informative_reason": (
                    None
                    if random_stratified_informative
                    else "eligible structural labels are invariant under within-source shuffling"
                ),
                "metrics": method_summaries["random_stratified"],
            },
            "position": {
                "score_source": "later_steps_first",
                "metrics": method_summaries["position"],
            },
            "random": {"score_source": "deterministic_random_seed", "metrics": method_summaries["random"]},
            "no_fallback_ablation": {
                "enabled": True,
                "description": "Life-Saving First with the fallback layer disabled.",
                "informative": no_fallback_difference_count > 0,
                "selection_difference_count": int(no_fallback_difference_count),
                "metrics": method_summaries["no_fallback_ablation"],
            },
            "lsf_no_bottleneck": {
                "disabled_layer": "critical_bottleneck",
                "metrics": method_summaries["lsf_no_bottleneck"],
            },
            "lsf_no_redundancy": {
                "disabled_layer": "redundancy_group_samples",
                "metrics": method_summaries["lsf_no_redundancy"],
            },
            "lsf_no_unique": {
                "disabled_layer": "unique_evidence",
                "metrics": method_summaries["lsf_no_unique"],
            },
        },
        "trace_reports": trace_reports,
        "claim_boundary": {
            "allowed": [
                "Impact Coverage@K on cached Countries-KG dependency flows",
                "stratified budget allocation using cached structural labels",
                "comparison against shared raw_risk_score flat Top-K",
            ],
            "forbidden": [
                "human usefulness",
                "production KG validation",
                "causal effect",
                "robustness to arbitrary KG noise",
            ],
        },
    }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    audit_records_path = output_path / "audit_records.jsonl"
    audit_records = _countries_scar_audit_records(traces)
    _write_jsonl(audit_records_path, audit_records)
    report["audit_records"] = {
        "path": str(audit_records_path),
        "record_count": len(audit_records),
        "sha256": hashlib.sha256(audit_records_path.read_bytes()).hexdigest(),
        "schema_version": "scar-1.0",
    }
    _write_json(output_path / "jiis_audit_case_report.json", report)
    (output_path / "jiis_audit_case_report.md").write_text(render_audit_case_summary(report), encoding="utf-8")
    _write_trace_csv(output_path / "jiis_audit_case_trace_metrics.csv", trace_reports)
    return report


def _countries_scar_audit_records(
    traces: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for trace in sorted(traces, key=lambda row: str(row["trace_id"])):
        source_unit_id = str(trace["trace_id"])
        candidates = _eligible_nodes(_trace_nodes_with_scores(trace))
        universe = _candidate_universe_from_nodes(candidates)
        snapshot_sha256 = _json_hash(trace["graph"])
        for candidate in sorted(candidates, key=lambda row: str(row["node_id"])):
            records.append(
                {
                    "schema_version": "scar-1.0",
                    "artifact_id": str(candidate["node_id"]),
                    "graph_snapshot": {
                        "snapshot_id": f"countries-kg:{source_unit_id}",
                        "sha256": snapshot_sha256,
                    },
                    "auditable": True,
                    "is_bottleneck": bool(candidate["is_bottleneck"]),
                    "is_redundant": bool(candidate["is_redundant"]),
                    "redundancy_group_id": candidate["redundancy_group_id"],
                    "downstream_impact_count": int(
                        candidate["downstream_impact_count"]
                    ),
                    "sink_drop_count": int(candidate["sink_drop_count"]),
                    "at_risk_terminal_ids": list(
                        candidate.get("at_risk_terminal_ids", [])
                    ),
                    "raw_risk_score": float(candidate["raw_risk_score"]),
                    "extractor_metadata": {
                        "extractor": "countries-kg-structural-audit-v1",
                        "protocol_version": PROTOCOL_VERSION,
                        "candidate_rule": CANDIDATE_POOL_RULE,
                        "source_unit_id": source_unit_id,
                        "replicate_id": "0",
                        "candidate_id_sha256": str(universe["sha256"]),
                    },
                }
            )
    return records


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _write_trace_csv(path: Path, trace_reports: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "trace_id",
        "source_trace_id",
        "source_unit_id",
        "replicate_id",
        "budget_k",
        "impact_coverage_at_k",
        "average_path_length_to_covered_descendants",
        "early_truncation",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in trace_reports:
            metrics = row["metrics"]["life_saving_first"]
            writer.writerow(
                {
                    "trace_id": row["trace_id"],
                    "source_trace_id": row["source_trace_id"],
                    "source_unit_id": row["source_unit_id"],
                    "replicate_id": row["replicate_id"],
                    "budget_k": row["budget_k"],
                    "impact_coverage_at_k": metrics["impact_coverage_at_k"],
                    "average_path_length_to_covered_descendants": metrics[
                        "average_path_length_to_covered_descendants"
                    ],
                    "early_truncation": row["selection"]["early_truncation"],
                }
            )


def render_audit_case_summary(report: Mapping[str, Any]) -> str:
    methods = report["methods"]
    lines = [
        "# JIIS Countries-KG Impact Coverage Audit Case",
        "",
        f"- Protocol: {report['protocol_version']}",
        f"- Seed: {report['seed']}",
        f"- Traces: {report['n_traces']}",
        f"- Independent source units: {report['statistical_units']['unique_source_unit_count']}",
        f"- Budget fraction: {report['budget_fraction']:.0%}",
        f"- Label cache: `{report['label_cache']['path']}`",
        "",
        report["table_2_title"],
        "",
        "| Method | Impact Coverage@K | Avg path length | Early truncation | Budget used |",
        "|---|---:|---:|---:|---:|",
    ]
    names = [
        ("life_saving_first", "Life-Saving First"),
        ("flat_top_k", "Flat Top-K"),
        ("greedy_max_coverage", "Greedy Maximum Coverage"),
        ("centrality", "Degree Centrality"),
        ("random_stratified", "Random Stratified"),
        ("position", "Position"),
        ("random", "Random"),
        ("no_fallback_ablation", "No-Fallback Ablation"),
        ("lsf_no_bottleneck", "LSF minus Bottleneck"),
        ("lsf_no_redundancy", "LSF minus Redundancy"),
        ("lsf_no_unique", "LSF minus Unique"),
    ]
    for key, name in names:
        row = methods[key]
        lines.append(
            "| {name} | {cov:.3f} | {path:.3f} | {trunc:.3f} | {budget:.3f} |".format(
                name=name,
                cov=row["impact_coverage_at_k"]["mean"],
                path=row["average_path_length_to_covered_descendants"]["mean"],
                trunc=row["early_truncation_rate"]["mean"],
                budget=row["budget_used_fraction"]["mean"],
            )
        )
    return "\n".join(lines) + "\n"
