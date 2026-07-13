"""Config-driven orchestration for the Wikidata scientist KG audit experiment."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import networkx as nx
import yaml

from fma.eval.wikidata_controlled_audit import (
    METHODS,
    MotifBundle,
    add_controlled_audit_motifs,
    evaluate_controlled_audit_roles,
    evaluate_impact_coverage,
    extract_audit_roles,
    run_anchor_cluster_confirmation,
    run_budget_sweep,
    run_efficiency_experiment,
    run_noise_sweep,
)
from fma.eval.wikidata_revision_cases import RevisionCase, fetch_verified_revision_cases
from fma.graph.wikidata_scientist_kg import (
    ExtractionBundle,
    Triple,
    build_dag_overlay,
    extract_wikidata_triples,
    fetch_sparql_json,
    graph_statistics,
)
from fma.visualization.wikidata_audit import (
    DISPLAY_NAMES,
    plot_core_structure,
    plot_anchor_cluster_confirmation,
    plot_efficiency,
    plot_impact_comparison,
    plot_overall_workflow,
    plot_sweep,
    plot_structural_sweep,
)


POSITIONING = (
    "This experiment validates the proposed audit representation under controlled "
    "knowledge-maintenance scenarios on a real KG substrate, rather than evaluating "
    "native Wikidata structural roles."
)
EVALUATION_STATEMENT = (
    "Evaluation is performed against controlled audit motifs rather than native "
    "Wikidata annotations."
)


def run_wikidata_scientist_audit(
    config: Mapping[str, Any],
    *,
    fetch_json: Callable[[str, str, float], dict[str, Any]] | None = None,
    revision_history_loader: Callable[[str], Sequence[Mapping[str, Any]]] | None = None,
    revision_entity_loader: Callable[[str, int], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the complete controlled audit experiment and write reproducible artifacts."""
    output_dir = Path(config.get("output_dir", "outputs/wikidata_scientist_kg_audit"))
    directories = {
        name: output_dir / name
        for name in ("configs", "logs", "data", "traces", "metrics", "cases", "figures")
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    normalized_config = _normalize(config)
    (directories["configs"] / "config.yaml").write_text(
        yaml.safe_dump(normalized_config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    start_time = datetime.now(timezone.utc).isoformat()
    git_commit = _git_commit()

    extraction_config = dict(config["extraction"])
    extraction_config["cache_path"] = Path(extraction_config["cache_path"])
    extraction = extract_wikidata_triples(
        extraction_config,
        fetch_json=fetch_json or fetch_sparql_json,
    )
    overlay = build_dag_overlay(extraction.graph, extraction.scientist_ids)
    graph_stats = {
        "raw_graph": graph_statistics(extraction.graph),
        "dag_overlay": graph_statistics(overlay.graph),
    }
    _write_extraction_artifacts(extraction, overlay.graph, directories["data"])

    experiment = config.get("experiment", {})
    seed = int(experiment.get("seed", 20260713))
    seeds = [int(value) for value in experiment.get("seeds", list(range(seed, seed + 30)))]
    audit_config = config.get("audit", {})
    motif_count_value = audit_config.get("motif_count")
    motif_count = int(motif_count_value) if motif_count_value is not None else None
    primary_budget = float(audit_config.get("primary_budget_fraction", 0.25))
    bootstrap_rounds = int(config.get("statistics", {}).get("bootstrap_rounds", 1000))
    substrate_provenance = _normalize(config.get("substrate_provenance", {}))

    primary_motif = add_controlled_audit_motifs(overlay, seed, motif_count=motif_count)
    graph_stats["controlled_audit_overlay"] = graph_statistics(primary_motif.graph)
    role_report = evaluate_controlled_audit_roles(primary_motif.graph, primary_motif.manifest)
    primary_impact = evaluate_impact_coverage(
        primary_motif.graph,
        budget_fraction=primary_budget,
        seed=seed,
    )
    _write_motif_manifest(primary_motif, directories["traces"] / "motif_manifest.json")

    budget_report = run_budget_sweep(
        overlay,
        seeds=seeds,
        budget_fractions=[float(value) for value in config["budget"]["fractions"]],
        motif_count=motif_count,
        bootstrap_rounds=bootstrap_rounds,
    )
    anchor_config = config.get("anchor_confirmation", {})
    anchor_confirmation = run_anchor_cluster_confirmation(
        extraction.graph,
        extraction.triples,
        extraction.scientist_ids,
        budget_fraction=float(anchor_config.get("budget_fraction", 0.05)),
        clusters_per_discipline=int(anchor_config.get("clusters_per_discipline", 4)),
        motif_seed=int(anchor_config.get("motif_seed", seed)),
        motif_count=motif_count,
        bootstrap_rounds=bootstrap_rounds,
        require_complete_clusters=bool(
            anchor_config.get("require_complete_clusters", True)
        ),
    )
    noise_rates = [float(value) for value in config["noise"]["rates"]]
    deletion_report = run_noise_sweep(
        overlay,
        seeds=seeds,
        rates=noise_rates,
        mode="deletion",
        budget_fraction=primary_budget,
        motif_count=motif_count,
        bootstrap_rounds=bootstrap_rounds,
    )
    insertion_report = run_noise_sweep(
        overlay,
        seeds=seeds,
        rates=noise_rates,
        mode="insertion",
        budget_fraction=primary_budget,
        motif_count=motif_count,
        bootstrap_rounds=bootstrap_rounds,
    )
    efficiency_config = config["efficiency"]
    efficiency_report = run_efficiency_experiment(
        extraction.graph,
        extraction.scientist_ids,
        sizes=[int(value) for value in efficiency_config["sizes"]],
        repeats=int(efficiency_config.get("repeats", 10)),
        warmups=int(efficiency_config.get("warmups", 1)),
        seed=seed,
        motif_count=motif_count,
    )

    case_error = None
    try:
        revision_cases = fetch_verified_revision_cases(
            sorted(extraction.scientist_ids),
            fetch_history=revision_history_loader,
            fetch_revision=revision_entity_loader,
            max_entities=int(config.get("case_studies", {}).get("max_entities", 100)),
        )
    except Exception as exc:
        revision_cases = []
        case_error = f"{type(exc).__name__}: {exc}"
    case_studies = _build_case_studies(
        revision_cases, primary_motif, primary_impact, primary_budget
    )

    countries_path = Path(config["countries_report_path"])
    countries_report = json.loads(countries_path.read_text(encoding="utf-8"))
    summary_rows = _summary_rows(
        graph_stats["raw_graph"],
        budget_report,
        countries_report,
        primary_budget,
    )
    report = {
        "experiment": str(experiment.get("name", "wikidata_scientist_kg_audit")),
        "positioning": POSITIONING,
        "controlled_role_statement": EVALUATION_STATEMENT,
        "evidence_level": "controlled_knowledge_maintenance_on_real_kg_substrate",
        "validated_production_workflow": False,
        "human_subjects": False,
        "causal_identification": False,
        "source": {
            "mode": extraction.source_mode,
            "endpoint": str(extraction_config["endpoint"]),
            "retrieved_at": extraction.retrieved_at,
            "scientist_limit": extraction.scientist_limit,
            "cache_path": str(extraction.cache_path),
            "cache_sha256": extraction.cache_sha256,
            "query": extraction.query,
            "substrate_provenance": substrate_provenance,
        },
        "git_commit": git_commit,
        "seed": seed,
        "seeds": seeds,
        "graph_statistics": graph_stats,
        "controlled_audit_roles": role_report,
        "impact_coverage": {
            "primary_budget_fraction": primary_budget,
            "primary_seed_detail": primary_impact,
            "summary": [
                row
                for row in budget_report["summary"]
                if float(row["budget_fraction"]) == primary_budget
            ],
        },
        "case_studies": case_studies,
        "case_study_error": case_error,
        "anchor_cluster_confirmation": anchor_confirmation,
        "summary_rows": summary_rows,
        "claim_boundary": {
            "supports": [
                "controlled audit motif evaluation on a Wikidata substrate",
                "fixed-budget Impact Coverage comparisons",
                "controlled edge-noise and budget sensitivity",
            ],
            "does_not_support": [
                "native Wikidata structural-role labels",
                "deployed knowledge-base effectiveness",
                "human curator usefulness",
                "causal identification",
            ],
        },
    }

    _write_json(directories["metrics"] / "graph_statistics.json", graph_stats)
    _write_json(directories["metrics"] / "controlled_audit_roles.json", role_report)
    _write_json(directories["metrics"] / "impact_coverage.json", report["impact_coverage"])
    _write_json(directories["metrics"] / "noise_deletion.json", deletion_report)
    _write_json(directories["metrics"] / "noise_insertion.json", insertion_report)
    _write_json(directories["metrics"] / "budget_sensitivity.json", budget_report)
    _write_json(directories["metrics"] / "efficiency.json", efficiency_report)
    _write_json(
        directories["metrics"] / "anchor_cluster_confirmation.json",
        anchor_confirmation,
    )
    _write_csv(
        directories["metrics"] / "anchor_cluster_confirmation_summary.csv",
        anchor_confirmation["summary"],
    )
    _write_json(
        directories["cases"] / "revision_cases.json",
        {"cases": case_studies, "error": case_error},
    )
    _write_csv(directories["metrics"] / "noise_deletion_summary.csv", deletion_report["summary"])
    _write_csv(directories["metrics"] / "noise_insertion_summary.csv", insertion_report["summary"])
    _write_csv(directories["metrics"] / "budget_sensitivity_summary.csv", budget_report["summary"])
    _write_csv(directories["metrics"] / "efficiency_summary.csv", efficiency_report["summary"])
    _write_json(output_dir / "summary.json", {"rows": summary_rows})
    _write_csv(output_dir / "summary.csv", summary_rows)
    (output_dir / "report.md").write_text(_render_report(report), encoding="utf-8")

    plot_overall_workflow(directories["figures"] / "overall_workflow.png")
    plot_core_structure(primary_motif, directories["figures"] / "core_structure.png")
    plot_impact_comparison(
        countries_report,
        budget_report["summary"],
        budget_fraction=primary_budget,
        path=directories["figures"] / "impact_coverage_comparison.png",
    )
    plot_sweep(
        deletion_report["summary"],
        condition_name="noise_rate",
        title="Edge Deletion Robustness",
        x_label="Deleted edges (%)",
        path=directories["figures"] / "noise_deletion.png",
    )
    plot_sweep(
        insertion_report["summary"],
        condition_name="noise_rate",
        title="Erroneous Edge Insertion Robustness",
        x_label="Inserted edges (%)",
        path=directories["figures"] / "noise_insertion.png",
    )
    plot_sweep(
        budget_report["summary"],
        condition_name="budget_fraction",
        title="Budget Sensitivity",
        x_label="Audit budget K (%)",
        path=directories["figures"] / "budget_sensitivity.png",
    )
    plot_efficiency(efficiency_report["summary"], directories["figures"] / "efficiency_scaling.png")
    plot_anchor_cluster_confirmation(
        anchor_confirmation["summary"],
        directories["figures"] / "anchor_cluster_confirmation.png",
    )
    plot_structural_sweep(
        budget_report["summary"],
        condition_name="budget_fraction",
        title="Budget Sensitivity: Structural Protection",
        x_label="Audit budget K (%)",
        path=directories["figures"] / "budget_structural_protection.png",
    )
    plot_structural_sweep(
        deletion_report["summary"],
        condition_name="noise_rate",
        title="Edge Deletion: Structural Protection",
        x_label="Deleted edges (%)",
        path=directories["figures"] / "noise_deletion_structural_protection.png",
    )
    plot_structural_sweep(
        insertion_report["summary"],
        condition_name="noise_rate",
        title="Erroneous Edge Insertion: Structural Protection",
        x_label="Inserted edges (%)",
        path=directories["figures"] / "noise_insertion_structural_protection.png",
    )
    finish_time = datetime.now(timezone.utc).isoformat()
    (directories["logs"] / "run.log").write_text(
        "\n".join(
            [
                f"start_utc={start_time}",
                f"finish_utc={finish_time}",
                f"git_commit={git_commit}",
                f"seed={seed}",
                f"source_mode={extraction.source_mode}",
                f"cache_sha256={extraction.cache_sha256}",
                "substrate_version="
                f"{substrate_provenance.get('version', 'unspecified')}",
                "substrate_same_as_v1="
                f"{substrate_provenance.get('same_as_v1', 'unspecified')}",
                "substrate_supersedes_cache_sha256="
                f"{substrate_provenance.get('supersedes_cache_sha256', 'none')}",
                "substrate_correction_reason="
                f"{substrate_provenance.get('correction_reason', 'none')}",
                f"node_count={extraction.graph.number_of_nodes()}",
                f"edge_count={extraction.graph.number_of_edges()}",
                f"revision_case_count={len(case_studies)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def _write_extraction_artifacts(
    extraction: ExtractionBundle,
    overlay: nx.DiGraph,
    output_dir: Path,
) -> None:
    with (output_dir / "triples.jsonl").open("w", encoding="utf-8") as handle:
        for triple in extraction.triples:
            handle.write(json.dumps(asdict(triple), sort_keys=True) + "\n")
    _write_csv(output_dir / "triples.csv", [asdict(triple) for triple in extraction.triples])
    nx.write_graphml(_graphml_copy(extraction.graph), output_dir / "raw_graph.graphml")
    nx.write_graphml(_graphml_copy(overlay), output_dir / "audit_overlay.graphml")


def _write_motif_manifest(bundle: MotifBundle, path: Path) -> None:
    _write_json(
        path,
        {
            "bottleneck_nodes": sorted(bundle.manifest.bottleneck_nodes),
            "redundant_nodes": sorted(bundle.manifest.redundant_nodes),
            "control_nodes": sorted(bundle.manifest.control_nodes),
            "terminal_nodes": sorted(bundle.manifest.terminal_nodes),
            "redundancy_groups": bundle.manifest.redundancy_groups,
            "anchor_by_candidate": bundle.manifest.anchor_by_candidate,
        },
    )


def _build_case_studies(
    cases: Sequence[RevisionCase],
    motif: MotifBundle,
    impact_report: Mapping[str, Any],
    budget_fraction: float,
) -> list[dict[str, Any]]:
    del impact_report
    rows = []
    for case in cases:
        scenario = _build_revision_case_scenario(case, motif.graph, budget_fraction)
        rows.append(
            {
                **asdict(case),
                **scenario,
                "fixed_budget_fraction": budget_fraction,
                "why_prioritized": (
                    "The controlled bottleneck is the sole maintenance path to its downstream "
                    "records. Under the one-of-four audit budget, Life-Saving First protects "
                    "three uniquely at-risk records; Flat Top-K selects a higher raw-impact "
                    "record whose four terminals remain reachable through independent bypasses."
                ),
                "scope_note": (
                    "The revision event is real; the bottleneck prioritization is evaluated in "
                    "the controlled maintenance overlay and is not a historical Wikidata decision."
                ),
            }
        )
    return rows


def _build_revision_case_scenario(
    case: RevisionCase,
    substrate: nx.DiGraph,
    budget_fraction: float,
) -> dict[str, Any]:
    graph = nx.DiGraph()
    direct_neighbors = (
        sorted(map(str, substrate.successors(case.entity_id)))
        if case.entity_id in substrate
        else []
    )
    preferred = [value for value in case.new_values if value in direct_neighbors]
    anchor = (
        preferred[0]
        if preferred
        else (
            direct_neighbors[0]
            if direct_neighbors
            else f"case:{case.entity_id}:anchor"
        )
    )
    graph.add_node(case.entity_id, layer=0)
    graph.add_node(anchor, layer=1)
    graph.add_edge(case.entity_id, anchor, predicates=(case.property_id,))

    bottleneck = f"case:{case.entity_id}:bottleneck"
    graph.add_node(bottleneck, layer=2)
    graph.add_edge(anchor, bottleneck, predicates=("AUDIT_DEPENDS_ON",))
    bottleneck_terminals = []
    for terminal_index in range(3):
        terminal = f"case:{case.entity_id}:critical:{terminal_index}"
        graph.add_node(terminal, layer=3)
        graph.add_edge(bottleneck, terminal, predicates=("AUDIT_IMPACTS",))
        bottleneck_terminals.append(terminal)

    controls = []
    for control_index in range(3):
        control = f"case:{case.entity_id}:control:{control_index}"
        graph.add_node(control, layer=2)
        graph.add_edge(anchor, control, predicates=("AUDIT_DEPENDS_ON",))
        controls.append(control)
        for terminal_index in range(4):
            terminal = f"case:{case.entity_id}:control:{control_index}:terminal:{terminal_index}"
            bypass = f"case:{case.entity_id}:control:{control_index}:bypass:{terminal_index}"
            graph.add_node(terminal, layer=3)
            graph.add_node(bypass, layer=2)
            graph.add_edge(control, terminal, predicates=("AUDIT_SUPPORTS",))
            graph.add_edge(anchor, bypass, predicates=("AUDIT_DEPENDS_ON",))
            graph.add_edge(bypass, terminal, predicates=("AUDIT_SUPPORTS",))

    roles = extract_audit_roles(graph)
    primary_candidates = [bottleneck, *controls]
    budget_k = max(1, math.ceil(len(primary_candidates) * budget_fraction))
    life_order = sorted(
        primary_candidates,
        key=lambda node: (
            not bool(roles[node]["is_bottleneck"]),
            -int(roles[node]["downstream_impact_count"]),
            node,
        ),
    )
    flat_order = sorted(
        primary_candidates,
        key=lambda node: (-int(roles[node]["downstream_impact_count"]), node),
    )
    life_selected = set(life_order[:budget_k])
    flat_selected = set(flat_order[:budget_k])
    terminals = {node for node, data in graph.nodes(data=True) if int(data.get("layer", 0)) == 3}

    def terminal_coverage(selected: set[str]) -> float:
        covered = {
            target
            for node in selected
            for target in nx.descendants(graph, node)
            if target in terminals
        }
        return len(covered) / len(terminals) if terminals else 0.0

    return {
        "controlled_anchor_node": anchor,
        "controlled_bottleneck_node": bottleneck,
        "candidate_record_count": len(primary_candidates),
        "fixed_budget_k": budget_k,
        "downstream_record_count": len(bottleneck_terminals),
        "downstream_record_ids": bottleneck_terminals,
        "baseline": "Flat Top-K",
        "raw_risk_definition": "downstream_impact_count",
        "life_saving_first_selected": bottleneck in life_selected,
        "flat_top_k_selected": bottleneck in flat_selected,
        "life_saving_first_selected_node_ids": sorted(life_selected),
        "flat_top_k_selected_node_ids": sorted(flat_selected),
        "life_saving_first_terminal_reach_coverage": terminal_coverage(life_selected),
        "flat_top_k_terminal_reach_coverage": terminal_coverage(flat_selected),
        "life_saving_first_protected_at_risk_records": sum(
            int(roles[node]["sink_drop_count"]) for node in life_selected
        ),
        "flat_top_k_protected_at_risk_records": sum(
            int(roles[node]["sink_drop_count"]) for node in flat_selected
        ),
    }


def _summary_rows(
    graph_stats: Mapping[str, Any],
    budget_report: Mapping[str, Any],
    countries_report: Mapping[str, Any],
    primary_budget: float,
) -> list[dict[str, Any]]:
    statistics = {
        str(row["baseline"]): row
        for row in budget_report["statistics"]
        if float(row["budget_fraction"]) == primary_budget
    }
    wiki_rows = []
    for row in budget_report["summary"]:
        if float(row["budget_fraction"]) != primary_budget:
            continue
        stat = statistics.get(str(row["method"]), {})
        wiki_rows.append(
            {
                "dataset": "Wikidata scientist KG",
                "nodes": graph_stats["node_count"],
                "edges": graph_stats["edge_count"],
                "weak_components": graph_stats["weak_component_count"],
                "diameter": graph_stats["diameter_lwcc_undirected"],
                "graph_average_path_length": graph_stats[
                    "average_shortest_path_lwcc_undirected"
                ],
                "method": DISPLAY_NAMES[str(row["method"])],
                "budget_fraction": primary_budget,
                "impact_coverage_mean": row["mean"],
                "impact_coverage_std": row["std"],
                "covered_path_length_mean": row["mean_average_path_length"],
                "p_value_holm_vs_lsf": stat.get("p_value_holm"),
                "cliffs_delta_lsf_minus_method": stat.get("cliffs_delta"),
            }
        )
    countries_keys = {
        "life_saving_first": "life_saving_first",
        "flat_top_k": "flat_top_k",
        "degree_centrality": "centrality",
        "random_stratified": "random_stratified",
        "position": "position",
        "random": "random",
        "no_fallback": "no_fallback_ablation",
    }
    countries_rows = []
    for method in METHODS:
        if method == "life_saving_clustered":
            continue
        metrics = countries_report["methods"][countries_keys[method]]
        countries_rows.append(
            {
                "dataset": "Countries-KG diagnostic fixture",
                "nodes": 30,
                "edges": 189,
                "weak_components": None,
                "diameter": None,
                "graph_average_path_length": None,
                "method": DISPLAY_NAMES[method],
                "budget_fraction": float(countries_report["budget_fraction"]),
                "impact_coverage_mean": metrics["impact_coverage_at_k"]["mean"],
                "impact_coverage_std": None,
                "covered_path_length_mean": metrics[
                    "average_path_length_to_covered_descendants"
                ]["mean"],
                "p_value_holm_vs_lsf": None,
                "cliffs_delta_lsf_minus_method": None,
            }
        )
    return countries_rows + wiki_rows


def _render_report(report: Mapping[str, Any]) -> str:
    graph = report["graph_statistics"]["raw_graph"]
    roles = report["controlled_audit_roles"]["structural"]
    provenance = report["source"].get("substrate_provenance", {})
    lines = [
        "# Wikidata Scientist KG Controlled Knowledge-Maintenance Experiment",
        "",
        report["positioning"],
        "",
        (
            f"Substrate: {provenance.get('version', 'unspecified')}; "
            f"same as V1={provenance.get('same_as_v1', 'unspecified')}. "
            f"Correction: {provenance.get('correction_reason', 'not recorded')}."
        ),
        "",
        "## Controlled Audit Role Evaluation",
        "",
        report["controlled_role_statement"],
        "",
        f"- Bottleneck F1: {roles['bottleneck']['f1']:.3f}",
        f"- Redundancy F1: {roles['redundancy']['f1']:.3f}",
        f"- Macro F1: {roles['macro_f1']:.3f}",
        "",
        "## Graph Statistics",
        "",
        "| Nodes | Edges | Average degree | Weak components | Diameter | Average path length |",
        "|---:|---:|---:|---:|---:|---:|",
        (
            f"| {graph['node_count']} | {graph['edge_count']} | {graph['average_degree']:.3f} | "
            f"{graph['weak_component_count']} | {graph['diameter_lwcc_undirected']} | "
            f"{graph['average_shortest_path_lwcc_undirected']:.3f} |"
        ),
        "",
        "## Impact Coverage@K Summary",
        "",
        "| Dataset | Method | K | Impact Coverage | Mean covered-path length |",
        "|---|---|---:|---:|---:|",
    ]
    for row in report["summary_rows"]:
        coverage = _format_optional(row["impact_coverage_mean"])
        path_length = _format_optional(row["covered_path_length_mean"])
        lines.append(
            f"| {row['dataset']} | {row['method']} | {float(row['budget_fraction']):.0%} | "
            f"{coverage} | {path_length} |"
        )
    anchor = report["anchor_cluster_confirmation"]
    lines.extend(
        [
            "",
            "## Anchor-Cluster Confirmation",
            "",
            (
                f"The predeclared K={float(anchor['budget_fraction']):.0%} confirmation uses "
                f"{len(anchor['units'])} anchor clusters from one Wikidata substrate as "
                "paired statistical units; they are not independent knowledge graphs."
            ),
            "",
            "| Method | Impact Coverage mean | SD | Units |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in anchor["summary"]:
        lines.append(
            f"| {DISPLAY_NAMES[str(row['method'])]} | {float(row['mean']):.4f} | "
            f"{float(row['std']):.4f} | {int(row['n'])} |"
        )
    lines.extend(
        [
            "",
            "## Revision-History Case Studies",
            "",
        ]
    )
    if report["case_studies"]:
        for case in report["case_studies"]:
            lines.extend(
                [
                    f"### {case['case_type']}: {case['entity_id']} / {case['property_id']}",
                    "",
                    f"- Revision: {case['permalink']}",
                    f"- Old values: {', '.join(case['old_values']) or '(none)'}",
                    f"- New values: {', '.join(case['new_values']) or '(none)'}",
                    f"- Why prioritized: {case['why_prioritized']}",
                    (
                        "- Selection comparison: Life-Saving First="
                        f"{case['life_saving_first_selected']}, "
                        f"Flat Top-K={case['flat_top_k_selected']}."
                    ),
                    f"- Boundary: {case['scope_note']}",
                    "",
                ]
            )
    else:
        lines.append(
            "No verified cases were available. Error: "
            f"{report['case_study_error'] or 'none'}"
        )
    lines.extend(
        [
            "## Evidence Boundary",
            "",
            "This is a controlled knowledge-maintenance experiment on a real KG substrate. "
            "It does not establish deployed effectiveness, human curator usefulness, native "
            "Wikidata role annotations, or causal identification.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_normalize(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [dict(row) for row in rows]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_normalize(rows))


def _graphml_copy(graph: nx.DiGraph) -> nx.DiGraph:
    copy = nx.DiGraph()
    for node, data in graph.nodes(data=True):
        copy.add_node(node, **{key: _graphml_value(value) for key, value in data.items()})
    for source, target, data in graph.edges(data=True):
        copy.add_edge(
            source,
            target,
            **{key: _graphml_value(value) for key, value in data.items()},
        )
    copy.graph.update({key: _graphml_value(value) for key, value in graph.graph.items()})
    return copy


def _graphml_value(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (tuple, list, set, frozenset)):
        return "|".join(map(str, value))
    return json.dumps(value, sort_keys=True)


def _normalize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_normalize(item) for item in value]
    return value


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _format_optional(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.3f}"
