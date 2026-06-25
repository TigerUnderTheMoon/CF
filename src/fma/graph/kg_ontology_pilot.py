"""Knowledge Graph ontology-aware edge construction pilot using the Countries KG.

Countries KG: Bordes et al., "Translating Embeddings for Modeling Multi-relational
Data", NeurIPS 2013

This module embeds a real KG structure (Countries KG, ~30 entities, ~200 triples)
with relation types ``locatedIn`` and ``neighborOf``, generates 30 synthetic
reasoning traces over KG queries using the existing fixture schema, and compares
TF-IDF-only baseline reflection graphs against KG-augmented graphs that map KG
relations to functional edge types accepted by ``ReflectionGraph``.

The pilot is labelled ``evidence_level: "pilot"`` and explicitly marks
``validated_kbs_workflow: False``.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from fma.eval.diagnostics.correlation_metrics import spearman, top_k_overlap
from fma.eval.structural_attribution import compute_node_necessity
from fma.graph.build_reflection_graph import build_reflection_graphs, node_id_for
from fma.graph.reflection_graph import ReflectionGraph, ReflectionNode

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "kbs_ontology_edge_pilot"
DEFAULT_OUTPUT_JSON = DEFAULT_OUTPUT_DIR / "kg_pilot_report.json"

# ============================================================
# Countries KG – Bordes et al., NeurIPS 2013
# ============================================================

_KG_LOCATED_IN: dict[str, str] = {
    "brazil": "americas",
    "uk": "europe",
    "usa": "americas",
    "france": "europe",
    "germany": "europe",
    "italy": "europe",
    "russia": "europe",
    "japan": "asia",
    "china": "asia",
    "india": "asia",
    "canada": "americas",
    "australia": "asia",
    "mexico": "americas",
    "spain": "europe",
    "portugal": "europe",
    "argentina": "americas",
    "south_africa": "africa",
    "egypt": "africa",
    "nigeria": "africa",
    "kenya": "africa",
    "south_korea": "asia",
    "indonesia": "asia",
    "turkey": "middle_east",
    "saudi_arabia": "middle_east",
    "iran": "middle_east",
}

_KG_NEIGHBOR_PAIRS: list[tuple[str, str]] = [
    ("argentina", "brazil"),
    ("argentina", "mexico"),
    ("argentina", "spain"),
    ("argentina", "uk"),
    ("australia", "brazil"),
    ("australia", "india"),
    ("australia", "indonesia"),
    ("australia", "japan"),
    ("australia", "south_africa"),
    ("australia", "uk"),
    ("australia", "usa"),
    ("brazil", "france"),
    ("brazil", "india"),
    ("brazil", "nigeria"),
    ("brazil", "portugal"),
    ("brazil", "south_africa"),
    ("brazil", "usa"),
    ("canada", "france"),
    ("canada", "uk"),
    ("canada", "usa"),
    ("china", "germany"),
    ("china", "india"),
    ("china", "indonesia"),
    ("china", "iran"),
    ("china", "japan"),
    ("china", "russia"),
    ("china", "saudi_arabia"),
    ("china", "south_korea"),
    ("egypt", "france"),
    ("egypt", "italy"),
    ("egypt", "kenya"),
    ("egypt", "nigeria"),
    ("egypt", "saudi_arabia"),
    ("egypt", "turkey"),
    ("egypt", "uk"),
    ("france", "germany"),
    ("france", "italy"),
    ("france", "mexico"),
    ("france", "south_africa"),
    ("france", "spain"),
    ("france", "uk"),
    ("germany", "italy"),
    ("germany", "japan"),
    ("germany", "russia"),
    ("germany", "south_korea"),
    ("germany", "turkey"),
    ("germany", "usa"),
    ("india", "indonesia"),
    ("india", "iran"),
    ("india", "kenya"),
    ("india", "nigeria"),
    ("india", "russia"),
    ("india", "south_africa"),
    ("india", "uk"),
    ("india", "usa"),
    ("indonesia", "japan"),
    ("iran", "russia"),
    ("iran", "saudi_arabia"),
    ("iran", "turkey"),
    ("italy", "spain"),
    ("italy", "turkey"),
    ("italy", "uk"),
    ("japan", "russia"),
    ("japan", "south_korea"),
    ("japan", "uk"),
    ("japan", "usa"),
    ("kenya", "nigeria"),
    ("kenya", "south_africa"),
    ("kenya", "uk"),
    ("mexico", "spain"),
    ("mexico", "usa"),
    ("nigeria", "south_africa"),
    ("nigeria", "turkey"),
    ("nigeria", "uk"),
    ("portugal", "spain"),
    ("portugal", "uk"),
    ("russia", "saudi_arabia"),
    ("russia", "turkey"),
    ("russia", "uk"),
    ("saudi_arabia", "turkey"),
    ("saudi_arabia", "usa"),
    ("south_korea", "usa"),
]


def _build_countries_kg() -> dict[str, Any]:
    entities: dict[str, dict[str, str]] = {}
    for region in sorted(set(_KG_LOCATED_IN.values())):
        entities[region] = {"type": "region"}
    for country, region in _KG_LOCATED_IN.items():
        entities[country] = {"type": "country", "region": region}

    triples: list[tuple[str, str, str]] = []
    for country, region in _KG_LOCATED_IN.items():
        triples.append((country, "locatedIn", region))
    for a, b in _KG_NEIGHBOR_PAIRS:
        triples.append((a, "neighborOf", b))
        triples.append((b, "neighborOf", a))

    return {"entities": entities, "triples": triples}


COUNTRIES_KG: dict[str, Any] = _build_countries_kg()

_KG_NEIGHBOR_SET: dict[str, set[str]] = {}
for _a, _b in _KG_NEIGHBOR_PAIRS:
    _KG_NEIGHBOR_SET.setdefault(_a, set()).add(_b)
    _KG_NEIGHBOR_SET.setdefault(_b, set()).add(_a)

_KG_COUNTRIES_BY_REGION: dict[str, list[str]] = {}
for _c, _r in _KG_LOCATED_IN.items():
    _KG_COUNTRIES_BY_REGION.setdefault(_r, []).append(_c)
for _r in _KG_COUNTRIES_BY_REGION:
    _KG_COUNTRIES_BY_REGION[_r].sort()

# ============================================================
# Edge-type helpers (following ontology_edge_pilot pattern)
# ============================================================

OPERATION_EDGE_TYPES: dict[str, str] = {
    "verify": "verifies",
    "decompose": "decomposes",
    "correct": "corrects",
    "revise": "revises",
    "plan": "revises",
    "critique": "critiques",
    "retry": "retries",
    "summarize": "summarizes",
}

KG_RELATION_EDGE_MAP: dict[str, str] = {
    "same_region": "verifies",
    "neighbor_concept": "elaborates",
    "located_in_target": "decomposes",
    "contradicts_constraint": "corrects",
    "depends_on_concept": "elaborates",
    "same_constraint": "verifies",
    "same_concept": "revises",
}


def _string_field(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    return str(value).strip() if value is not None else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _taxonomy_label(step: dict[str, Any]) -> str:
    label = step.get("category") or step.get("reflection_type") or step.get("type") or "OTHER"
    return str(label).strip().upper().replace("-", "_") or "OTHER"


def _step_content(step: dict[str, Any]) -> str:
    return str(step.get("text") or step.get("content") or "").strip()


def _utility_score(step: dict[str, Any]) -> float:
    return float(step.get("utility_score", 0.0))


def _functional_edge_type(step: dict[str, Any], relation: str | None = None) -> str:
    if relation in KG_RELATION_EDGE_MAP:
        return KG_RELATION_EDGE_MAP[relation]
    operation = str(step.get("operation_type") or "").strip().lower()
    if operation in OPERATION_EDGE_TYPES:
        return OPERATION_EDGE_TYPES[operation]
    label = _taxonomy_label(step)
    if "ERROR" in label or "CORRECTION" in label:
        return "corrects"
    if "VERIFICATION" in label or "CONSTRAINT" in label:
        return "verifies"
    if "DECOMPOSITION" in label:
        return "decomposes"
    if "PLANNING" in label:
        return "revises"
    return "elaborates"


# ============================================================
# KG ontology relation detection
# ============================================================


def _kg_ontology_relation(
    left_step: dict[str, Any],
    right_step: dict[str, Any],
) -> str | None:
    """Detect KG-aware ontology relations between two reasoning steps.

    Extends the ``_ontology_relation()`` pattern from
    ``fma.graph.ontology_edge_pilot`` with KG-specific checks:
    same_region, neighbor_concept, located_in_target.
    """
    left_concept = _string_field(left_step, "concept_id")
    right_concept = _string_field(right_step, "concept_id")
    left_constraint = _string_field(left_step, "constraint_id")
    right_constraint = _string_field(right_step, "constraint_id")

    if right_step.get("contradicts_constraint_id") == left_constraint and left_constraint:
        return "contradicts_constraint"
    if left_concept in _string_list(right_step.get("depends_on_concept_ids")):
        return "depends_on_concept"
    if left_constraint and left_constraint == right_constraint:
        return "same_constraint"
    if left_concept and left_concept == right_concept:
        return "same_concept"

    left_region = _KG_LOCATED_IN.get(left_concept)
    right_region = _KG_LOCATED_IN.get(right_concept)
    if left_region and right_region and left_region == right_region:
        return "same_region"

    if left_concept and right_concept:
        neighbors = _KG_NEIGHBOR_SET.get(left_concept, set())
        if right_concept in neighbors:
            return "neighbor_concept"

    if right_constraint and left_region and left_region == right_constraint:
        return "located_in_target"

    return None


# ============================================================
# Synthetic trace generation
# ============================================================


def _generate_location_query_trace(
    region: str,
    countries: list[str],
    trace_id: str,
    rng: random.Random,
) -> dict[str, Any]:
    """Generate a trace for: "Which countries are located in Region X?" """
    selected = rng.sample(countries, min(3, len(countries)))
    steps: list[dict[str, Any]] = [
        {
            "category": "DECOMPOSITION",
            "text": f"Identify the set of countries located in {region}.",
            "concept_id": region,
            "constraint_id": region,
            "operation_type": "decompose",
            "utility_score": round(rng.uniform(0.15, 0.35), 2),
        },
    ]
    for i, country in enumerate(selected):
        steps.append({
            "category": "VERIFICATION",
            "text": f"Verify that {country} is located in {region}.",
            "concept_id": country,
            "constraint_id": region,
            "operation_type": "verify",
            "depends_on_concept_ids": [region],
            "utility_score": round(rng.uniform(0.50, 0.85), 2),
        })
    neighbors_of_last: list[str] = []
    for n in sorted(_KG_NEIGHBOR_SET.get(selected[-1], set())):
        if n in _KG_LOCATED_IN:
            neighbors_of_last.append(n)
            if len(neighbors_of_last) >= 2:
                break
    if neighbors_of_last:
        steps.append({
            "category": "VERIFICATION",
            "text": f"Check neighbor consistency for {selected[-1]}: {', '.join(neighbors_of_last)}.",
            "concept_id": neighbors_of_last[0],
            "constraint_id": region,
            "operation_type": "verify",
            "depends_on_concept_ids": [selected[-1]],
            "utility_score": round(rng.uniform(0.40, 0.70), 2),
        })
    steps.append({
        "category": "PLANNING",
        "text": f"Conclude: the countries located in {region} include {', '.join(selected)}.",
        "concept_id": region,
        "constraint_id": region,
        "operation_type": "revise",
        "depends_on_concept_ids": [s["concept_id"] for s in steps[:-1]],
        "utility_score": round(rng.uniform(0.60, 0.90), 2),
    })
    return {"trace_id": trace_id, "domain": f"kg_location_{region}", "reflection_chain": steps}


def _generate_neighbor_verification_trace(
    country_a: str,
    country_b: str,
    trace_id: str,
    rng: random.Random,
) -> dict[str, Any]:
    """Generate a trace for: "Is Country A a neighbor of Country B?" """
    region_a = _KG_LOCATED_IN.get(country_a, "unknown")
    region_b = _KG_LOCATED_IN.get(country_b, "unknown")
    are_neighbors = country_b in _KG_NEIGHBOR_SET.get(country_a, set())
    relation_str = "are" if are_neighbors else "are not"
    steps: list[dict[str, Any]] = [
        {
            "category": "VERIFICATION",
            "text": f"Check whether {country_a} and {country_b} {relation_str} neighbors.",
            "concept_id": country_a,
            "constraint_id": "neighborOf",
            "operation_type": "verify",
            "utility_score": round(rng.uniform(0.40, 0.70), 2),
        },
        {
            "category": "VERIFICATION",
            "text": f"Verify location consistency: {country_a} is in {region_a}, {country_b} is in {region_b}.",
            "concept_id": country_b,
            "constraint_id": "neighborOf",
            "operation_type": "verify",
            "depends_on_concept_ids": [country_a],
            "utility_score": round(rng.uniform(0.50, 0.85), 2),
        },
    ]
    if region_a != region_b:
        steps.append({
            "category": "DECOMPOSITION",
            "text": f"Cross-region neighbor pair: {country_a} ({region_a}) and {country_b} ({region_b}).",
            "concept_id": country_a,
            "constraint_id": "neighborOf",
            "operation_type": "decompose",
            "depends_on_concept_ids": [country_b],
            "utility_score": round(rng.uniform(0.30, 0.60), 2),
        })
    steps.append({
        "category": "PLANNING",
        "text": f"Conclude: {country_a} and {country_b} {relation_str} neighbors.",
        "concept_id": country_b,
        "constraint_id": "neighborOf",
        "operation_type": "revise",
        "depends_on_concept_ids": [country_a],
        "utility_score": round(rng.uniform(0.60, 0.90), 2),
    })
    return {"trace_id": trace_id, "domain": "kg_neighbor_verify", "reflection_chain": steps}


def _generate_region_connectivity_trace(
    country: str,
    trace_id: str,
    rng: random.Random,
) -> dict[str, Any]:
    """Generate a trace for: "What regions does Country connect to via neighbors?" """
    region = _KG_LOCATED_IN.get(country, "unknown")
    neighbors = sorted(_KG_NEIGHBOR_SET.get(country, set()) & set(_KG_LOCATED_IN.keys()))
    neighbor_regions: dict[str, list[str]] = {}
    for n in neighbors[:5]:
        nr = _KG_LOCATED_IN.get(n, "unknown")
        neighbor_regions.setdefault(nr, []).append(n)

    steps: list[dict[str, Any]] = [
        {
            "category": "DECOMPOSITION",
            "text": f"Identify {country} and its region {region}, then enumerate its neighbors.",
            "concept_id": country,
            "constraint_id": region,
            "operation_type": "decompose",
            "utility_score": round(rng.uniform(0.15, 0.35), 2),
        },
    ]
    for nr, nc_list in sorted(neighbor_regions.items()):
        representative = nc_list[0]
        steps.append({
            "category": "VERIFICATION",
            "text": f"Verify neighbor {representative} in {nr} connects {country} to {nr}.",
            "concept_id": representative,
            "constraint_id": nr,
            "operation_type": "verify",
            "depends_on_concept_ids": [country],
            "utility_score": round(rng.uniform(0.50, 0.85), 2),
        })
    if neighbor_regions:
        last_representative = list(neighbor_regions.values())[-1][0]
        steps.append({
            "category": "VERIFICATION",
            "text": f"Check region assignment consistency for neighbors of {country}.",
            "concept_id": last_representative,
            "constraint_id": region,
            "operation_type": "verify",
            "depends_on_concept_ids": [country, last_representative],
            "utility_score": round(rng.uniform(0.40, 0.70), 2),
        })
    steps.append({
        "category": "PLANNING",
        "text": f"Conclude: {country} connects to {', '.join(sorted(neighbor_regions.keys()))} via neighbors.",
        "concept_id": country,
        "constraint_id": region,
        "operation_type": "revise",
        "depends_on_concept_ids": [s["concept_id"] for s in steps[:-1]],
        "utility_score": round(rng.uniform(0.60, 0.90), 2),
    })
    return {"trace_id": trace_id, "domain": "kg_region_connectivity", "reflection_chain": steps}


def generate_kg_traces(
    kg: dict[str, Any] | None = None,
    num_traces: int = 30,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate deterministic synthetic reasoning traces over KG queries.

    Three query patterns are used in roughly equal proportion:
    - Location query: which countries are in a region
    - Neighbor verification: is country A a neighbor of country B
    - Region connectivity: what regions does a country connect to

    Each step carries ``concept_id``, ``constraint_id``, and
    ``depends_on_concept_ids`` referencing KG entities, enabling the
    KG-augmented ontology relation detector.
    """
    rng = random.Random(seed)
    traces: list[dict[str, Any]] = []
    regions = sorted(_KG_COUNTRIES_BY_REGION.keys())
    neighbor_pairs = list(_KG_NEIGHBOR_PAIRS)
    countries = sorted(_KG_LOCATED_IN.keys())

    num_per_pattern = num_traces // 3
    remainder = num_traces - 3 * num_per_pattern

    for i in range(num_per_pattern + (1 if remainder > 0 else 0)):
        region = rng.choice(regions)
        countries_in_region = _KG_COUNTRIES_BY_REGION[region]
        if not countries_in_region:
            continue
        traces.append(
            _generate_location_query_trace(
                region, countries_in_region, f"kg_loc_{i:03d}", rng
            )
        )

    for i in range(num_per_pattern + (1 if remainder > 1 else 0)):
        pair = rng.choice(neighbor_pairs)
        traces.append(
            _generate_neighbor_verification_trace(
                pair[0], pair[1], f"kg_nbr_{i:03d}", rng
            )
        )

    for i in range(num_per_pattern + (1 if remainder > 2 else 0)):
        country = rng.choice(countries)
        traces.append(
            _generate_region_connectivity_trace(
                country, f"kg_reg_{i:03d}", rng
            )
        )

    return traces[:num_traces]


