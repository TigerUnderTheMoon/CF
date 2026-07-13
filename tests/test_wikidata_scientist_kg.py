from __future__ import annotations

import json
import math
import re
from pathlib import Path

import networkx as nx
import pytest

from fma.graph.wikidata_scientist_kg import (
    Triple,
    OCCUPATION_QIDS,
    build_clean_digraph,
    build_dag_overlay,
    extract_wikidata_triples,
    generate_scientist_seed_query,
    generate_sparql_query,
    graph_statistics,
    parse_sparql_response,
)


def _binding(subject: str, predicate: str, obj: str) -> dict[str, dict[str, str]]:
    return {
        "subject": {"type": "uri", "value": f"http://www.wikidata.org/entity/{subject}"},
        "predicate": {
            "type": "uri",
            "value": f"http://www.wikidata.org/prop/direct/{predicate}",
        },
        "object": {"type": "uri", "value": f"http://www.wikidata.org/entity/{obj}"},
    }


def test_sparql_query_contains_science_and_social_science_scope() -> None:
    query = generate_sparql_query(300)

    assert "SELECT DISTINCT ?subject ?predicate ?object" in query
    assert "wd:Q188094" in query  # economist
    assert "wd:Q2306091" in query  # sociologist
    assert "wd:Q1238570" in query  # political scientist
    assert "wd:Q212980" in query  # psychologist
    assert "wd:Q4773904" in query  # anthropologist
    assert '"1980-01-01T00:00:00Z"^^xsd:dateTime' in query
    assert "LIMIT 300" in query


def test_scientist_seed_query_uses_stable_per_occupation_quotas() -> None:
    query = generate_scientist_seed_query(300)

    assert "BIND(wd:Q169470 AS ?occupation)" in query
    assert "BIND(wd:Q188094 AS ?occupation)" in query
    assert "BIND(wd:Q2306091 AS ?occupation)" in query
    assert "BIND(wd:Q1238570 AS ?occupation)" in query
    assert "BIND(wd:Q212980 AS ?occupation)" in query
    assert "BIND(wd:Q4773904 AS ?occupation)" in query
    assert query.count("ORDER BY ?scientist") == 12
    assert query.count("LIMIT 28") == 3
    assert query.count("LIMIT 27") == 8
    assert query.rstrip().endswith("LIMIT 300")


def test_parse_sparql_response_keeps_only_wikidata_entity_triples() -> None:
    response = {
        "results": {
            "bindings": [
                {
                    "subject": {"type": "uri", "value": "http://www.wikidata.org/entity/Q1"},
                    "predicate": {
                        "type": "uri",
                        "value": "http://www.wikidata.org/prop/direct/P108",
                    },
                    "object": {"type": "uri", "value": "http://www.wikidata.org/entity/Q2"},
                },
                {
                    "subject": {"type": "uri", "value": "http://www.wikidata.org/entity/Q1"},
                    "predicate": {
                        "type": "uri",
                        "value": "http://www.wikidata.org/prop/direct/P569",
                    },
                    "object": {"type": "literal", "value": "1985-01-01"},
                },
            ]
        }
    }

    assert parse_sparql_response(response) == [Triple("Q1", "P108", "Q2")]


def test_clean_digraph_removes_self_loops_and_aggregates_predicates() -> None:
    triples = [
        Triple("Q1", "P108", "Q2"),
        Triple("Q1", "P108", "Q2"),
        Triple("Q1", "P463", "Q2"),
        Triple("Q2", "P31", "Q3"),
        Triple("Q3", "P279", "Q3"),
        Triple("Q9", "P31", "Q9"),
    ]

    graph = build_clean_digraph(triples)

    assert isinstance(graph, nx.DiGraph)
    assert set(graph.nodes) == {"Q1", "Q2", "Q3"}
    assert graph.number_of_edges() == 2
    assert graph["Q1"]["Q2"]["predicates"] == ("P108", "P463")
    assert graph.graph["unique_triple_count"] == 5
    assert graph.graph["self_loop_count_removed"] == 2


