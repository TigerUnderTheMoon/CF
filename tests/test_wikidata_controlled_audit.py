from __future__ import annotations

import networkx as nx
import pytest

from fma.eval.wikidata_controlled_audit import (
    add_controlled_audit_motifs,
    evaluate_controlled_audit_roles,
    evaluate_impact_coverage,
    extract_audit_roles,
    impact_coverage_metrics,
    life_saving_clustered_selection,
    paired_statistical_test,
    perturb_overlay_edges,
    run_anchor_cluster_confirmation,
    run_budget_sweep,
    run_noise_sweep,
)
from fma.graph.wikidata_scientist_kg import Triple, build_clean_digraph, build_dag_overlay


def _base_overlay():
    triples = []
    for index in range(4):
        scientist = f"Q{index + 1}"
        institution = f"Q{100 + index}"
        context = f"Q{200 + index}"
        terminal = f"Q{300 + index}"
        triples.extend(
            [
                Triple(scientist, "P108", institution),
                Triple(institution, "P17", context),
                Triple(context, "P30", terminal),
            ]
        )
    graph = build_clean_digraph(triples)
    return build_dag_overlay(graph, {"Q1", "Q2", "Q3", "Q4"})


def test_controlled_motifs_have_expected_roles_and_degree_matched_controls() -> None:
    bundle = add_controlled_audit_motifs(_base_overlay(), seed=17, motif_count=2)
    manifest = bundle.manifest

    assert len(manifest.bottleneck_nodes) == 2
    assert len(manifest.redundant_nodes) == 4
    assert len(manifest.control_nodes) == 2
    assert len(manifest.redundancy_groups) == 2
    assert nx.is_directed_acyclic_graph(bundle.graph)
    assert all(bundle.graph.nodes[node]["layer"] == 2 for node in manifest.candidate_nodes)
    assert all(bundle.graph.out_degree(node) == 3 for node in manifest.candidate_nodes)
    assert all(bundle.graph.in_degree(node) == 1 for node in manifest.candidate_nodes)


def test_structural_extractor_identifies_controlled_roles_without_manifest() -> None:
    bundle = add_controlled_audit_motifs(_base_overlay(), seed=23, motif_count=2)

    roles = extract_audit_roles(bundle.graph)

    predicted_bottlenecks = {
        node
        for node in bundle.manifest.bottleneck_nodes
        if roles[node]["is_bottleneck"]
    }
    assert predicted_bottlenecks == set(bundle.manifest.bottleneck_nodes)
    assert {node for node in bundle.manifest.redundant_nodes if roles[node]["is_redundant"]} == set(
        bundle.manifest.redundant_nodes
    )
    assert not any(roles[node]["is_bottleneck"] for node in bundle.manifest.control_nodes)
    assert not any(roles[node]["is_redundant"] for node in bundle.manifest.control_nodes)


def test_role_extraction_is_invariant_to_controlled_node_prefixes() -> None:
    bundle = add_controlled_audit_motifs(_base_overlay(), seed=31, motif_count=1)
    mapping = {node: f"renamed-{index}" for index, node in enumerate(sorted(bundle.graph))}
    renamed = nx.relabel_nodes(bundle.graph, mapping, copy=True)

    original_roles = extract_audit_roles(bundle.graph)
    renamed_roles = extract_audit_roles(renamed)

    for original, replacement in mapping.items():
        assert (
            original_roles[original]["is_bottleneck"]
            == renamed_roles[replacement]["is_bottleneck"]
        )
        assert (
            original_roles[original]["is_redundant"]
            == renamed_roles[replacement]["is_redundant"]
        )


def test_controlled_audit_role_evaluation_reports_metrics_and_baselines() -> None:
    bundle = add_controlled_audit_motifs(_base_overlay(), seed=41, motif_count=2)

    report = evaluate_controlled_audit_roles(bundle.graph, bundle.manifest)

    assert report["title"] == "Controlled Audit Role Evaluation"
    assert report["evaluation_target"] == "controlled_audit_motifs_not_native_wikidata_annotations"
    assert report["structural"]["bottleneck"]["f1"] == 1.0
    assert report["structural"]["redundancy"]["f1"] == 1.0
    assert report["structural"]["macro_f1"] == 1.0
    assert set(report["baselines"]) == {"tfidf", "betweenness", "out_closeness"}
    assert report["support"] == {"bottleneck": 2, "redundancy": 4, "controlled_candidates": 8}