# ============================================================
# KG-augmented graph construction
# ============================================================


def build_kg_augmented_graph(
    trace: dict[str, Any],
    index: int = 0,
) -> tuple[ReflectionGraph, list[dict[str, Any]]]:
    """Build a temporal graph augmented with KG ontology edges.

    Follows the same construction pattern as
    ``build_ontology_edge_graph`` in ``fma.graph.ontology_edge_pilot``
    but uses ``_kg_ontology_relation`` for KG-aware edge detection.
    """
    trace_id = _trace_id(trace, index)
    steps = _reflection_steps(trace)
    graph = ReflectionGraph(trace_id)
    node_ids: list[str] = []

    for step_index, step in enumerate(steps):
        node_id = node_id_for(trace_id, step_index)
        graph.add_node(
            ReflectionNode(
                node_id=node_id,
                trace_id=trace_id,
                step_index=step_index,
                taxonomy_label=_taxonomy_label(step),
                utility_score=_utility_score(step),
                structural_influence=0.0,
                content=_step_content(step),
            )
        )
        node_ids.append(node_id)

    for position in range(len(node_ids) - 1):
        graph.add_edge(
            node_ids[position],
            node_ids[position + 1],
            _functional_edge_type(steps[position + 1]),
            weight=1.0,
            quality=1.0,
        )

    kg_edges: list[dict[str, Any]] = []
    for left_index, left_step in enumerate(steps):
        for right_index in range(left_index + 1, len(steps)):
            right_step = steps[right_index]
            relation = _kg_ontology_relation(left_step, right_step)
            if relation is None:
                continue
            edge_type = _functional_edge_type(right_step, relation=relation)
            source = node_ids[left_index]
            target = node_ids[right_index]
            added = False
            if not graph.has_edge(source, target):
                graph.add_edge(source, target, edge_type, weight=0.9, quality=1.0)
                added = True
            kg_edges.append({
                "trace_id": trace_id,
                "source_step_idx": left_index,
                "target_step_idx": right_index,
                "source_concept_id": _string_field(left_step, "concept_id"),
                "target_concept_id": _string_field(right_step, "concept_id"),
                "constraint_id": _string_field(right_step, "constraint_id"),
                "ontology_relation": relation,
                "edge_type": edge_type,
                "added_to_graph": added,
            })

    if node_ids:
        graph.freeze_sources([node_ids[0]])
    return graph, kg_edges