def test_dag_overlay_assigns_layer_3_from_layer_2_outgoing_neighbors() -> None:
    graph = build_clean_digraph(
        [
            Triple("Q1", "P108", "Q2"),
            Triple("Q1", "P101", "Q3"),
            Triple("Q2", "P17", "Q4"),
            Triple("Q3", "P279", "Q5"),
            Triple("Q4", "P30", "Q6"),
            Triple("Q5", "P279", "Q7"),
            Triple("Q6", "P31", "Q1"),  # back edge excluded from the overlay
            Triple("Q2", "P31", "Q3"),  # same-layer edge excluded
        ]
    )

    overlay = build_dag_overlay(graph, {"Q1"})

    assert overlay.layers == {
        0: {"Q1"},
        1: {"Q2", "Q3"},
        2: {"Q4", "Q5"},
        3: {"Q6", "Q7"},
    }
    assert set(overlay.graph.edges) == {
        ("Q1", "Q2"),
        ("Q1", "Q3"),
        ("Q2", "Q4"),
        ("Q3", "Q5"),
        ("Q4", "Q6"),
        ("Q5", "Q7"),
    }
    assert nx.is_directed_acyclic_graph(overlay.graph)
    assert all(overlay.graph.out_degree(node) == 0 for node in overlay.layers[3])


def test_graph_statistics_use_largest_weak_component_projection() -> None:
    graph = nx.DiGraph()
    graph.add_edges_from([("a", "b"), ("b", "c"), ("x", "y")])

    stats = graph_statistics(graph)

    assert stats["node_count"] == 5
    assert stats["edge_count"] == 3
    assert stats["weak_component_count"] == 2
    assert math.isclose(stats["average_degree"], 6 / 5)
    assert stats["diameter_lwcc_undirected"] == 2
    assert math.isclose(stats["average_shortest_path_lwcc_undirected"], 4 / 3)


def test_extraction_increases_limit_until_scale_gate_is_met(tmp_path: Path) -> None:
    responses = [
        {"results": {"bindings": [_binding("Q1", "P106", "Q169470")]}},
        {
            "results": {
                "bindings": [
                    _binding("Q1", "P106", "Q169470"),
                    _binding("Q1", "P108", "Q2"),
                    _binding("Q2", "P17", "Q3"),
                    _binding("Q3", "P30", "Q4"),
                ]
            }
        },
    ]
    calls: list[str] = []

    def fetch_json(_endpoint: str, query: str, _timeout: float) -> dict[str, object]:
        calls.append(query)
        return responses[len(calls) - 1]

    bundle = extract_wikidata_triples(
        {
            "endpoint": "https://query.wikidata.org/sparql",
            "scientist_limits": [1, 2],
            "min_nodes": 4,
            "max_nodes": 10,
            "min_edges": 3,
            "max_edges": 10,
            "cache_path": tmp_path / "wdqs.json",
            "timeout_seconds": 1,
        },
        fetch_json=fetch_json,
    )

    assert bundle.scientist_limit == 2
    assert bundle.scientist_ids == {"Q1"}
    assert bundle.source_mode == "live"
    assert bundle.graph.number_of_nodes() == 5
    assert bundle.graph.number_of_edges() == 4
    assert bundle.cache_sha256
    assert len(calls) == 2


def test_extraction_uses_hashed_cache_after_network_failure(tmp_path: Path) -> None:
    cache_path = tmp_path / "wdqs.json"
    cache_path.write_text(
        '{"query":"cached","scientist_limit":2,"payload":{"results":{"bindings":['
        '{"subject":{"type":"uri","value":"http://www.wikidata.org/entity/Q1"},'
        '"predicate":{"type":"uri","value":"http://www.wikidata.org/prop/direct/P106"},'
        '"object":{"type":"uri","value":"http://www.wikidata.org/entity/Q169470"}},'
        '{"subject":{"type":"uri","value":"http://www.wikidata.org/entity/Q1"},'
        '"predicate":{"type":"uri","value":"http://www.wikidata.org/prop/direct/P108"},'
        '"object":{"type":"uri","value":"http://www.wikidata.org/entity/Q2"}},'
        '{"subject":{"type":"uri","value":"http://www.wikidata.org/entity/Q2"},'
        '"predicate":{"type":"uri","value":"http://www.wikidata.org/prop/direct/P17"},'
        '"object":{"type":"uri","value":"http://www.wikidata.org/entity/Q3"}}]}}}',
        encoding="utf-8",
    )

    def fail_fetch(_endpoint: str, _query: str, _timeout: float) -> dict[str, object]:
        raise OSError("offline")

    bundle = extract_wikidata_triples(
        {
            "endpoint": "https://query.wikidata.org/sparql",
            "scientist_limits": [2],
            "min_nodes": 4,
            "max_nodes": 10,
            "min_edges": 3,
            "max_edges": 10,
            "cache_path": cache_path,
            "timeout_seconds": 1,
        },
        fetch_json=fail_fetch,
    )

    assert bundle.source_mode == "cached"
    assert bundle.query == "cached"
    assert bundle.cache_sha256


