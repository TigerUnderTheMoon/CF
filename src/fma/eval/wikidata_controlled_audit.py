"""Controlled knowledge-maintenance evaluation on Wikidata-backed audit DAGs."""

from __future__ import annotations

import math
import hashlib
import platform
import random
import sys
import time
import tracemalloc
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from statistics import mean, stdev
from typing import Any, Mapping, Sequence

import networkx as nx
from scipy.stats import rankdata, wilcoxon

from fma.graph.similarity import TextSimilarity
from fma.graph.wikidata_scientist_kg import DagOverlay, Triple, build_dag_overlay


@dataclass(frozen=True)
class MotifManifest:
    bottleneck_nodes: frozenset[str]
    redundant_nodes: frozenset[str]
    control_nodes: frozenset[str]
    redundancy_groups: dict[str, tuple[str, str]]
    terminal_nodes: frozenset[str]
    anchor_by_candidate: dict[str, str]

    @property
    def candidate_nodes(self) -> frozenset[str]:
        return self.bottleneck_nodes | self.redundant_nodes | self.control_nodes


@dataclass(frozen=True)
class MotifBundle:
    graph: nx.DiGraph
    layers: dict[int, set[str]]
    manifest: MotifManifest


def add_controlled_audit_motifs(
    overlay: DagOverlay,
    seed: int,
    *,
    motif_count: int | None = None,
) -> MotifBundle:
    """Attach deterministic maintenance motifs while preserving the four-layer DAG."""
    graph = overlay.graph.copy()
    layers = {layer: set(nodes) for layer, nodes in overlay.layers.items()}
    anchors = sorted(layers.get(1, set()))
    if not anchors:
        raise ValueError("controlled audit motifs require at least one Layer 1 anchor")
    count = motif_count if motif_count is not None else max(10, min(20, round(0.01 * len(graph))))
    if count <= 0:
        raise ValueError("motif_count must be positive")
    rng = random.Random(seed)
    rng.shuffle(anchors)

    bottlenecks: set[str] = set()
    redundant: set[str] = set()
    controls: set[str] = set()
    terminals: set[str] = set()
    groups: dict[str, tuple[str, str]] = {}
    anchors_by_candidate: dict[str, str] = {}

    def add_record(node: str, label: str) -> None:
        graph.add_node(node, layer=2, label=label, controlled_motif=True)
        layers[2].add(node)

    def add_terminal(node: str, label: str) -> None:
        graph.add_node(node, layer=3, label=label, controlled_motif=True)
        layers[3].add(node)
        terminals.add(node)

    for index in range(count):
        anchor = anchors[index % len(anchors)]
        prefix = f"cm:{seed}:{index:03d}"

        bottleneck = f"{prefix}:b"
        add_record(bottleneck, f"maintenance bridge {index}")
        graph.add_edge(anchor, bottleneck, predicates=("AUDIT_DEPENDS_ON",), controlled_motif=True)
        bottlenecks.add(bottleneck)
        anchors_by_candidate[bottleneck] = anchor
        for terminal_index in range(3):
            terminal = f"{prefix}:bt:{terminal_index}"
            add_terminal(terminal, f"maintenance terminal {index} {terminal_index}")
            graph.add_edge(
                bottleneck,
                terminal,
                predicates=("AUDIT_IMPACTS",),
                controlled_motif=True,
            )

        left, right = f"{prefix}:r:a", f"{prefix}:r:b"
        add_record(left, f"parallel evidence {index}")
        add_record(right, f"parallel evidence {index}")
        graph.add_edge(anchor, left, predicates=("AUDIT_DEPENDS_ON",), controlled_motif=True)
        graph.add_edge(anchor, right, predicates=("AUDIT_DEPENDS_ON",), controlled_motif=True)
        shared_terminals = []
        for terminal_index in range(3):
            terminal = f"{prefix}:rt:{terminal_index}"
            add_terminal(terminal, f"shared maintenance terminal {index} {terminal_index}")
            shared_terminals.append(terminal)
            graph.add_edge(left, terminal, predicates=("AUDIT_SUPPORTS",), controlled_motif=True)
            graph.add_edge(right, terminal, predicates=("AUDIT_SUPPORTS",), controlled_motif=True)
        group_id = f"controlled_rg_{index:03d}"
        groups[group_id] = (left, right)
        redundant.update((left, right))
        anchors_by_candidate[left] = anchor
        anchors_by_candidate[right] = anchor

        control = f"{prefix}:c"
        add_record(control, f"independent evidence {index}")
        graph.add_edge(anchor, control, predicates=("AUDIT_DEPENDS_ON",), controlled_motif=True)
        controls.add(control)
        anchors_by_candidate[control] = anchor
        for terminal_index in range(3):
            terminal = f"{prefix}:ct:{terminal_index}"
            add_terminal(terminal, f"independent terminal {index} {terminal_index}")
            graph.add_edge(control, terminal, predicates=("AUDIT_SUPPORTS",), controlled_motif=True)
            bypass = f"{prefix}:cb:{terminal_index}"
            add_record(bypass, f"independent bypass {index} {terminal_index}")
            graph.add_edge(anchor, bypass, predicates=("AUDIT_DEPENDS_ON",), controlled_motif=True)
            graph.add_edge(bypass, terminal, predicates=("AUDIT_SUPPORTS",), controlled_motif=True)

    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("controlled audit motifs introduced a cycle")
    if any(graph.out_degree(node) for node in layers[3]):
        raise ValueError("controlled audit motifs must preserve Layer 3 terminal semantics")
    return MotifBundle(
        graph=graph,
        layers=layers,
        manifest=MotifManifest(
            bottleneck_nodes=frozenset(bottlenecks),
            redundant_nodes=frozenset(redundant),
            control_nodes=frozenset(controls),
            redundancy_groups=groups,
            terminal_nodes=frozenset(terminals),
            anchor_by_candidate=anchors_by_candidate,
        ),
    )


def extract_audit_roles(
    graph: nx.DiGraph,
    *,
    redundancy_threshold: float = 0.85,
) -> dict[str, dict[str, Any]]:
    """Extract bottleneck and redundancy roles using topology only."""
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("audit role extraction requires a DAG")
    nodes = sorted(map(str, graph.nodes))
    sources = {node for node in nodes if graph.in_degree(node) == 0}
    terminals = {node for node in nodes if graph.out_degree(node) == 0}
    topological = list(map(str, nx.topological_sort(graph)))
    node_index = {node: index for index, node in enumerate(nodes)}
    terminal_index = {node: index for index, node in enumerate(sorted(terminals))}
    descendant_bits: dict[str, int] = {}
    coverage_bits: dict[str, int] = {}
    for node in reversed(topological):
        descendants_value = 0
        coverage_value = 0
        for child in graph.successors(node):
            child = str(child)
            descendants_value |= descendant_bits[child] | (1 << node_index[child])
            coverage_value |= coverage_bits[child]
            if child in terminal_index:
                coverage_value |= 1 << terminal_index[child]
        descendant_bits[node] = descendants_value
        coverage_bits[node] = coverage_value

    super_source = "__fma_audit_super_source__"
    while super_source in graph:
        super_source += "_"
    dominator_graph = graph.copy()
    dominator_graph.add_node(super_source)
    dominator_graph.add_edges_from((super_source, source) for source in sources)
    immediate = nx.immediate_dominators(dominator_graph, super_source)
    dominator_children: dict[str, list[str]] = defaultdict(list)
    for node, parent_node in immediate.items():
        if node != super_source:
            dominator_children[str(parent_node)].append(str(node))
    dominated_terminals: dict[str, frozenset[str]] = {}

    def collect_dominated_terminals(node: str) -> frozenset[str]:
        collected = {node} if node in terminals else set()
        for child in dominator_children.get(node, []):
            collected.update(collect_dominated_terminals(child))
        dominated_terminals[node] = frozenset(collected)
        return dominated_terminals[node]

    collect_dominated_terminals(super_source)
    sink_drop = {node: len(dominated_terminals.get(node, ())) for node in nodes}

    parent = {node: node for node in nodes}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for index, left in enumerate(nodes):
        for right in nodes[index + 1 :]:
            left_coverage, right_coverage = coverage_bits[left], coverage_bits[right]
            if not left_coverage or not right_coverage:
                continue
            similarity = (left_coverage & right_coverage).bit_count() / (
                left_coverage | right_coverage
            ).bit_count()
            if similarity > redundancy_threshold:
                union(left, right)
    members: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        members[find(node)].append(node)
    group_id_by_node: dict[str, str | None] = {}
    group_index = 0
    for root in sorted(members):
        group = members[root]
        group_id = f"rg_{group_index:04d}" if len(group) > 1 else None
        if group_id:
            group_index += 1
        for node in group:
            group_id_by_node[node] = group_id

    return {
        node: {
            "is_bottleneck": bool(sink_drop[node] > 0 and descendant_bits[node]),
            "is_redundant": group_id_by_node[node] is not None,
            "redundancy_group_id": group_id_by_node[node],
            "sink_drop_count": sink_drop[node],
            "at_risk_terminal_ids": tuple(sorted(dominated_terminals.get(node, ()))),
            "downstream_impact_count": descendant_bits[node].bit_count(),
            "terminal_coverage_count": coverage_bits[node].bit_count(),
        }
        for node in nodes
    }