# ============================================================
# Comparison and pilot logic
# ============================================================


def _compare_graph_sets(
    baseline_graphs: Sequence[ReflectionGraph],
    kg_graphs: Sequence[ReflectionGraph],
) -> dict[str, Any]:
    baseline_scores = _node_necessity_by_key(baseline_graphs)
    kg_scores = _node_necessity_by_key(kg_graphs)
    keys = sorted(set(baseline_scores) & set(kg_scores))
    baseline_values = [baseline_scores[key] for key in keys]
    kg_values = [kg_scores[key] for key in keys]
    deltas = [abs(kg_scores[key] - baseline_scores[key]) for key in keys]
    return {
        "matched_node_count": len(keys),
        "all_kg_graphs_are_dags": all(_is_dag(g) for g in kg_graphs),
        "all_baseline_graphs_are_dags": all(_is_dag(g) for g in baseline_graphs),
        "mean_abs_structural_necessity_delta": (
            float(sum(deltas) / len(deltas)) if deltas else 0.0
        ),
        "structural_necessity_spearman": spearman(baseline_values, kg_values),
        "bottleneck_top1_overlap": top_k_overlap(
            baseline_values, kg_values, 1, keys=keys
        ) if keys else 0.0,
    }


def _node_necessity_by_key(
    graphs: Sequence[ReflectionGraph],
) -> dict[tuple[str, int], float]:
    rows: dict[tuple[str, int], float] = {}
    for graph in graphs:
        for row in compute_node_necessity(graph):
            rows[(row.trace_id, row.step_idx)] = float(row.necessity_normalized)
    return rows