def test_impact_coverage_uses_shared_budget_and_reports_policy_layers() -> None:
    bundle = add_controlled_audit_motifs(_base_overlay(), seed=43, motif_count=2)

    report = evaluate_impact_coverage(bundle.graph, budget_fraction=0.25, seed=43)

    assert set(report["methods"]) == {
        "life_saving_first",
        "life_saving_clustered",
        "flat_top_k",
        "degree_centrality",
        "random_stratified",
        "position",
        "random",
        "no_fallback",
    }
    budgets = {row["budget_k"] for row in report["methods"].values()}
    assert len(budgets) == 1
    assert 0.0 <= report["methods"]["life_saving_first"]["impact_coverage_at_k"] <= 1.0
    assert report["methods"]["life_saving_first"]["average_path_length"] >= 0.0
    assert [row["layer"] for row in report["life_saving_first_layers"]] == [
        "critical_bottleneck",
        "unique_evidence",
        "redundancy_group_samples",
        "fallback",
    ]
    assert all(
        "candidate_count" in row and "cumulative_coverage" in row
        for row in report["life_saving_first_layers"]
    )
    structural_metrics = report["methods"]["life_saving_first"]
    assert 0.0 <= structural_metrics["protected_at_risk_coverage_at_k"] <= 1.0
    assert structural_metrics["protected_at_risk_record_count"] >= 0
    assert 0.0 <= structural_metrics["sink_drop_mass_at_k"] <= 1.0
    assert 0.0 <= structural_metrics["bottleneck_precision_at_k"] <= 1.0
    assert 0.0 <= structural_metrics["bottleneck_recall_at_k"] <= 1.0
    assert 0.0 <= structural_metrics["redundancy_waste_at_k"] <= 1.0


def test_clean_reference_graph_prevents_erroneous_edge_coverage_inflation() -> None:
    clean = nx.DiGraph()
    clean.add_node("a", layer=1)
    clean.add_node("t1", layer=3)
    clean.add_node("t2", layer=3)
    clean.add_edge("a", "t1")
    noisy = clean.copy()
    noisy.add_edge("a", "t2", erroneous_edge=True)

    dirty_metrics = impact_coverage_metrics(noisy, ["a"])
    clean_metrics = impact_coverage_metrics(clean, ["a"])
    report = evaluate_impact_coverage(
        noisy,
        reference_graph=clean,
        budget_fraction=1.0,
        seed=11,
    )

    assert dirty_metrics["impact_coverage_at_k"] == 1.0
    assert clean_metrics["impact_coverage_at_k"] == 0.5
    assert report["evaluation_graph"] == "clean_reference"
    assert report["methods"]["flat_top_k"]["impact_coverage_at_k"] == 0.5
    assert report["methods"]["life_saving_first"]["protected_at_risk_record_count"] == 1


def test_clean_reference_graph_fixes_structural_protection_denominators() -> None:
    clean = nx.DiGraph()
    clean.add_nodes_from(
        [("a", {"layer": 1}), ("b", {"layer": 1}), ("t1", {"layer": 3}), ("t2", {"layer": 3})]
    )
    clean.add_edges_from([("a", "t1"), ("b", "t2")])
    noisy = clean.copy()
    noisy.remove_edge("b", "t2")

    report = evaluate_impact_coverage(
        noisy,
        reference_graph=clean,
        budget_fraction=1.0,
        seed=11,
    )
    metrics = report["methods"]["life_saving_first"]

    assert metrics["protected_at_risk_record_count"] == 1
    assert metrics["protected_at_risk_record_total"] == 2
    assert metrics["protected_at_risk_coverage_at_k"] == 0.5
    assert metrics["sink_drop_mass_selected"] == 1
    assert metrics["sink_drop_mass_total"] == 2
    assert metrics["sink_drop_mass_at_k"] == 0.5