def evaluate_controlled_audit_roles(
    graph: nx.DiGraph,
    manifest: MotifManifest,
) -> dict[str, Any]:
    """Evaluate structural roles only on controlled candidates."""
    roles = extract_audit_roles(graph)
    candidates = sorted(manifest.candidate_nodes)
    bottleneck_truth = [node in manifest.bottleneck_nodes for node in candidates]
    redundancy_truth = [node in manifest.redundant_nodes for node in candidates]
    structural_bottleneck = [bool(roles[node]["is_bottleneck"]) for node in candidates]
    structural_redundancy = [bool(roles[node]["is_redundant"]) for node in candidates]

    tfidf_bottleneck, tfidf_redundancy = _tfidf_predictions(graph, candidates, bottleneck_truth)
    betweenness = nx.betweenness_centrality(graph)
    out_closeness = nx.closeness_centrality(graph.reverse(copy=False))
    betweenness_pred = _top_k_predictions(candidates, betweenness, sum(bottleneck_truth))
    out_closeness_pred = _top_k_predictions(candidates, out_closeness, sum(bottleneck_truth))

    bottleneck_metrics = _binary_metrics(bottleneck_truth, structural_bottleneck)
    redundancy_metrics = _binary_metrics(redundancy_truth, structural_redundancy)
    return {
        "title": "Controlled Audit Role Evaluation",
        "evaluation_target": "controlled_audit_motifs_not_native_wikidata_annotations",
        "statement": (
            "Evaluation is performed against controlled audit motifs rather than "
            "native Wikidata annotations."
        ),
        "support": {
            "bottleneck": len(manifest.bottleneck_nodes),
            "redundancy": len(manifest.redundant_nodes),
            "controlled_candidates": len(candidates),
        },
        "structural": {
            "bottleneck": bottleneck_metrics,
            "redundancy": redundancy_metrics,
            "macro_f1": (bottleneck_metrics["f1"] + redundancy_metrics["f1"]) / 2.0,
        },
        "baselines": {
            "tfidf": {
                "bottleneck": _binary_metrics(bottleneck_truth, tfidf_bottleneck),
                "redundancy": _binary_metrics(redundancy_truth, tfidf_redundancy),
            },
            "betweenness": {
                "bottleneck": _binary_metrics(bottleneck_truth, betweenness_pred),
                "redundancy": None,
            },
            "out_closeness": {
                "bottleneck": _binary_metrics(bottleneck_truth, out_closeness_pred),
                "redundancy": None,
            },
        },
    }


FAIR_PROTOCOL_VERSION = "fair-v1"
CANDIDATE_RULE = "layer > 0 and downstream_impact_count > 0"

METHODS = (
    "life_saving_first",
    "life_saving_clustered",
    "greedy_maximum_coverage",
    "flat_top_k",
    "degree_centrality",
    "random_stratified",
    "position",
    "random",
    "no_fallback",
    "lsf_minus_bottleneck",
    "lsf_minus_redundancy",
    "lsf_minus_unique_layer",
)

PRIMARY_INFERENCE_BASELINES = (
    "flat_top_k",
    "greedy_maximum_coverage",
    "degree_centrality",
)

POLICY_LAYERS = (
    "critical_bottleneck",
    "unique_evidence",
    "redundancy_group_samples",
    "fallback",
)

DISCIPLINE_OCCUPATIONS = (
    ("physical_sciences", frozenset({"Q169470", "Q170790", "Q11063"})),
    ("life_sciences", frozenset({"Q593644", "Q864503"})),
    ("computing", frozenset({"Q82594"})),
    (
        "social_sciences",
        frozenset({"Q188094", "Q2306091", "Q1238570", "Q212980", "Q4773904"}),
    ),
)

ANCHOR_CONFIRMATION_METHODS = (
    "life_saving_first",
    "life_saving_clustered",
    "greedy_maximum_coverage",
    "flat_top_k",
    "degree_centrality",
)