def _is_dag(graph: ReflectionGraph) -> bool:
    try:
        graph.topological_order()
    except ValueError:
        return False
    return True


def _trace_id(trace: dict[str, Any], index: int) -> str:
    return str(
        trace.get("trace_id")
        or trace.get("sample_id")
        or trace.get("task_id")
        or f"kg_trace_{index:05d}"
    )


def _reflection_steps(trace: dict[str, Any]) -> list[dict[str, Any]]:
    chain = trace.get("reflection_chain")
    if isinstance(chain, list):
        return [dict(step) for step in chain if isinstance(step, dict)]
    return []


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ============================================================
# Public pilot entry point
# ============================================================


def run_kg_pilot(
    *,
    num_traces: int = 30,
    seed: int = 42,
    output_json: str | Path | None = None,
) -> dict[str, Any]:
    """Run the Countries KG ontology-aware edge construction pilot.

    Returns the full report dict. When *output_json* is provided the
    report is also saved to disk.
    """
    traces = generate_kg_traces(num_traces=num_traces, seed=seed)

    baseline_graphs = build_reflection_graphs(
        traces,
        similarity_method="tfidf",
        similarity_threshold=0.15,
    )

    kg_graphs: list[ReflectionGraph] = []
    kg_edges: list[dict[str, Any]] = []
    for index, trace in enumerate(traces):
        graph, edges = build_kg_augmented_graph(trace, index=index)
        kg_graphs.append(graph)
        kg_edges.extend(edges)

    comparison = _compare_graph_sets(baseline_graphs, kg_graphs)

    report: dict[str, Any] = {
        "evidence_level": "pilot",
        "validated_kbs_workflow": False,
        "uses_real_ontology": True,
        "claim_boundary": (
            "Pilot-level KG ontology-aware edge construction using the Countries KG "
            "(Bordes et al., 2013) only; not a deployed KBS validation and not "
            "evidence for rule-engine, ontology-reasoner, KG-query, PRM-training, "
            "replay, or downstream-filtering claims."
        ),
        "kg_metadata": {
            "source": "Bordes et al., Translating Embeddings for Modeling Multi-relational Data, NeurIPS 2013",
            "num_entities": len(COUNTRIES_KG["entities"]),
            "num_triples": len(COUNTRIES_KG["triples"]),
            "relation_types": sorted(
                {t[1] for t in COUNTRIES_KG["triples"]}
            ),
            "entity_type_counts": dict(
                sorted(Counter(e["type"] for e in COUNTRIES_KG["entities"].values()).items())
            ),
        },
        "trace_generation": {
            "num_traces": len(traces),
            "seed": seed,
            "pattern_counts": dict(
                sorted(Counter(t["domain"].split("_", 1)[1] if "_" in t.get("domain", "") else "unknown" for t in traces).items())
            ),
        },
        "summary": {
            "num_traces": len(traces),
            "baseline_edge_count": sum(len(g.edges) for g in baseline_graphs),
            "kg_graph_edge_count": sum(len(g.edges) for g in kg_graphs),
            "kg_candidate_edge_count": len(kg_edges),
            "kg_added_edge_count": sum(1 for e in kg_edges if e["added_to_graph"]),
            "kg_relation_counts": dict(
                sorted(Counter(e["ontology_relation"] for e in kg_edges).items())
            ),
            "functional_edge_type_counts": dict(
                sorted(Counter(e["edge_type"] for e in kg_edges).items())
            ),
        },
        "comparison": comparison,
        "kg_edges_sample": kg_edges[:20],
    }

    out_path = Path(output_json) if output_json else DEFAULT_OUTPUT_JSON
    _write_json(out_path, report)
    return report


__all__ = [
    "COUNTRIES_KG",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_OUTPUT_JSON",
    "build_kg_augmented_graph",
    "generate_kg_traces",
    "run_kg_pilot",
]


if __name__ == "__main__":
    report = run_kg_pilot()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