def test_clean_reference_noise_can_use_an_absolute_fixed_budget() -> None:
    clean = nx.DiGraph()
    for index in range(10):
        source, terminal = f"s{index}", f"t{index}"
        clean.add_node(source, layer=1)
        clean.add_node(terminal, layer=3)
        clean.add_edge(source, terminal)
    noisy = clean.copy()
    noisy.remove_edges_from((f"s{index}", f"t{index}") for index in range(5, 10))

    report = evaluate_impact_coverage(
        noisy,
        reference_graph=clean,
        budget_fraction=0.5,
        fixed_budget_k=5,
        seed=11,
    )

    assert report["budget_source"] == "fixed_absolute"
    assert {row["budget_k"] for row in report["methods"].values()} == {5}


def test_life_saving_clustered_rotates_across_bottleneck_coverage_groups() -> None:
    candidates = [
        {
            "node_id": "a",
            "is_bottleneck": True,
            "is_redundant": True,
            "redundancy_group_id": "g1",
            "downstream_impact_count": 10,
            "raw_risk_score": 1.0,
            "degree": 5,
        },
        {
            "node_id": "b",
            "is_bottleneck": True,
            "is_redundant": True,
            "redundancy_group_id": "g1",
            "downstream_impact_count": 9,
            "raw_risk_score": 0.9,
            "degree": 4,
        },
        {
            "node_id": "c",
            "is_bottleneck": True,
            "is_redundant": False,
            "redundancy_group_id": None,
            "downstream_impact_count": 8,
            "raw_risk_score": 0.8,
            "degree": 3,
        },
    ]

    selection = life_saving_clustered_selection(candidates, budget=2, seed=3)

    assert selection["selected_node_ids"] == ["a", "c"]
    assert selection["critical_cluster_count"] == 2

    permuted = life_saving_clustered_selection(
        list(reversed(candidates)), budget=2, seed=99
    )
    assert permuted["selected_node_ids"] == ["a", "c"]
    assert life_saving_clustered_selection([], budget=0, seed=3)["selected_node_ids"] == []
    assert life_saving_clustered_selection(candidates, budget=0, seed=3)[
        "selected_node_ids"
    ] == []
    duplicate = life_saving_clustered_selection(
        [candidates[0], dict(candidates[0]), candidates[2]],
        budget=5,
        seed=3,
    )
    assert duplicate["selected_node_ids"] == ["a", "c"]
    with pytest.raises(ValueError, match="budget must be non-negative"):
        life_saving_clustered_selection(candidates, budget=-1, seed=3)


def test_edge_perturbations_preserve_controlled_edges_and_dag_order() -> None:
    bundle = add_controlled_audit_motifs(_base_overlay(), seed=47, motif_count=1)
    controlled_edges = {
        (source, target)
        for source, target, data in bundle.graph.edges(data=True)
        if data.get("controlled_motif")
    }
    non_controlled_count = bundle.graph.number_of_edges() - len(controlled_edges)

    deleted, deletion = perturb_overlay_edges(bundle.graph, rate=0.25, mode="deletion", seed=47)
    inserted, insertion = perturb_overlay_edges(bundle.graph, rate=0.25, mode="insertion", seed=47)

    assert deletion["changed_edge_count"] == round(non_controlled_count * 0.25)
    assert controlled_edges <= set(deleted.edges)
    assert insertion["changed_edge_count"] == round(non_controlled_count * 0.25)
    assert nx.is_directed_acyclic_graph(inserted)
    for source, target, data in inserted.edges(data=True):
        if data.get("erroneous_edge"):
            assert inserted.nodes[source]["layer"] < inserted.nodes[target]["layer"]


def test_paired_statistics_handle_all_zero_differences() -> None:
    result = paired_statistical_test([0.5, 0.5, 0.5], [0.5, 0.5, 0.5], seed=3, bootstrap_rounds=50)

    assert result["p_value"] == 1.0
    assert result["cliffs_delta"] == 0.0
    assert result["degenerate"] is True
    assert result["effect_ci95"] == [0.0, 0.0]


def test_budget_and_noise_sweeps_emit_paired_seed_records() -> None:
    overlay = _base_overlay()

    budget = run_budget_sweep(
        overlay,
        seeds=[5, 7],
        budget_fractions=[0.10, 0.25],
        motif_count=1,
        bootstrap_rounds=20,
    )
    noise = run_noise_sweep(
        overlay,
        seeds=[5, 7],
        rates=[0.0, 0.20],
        mode="deletion",
        budget_fraction=0.25,
        motif_count=1,
        bootstrap_rounds=20,
    )

    assert len(budget["rows"]) == 2 * 2 * 8
    assert len(noise["rows"]) == 2 * 2 * 8
    assert {row["seed"] for row in budget["rows"]} == {5, 7}
    assert {row["budget_fraction"] for row in budget["rows"]} == {0.10, 0.25}
    assert {row["noise_rate"] for row in noise["rows"]} == {0.0, 0.20}
    assert all(row["noise_mode"] == "deletion" for row in noise["rows"])
    assert noise["evaluation_graph"] == "clean_reference"
    assert noise["budget_source"] == "clean_reference_candidate_count"
    assert all("protected_at_risk_coverage" in row for row in noise["rows"])
    for seed in {5, 7}:
        assert len({row["budget_k"] for row in noise["rows"] if row["seed"] == seed}) == 1
    assert budget["statistics"]
    assert noise["statistics"]
    assert noise["degradation_statistics"]
    assert {row["metric"] for row in noise["degradation_statistics"]} == {
        "impact_coverage",
        "protected_at_risk_coverage",
        "sink_drop_mass",
    }
    assert all("mean_average_path_length" in row for row in budget["summary"])
    assert all("std_protected_at_risk_coverage" in row for row in budget["summary"])
    assert all("std_sink_drop_mass" in row for row in noise["summary"])
    assert all("mean_change_from_first_condition" in row for row in noise["summary"])


def test_anchor_cluster_confirmation_uses_discipline_units_at_five_percent() -> None:
    occupations = {
        "Q1": ("Q169470", "Q188094"),
        "Q2": ("Q188094",),
        "Q3": ("Q82594",),
        "Q4": ("Q864503",),
    }
    triples = []
    for index, (scientist, scientist_occupations) in enumerate(occupations.items()):
        institution = f"Q{100 + index}"
        context = f"Q{200 + index}"
        terminal = f"Q{300 + index}"
        triples.extend(
            [Triple(scientist, "P106", occupation) for occupation in scientist_occupations]
        )
        triples.extend(
            [
                Triple(scientist, "P108", institution),
                Triple(institution, "P17", context),
                Triple(context, "P30", terminal),
            ]
        )
    graph = build_clean_digraph(triples)

    report = run_anchor_cluster_confirmation(
        graph,
        triples,
        set(occupations),
        budget_fraction=0.05,
        clusters_per_discipline=2,
        motif_seed=29,
        motif_count=1,
        bootstrap_rounds=20,
        require_complete_clusters=False,
    )

    assert report["statistical_unit"] == "anchor_cluster"
    assert report["budget_fraction"] == 0.05
    assert report["discipline_assignments"]["Q1"] == "physical_sciences"
    assert report["discipline_assignments"]["Q2"] == "social_sciences"
    assert {unit["discipline"] for unit in report["units"]} == {
        "physical_sciences",
        "life_sciences",
        "computing",
        "social_sciences",
    }
    assert len(report["rows"]) == len(report["units"]) * 4
    assert {row["method"] for row in report["rows"]} == {
        "life_saving_first",
        "life_saving_clustered",
        "flat_top_k",
        "degree_centrality",
    }
    assert all(row["budget_fraction"] == 0.05 for row in report["rows"])
    assert all(unit["motif_seed"] == 29 for unit in report["units"])
    assert all(row["n"] == len(report["units"]) for row in report["summary"])
    assert report["statistics"]
    assert all("p_value_holm" in row for row in report["statistics"])


def test_anchor_cluster_confirmation_requires_all_discipline_clusters() -> None:
    triples = [
        Triple("Q1", "P106", "Q169470"),
        Triple("Q1", "P108", "Q100"),
        Triple("Q100", "P17", "Q200"),
        Triple("Q200", "P30", "Q300"),
    ]

    with pytest.raises(ValueError, match="missing required anchor clusters"):
        run_anchor_cluster_confirmation(
            build_clean_digraph(triples),
            triples,
            {"Q1"},
            clusters_per_discipline=1,
            motif_count=1,
            bootstrap_rounds=20,
        )