def test_extraction_deterministically_trims_graph_above_upper_bounds(tmp_path: Path) -> None:
    response = {
        "results": {
            "bindings": [
                _binding("Q1", "P106", "Q169470"),
                _binding("Q1", "P108", "Q2"),
                _binding("Q2", "P17", "Q3"),
                _binding("Q3", "P30", "Q4"),
                _binding("Q4", "P31", "Q5"),
                _binding("Q5", "P279", "Q6"),
            ]
        }
    }

    bundle = extract_wikidata_triples(
        {
            "endpoint": "https://query.wikidata.org/sparql",
            "scientist_limits": [1],
            "min_nodes": 4,
            "max_nodes": 5,
            "min_edges": 3,
            "max_edges": 4,
            "cache_path": tmp_path / "wdqs.json",
            "timeout_seconds": 1,
        },
        fetch_json=lambda *_args: response,
    )

    assert bundle.scientist_ids == {"Q1"}
    assert set(bundle.graph) == {"Q1", "Q169470", "Q2", "Q3", "Q4"}
    assert bundle.graph.number_of_edges() == 4


def test_staged_extraction_uses_seed_direct_and_context_queries(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch_json(_endpoint: str, query: str, _timeout: float) -> dict[str, object]:
        calls.append(query)
        if "SELECT DISTINCT ?scientist ?occupation" in query:
            return {
                "results": {
                    "bindings": [
                        {
                            "scientist": {
                                "type": "uri",
                                "value": "http://www.wikidata.org/entity/Q1",
                            },
                            "occupation": {
                                "type": "uri",
                                "value": "http://www.wikidata.org/entity/Q169470",
                            },
                        }
                    ]
                }
            }
        if "wdt:P108" in query and "VALUES ?subject" in query:
            return {"results": {"bindings": [_binding("Q1", "P108", "Q2")]}}
        if "wd:Q2" in query:
            return {"results": {"bindings": [_binding("Q2", "P17", "Q3")]}}
        if "wd:Q3" in query:
            return {"results": {"bindings": [_binding("Q3", "P30", "Q4")]}}
        raise AssertionError(f"unexpected staged query: {query}")

    bundle = extract_wikidata_triples(
        {
            "endpoint": "https://query.wikidata.org/sparql",
            "query_mode": "staged",
            "batch_size": 10,
            "scientist_limits": [1],
            "min_nodes": 4,
            "max_nodes": 10,
            "min_edges": 3,
            "max_edges": 10,
            "cache_path": tmp_path / "wdqs.json",
            "timeout_seconds": 1,
        },
        fetch_json=fetch_json,
    )

    assert bundle.source_mode == "live"
    assert bundle.scientist_ids == {"Q1"}
    assert set(bundle.graph.edges) == {("Q1", "Q2"), ("Q2", "Q3"), ("Q3", "Q4")}
    assert len(calls) == 4
    cached = (tmp_path / "wdqs.json").read_text(encoding="utf-8")
    assert "staged_query_log" in cached


def test_staged_extraction_fetches_occupation_quotas_independently(tmp_path: Path) -> None:
    seed_calls: list[str] = []
    scientist_by_occupation = {
        occupation: f"Q{1000 + index}"
        for index, occupation in enumerate(OCCUPATION_QIDS)
    }

    def fetch_json(_endpoint: str, query: str, _timeout: float) -> dict[str, object]:
        if "SELECT DISTINCT ?scientist ?occupation" in query:
            seed_calls.append(query)
            occupation = re.search(r"BIND\(wd:(Q\d+) AS \?occupation\)", query).group(1)
            scientist = scientist_by_occupation[occupation]
            return {
                "results": {
                    "bindings": [
                        {
                            "scientist": {
                                "type": "uri",
                                "value": f"http://www.wikidata.org/entity/{scientist}",
                            },
                            "occupation": {
                                "type": "uri",
                                "value": f"http://www.wikidata.org/entity/{occupation}",
                            },
                        }
                    ]
                }
            }
        if "wdt:P108" in query:
            bindings = []
            for index, (occupation, scientist) in enumerate(scientist_by_occupation.items()):
                bindings.extend(
                    [
                        _binding(scientist, "P106", occupation),
                        _binding(scientist, "P108", f"Q{2000 + index}"),
                    ]
                )
            return {"results": {"bindings": bindings}}
        if "wd:Q2000" in query:
            return {
                "results": {
                    "bindings": [
                        _binding(f"Q{2000 + index}", "P17", f"Q{3000 + index}")
                        for index in range(len(OCCUPATION_QIDS))
                    ]
                }
            }
        if "wd:Q3000" in query:
            return {
                "results": {
                    "bindings": [
                        _binding(f"Q{3000 + index}", "P30", f"Q{4000 + index}")
                        for index in range(len(OCCUPATION_QIDS))
                    ]
                }
            }
        raise AssertionError(f"unexpected staged query: {query}")

    bundle = extract_wikidata_triples(
        {
            "endpoint": "https://query.wikidata.org/sparql",
            "query_mode": "staged",
            "batch_size": 100,
            "scientist_limits": [11],
            "min_nodes": 50,
            "max_nodes": 100,
            "min_edges": 40,
            "max_edges": 100,
            "cache_path": tmp_path / "wdqs.json",
            "timeout_seconds": 1,
        },
        fetch_json=fetch_json,
    )

    assert len(seed_calls) == len(OCCUPATION_QIDS)
    assert all("UNION" not in query for query in seed_calls)
    assert bundle.scientist_ids == set(scientist_by_occupation.values())


def test_prefer_cache_replays_without_network_call(tmp_path: Path) -> None:
    cache_path = tmp_path / "wdqs.json"
    cache_path.write_text(
        json.dumps(
            {
                "query": "cached staged query",
                "scientist_limit": 1,
                "retrieved_at": "2026-01-01T00:00:00Z",
                "scientist_ids": ["Q1"],
                "trimmed_triples": [
                    {"subject": "Q1", "predicate": "P108", "object": "Q2"},
                    {"subject": "Q2", "predicate": "P17", "object": "Q3"},
                    {"subject": "Q3", "predicate": "P30", "object": "Q4"},
                ],
                "payload": {"results": {"bindings": []}},
            }
        ),
        encoding="utf-8",
    )

    calls = 0

    def unexpected_fetch(*_args):
        nonlocal calls
        calls += 1
        raise OSError("network must not be called when prefer_cache is enabled")

    bundle = extract_wikidata_triples(
        {
            "endpoint": "https://query.wikidata.org/sparql",
            "query_mode": "staged",
            "prefer_cache": True,
            "scientist_limits": [1],
            "min_nodes": 4,
            "max_nodes": 10,
            "min_edges": 3,
            "max_edges": 10,
            "cache_path": cache_path,
        },
        fetch_json=unexpected_fetch,
    )

    assert bundle.source_mode == "cached"
    assert bundle.scientist_ids == {"Q1"}

    with pytest.raises(ValueError, match="cache SHA-256 mismatch"):
        extract_wikidata_triples(
            {
                "endpoint": "https://query.wikidata.org/sparql",
                "query_mode": "staged",
                "prefer_cache": True,
                "scientist_limits": [1],
                "min_nodes": 4,
                "max_nodes": 10,
                "min_edges": 3,
                "max_edges": 10,
                "cache_path": cache_path,
                "timeout_seconds": 1,
                "expected_cache_sha256": "0" * 64,
            },
            fetch_json=lambda *_args: (_ for _ in ()).throw(AssertionError("network used")),
        )
    assert calls == 0