def evaluate_impact_coverage(
    graph: nx.DiGraph,
    *,
    budget_fraction: float,
    seed: int,
    reference_graph: nx.DiGraph | None = None,
    fixed_budget_k: int | None = None,
    _roles: Mapping[str, Mapping[str, Any]] | None = None,
    _reference_roles: Mapping[str, Mapping[str, Any]] | None = None,
    source_unit_id: str = "wikidata_scientist_substrate",
    replicate_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate Life-Saving First and fixed-budget baselines on one audit DAG."""
    if not 0.0 < budget_fraction <= 1.0:
        raise ValueError("budget_fraction must be in (0, 1]")
    roles = _roles or extract_audit_roles(graph)
    evaluation_graph = reference_graph if reference_graph is not None else graph
    reference_roles = (
        roles
        if reference_graph is None
        else (_reference_roles or extract_audit_roles(evaluation_graph))
    )
    records = _node_records(graph, roles)
    candidates = [record for record in records if _is_fair_candidate(record)]
    candidate_ids = sorted(str(record["node_id"]) for record in candidates)
    candidate_id_sha256 = _candidate_id_sha256(candidate_ids)
    reference_records = records if reference_graph is None else _node_records(
        evaluation_graph, reference_roles
    )
    reference_candidate_ids = [
        str(record["node_id"])
        for record in reference_records
        if _is_fair_candidate(record)
    ]
    proportional_budget = (
        max(1, math.ceil(len(candidates) * budget_fraction)) if candidates else 0
    )
    if fixed_budget_k is not None:
        if fixed_budget_k < 0:
            raise ValueError("fixed_budget_k must be non-negative")
        if fixed_budget_k > len(candidates):
            raise ValueError(
                f"fixed_budget_k={fixed_budget_k} exceeds selection candidates="
                f"{len(candidates)}"
            )
        budget = fixed_budget_k
        budget_source = "fixed_absolute"
    else:
        budget = proportional_budget
        budget_source = "selection_graph_candidate_count"

    life_saving = _life_saving_selection(
        candidates, budget=budget, seed=seed, include_fallback=True
    )
    life_saving_clustered = life_saving_clustered_selection(
        candidates, budget=budget, seed=seed, include_fallback=True
    )
    no_fallback = _life_saving_selection(
        candidates, budget=budget, seed=seed, include_fallback=False
    )
    randomized_roles = _randomized_role_records(candidates, seed)
    random_stratified = _life_saving_selection(
        randomized_roles,
        budget=budget,
        seed=seed,
        include_fallback=True,
    )
    selections = {
        "life_saving_first": life_saving,
        "life_saving_clustered": life_saving_clustered,
        "greedy_maximum_coverage": greedy_maximum_coverage_selection(
            graph, candidates, budget=budget
        ),
        "flat_top_k": _ordered_selection(
            candidates, budget, lambda row: (-row["raw_risk_score"], row["node_id"])
        ),
        "degree_centrality": _ordered_selection(
            candidates, budget, lambda row: (-row["degree"], row["node_id"])
        ),
        "random_stratified": random_stratified,
        "position": _ordered_selection(
            candidates, budget, lambda row: (-row["layer"], row["node_id"])
        ),
        "random": _random_selection(candidates, budget, seed),
        "no_fallback": no_fallback,
        "lsf_minus_bottleneck": _life_saving_selection(
            candidates,
            budget=budget,
            seed=seed,
            include_fallback=True,
            use_bottleneck=False,
        ),
        "lsf_minus_redundancy": _life_saving_selection(
            candidates,
            budget=budget,
            seed=seed,
            include_fallback=True,
            use_redundancy=False,
        ),
        "lsf_minus_unique_layer": _life_saving_selection(
            candidates,
            budget=budget,
            seed=seed,
            include_fallback=True,
            use_unique_layer=False,
        ),
    }
    methods: dict[str, dict[str, Any]] = {}
    for method, selection in selections.items():
        metrics = impact_coverage_metrics(evaluation_graph, selection["selected_node_ids"])
        structural_metrics = _structural_protection_metrics(
            reference_roles,
            reference_candidate_ids,
            selection["selected_node_ids"],
        )
        methods[method] = {
            **metrics,
            **structural_metrics,
            "budget_k": budget,
            "budget_used": len(selection["selected_node_ids"]),
            "selected_node_ids": selection["selected_node_ids"],
            "candidate_id_sha256": candidate_id_sha256,
            "selection_changed_vs_lsf": (
                selection["selected_node_ids"] != life_saving["selected_node_ids"]
            ),
        }
    return {
        "protocol_version": FAIR_PROTOCOL_VERSION,
        "candidate_rule": CANDIDATE_RULE,
        "candidate_ids": candidate_ids,
        "candidate_id_sha256": candidate_id_sha256,
        "candidate_records": [dict(record) for record in candidates],
        "source_unit_id": str(source_unit_id),
        "replicate_id": str(replicate_id if replicate_id is not None else seed),
        "budget_fraction": float(budget_fraction),
        "candidate_count": len(candidates),
        "budget_source": budget_source,
        "evaluation_graph": (
            "clean_reference" if reference_graph is not None else "selection_graph"
        ),
        "methods": methods,
        "life_saving_first_layers": _policy_layer_report(
            evaluation_graph, life_saving, budget
        ),
    }


def perturb_overlay_edges(
    graph: nx.DiGraph,
    *,
    rate: float,
    mode: str,
    seed: int,
) -> tuple[nx.DiGraph, dict[str, Any]]:
    """Delete real edges or insert layer-respecting erroneous edges."""
    if mode not in {"deletion", "insertion"}:
        raise ValueError("mode must be 'deletion' or 'insertion'")
    if not 0.0 <= rate <= 1.0:
        raise ValueError("rate must be in [0, 1]")
    perturbed = graph.copy()
    eligible_edges = sorted(
        (str(source), str(target))
        for source, target, data in graph.edges(data=True)
        if not data.get("controlled_motif")
    )
    target_count = round(len(eligible_edges) * rate)
    rng = random.Random(f"{seed}|{mode}|{rate:.8f}")
    changed: list[tuple[str, str]] = []
    if mode == "deletion":
        changed = rng.sample(eligible_edges, k=min(target_count, len(eligible_edges)))
        perturbed.remove_edges_from(changed)
    else:
        absent = sorted(
            (str(source), str(target))
            for source in graph.nodes
            for target in graph.nodes
            if int(graph.nodes[source].get("layer", -1)) < int(graph.nodes[target].get("layer", -1))
            and not graph.has_edge(source, target)
        )
        changed = rng.sample(absent, k=min(target_count, len(absent)))
        for source, target in changed:
            perturbed.add_edge(
                source,
                target,
                predicates=("P31",),
                controlled_motif=False,
                erroneous_edge=True,
            )
    if not nx.is_directed_acyclic_graph(perturbed):
        raise ValueError("edge perturbation must preserve the DAG overlay")
    return perturbed, {
        "mode": mode,
        "rate": float(rate),
        "eligible_edge_count": len(eligible_edges),
        "requested_edge_count": target_count,
        "changed_edge_count": len(changed),
        "changed_edges": [list(edge) for edge in changed],
    }


def paired_statistical_test(
    primary: Sequence[float],
    baseline: Sequence[float],
    *,
    seed: int,
    bootstrap_rounds: int = 1000,
) -> dict[str, Any]:
    """Return paired Wilcoxon, signed-rank effect, and paired bootstrap intervals."""
    if len(primary) != len(baseline) or not primary:
        raise ValueError("paired samples must be non-empty and have equal length")
    differences = [
        float(left) - float(right)
        for left, right in zip(primary, baseline, strict=True)
    ]
    if all(abs(value) <= 1e-15 for value in differences):
        return {
            "p_value": 1.0,
            "rank_biserial": 0.0,
            "effect_ci95": [0.0, 0.0],
            "degenerate": True,
            "mean_difference": 0.0,
            "mean_difference_ci95": [0.0, 0.0],
            "bootstrap_rounds": int(bootstrap_rounds),
        }
    p_value = float(wilcoxon(differences, alternative="two-sided").pvalue)
    effect = _matched_rank_biserial(differences)
    rng = random.Random(seed)
    effects = []
    mean_differences = []
    for _ in range(bootstrap_rounds):
        indices = [rng.randrange(len(primary)) for _ in primary]
        sampled = [differences[index] for index in indices]
        effects.append(_matched_rank_biserial(sampled))
        mean_differences.append(float(mean(sampled)))
    effect_ci = _percentile_interval(effects, fallback=effect)
    mean_ci = _percentile_interval(
        mean_differences,
        fallback=float(mean(differences)),
    )
    return {
        "p_value": p_value,
        "rank_biserial": float(effect),
        "effect_ci95": effect_ci,
        "degenerate": False,
        "mean_difference": float(mean(differences)),
        "mean_difference_ci95": mean_ci,
        "bootstrap_rounds": int(bootstrap_rounds),
    }


def run_budget_sweep(
    overlay: DagOverlay,
    *,
    seeds: Sequence[int],
    budget_fractions: Sequence[float],
    motif_count: int | None = None,
    bootstrap_rounds: int = 1000,
    primary_budget_fraction: float = 0.25,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    layer_counts: Counter[str] = Counter()
    for seed in seeds:
        motif = add_controlled_audit_motifs(overlay, seed, motif_count=motif_count)
        roles = extract_audit_roles(motif.graph)
        for budget_fraction in budget_fractions:
            report = evaluate_impact_coverage(
                motif.graph,
                budget_fraction=float(budget_fraction),
                seed=int(seed),
                _roles=roles,
            )
            for layer in report["life_saving_first_layers"]:
                layer_counts[str(layer["layer"])] += int(layer["selected_count"])
            rows.extend(
                _method_rows(
                    report,
                    seed=int(seed),
                    condition_name="budget_fraction",
                    condition_value=float(budget_fraction),
                )
            )
    result = _sweep_report(
        rows,
        condition_name="budget_fraction",
        seeds=seeds,
        bootstrap_rounds=bootstrap_rounds,
        inference_condition=float(primary_budget_fraction),
        inference_baselines=PRIMARY_INFERENCE_BASELINES,
        holm_family="primary_budget_predeclared",
    )
    result["layer_activation"] = {
        "counts": {layer: int(layer_counts.get(layer, 0)) for layer in POLICY_LAYERS},
        "unexercised_layers": [
            layer for layer in POLICY_LAYERS if layer_counts.get(layer, 0) == 0
        ],
        "unit": "selected_records_across_motif_seed_and_budget",
    }
    return result


def run_noise_sweep(
    overlay: DagOverlay,
    *,
    seeds: Sequence[int],
    rates: Sequence[float],
    mode: str,
    budget_fraction: float,
    motif_count: int | None = None,
    bootstrap_rounds: int = 1000,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    perturbations: list[dict[str, Any]] = []
    fixed_budget_by_seed: dict[int, int] = {}
    for seed in seeds:
        motif = add_controlled_audit_motifs(overlay, seed, motif_count=motif_count)
        reference_roles = extract_audit_roles(motif.graph)
        reference_candidates = [
            record
            for record in _node_records(motif.graph, reference_roles)
            if _is_fair_candidate(record)
        ]
        fixed_budget = (
            max(1, math.ceil(len(reference_candidates) * budget_fraction))
            if reference_candidates
            else 0
        )
        fixed_budget_by_seed[int(seed)] = fixed_budget
        for rate in rates:
            graph, perturbation = perturb_overlay_edges(
                motif.graph,
                rate=float(rate),
                mode=mode,
                seed=int(seed),
            )
            perturbations.append({"seed": int(seed), **perturbation})
            report = evaluate_impact_coverage(
                graph,
                reference_graph=motif.graph,
                budget_fraction=budget_fraction,
                fixed_budget_k=fixed_budget,
                _reference_roles=reference_roles,
                seed=int(seed),
            )
            method_rows = _method_rows(
                report,
                seed=int(seed),
                condition_name="noise_rate",
                condition_value=float(rate),
            )
            for row in method_rows:
                row["noise_mode"] = mode
            rows.extend(method_rows)
    result = _sweep_report(
        rows,
        condition_name="noise_rate",
        seeds=seeds,
        bootstrap_rounds=bootstrap_rounds,
        inference_condition=None,
        inference_baselines=(),
        holm_family=None,
    )
    result["mode"] = mode
    result["evaluation_graph"] = "clean_reference"
    result["budget_source"] = "clean_reference_candidate_count"
    result["fixed_budget_k_by_seed"] = fixed_budget_by_seed
    result["perturbations"] = perturbations
    result["degradation_statistics"] = _noise_degradation_statistics(
        rows,
        seeds=seeds,
        bootstrap_rounds=bootstrap_rounds,
    )
    return result


def run_anchor_cluster_confirmation(
    raw_graph: nx.DiGraph,
    triples: Sequence[Triple],
    scientist_ids: set[str],
    *,
    budget_fraction: float = 0.05,
    clusters_per_discipline: int = 4,
    motif_seed: int = 0,
    motif_count: int | None = None,
    bootstrap_rounds: int = 1000,
    require_complete_clusters: bool = True,
) -> dict[str, Any]:
    """Evaluate the predeclared low budget with anchor clusters as paired units."""
    if not 0.0 < budget_fraction <= 1.0:
        raise ValueError("budget_fraction must be in (0, 1]")
    if clusters_per_discipline <= 0:
        raise ValueError("clusters_per_discipline must be positive")

    assignments = _assign_scientist_disciplines(triples, scientist_ids)
    clusters = _discipline_anchor_clusters(assignments, clusters_per_discipline)
    if require_complete_clusters:
        _require_complete_anchor_clusters(clusters, clusters_per_discipline)
    units: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    skipped_units: list[dict[str, Any]] = []
    clustered_changed = False
    for discipline, cluster_index, anchors in clusters:
        unit_id = f"{discipline}:{cluster_index:02d}"
        neighborhood = _outgoing_neighborhood(raw_graph, set(anchors), cutoff=3)
        unit_graph = raw_graph.subgraph(neighborhood).copy()
        overlay = build_dag_overlay(unit_graph, set(anchors))
        if not overlay.layers.get(1):
            skipped_units.append(
                {
                    "unit_id": unit_id,
                    "discipline": discipline,
                    "anchor_ids": anchors,
                    "reason": "no_layer_1_context",
                }
            )
            continue
        motif = add_controlled_audit_motifs(
            overlay,
            motif_seed,
            motif_count=motif_count,
        )
        evaluation = evaluate_impact_coverage(
            motif.graph,
            budget_fraction=budget_fraction,
            seed=motif_seed,
        )
        clustered_changed = clustered_changed or (
            evaluation["methods"]["life_saving_clustered"]["selected_node_ids"]
            != evaluation["methods"]["life_saving_first"]["selected_node_ids"]
        )
        units.append(
            {
                "unit_id": unit_id,
                "discipline": discipline,
                "anchor_ids": anchors,
                "anchor_count": len(anchors),
                "raw_node_count": unit_graph.number_of_nodes(),
                "raw_edge_count": unit_graph.number_of_edges(),
                "overlay_node_count": overlay.graph.number_of_nodes(),
                "overlay_edge_count": overlay.graph.number_of_edges(),
                "candidate_count": evaluation["candidate_count"],
                "budget_k": evaluation["methods"]["life_saving_first"]["budget_k"],
                "motif_seed": motif_seed,
            }
        )
        for method in ANCHOR_CONFIRMATION_METHODS:
            metrics = evaluation["methods"][method]
            rows.append(
                {
                    "unit_id": unit_id,
                    "discipline": discipline,
                    "anchor_count": len(anchors),
                    "method": method,
                    "budget_fraction": float(budget_fraction),
                    "budget_k": int(metrics["budget_k"]),
                    "impact_coverage": float(metrics["impact_coverage_at_k"]),
                    "average_path_length": float(metrics["average_path_length"]),
                    "protected_at_risk_coverage": float(
                        metrics["protected_at_risk_coverage_at_k"]
                    ),
                    "sink_drop_mass": float(metrics["sink_drop_mass_at_k"]),
                    "redundancy_waste": float(metrics["redundancy_waste_at_k"]),
                }
            )

    if not units:
        raise ValueError("anchor-cluster confirmation produced no evaluable units")
    if require_complete_clusters:
        evaluated = [
            (str(unit["discipline"]), int(str(unit["unit_id"]).rsplit(":", 1)[1]), [])
            for unit in units
        ]
        _require_complete_anchor_clusters(evaluated, clusters_per_discipline)
    reporting_methods = [
        method
        for method in ANCHOR_CONFIRMATION_METHODS
        if method != "life_saving_clustered" or clustered_changed
    ]
    summary = _anchor_cluster_summary(rows, methods=reporting_methods)
    statistics = _anchor_cluster_statistics(
        rows,
        motif_seed=motif_seed,
        bootstrap_rounds=bootstrap_rounds,
        include_clustered=clustered_changed,
    )
    return {
        "statistical_unit": "anchor_cluster",
        "budget_fraction": float(budget_fraction),
        "clusters_per_discipline": clusters_per_discipline,
        "motif_seed": motif_seed,
        "require_complete_clusters": require_complete_clusters,
        "discipline_priority": [name for name, _ in DISCIPLINE_OCCUPATIONS],
        "discipline_assignments": assignments,
        "unassigned_scientist_ids": sorted(set(scientist_ids) - set(assignments)),
        "units": units,
        "skipped_units": skipped_units,
        "rows": rows,
        "summary": summary,
        "statistics": statistics,
        "non_informative_methods": (
            [] if clustered_changed else ["life_saving_clustered"]
        ),
        "independence_boundary": (
            "Anchor clusters are paired units from one extracted Wikidata substrate, "
            "not independent knowledge graphs."
        ),
    }


def _assign_scientist_disciplines(
    triples: Sequence[Triple],
    scientist_ids: set[str],
) -> dict[str, str]:
    occupations: dict[str, set[str]] = defaultdict(set)
    for triple in triples:
        if triple.predicate == "P106" and triple.subject in scientist_ids:
            occupations[triple.subject].add(triple.object)
    assignments: dict[str, str] = {}
    for scientist in sorted(scientist_ids):
        for discipline, discipline_occupations in DISCIPLINE_OCCUPATIONS:
            if occupations[scientist] & discipline_occupations:
                assignments[scientist] = discipline
                break
    return assignments


def _discipline_anchor_clusters(
    assignments: Mapping[str, str],
    clusters_per_discipline: int,
) -> list[tuple[str, int, list[str]]]:
    by_discipline: dict[str, list[str]] = defaultdict(list)
    for scientist, discipline in assignments.items():
        by_discipline[discipline].append(scientist)
    clusters = []
    for discipline, _ in DISCIPLINE_OCCUPATIONS:
        ranked = sorted(
            by_discipline.get(discipline, []),
            key=lambda scientist: (
                hashlib.sha256(f"{discipline}|{scientist}".encode("ascii")).hexdigest(),
                scientist,
            ),
        )
        cluster_count = min(clusters_per_discipline, len(ranked))
        buckets = [[] for _ in range(cluster_count)]
        for index, scientist in enumerate(ranked):
            buckets[index % cluster_count].append(scientist)
        clusters.extend(
            (discipline, index + 1, sorted(bucket))
            for index, bucket in enumerate(buckets)
            if bucket
        )
    return clusters


def _require_complete_anchor_clusters(
    clusters: Sequence[tuple[str, int, Sequence[str]]],
    clusters_per_discipline: int,
) -> None:
    counts = Counter(discipline for discipline, _, _ in clusters)
    missing = [
        f"{discipline}={counts.get(discipline, 0)}/{clusters_per_discipline}"
        for discipline, _ in DISCIPLINE_OCCUPATIONS
        if counts.get(discipline, 0) != clusters_per_discipline
    ]
    if missing:
        raise ValueError("missing required anchor clusters: " + ", ".join(missing))


def _outgoing_neighborhood(
    graph: nx.DiGraph,
    anchors: set[str],
    *,
    cutoff: int,
) -> set[str]:
    selected = set(graph).intersection(anchors)
    frontier = set(selected)
    for _ in range(cutoff):
        next_frontier = {
            str(target)
            for source in frontier
            for target in graph.successors(source)
            if str(target) not in selected
        }
        selected.update(next_frontier)
        frontier = next_frontier
        if not frontier:
            break
    return selected


def _anchor_cluster_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    methods: Sequence[str] = ANCHOR_CONFIRMATION_METHODS,
) -> list[dict[str, Any]]:
    summary = []
    for method in methods:
        method_rows = [row for row in rows if row["method"] == method]
        values = [float(row["impact_coverage"]) for row in method_rows]
        summary.append(
            {
                "method": method,
                "mean": float(mean(values)),
                "std": float(stdev(values)) if len(values) > 1 else 0.0,
                "mean_average_path_length": float(
                    mean(float(row["average_path_length"]) for row in method_rows)
                ),
                "mean_protected_at_risk_coverage": float(
                    mean(float(row["protected_at_risk_coverage"]) for row in method_rows)
                ),
                "mean_sink_drop_mass": float(
                    mean(float(row["sink_drop_mass"]) for row in method_rows)
                ),
                "mean_redundancy_waste": float(
                    mean(float(row["redundancy_waste"]) for row in method_rows)
                ),
                "n": len(values),
            }
        )
    return summary


def _anchor_cluster_statistics(
    rows: Sequence[Mapping[str, Any]],
    *,
    motif_seed: int,
    bootstrap_rounds: int,
    include_clustered: bool = True,
) -> list[dict[str, Any]]:
    indexed = {
        (str(row["unit_id"]), str(row["method"])): float(row["impact_coverage"])
        for row in rows
    }
    unit_ids = sorted({str(row["unit_id"]) for row in rows})
    comparisons = [
        ("life_saving_first", "greedy_maximum_coverage"),
        ("life_saving_first", "flat_top_k"),
        ("life_saving_first", "degree_centrality"),
    ]
    if include_clustered:
        comparisons = [
            ("life_saving_first", "life_saving_clustered"),
            *comparisons,
            ("life_saving_clustered", "greedy_maximum_coverage"),
            ("life_saving_clustered", "flat_top_k"),
            ("life_saving_clustered", "degree_centrality"),
        ]
    statistics = []
    for primary, baseline in comparisons:
        result = paired_statistical_test(
            [indexed[(unit_id, primary)] for unit_id in unit_ids],
            [indexed[(unit_id, baseline)] for unit_id in unit_ids],
            seed=motif_seed + sum(map(ord, primary + baseline)),
            bootstrap_rounds=bootstrap_rounds,
        )
        statistics.append(
            {
                "primary": primary,
                "baseline": baseline,
                "statistical_unit": "anchor_cluster",
                "n": len(unit_ids),
                **result,
            }
        )
    _apply_holm_correction(statistics)
    return statistics


def _noise_degradation_statistics(
    rows: Sequence[Mapping[str, Any]],
    *,
    seeds: Sequence[int],
    bootstrap_rounds: int,
) -> list[dict[str, Any]]:
    metrics = ("impact_coverage", "protected_at_risk_coverage")
    rates = sorted({float(row["noise_rate"]) for row in rows})
    if not rates or 0.20 not in rates:
        return []
    reference_rate = rates[0]
    index = {
        (int(row["seed"]), float(row["noise_rate"]), str(row["method"])): row
        for row in rows
    }
    statistics: list[dict[str, Any]] = []
    rate = 0.20
    for metric in metrics:
        primary_delta = [
            float(index[(seed, rate, "life_saving_first")][metric])
            - float(index[(seed, reference_rate, "life_saving_first")][metric])
            for seed in seeds
        ]
        for baseline in ("flat_top_k", "greedy_maximum_coverage"):
            baseline_delta = [
                float(index[(seed, rate, baseline)][metric])
                - float(index[(seed, reference_rate, baseline)][metric])
                for seed in seeds
            ]
            result = paired_statistical_test(
                primary_delta,
                baseline_delta,
                seed=int(sum(seeds) + round(rate * 10000) + len(metric) + len(baseline)),
                bootstrap_rounds=bootstrap_rounds,
            )
            statistics.append(
                {
                    "noise_rate": rate,
                    "reference_noise_rate": reference_rate,
                    "metric": metric,
                    "baseline": baseline,
                    "life_saving_first_mean_change": float(mean(primary_delta)),
                    "baseline_mean_change": float(mean(baseline_delta)),
                    "positive_mean_difference_means_less_degradation": True,
                    "holm_family": "noise_20pct_predeclared",
                    **result,
                }
            )
    _apply_holm_correction(statistics)
    return statistics


def run_efficiency_experiment(
    raw_graph: nx.DiGraph,
    scientist_ids: set[str],
    *,
    sizes: Sequence[int],
    repeats: int,
    warmups: int,
    seed: int,
    motif_count: int | None = None,
) -> dict[str, Any]:
    """Measure pipeline stages on deterministic real-substrate graph samples."""
    if repeats <= 0 or warmups < 0:
        raise ValueError("repeats must be positive and warmups must be non-negative")
    rows: list[dict[str, Any]] = []
    for target_nodes in sizes:
        sample = _deterministic_graph_sample(raw_graph, scientist_ids, int(target_nodes))
        sample_scientists = set(sample).intersection(scientist_ids)
        if not sample_scientists:
            raise ValueError(f"size {target_nodes} sample contains no scientist anchors")
        for _ in range(warmups):
            _measure_efficiency_once(
                sample, sample_scientists, seed, motif_count, trace_memory=False
            )
        for repeat in range(repeats):
            row = _measure_efficiency_once(
                sample,
                sample_scientists,
                seed + repeat,
                motif_count,
                trace_memory=True,
            )
            rows.append(
                {
                    "target_nodes": int(target_nodes),
                    "actual_nodes": sample.number_of_nodes(),
                    "actual_edges": sample.number_of_edges(),
                    "repeat": repeat,
                    **row,
                }
            )
    means = {
        size: mean(row["total_seconds"] for row in rows if row["target_nodes"] == size)
        for size in sorted({row["target_nodes"] for row in rows})
    }
    return {
        "rows": rows,
        "summary": _efficiency_summary(rows),
        "empirical_log_log_slope": _log_log_slope(means),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor(),
            "networkx": nx.__version__,
        },
        "complexity": {
            "cleaning_and_layering": "O(V + E)",
            "bottleneck_definition": "Exact node-removal definition: O(V(V + E)) worst case",
            "bottleneck_implementation": (
                "Equivalent super-source immediate-dominator computation; implementation-dependent "
                "iterative complexity, measured empirically"
            ),
            "terminal_coverage_and_redundancy": (
                "Reverse-DAG integer bitsets plus O(V^2) pairwise bitset Jaccard comparisons"
            ),
            "selection": "O(V log V)",
            "impact_coverage": "O(V + E) multi-source shortest-path traversal",
        },
        "claim_boundary": "empirical_scaling_trend_not_asymptotic_optimality",
    }


def _node_records(
    graph: nx.DiGraph,
    roles: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    impacts = [int(row["downstream_impact_count"]) for row in roles.values()]
    minimum, maximum = (min(impacts), max(impacts)) if impacts else (0, 0)
    records = []
    for node in sorted(map(str, graph.nodes)):
        impact = int(roles[node]["downstream_impact_count"])
        raw_risk = (impact - minimum) / (maximum - minimum) if maximum > minimum else 0.0
        records.append(
            {
                "node_id": node,
                "layer": int(graph.nodes[node].get("layer", 0)),
                "degree": int(graph.in_degree(node) + graph.out_degree(node)),
                "downstream_impact_count": impact,
                "raw_risk_score": float(raw_risk),
                "is_bottleneck": bool(roles[node]["is_bottleneck"]),
                "is_redundant": bool(roles[node]["is_redundant"]),
                "redundancy_group_id": roles[node]["redundancy_group_id"],
                "sink_drop_count": int(roles[node]["sink_drop_count"]),
                "at_risk_terminal_ids": list(roles[node]["at_risk_terminal_ids"]),
            }
        )
    return records


def _is_fair_candidate(record: Mapping[str, Any]) -> bool:
    return int(record["layer"]) > 0 and int(record["downstream_impact_count"]) > 0


def _candidate_id_sha256(candidate_ids: Sequence[str]) -> str:
    payload = "\n".join(sorted(map(str, candidate_ids))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def greedy_maximum_coverage_selection(
    graph: nx.DiGraph,
    candidates: Sequence[Mapping[str, Any]],
    *,
    budget: int,
) -> dict[str, Any]:
    """Select nodes by deterministic marginal descendant coverage."""
    if budget < 0:
        raise ValueError("budget must be non-negative")
    by_id = {str(row["node_id"]): row for row in candidates}
    auditable = {
        str(node)
        for node, data in graph.nodes(data=True)
        if int(data.get("layer", 0)) > 0
    }
    descendant_sets = {
        node_id: {str(node) for node in nx.descendants(graph, node_id)} & auditable
        for node_id in by_id
        if node_id in graph
    }
    selected: list[str] = []
    covered: set[str] = set()
    marginal_counts: list[int] = []
    remaining = set(by_id)
    while remaining and len(selected) < budget:
        ranked = sorted(
            remaining,
            key=lambda node_id: (
                -len(descendant_sets.get(node_id, set()) - covered),
                _selection_order_key(by_id[node_id]),
            ),
        )
        chosen = ranked[0]
        newly_covered = descendant_sets.get(chosen, set()) - covered
        selected.append(chosen)
        marginal_counts.append(len(newly_covered))
        covered.update(newly_covered)
        remaining.remove(chosen)
    return {
        "selected_node_ids": selected,
        "marginal_descendant_counts": marginal_counts,
    }


def greedy_utility_oracle_selection(
    graph: nx.DiGraph,
    candidates: Sequence[Mapping[str, Any]],
    reference_roles: Mapping[str, Mapping[str, Any]],
    *,
    budget: int,
    lambda_weight: float,
) -> dict[str, Any]:
    """Greedily maximize the diagnostic coverage-protection utility."""
    if budget < 0:
        raise ValueError("budget must be non-negative")
    if not 0.0 <= lambda_weight <= 1.0:
        raise ValueError("lambda_weight must be in [0, 1]")
    by_id = {str(row["node_id"]): row for row in candidates}
    auditable = sorted(
        str(node)
        for node, data in graph.nodes(data=True)
        if int(data.get("layer", 0)) > 0
    )
    auditable_index = {node: index for index, node in enumerate(auditable)}
    descendant_bits: dict[str, int] = {}
    for node in reversed(list(map(str, nx.topological_sort(graph)))):
        bits = 0
        for child in graph.successors(node):
            child = str(child)
            bits |= descendant_bits[child]
            if child in auditable_index:
                bits |= 1 << auditable_index[child]
        descendant_bits[node] = bits
    at_risk_ids = sorted(
        {
            str(terminal)
            for node_id in by_id
            for terminal in reference_roles.get(node_id, {}).get(
                "at_risk_terminal_ids", ()
            )
        }
    )
    risk_index = {terminal: index for index, terminal in enumerate(at_risk_ids)}
    risk_bits = {
        node_id: sum(
            1 << risk_index[str(terminal)]
            for terminal in reference_roles.get(node_id, {}).get(
                "at_risk_terminal_ids", ()
            )
            if str(terminal) in risk_index
        )
        for node_id in by_id
    }
    selected: list[str] = []
    selected_bits = 0
    covered_bits = 0
    protected_bits = 0
    marginal_utilities: list[float] = []
    current_utility = 0.0
    remaining = set(by_id)
    while remaining and len(selected) < budget:
        denominator = max(1, len(auditable) - len(selected) - 1)

        def score(node_id: str) -> tuple[float, tuple[int, float, int, str]]:
            node_bit = (
                1 << auditable_index[node_id] if node_id in auditable_index else 0
            )
            coverage = (
                (covered_bits | descendant_bits.get(node_id, 0))
                & ~(selected_bits | node_bit)
            ).bit_count() / denominator
            protection = (
                (protected_bits | risk_bits.get(node_id, 0)).bit_count()
                / len(at_risk_ids)
                if at_risk_ids
                else 0.0
            )
            utility = lambda_weight * coverage + (1.0 - lambda_weight) * protection
            return utility, _selection_order_key(by_id[node_id])

        chosen = min(remaining, key=lambda node_id: (-score(node_id)[0], score(node_id)[1]))
        utility, _ = score(chosen)
        selected.append(chosen)
        if chosen in auditable_index:
            selected_bits |= 1 << auditable_index[chosen]
        covered_bits = (covered_bits | descendant_bits.get(chosen, 0)) & ~selected_bits
        protected_bits |= risk_bits.get(chosen, 0)
        marginal_utilities.append(float(utility - current_utility))
        current_utility = utility
        remaining.remove(chosen)
    denominator = max(1, len(auditable) - len(selected))
    coverage = covered_bits.bit_count() / denominator if auditable else 0.0
    protection = (
        protected_bits.bit_count() / len(at_risk_ids) if at_risk_ids else 0.0
    )
    return {
        "selected_node_ids": selected,
        "lambda": float(lambda_weight),
        "impact_coverage": float(coverage),
        "protected_at_risk_coverage": float(protection),
        "utility": float(lambda_weight * coverage + (1.0 - lambda_weight) * protection),
        "marginal_utilities": marginal_utilities,
        "diagnostic_oracle": True,
    }


def compute_utility_tradeoff(
    rows: Sequence[Mapping[str, Any]],
    *,
    baselines: Sequence[str] = PRIMARY_INFERENCE_BASELINES,
    lambda_values: Sequence[float] | None = None,
    seed: int,
    bootstrap_rounds: int = 10000,
) -> dict[str, Any]:
    """Summarize paired seed-level coverage-protection tradeoffs."""
    lambdas = [
        float(value)
        for value in (
            lambda_values
            if lambda_values is not None
            else [index / 100 for index in range(101)]
        )
    ]
    if not lambdas or lambdas != sorted(lambdas) or lambdas[0] < 0.0 or lambdas[-1] > 1.0:
        raise ValueError("lambda_values must be a sorted non-empty grid within [0, 1]")
    index = {
        (int(row["seed"]), str(row["method"])): (
            float(row["impact_coverage"]),
            float(row["protected_at_risk_coverage"]),
        )
        for row in rows
    }
    available_methods = {method for _, method in index}
    methods = [
        method
        for method in ("life_saving_first", *baselines)
        if method in available_methods
    ]
    seed_ids = sorted(
        seed_id
        for seed_id in {seed_id for seed_id, _ in index}
        if all((seed_id, method) in index for method in methods)
    )
    if "life_saving_first" not in methods or not seed_ids:
        raise ValueError("utility tradeoff requires paired Life-Saving First rows")

    def mean_point(method: str, sampled_seeds: Sequence[int]) -> tuple[float, float]:
        return (
            float(mean(index[(seed_id, method)][0] for seed_id in sampled_seeds)),
            float(mean(index[(seed_id, method)][1] for seed_id in sampled_seeds)),
        )

    method_points = {
        method: mean_point(method, seed_ids)
        for method in methods
    }
    pareto = {
        method: not any(
            other != method
            and method_points[other][0] >= point[0]
            and method_points[other][1] >= point[1]
            and method_points[other] != point
            for other in methods
        )
        for method, point in method_points.items()
    }
    curves = [
        {
            "lambda": lambda_weight,
            "method": method,
            "mean_utility": float(
                lambda_weight * method_points[method][0]
                + (1.0 - lambda_weight) * method_points[method][1]
            ),
        }
        for lambda_weight in lambdas
        for method in methods
    ]
    rng = random.Random(seed)
    crossovers = []
    for baseline in methods[1:]:
        observed = _utility_grid_crossover(
            method_points["life_saving_first"], method_points[baseline], lambdas
        )
        bootstrapped: list[float] = []
        for _ in range(bootstrap_rounds):
            sampled = [seed_ids[rng.randrange(len(seed_ids))] for _ in seed_ids]
            crossover = _utility_grid_crossover(
                mean_point("life_saving_first", sampled),
                mean_point(baseline, sampled),
                lambdas,
            )
            if crossover is not None:
                bootstrapped.append(crossover)
        valid_fraction = len(bootstrapped) / bootstrap_rounds if bootstrap_rounds else 0.0
        stable = observed is not None and valid_fraction >= 0.95
        crossovers.append(
            {
                "baseline": baseline,
                "valid_fraction": float(valid_fraction),
                "stable": stable,
                "lambda_star": float(observed) if stable and observed is not None else None,
                "lambda_star_ci95": (
                    _percentile_interval(bootstrapped, fallback=float(observed))
                    if stable and observed is not None
                    else None
                ),
                "decision_rule": "report threshold only when bootstrap valid fraction >= 0.95",
            }
        )
    return {
        "statistical_unit": "motif_seed",
        "paired_seed_count": len(seed_ids),
        "lambda_values": lambdas,
        "lambda_step": float(lambdas[1] - lambdas[0]) if len(lambdas) > 1 else 0.0,
        "bootstrap_rounds": int(bootstrap_rounds),
        "method_points": [
            {
                "method": method,
                "mean_impact_coverage": method_points[method][0],
                "mean_protected_at_risk_coverage": method_points[method][1],
                "pareto_nondominated": pareto[method],
            }
            for method in methods
        ],
        "curves": curves,
        "crossovers": crossovers,
    }


def _utility_grid_crossover(
    primary: tuple[float, float],
    baseline: tuple[float, float],
    lambdas: Sequence[float],
) -> float | None:
    differences = [
        lambda_weight * (primary[0] - baseline[0])
        + (1.0 - lambda_weight) * (primary[1] - baseline[1])
        for lambda_weight in lambdas
    ]
    for index, difference in enumerate(differences):
        if abs(difference) <= 1e-15:
            return float(lambdas[index])
        if index and difference * differences[index - 1] < 0.0:
            return float(lambdas[index])
    return None


def _life_saving_selection(
    candidates: Sequence[Mapping[str, Any]],
    *,
    budget: int,
    seed: int,
    include_fallback: bool,
    use_bottleneck: bool = True,
    use_redundancy: bool = True,
    use_unique_layer: bool = True,
) -> dict[str, Any]:
    del seed  # deterministic structural ordering; retained for the shared interface
    selected: list[Mapping[str, Any]] = []
    selected_ids: set[str] = set()
    layer_records: dict[str, list[str]] = {layer: [] for layer in POLICY_LAYERS}

    def add(layer: str, rows: Sequence[Mapping[str, Any]]) -> None:
        remaining = budget - len(selected)
        if remaining <= 0:
            return
        available = [row for row in rows if str(row["node_id"]) not in selected_ids]
        chosen = sorted(available, key=_selection_order_key)[:remaining]
        selected.extend(chosen)
        selected_ids.update(str(row["node_id"]) for row in chosen)
        layer_records[layer] = [str(row["node_id"]) for row in chosen]

    if use_bottleneck:
        add("critical_bottleneck", [row for row in candidates if row["is_bottleneck"]])
    if use_unique_layer:
        add(
            "unique_evidence",
            [
                row
                for row in candidates
                if (not use_bottleneck or not row["is_bottleneck"])
                and (not use_redundancy or not row["is_redundant"])
            ],
        )
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    if use_redundancy:
        for row in candidates:
            if row["redundancy_group_id"]:
                groups[str(row["redundancy_group_id"])].append(row)
    representatives = [sorted(group, key=_selection_order_key)[0] for group in groups.values()]
    add("redundancy_group_samples", representatives)
    if include_fallback:
        add("fallback", candidates)
    return {
        "selected_node_ids": [str(row["node_id"]) for row in selected],
        "layer_records": layer_records,
        "candidate_records": [dict(row) for row in candidates],
    }


def life_saving_clustered_selection(
    candidates: Sequence[Mapping[str, Any]],
    *,
    budget: int,
    seed: int,
    include_fallback: bool = True,
) -> dict[str, Any]:
    """Rotate critical selections across structural coverage groups."""
    if budget < 0:
        raise ValueError("budget must be non-negative")
    del seed  # deterministic structural ordering; retained for the shared interface
    selected: list[Mapping[str, Any]] = []
    selected_ids: set[str] = set()
    layer_records: dict[str, list[str]] = {layer: [] for layer in POLICY_LAYERS}

    def add(
        layer: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        preserve_order: bool = False,
    ) -> None:
        remaining = budget - len(selected)
        if remaining <= 0:
            return
        available = []
        seen_ids = set(selected_ids)
        for row in rows:
            node_id = str(row["node_id"])
            if node_id in seen_ids:
                continue
            available.append(row)
            seen_ids.add(node_id)
        chosen = (available if preserve_order else sorted(available, key=_selection_order_key))[
            :remaining
        ]
        selected.extend(chosen)
        selected_ids.update(str(row["node_id"]) for row in chosen)
        layer_records[layer] = [str(row["node_id"]) for row in chosen]

    critical_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in candidates:
        if not row["is_bottleneck"]:
            continue
        group_id = row.get("redundancy_group_id")
        key = str(group_id) if group_id else f"singleton:{row['node_id']}"
        critical_groups[key].append(row)
    ordered_groups = sorted(
        (sorted(group, key=_selection_order_key) for group in critical_groups.values()),
        key=lambda group: _selection_order_key(group[0]),
    )
    queue = deque((group, 0) for group in ordered_groups)
    rotated_critical = []
    while queue:
        group, index = queue.popleft()
        rotated_critical.append(group[index])
        if index + 1 < len(group):
            queue.append((group, index + 1))
    add("critical_bottleneck", rotated_critical, preserve_order=True)
    add(
        "unique_evidence",
        [row for row in candidates if not row["is_bottleneck"] and not row["is_redundant"]],
    )
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in candidates:
        if row["redundancy_group_id"]:
            groups[str(row["redundancy_group_id"])].append(row)
    representatives = [
        sorted(group, key=_selection_order_key)[0] for group in groups.values()
    ]
    add("redundancy_group_samples", representatives)
    if include_fallback:
        add("fallback", candidates)
    return {
        "selected_node_ids": [str(row["node_id"]) for row in selected],
        "layer_records": layer_records,
        "candidate_records": [dict(row) for row in candidates],
        "critical_cluster_count": len(ordered_groups),
    }


def _selection_order_key(row: Mapping[str, Any]) -> tuple[int, float, int, str]:
    return (
        -int(row["downstream_impact_count"]),
        -float(row["raw_risk_score"]),
        -int(row["degree"]),
        str(row["node_id"]),
    )


def _ordered_selection(
    candidates: Sequence[Mapping[str, Any]],
    budget: int,
    key: Any,
) -> dict[str, Any]:
    chosen = sorted(candidates, key=key)[:budget]
    return {"selected_node_ids": [str(row["node_id"]) for row in chosen]}


def _random_selection(
    candidates: Sequence[Mapping[str, Any]],
    budget: int,
    seed: int,
) -> dict[str, Any]:
    ordered = list(candidates)
    random.Random(f"{seed}|random").shuffle(ordered)
    return {"selected_node_ids": [str(row["node_id"]) for row in ordered[:budget]]}


def _randomized_role_records(
    candidates: Sequence[Mapping[str, Any]],
    seed: int,
) -> list[dict[str, Any]]:
    records = [dict(row) for row in candidates]
    bottlenecks = [bool(row["is_bottleneck"]) for row in records]
    group_ids = [row["redundancy_group_id"] for row in records]
    rng = random.Random(f"{seed}|random-stratified")
    rng.shuffle(bottlenecks)
    rng.shuffle(group_ids)
    for row, bottleneck, group_id in zip(records, bottlenecks, group_ids, strict=True):
        row["is_bottleneck"] = bottleneck
        row["is_redundant"] = group_id is not None
        row["redundancy_group_id"] = group_id
    return records


def impact_coverage_metrics(
    graph: nx.DiGraph,
    selected_nodes: Sequence[str],
) -> dict[str, Any]:
    selected = set(map(str, selected_nodes))
    auditable_unselected = {
        str(node)
        for node, data in graph.nodes(data=True)
        if int(data.get("layer", 0)) > 0 and str(node) not in selected
    }
    valid_sources = {source for source in selected if source in graph}
    all_distances = (
        nx.multi_source_dijkstra_path_length(graph, valid_sources, weight=None)
        if valid_sources
        else {}
    )
    distances = {
        str(target): int(distance)
        for target, distance in all_distances.items()
        if str(target) in auditable_unselected and str(target) not in valid_sources
    }
    denominator = len(auditable_unselected)
    return {
        "impact_coverage_at_k": len(distances) / denominator if denominator else 0.0,
        "covered_descendant_count": len(distances),
        "auditable_unselected_count": denominator,
        "average_path_length": float(mean(distances.values())) if distances else 0.0,
    }


def _structural_protection_metrics(
    reference_roles: Mapping[str, Mapping[str, Any]],
    candidate_node_ids: Sequence[str],
    selected_node_ids: Sequence[str],
) -> dict[str, Any]:
    candidates = [node for node in candidate_node_ids if node in reference_roles]
    selected = [node for node in selected_node_ids if node in reference_roles]
    at_risk_universe = {
        terminal
        for node in candidates
        for terminal in reference_roles[node].get("at_risk_terminal_ids", ())
        if reference_roles[node].get("is_bottleneck")
    }
    protected = {
        terminal
        for node in selected
        for terminal in reference_roles[node].get("at_risk_terminal_ids", ())
        if reference_roles[node].get("is_bottleneck")
    }
    total_sink_drop = sum(int(reference_roles[node]["sink_drop_count"]) for node in candidates)
    selected_sink_drop = sum(int(reference_roles[node]["sink_drop_count"]) for node in selected)
    bottleneck_total = sum(bool(reference_roles[node]["is_bottleneck"]) for node in candidates)
    bottleneck_selected = sum(bool(reference_roles[node]["is_bottleneck"]) for node in selected)
    selected_groups: dict[str, int] = defaultdict(int)
    for node in selected:
        group_id = reference_roles[node].get("redundancy_group_id")
        if group_id:
            selected_groups[str(group_id)] += 1
    redundant_excess = sum(max(0, count - 1) for count in selected_groups.values())
    return {
        "protected_at_risk_record_count": len(protected),
        "protected_at_risk_record_total": len(at_risk_universe),
        "protected_at_risk_coverage_at_k": (
            len(protected) / len(at_risk_universe) if at_risk_universe else 0.0
        ),
        "sink_drop_mass_selected": selected_sink_drop,
        "sink_drop_mass_total": total_sink_drop,
        "sink_drop_mass_at_k": (
            selected_sink_drop / total_sink_drop if total_sink_drop else 0.0
        ),
        "bottleneck_selected_count": bottleneck_selected,
        "bottleneck_candidate_count": bottleneck_total,
        "bottleneck_precision_at_k": (
            bottleneck_selected / len(selected) if selected else 0.0
        ),
        "bottleneck_recall_at_k": (
            bottleneck_selected / bottleneck_total if bottleneck_total else 0.0
        ),
        "redundancy_waste_count": redundant_excess,
        "redundancy_waste_at_k": (
            redundant_excess / len(selected) if selected else 0.0
        ),
    }


def _policy_layer_report(
    graph: nx.DiGraph,
    selection: Mapping[str, Any],
    budget: int,
) -> list[dict[str, Any]]:
    records = selection["candidate_records"]
    by_id = {str(row["node_id"]): row for row in records}
    candidate_ids = {
        "critical_bottleneck": [str(row["node_id"]) for row in records if row["is_bottleneck"]],
        "unique_evidence": [
            str(row["node_id"])
            for row in records
            if not row["is_bottleneck"] and not row["is_redundant"]
        ],
        "redundancy_group_samples": sorted(
            {
                str(row["redundancy_group_id"])
                for row in records
                if row["redundancy_group_id"]
            }
        ),
        "fallback": [str(row["node_id"]) for row in records],
    }
    cumulative: list[str] = []
    report = []
    for layer in POLICY_LAYERS:
        selected = list(selection["layer_records"].get(layer, []))
        cumulative.extend(selected)
        layer_coverage = (
            impact_coverage_metrics(graph, selected)["impact_coverage_at_k"]
            if selected
            else 0.0
        )
        cumulative_coverage = (
            impact_coverage_metrics(graph, cumulative)["impact_coverage_at_k"]
            if cumulative
            else 0.0
        )
        report.append(
            {
                "layer": layer,
                "candidate_count": len(candidate_ids[layer]),
                "selected_count": len(selected),
                "budget_share": len(selected) / budget if budget else 0.0,
                "layer_coverage": float(layer_coverage),
                "cumulative_coverage": float(cumulative_coverage),
                "selected_node_ids": selected,
            }
        )
    del by_id
    return report


def _method_rows(
    report: Mapping[str, Any],
    *,
    seed: int,
    condition_name: str,
    condition_value: float,
) -> list[dict[str, Any]]:
    return [
        {
            "seed": seed,
            condition_name: condition_value,
            "method": method,
            "impact_coverage": float(metrics["impact_coverage_at_k"]),
            "average_path_length": float(metrics["average_path_length"]),
            "protected_at_risk_coverage": float(
                metrics["protected_at_risk_coverage_at_k"]
            ),
            "protected_at_risk_record_count": int(
                metrics["protected_at_risk_record_count"]
            ),
            "sink_drop_mass": float(metrics["sink_drop_mass_at_k"]),
            "bottleneck_precision": float(metrics["bottleneck_precision_at_k"]),
            "bottleneck_recall": float(metrics["bottleneck_recall_at_k"]),
            "redundancy_waste": float(metrics["redundancy_waste_at_k"]),
            "budget_k": int(metrics["budget_k"]),
            "budget_used": int(metrics["budget_used"]),
            "selected_node_ids": list(metrics["selected_node_ids"]),
            "selection_changed_vs_lsf": bool(metrics["selection_changed_vs_lsf"]),
        }
        for method, metrics in report["methods"].items()
    ]


def _sweep_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    condition_name: str,
    seeds: Sequence[int],
    bootstrap_rounds: int,
    inference_condition: float | None = None,
    inference_baselines: Sequence[str] = (),
    holm_family: str | None = None,
) -> dict[str, Any]:
    conditional_methods = {"life_saving_clustered", "no_fallback"}
    informative_conditional = {
        method
        for method in conditional_methods
        if any(
            str(row["method"]) == method
            and bool(row.get("selection_changed_vs_lsf", False))
            for row in rows
        )
    }
    non_informative_methods = sorted(conditional_methods - informative_conditional)
    reporting_rows = [
        row
        for row in rows
        if str(row["method"]) not in conditional_methods
        or str(row["method"]) in informative_conditional
    ]
    grouped: dict[tuple[float, str], list[float]] = defaultdict(list)
    for row in reporting_rows:
        grouped[(float(row[condition_name]), str(row["method"]))].append(
            float(row["impact_coverage"])
        )
    summary = [
        {
            condition_name: condition,
            "method": method,
            "mean": float(mean(values)),
            "std": float(stdev(values)) if len(values) > 1 else 0.0,
            "mean_average_path_length": float(
                mean(
                    float(row["average_path_length"])
                    for row in reporting_rows
                    if float(row[condition_name]) == condition and str(row["method"]) == method
                )
            ),
            "mean_protected_at_risk_coverage": _condition_method_mean(
                reporting_rows, condition_name, condition, method, "protected_at_risk_coverage"
            ),
            "std_protected_at_risk_coverage": _condition_method_std(
                reporting_rows, condition_name, condition, method, "protected_at_risk_coverage"
            ),
            "mean_sink_drop_mass": _condition_method_mean(
                reporting_rows, condition_name, condition, method, "sink_drop_mass"
            ),
            "std_sink_drop_mass": _condition_method_std(
                reporting_rows, condition_name, condition, method, "sink_drop_mass"
            ),
            "mean_bottleneck_precision": _condition_method_mean(
                reporting_rows, condition_name, condition, method, "bottleneck_precision"
            ),
            "mean_bottleneck_recall": _condition_method_mean(
                reporting_rows, condition_name, condition, method, "bottleneck_recall"
            ),
            "mean_redundancy_waste": _condition_method_mean(
                reporting_rows, condition_name, condition, method, "redundancy_waste"
            ),
            "n": len(values),
        }
        for (condition, method), values in sorted(grouped.items())
    ]
    first_condition = min(float(row[condition_name]) for row in rows)
    first_means = {
        row["method"]: float(row["mean"])
        for row in summary
        if float(row[condition_name]) == first_condition
    }
    for row in summary:
        row["mean_change_from_first_condition"] = float(row["mean"] - first_means[row["method"]])
    statistics = []
    conditions = (
        [float(inference_condition)]
        if inference_condition is not None
        and any(float(row[condition_name]) == float(inference_condition) for row in rows)
        else []
    )
    for condition in conditions:
        primary_by_seed = {
            int(row["seed"]): float(row["impact_coverage"])
            for row in rows
            if float(row[condition_name]) == condition and row["method"] == "life_saving_first"
        }
        for method in inference_baselines:
            baseline_by_seed = {
                int(row["seed"]): float(row["impact_coverage"])
                for row in rows
                if float(row[condition_name]) == condition and row["method"] == method
            }
            paired_seeds = sorted(set(primary_by_seed).intersection(baseline_by_seed))
            result = paired_statistical_test(
                [primary_by_seed[seed] for seed in paired_seeds],
                [baseline_by_seed[seed] for seed in paired_seeds],
                seed=int(sum(seeds) + round(condition * 10000) + len(method)),
                bootstrap_rounds=bootstrap_rounds,
            )
            statistics.append(
                {
                    condition_name: condition,
                    "baseline": method,
                    "holm_family": holm_family,
                    **result,
                }
            )
    _apply_holm_correction(statistics)
    return {
        "rows": [dict(row) for row in rows],
        "summary": summary,
        "statistics": statistics,
        "non_informative_methods": non_informative_methods,
    }


def _condition_method_mean(
    rows: Sequence[Mapping[str, Any]],
    condition_name: str,
    condition: float,
    method: str,
    metric: str,
) -> float:
    return float(
        mean(
            float(row[metric])
            for row in rows
            if float(row[condition_name]) == condition and str(row["method"]) == method
        )
    )


def _condition_method_std(
    rows: Sequence[Mapping[str, Any]],
    condition_name: str,
    condition: float,
    method: str,
    metric: str,
) -> float:
    values = [
        float(row[metric])
        for row in rows
        if float(row[condition_name]) == condition and str(row["method"]) == method
    ]
    return float(stdev(values)) if len(values) > 1 else 0.0


def _apply_holm_correction(statistics: list[dict[str, Any]]) -> None:
    ordered = sorted(enumerate(statistics), key=lambda item: float(item[1]["p_value"]))
    running = 0.0
    total = len(ordered)
    for rank, (index, row) in enumerate(ordered):
        adjusted = min(1.0, (total - rank) * float(row["p_value"]))
        running = max(running, adjusted)
        statistics[index]["p_value_holm"] = float(running)


def apply_holm_correction(statistics: list[dict[str, Any]]) -> None:
    """Apply Holm correction in place to one explicitly declared family."""
    _apply_holm_correction(statistics)


def _matched_rank_biserial(differences: Sequence[float]) -> float:
    nonzero = [float(value) for value in differences if abs(float(value)) > 1e-15]
    if not nonzero:
        return 0.0
    ranks = rankdata([abs(value) for value in nonzero], method="average")
    positive = sum(float(rank) for rank, value in zip(ranks, nonzero, strict=True) if value > 0)
    negative = sum(float(rank) for rank, value in zip(ranks, nonzero, strict=True) if value < 0)
    total = positive + negative
    return float((positive - negative) / total) if total else 0.0


def _percentile_interval(values: Sequence[float], *, fallback: float) -> list[float]:
    if not values:
        return [float(fallback), float(fallback)]
    ordered = sorted(float(value) for value in values)
    lower_index = max(0, math.floor(0.025 * (len(ordered) - 1)))
    upper_index = min(len(ordered) - 1, math.ceil(0.975 * (len(ordered) - 1)))
    return [ordered[lower_index], ordered[upper_index]]


def _deterministic_graph_sample(
    graph: nx.DiGraph,
    scientist_ids: set[str],
    target_nodes: int,
) -> nx.DiGraph:
    if target_nodes <= 0 or target_nodes > graph.number_of_nodes():
        raise ValueError(
            f"requested efficiency size {target_nodes} exceeds available real graph nodes "
            f"({graph.number_of_nodes()})"
        )
    selected = set(sorted(set(graph).intersection(scientist_ids))[:target_nodes])
    queue = list(sorted(selected))
    cursor = 0
    while cursor < len(queue) and len(selected) < target_nodes:
        source = queue[cursor]
        cursor += 1
        neighbors = sorted(
            set(map(str, graph.successors(source)))
            | set(map(str, graph.predecessors(source)))
        )
        for neighbor in neighbors:
            if neighbor in selected:
                continue
            selected.add(neighbor)
            queue.append(neighbor)
            if len(selected) == target_nodes:
                break
    if len(selected) < target_nodes:
        selected.update(
            sorted(set(map(str, graph.nodes)) - selected)[: target_nodes - len(selected)]
        )
    return graph.subgraph(selected).copy()


def _measure_efficiency_once(
    graph: nx.DiGraph,
    scientist_ids: set[str],
    seed: int,
    motif_count: int | None,
    *,
    trace_memory: bool,
) -> dict[str, float]:
    if trace_memory:
        tracemalloc.start()
    total_start = time.perf_counter()
    start = total_start
    overlay = build_dag_overlay(graph, scientist_ids)
    dag_seconds = time.perf_counter() - start
    start = time.perf_counter()
    motif = add_controlled_audit_motifs(overlay, seed, motif_count=motif_count)
    motif_seconds = time.perf_counter() - start
    start = time.perf_counter()
    roles = extract_audit_roles(motif.graph)
    role_seconds = time.perf_counter() - start
    start = time.perf_counter()
    records = _node_records(motif.graph, roles)
    candidates = [record for record in records if _is_fair_candidate(record)]
    budget = max(1, math.ceil(0.25 * len(candidates))) if candidates else 0
    selection = _life_saving_selection(candidates, budget=budget, seed=seed, include_fallback=True)
    selection_seconds = time.perf_counter() - start
    start = time.perf_counter()
    life_saving_clustered_selection(
        candidates,
        budget=budget,
        seed=seed,
        include_fallback=True,
    )
    clustered_selection_seconds = time.perf_counter() - start
    start = time.perf_counter()
    impact_coverage_metrics(motif.graph, selection["selected_node_ids"])
    impact_seconds = time.perf_counter() - start
    total_seconds = time.perf_counter() - total_start
    peak_mb = 0.0
    if trace_memory:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak / (1024 * 1024)
    return {
        "dag_overlay_seconds": float(dag_seconds),
        "motif_seconds": float(motif_seconds),
        "role_extraction_seconds": float(role_seconds),
        "selection_seconds": float(selection_seconds),
        "clustered_selection_seconds": float(clustered_selection_seconds),
        "impact_coverage_seconds": float(impact_seconds),
        "total_seconds": float(total_seconds),
        "peak_python_mb": float(peak_mb),
    }


def _efficiency_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for size in sorted({int(row["target_nodes"]) for row in rows}):
        selected = [row for row in rows if int(row["target_nodes"]) == size]
        output.append(
            {
                "target_nodes": size,
                "actual_nodes": int(selected[0]["actual_nodes"]),
                "actual_edges": int(selected[0]["actual_edges"]),
                "mean_total_seconds": float(mean(row["total_seconds"] for row in selected)),
                "std_total_seconds": float(stdev(row["total_seconds"] for row in selected))
                if len(selected) > 1
                else 0.0,
                "mean_peak_python_mb": float(mean(row["peak_python_mb"] for row in selected)),
                "std_peak_python_mb": float(stdev(row["peak_python_mb"] for row in selected))
                if len(selected) > 1
                else 0.0,
            }
        )
    return output


def _log_log_slope(means: Mapping[int, float]) -> float | None:
    points = [(math.log(size), math.log(seconds)) for size, seconds in means.items() if seconds > 0]
    if len(points) < 2:
        return None
    x_mean = mean(point[0] for point in points)
    y_mean = mean(point[1] for point in points)
    denominator = sum((x - x_mean) ** 2 for x, _y in points)
    if denominator == 0.0:
        return None
    return float(sum((x - x_mean) * (y - y_mean) for x, y in points) / denominator)


def _tfidf_predictions(
    graph: nx.DiGraph,
    candidates: Sequence[str],
    bottleneck_truth: Sequence[bool],
) -> tuple[list[bool], list[bool]]:
    texts = [str(graph.nodes[node].get("label", node)) for node in candidates]
    similarity = TextSimilarity(method="tfidf").fit_corpus(texts).similarity_matrix(texts)
    semantic_degree = [float(sum(row) - 1.0) for row in similarity]
    top_count = sum(bool(value) for value in bottleneck_truth)
    top_indices = {
        index
        for index, _score in sorted(
            enumerate(semantic_degree), key=lambda item: (-item[1], candidates[item[0]])
        )[:top_count]
    }
    bottleneck = [index in top_indices for index in range(len(candidates))]
    redundancy = [
        any(index != other and similarity[index, other] > 0.85 for other in range(len(candidates)))
        for index in range(len(candidates))
    ]
    return bottleneck, redundancy


def _top_k_predictions(
    candidates: Sequence[str],
    scores: Mapping[str, float],
    count: int,
) -> list[bool]:
    selected = set(
        sorted(candidates, key=lambda node: (-float(scores.get(node, 0.0)), node))[
            :count
        ]
    )
    return [node in selected for node in candidates]


def _binary_metrics(truth: Sequence[bool], predicted: Sequence[bool]) -> dict[str, Any]:
    tp = sum(1 for actual, guess in zip(truth, predicted, strict=True) if actual and guess)
    fp = sum(1 for actual, guess in zip(truth, predicted, strict=True) if not actual and guess)
    fn = sum(1 for actual, guess in zip(truth, predicted, strict=True) if actual and not guess)
    tn = sum(1 for actual, guess in zip(truth, predicted, strict=True) if not actual and not guess)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "support": int(sum(truth)),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }
