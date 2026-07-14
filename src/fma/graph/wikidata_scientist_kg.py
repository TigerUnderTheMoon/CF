"""Wikidata scientist subgraph extraction and directed overlay construction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import networkx as nx


WIKIDATA_ENTITY_PREFIX = "http://www.wikidata.org/entity/"
WIKIDATA_DIRECT_PROPERTY_PREFIX = "http://www.wikidata.org/prop/direct/"

OCCUPATION_QIDS = (
    "Q169470",  # physicist
    "Q593644",  # chemist
    "Q864503",  # biologist
    "Q170790",  # mathematician
    "Q82594",  # computer scientist
    "Q11063",  # astronomer
    "Q188094",  # economist
    "Q2306091",  # sociologist
    "Q1238570",  # political scientist
    "Q212980",  # psychologist
    "Q4773904",  # anthropologist
)

DIRECT_PREDICATES = frozenset({"P106", "P108", "P69", "P101", "P463", "P166", "P27"})
CONTEXT_PREDICATES = frozenset({"P17", "P31", "P279", "P361", "P749", "P30"})


@dataclass(frozen=True, order=True)
class Triple:
    subject: str
    predicate: str
    object: str


@dataclass(frozen=True)
class DagOverlay:
    graph: nx.DiGraph
    layers: dict[int, set[str]]


@dataclass(frozen=True)
class ExtractionBundle:
    triples: list[Triple]
    graph: nx.DiGraph
    scientist_ids: set[str]
    query: str
    scientist_limit: int
    source_mode: str
    retrieved_at: str
    cache_path: Path
    cache_sha256: str


def generate_sparql_query(scientist_limit: int) -> str:
    """Return the canonical one-to-three-hop scientist extraction query."""
    if scientist_limit <= 0:
        raise ValueError("scientist_limit must be positive")
    direct = " ".join(f"wdt:{pid}" for pid in sorted(DIRECT_PREDICATES))
    context = " ".join(f"wdt:{pid}" for pid in sorted(CONTEXT_PREDICATES))
    scientist_union = _stratified_scientist_union(scientist_limit)
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?subject ?predicate ?object WHERE {{
  {{
    SELECT DISTINCT ?scientist WHERE {{
{scientist_union}
    }}
    ORDER BY ?scientist
    LIMIT {scientist_limit}
  }}
  {{
    VALUES ?predicate {{ {direct} }}
    ?scientist ?predicate ?object .
    BIND(?scientist AS ?subject)
  }} UNION {{
    VALUES ?firstPredicate {{ {direct} }}
    VALUES ?predicate {{ {context} }}
    ?scientist ?firstPredicate ?subject .
    ?subject ?predicate ?object .
  }} UNION {{
    VALUES ?firstPredicate {{ {direct} }}
    VALUES ?secondPredicate {{ {context} }}
    VALUES ?predicate {{ {context} }}
    ?scientist ?firstPredicate ?middle .
    ?middle ?secondPredicate ?subject .
    ?subject ?predicate ?object .
  }}
  FILTER(STRSTARTS(STR(?subject), STR(wd:)))
  FILTER(STRSTARTS(STR(?object), STR(wd:)))
}}
"""


def generate_scientist_seed_query(scientist_limit: int) -> str:
    if scientist_limit <= 0:
        raise ValueError("scientist_limit must be positive")
    scientist_union = _stratified_scientist_union(scientist_limit)
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?scientist ?occupation WHERE {{
{scientist_union}
}}
ORDER BY ?scientist
LIMIT {scientist_limit}
"""


def generate_occupation_seed_query(occupation: str, scientist_limit: int) -> str:
    if occupation not in OCCUPATION_QIDS:
        raise ValueError(f"unsupported scientist occupation: {occupation}")
    if scientist_limit <= 0:
        raise ValueError("scientist_limit must be positive")
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?scientist ?occupation WHERE {{
  BIND(wd:{occupation} AS ?occupation)
  ?scientist wdt:P31 wd:Q5 ;
             wdt:P106 ?occupation ;
             wdt:P569 ?birthDate .
  FILTER(?birthDate >= "1980-01-01T00:00:00Z"^^xsd:dateTime)
}}
ORDER BY ?scientist
LIMIT {scientist_limit}
"""


def _stratified_scientist_union(scientist_limit: int) -> str:
    branches = []
    for occupation, quota in _occupation_quotas(scientist_limit):
        branches.append(
            f"""  {{
    SELECT ?scientist ?occupation WHERE {{
      BIND(wd:{occupation} AS ?occupation)
      ?scientist wdt:P31 wd:Q5 ;
                 wdt:P106 ?occupation ;
                 wdt:P569 ?birthDate .
      FILTER(?birthDate >= "1980-01-01T00:00:00Z"^^xsd:dateTime)
    }}
    ORDER BY ?scientist
    LIMIT {quota}
  }}"""
        )
    return " UNION\n".join(branches)


def _occupation_quotas(scientist_limit: int) -> list[tuple[str, int]]:
    base_quota, remainder = divmod(scientist_limit, len(OCCUPATION_QIDS))
    return [
        (occupation, base_quota + (1 if index < remainder else 0))
        for index, occupation in enumerate(OCCUPATION_QIDS)
        if base_quota + (1 if index < remainder else 0) > 0
    ]


def generate_entity_relation_query(entity_ids: Sequence[str], predicates: Sequence[str]) -> str:
    if not entity_ids:
        raise ValueError("entity_ids must not be empty")
    entities = " ".join(f"wd:{qid}" for qid in sorted(set(entity_ids)))
    predicate_values = " ".join(f"wdt:{pid}" for pid in sorted(set(predicates)))
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>

SELECT DISTINCT ?subject ?predicate ?object WHERE {{
  VALUES ?subject {{ {entities} }}
  VALUES ?predicate {{ {predicate_values} }}
  ?subject ?predicate ?object .
  FILTER(STRSTARTS(STR(?object), STR(wd:)))
}}
"""


def parse_sparql_response(payload: Mapping[str, Any]) -> list[Triple]:
    """Parse WDQS JSON bindings into sorted entity-only triples."""
    rows = payload.get("results", {}).get("bindings", [])
    triples: set[Triple] = set()
    for row in rows:
        subject = row.get("subject", {})
        predicate = row.get("predicate", {})
        obj = row.get("object", {})
        if (
            subject.get("type") != "uri"
            or predicate.get("type") != "uri"
            or obj.get("type") != "uri"
        ):
            continue
        subject_value = str(subject.get("value", ""))
        predicate_value = str(predicate.get("value", ""))
        object_value = str(obj.get("value", ""))
        if not subject_value.startswith(WIKIDATA_ENTITY_PREFIX):
            continue
        if not predicate_value.startswith(WIKIDATA_DIRECT_PROPERTY_PREFIX):
            continue
        if not object_value.startswith(WIKIDATA_ENTITY_PREFIX):
            continue
        triples.add(
            Triple(
                subject_value.removeprefix(WIKIDATA_ENTITY_PREFIX),
                predicate_value.removeprefix(WIKIDATA_DIRECT_PROPERTY_PREFIX),
                object_value.removeprefix(WIKIDATA_ENTITY_PREFIX),
            )
        )
    return sorted(triples)


def fetch_sparql_json(endpoint: str, query: str, timeout_seconds: float) -> dict[str, Any]:
    """Execute a WDQS POST request using only the Python standard library."""
    body = urlencode({"query": query, "format": "json"}).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "FMA-Wikidata-Scientist-Audit/1.0",
        },
        method="POST",
    )
    # S310: the endpoint is an explicit experiment configuration value.
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def extract_wikidata_triples(
    config: Mapping[str, Any],
    *,
    fetch_json: Any = fetch_sparql_json,
) -> ExtractionBundle:
    """Extract a scale-gated Wikidata subgraph, with cache-only failure fallback."""
    cache_path = Path(config["cache_path"])
    if bool(config.get("prefer_cache")) and cache_path.is_file():
        return _validate_expected_cache_hash(
            _load_cached_extraction(config, cache_path), config
        )
    if bool(config.get("offline")):
        raise FileNotFoundError(f"offline Wikidata cache is missing: {cache_path}")
    if str(config.get("query_mode", "canonical")) == "staged":
        return _validate_expected_cache_hash(
            _extract_wikidata_triples_staged(config, fetch_json=fetch_json), config
        )
    endpoint = str(config["endpoint"])
    limits = [int(value) for value in config.get("scientist_limits", [300, 350, 400, 450, 500])]
    timeout_seconds = float(config.get("timeout_seconds", 120.0))
    cache_path = Path(config["cache_path"])
    last_scale: tuple[int, int] | None = None
    last_error: Exception | None = None

    for scientist_limit in limits:
        query = generate_sparql_query(scientist_limit)
        try:
            payload = fetch_json(endpoint, query, timeout_seconds)
        except Exception as exc:  # network and endpoint failures share the cache fallback
            last_error = exc
            break
        bundle = _bundle_from_payload(
            payload=payload,
            query=query,
            scientist_limit=scientist_limit,
            source_mode="live",
            cache_path=cache_path,
        )
        if _scale_above_upper_bound(bundle.graph, config):
            bundle = _trim_bundle_to_upper_bounds(bundle, config)
        last_scale = (bundle.graph.number_of_nodes(), bundle.graph.number_of_edges())
        if _scale_in_bounds(bundle.graph, config):
            _write_extraction_cache(bundle, payload)
            return _validate_expected_cache_hash(_bundle_with_cache_hash(bundle), config)

    if last_error is not None and cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("trimmed_triples"):
            triples = [Triple(**row) for row in cached["trimmed_triples"]]
            bundle = _bundle_from_triples(
                triples=triples,
                query=str(cached["query"]),
                scientist_limit=int(cached["scientist_limit"]),
                source_mode="cached",
                cache_path=cache_path,
                retrieved_at=str(cached.get("retrieved_at", "")),
                scientist_ids=set(map(str, cached.get("scientist_ids", []))) or None,
            )
        else:
            bundle = _bundle_from_payload(
                payload=cached["payload"],
                query=str(cached["query"]),
                scientist_limit=int(cached["scientist_limit"]),
                source_mode="cached",
                cache_path=cache_path,
                retrieved_at=str(cached.get("retrieved_at", "")),
            )
        if not _scale_in_bounds(bundle.graph, config):
            raise ValueError("cached Wikidata graph does not satisfy the configured scale gate")
        return _validate_expected_cache_hash(_bundle_with_cache_hash(bundle), config)

    detail = f"; last scale={last_scale}" if last_scale else ""
    if last_error is not None:
        detail += f"; endpoint error={type(last_error).__name__}: {last_error}"
    raise ValueError(f"Wikidata extraction did not satisfy the configured scale gate{detail}")


def _load_cached_extraction(
    config: Mapping[str, Any],
    cache_path: Path,
) -> ExtractionBundle:
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    if cached.get("trimmed_triples"):
        bundle = _bundle_from_triples(
            triples=[Triple(**row) for row in cached["trimmed_triples"]],
            query=str(cached["query"]),
            scientist_limit=int(cached["scientist_limit"]),
            source_mode="cached",
            cache_path=cache_path,
            retrieved_at=str(cached.get("retrieved_at", "")),
            scientist_ids=set(map(str, cached.get("scientist_ids", []))) or None,
        )
    else:
        bundle = _bundle_from_payload(
            payload=cached["payload"],
            query=str(cached["query"]),
            scientist_limit=int(cached["scientist_limit"]),
            source_mode="cached",
            cache_path=cache_path,
            retrieved_at=str(cached.get("retrieved_at", "")),
        )
    if not _scale_in_bounds(bundle.graph, config):
        raise ValueError("cached Wikidata graph does not satisfy the configured scale gate")
    return _bundle_with_cache_hash(bundle)


def _extract_wikidata_triples_staged(
    config: Mapping[str, Any],
    *,
    fetch_json: Any,
) -> ExtractionBundle:
    endpoint = str(config["endpoint"])
    limits = [int(value) for value in config.get("scientist_limits", [300, 350, 400, 450, 500])]
    timeout_seconds = float(config.get("timeout_seconds", 120.0))
    batch_size = int(config.get("batch_size", 100))
    cache_path = Path(config["cache_path"])
    last_scale: tuple[int, int] | None = None
    last_error: Exception | None = None

    for scientist_limit in limits:
        query_log: list[str] = []
        try:
            scientist_ids: set[str] = set()
            for occupation, quota in _occupation_quotas(scientist_limit):
                seed_query = generate_occupation_seed_query(occupation, quota)
                query_log.append(seed_query)
                seed_payload = fetch_json(endpoint, seed_query, timeout_seconds)
                scientist_ids.update(_parse_scientist_ids(seed_payload))
            direct = _fetch_relation_batches(
                scientist_ids,
                DIRECT_PREDICATES,
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                batch_size=batch_size,
                fetch_json=fetch_json,
                query_log=query_log,
            )
            layer_1 = sorted({triple.object for triple in direct} - scientist_ids)
            second_hop = _fetch_relation_batches(
                layer_1,
                CONTEXT_PREDICATES,
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                batch_size=batch_size,
                fetch_json=fetch_json,
                query_log=query_log,
            )
            layer_2 = sorted(
                {triple.object for triple in second_hop} - scientist_ids - set(layer_1)
            )
            third_hop = _fetch_relation_batches(
                layer_2,
                CONTEXT_PREDICATES,
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                batch_size=batch_size,
                fetch_json=fetch_json,
                query_log=query_log,
            )
        except Exception as exc:
            last_error = exc
            break
        bundle = _bundle_from_triples(
            triples=sorted(set(direct) | set(second_hop) | set(third_hop)),
            query=generate_sparql_query(scientist_limit),
            scientist_limit=scientist_limit,
            source_mode="live",
            cache_path=cache_path,
            scientist_ids=scientist_ids,
        )
        if _scale_above_upper_bound(bundle.graph, config):
            bundle = _trim_bundle_to_upper_bounds(bundle, config)
        last_scale = (bundle.graph.number_of_nodes(), bundle.graph.number_of_edges())
        if _scale_in_bounds(bundle.graph, config):
            _write_extraction_cache(
                bundle,
                {"results": {"bindings": []}},
                staged_query_log=query_log,
            )
            return _bundle_with_cache_hash(bundle)

    if last_error is not None and cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        triples = [Triple(**row) for row in cached.get("trimmed_triples", [])]
        bundle = _bundle_from_triples(
            triples=triples,
            query=str(cached["query"]),
            scientist_limit=int(cached["scientist_limit"]),
            source_mode="cached",
            cache_path=cache_path,
            retrieved_at=str(cached.get("retrieved_at", "")),
            scientist_ids=set(map(str, cached.get("scientist_ids", []))) or None,
        )
        if not _scale_in_bounds(bundle.graph, config):
            raise ValueError("cached Wikidata graph does not satisfy the configured scale gate")
        return _bundle_with_cache_hash(bundle)
    detail = f"; last scale={last_scale}" if last_scale else ""
    if last_error is not None:
        detail += f"; endpoint error={type(last_error).__name__}: {last_error}"
    raise ValueError(
        f"staged Wikidata extraction did not satisfy the configured scale gate{detail}"
    )


def _parse_scientist_ids(payload: Mapping[str, Any]) -> set[str]:
    scientist_ids = set()
    for row in payload.get("results", {}).get("bindings", []):
        scientist = row.get("scientist", {})
        if scientist.get("type") != "uri":
            continue
        value = str(scientist.get("value", ""))
        if value.startswith(WIKIDATA_ENTITY_PREFIX):
            scientist_ids.add(value.removeprefix(WIKIDATA_ENTITY_PREFIX))
    return scientist_ids


def _fetch_relation_batches(
    entity_ids: Sequence[str] | set[str],
    predicates: Sequence[str] | frozenset[str],
    *,
    endpoint: str,
    timeout_seconds: float,
    batch_size: int,
    fetch_json: Any,
    query_log: list[str],
) -> list[Triple]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    entities = sorted(set(entity_ids))
    triples: set[Triple] = set()
    for start in range(0, len(entities), batch_size):
        query = generate_entity_relation_query(entities[start : start + batch_size], predicates)
        query_log.append(query)
        triples.update(parse_sparql_response(fetch_json(endpoint, query, timeout_seconds)))
    return sorted(triples)


def _bundle_from_payload(
    *,
    payload: Mapping[str, Any],
    query: str,
    scientist_limit: int,
    source_mode: str,
    cache_path: Path,
    retrieved_at: str | None = None,
) -> ExtractionBundle:
    triples = parse_sparql_response(payload)
    return _bundle_from_triples(
        triples=triples,
        query=query,
        scientist_limit=scientist_limit,
        source_mode=source_mode,
        cache_path=cache_path,
        retrieved_at=retrieved_at,
    )


def _bundle_from_triples(
    *,
    triples: list[Triple],
    query: str,
    scientist_limit: int,
    source_mode: str,
    cache_path: Path,
    retrieved_at: str | None = None,
    scientist_ids: set[str] | None = None,
) -> ExtractionBundle:
    graph = build_clean_digraph(triples)
    resolved_scientists = scientist_ids or {
        triple.subject
        for triple in triples
        if triple.predicate == "P106" and triple.object in OCCUPATION_QIDS
    }
    return ExtractionBundle(
        triples=triples,
        graph=graph,
        scientist_ids=resolved_scientists,
        query=query,
        scientist_limit=scientist_limit,
        source_mode=source_mode,
        retrieved_at=retrieved_at or datetime.now(timezone.utc).isoformat(),
        cache_path=cache_path,
        cache_sha256="",
    )


def _scale_in_bounds(graph: nx.DiGraph, config: Mapping[str, Any]) -> bool:
    nodes = graph.number_of_nodes()
    edges = graph.number_of_edges()
    return (
        int(config.get("min_nodes", 500)) <= nodes <= int(config.get("max_nodes", 2000))
        and int(config.get("min_edges", 3000)) <= edges <= int(config.get("max_edges", 10000))
    )


def _scale_above_upper_bound(graph: nx.DiGraph, config: Mapping[str, Any]) -> bool:
    return (
        graph.number_of_nodes() > int(config.get("max_nodes", 2000))
        or graph.number_of_edges() > int(config.get("max_edges", 10000))
    )


def _trim_bundle_to_upper_bounds(
    bundle: ExtractionBundle,
    config: Mapping[str, Any],
) -> ExtractionBundle:
    max_nodes = int(config.get("max_nodes", 2000))
    max_edges = int(config.get("max_edges", 10000))
    graph = bundle.graph
    selected: set[str] = set(sorted(bundle.scientist_ids)[:max_nodes])
    queue = list(sorted(selected))
    cursor = 0
    while cursor < len(queue) and len(selected) < max_nodes:
        source = queue[cursor]
        cursor += 1
        for target in sorted(map(str, graph.successors(source))):
            if target in selected:
                continue
            selected.add(target)
            queue.append(target)
            if len(selected) >= max_nodes:
                break
    if len(selected) < max_nodes:
        selected.update(sorted(set(map(str, graph.nodes)) - selected)[: max_nodes - len(selected)])

    triples_by_pair: dict[tuple[str, str], list[Triple]] = {}
    for triple in bundle.triples:
        if triple.subject in selected and triple.object in selected:
            triples_by_pair.setdefault((triple.subject, triple.object), []).append(triple)
    kept_pairs = sorted(triples_by_pair)[:max_edges]
    triples = sorted(triple for pair in kept_pairs for triple in triples_by_pair[pair])
    return _bundle_from_triples(
        triples=triples,
        query=bundle.query,
        scientist_limit=bundle.scientist_limit,
        source_mode=bundle.source_mode,
        cache_path=bundle.cache_path,
        retrieved_at=bundle.retrieved_at,
    )


def _write_extraction_cache(
    bundle: ExtractionBundle,
    payload: Mapping[str, Any],
    *,
    staged_query_log: Sequence[str] | None = None,
) -> None:
    bundle.cache_path.parent.mkdir(parents=True, exist_ok=True)
    bundle.cache_path.write_text(
        json.dumps(
            {
                "query": bundle.query,
                "scientist_limit": bundle.scientist_limit,
                "retrieved_at": bundle.retrieved_at,
                "payload": payload,
                "scientist_ids": sorted(bundle.scientist_ids),
                "staged_query_log": list(staged_query_log or []),
                "trimmed_triples": [
                    {"subject": row.subject, "predicate": row.predicate, "object": row.object}
                    for row in bundle.triples
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _bundle_with_cache_hash(bundle: ExtractionBundle) -> ExtractionBundle:
    digest = hashlib.sha256(bundle.cache_path.read_bytes()).hexdigest()
    return ExtractionBundle(
        triples=bundle.triples,
        graph=bundle.graph,
        scientist_ids=bundle.scientist_ids,
        query=bundle.query,
        scientist_limit=bundle.scientist_limit,
        source_mode=bundle.source_mode,
        retrieved_at=bundle.retrieved_at,
        cache_path=bundle.cache_path,
        cache_sha256=digest,
    )


def _validate_expected_cache_hash(
    bundle: ExtractionBundle,
    config: Mapping[str, Any],
) -> ExtractionBundle:
    expected = str(config.get("expected_cache_sha256", "")).lower()
    if expected and bundle.cache_sha256.lower() != expected:
        raise ValueError(
            "cache SHA-256 mismatch: "
            f"expected {expected}, observed {bundle.cache_sha256.lower()}"
        )
    return bundle


def build_clean_digraph(triples: Sequence[Triple]) -> nx.DiGraph:
    """Build a simple DiGraph while retaining all predicates per ordered pair."""
    unique_triples = set(triples)
    self_loops = {triple for triple in unique_triples if triple.subject == triple.object}
    predicates_by_pair: dict[tuple[str, str], set[str]] = {}
    for triple in unique_triples - self_loops:
        predicates_by_pair.setdefault((triple.subject, triple.object), set()).add(triple.predicate)

    graph = nx.DiGraph()
    for (subject, obj), predicates in sorted(predicates_by_pair.items()):
        graph.add_edge(subject, obj, predicates=tuple(sorted(predicates)))
    graph.remove_nodes_from(list(nx.isolates(graph)))
    graph.graph.update(
        raw_triple_count=len(triples),
        unique_triple_count=len(unique_triples),
        duplicate_triple_count=len(triples) - len(unique_triples),
        self_loop_count_removed=len(self_loops),
    )
    return graph


def build_dag_overlay(graph: nx.DiGraph, scientist_ids: set[str]) -> DagOverlay:
    """Project the raw graph into the fixed four-layer audit DAG."""
    layer_0 = set(graph).intersection(scientist_ids)
    layer_1: set[str] = set()
    for scientist in layer_0:
        for target in graph.successors(scientist):
            predicates = set(graph[scientist][target].get("predicates", ()))
            if predicates.intersection(DIRECT_PREDICATES):
                layer_1.add(str(target))
    layer_1 -= layer_0

    layer_2: set[str] = set()
    for source in layer_1:
        for target in graph.successors(source):
            predicates = set(graph[source][target].get("predicates", ()))
            if predicates.intersection(CONTEXT_PREDICATES):
                layer_2.add(str(target))
    layer_2 -= layer_0 | layer_1

    layer_3 = {
        str(target)
        for source in layer_2
        for target in graph.successors(source)
        if str(target) not in layer_0 | layer_1 | layer_2
    }
    layers = {0: layer_0, 1: layer_1, 2: layer_2, 3: layer_3}
    layer_by_node = {node: layer for layer, nodes in layers.items() for node in nodes}

    overlay = nx.DiGraph()
    for node, layer in sorted(layer_by_node.items()):
        overlay.add_node(node, layer=layer, controlled_motif=False)
    for source, target, attributes in graph.edges(data=True):
        source_layer = layer_by_node.get(str(source))
        target_layer = layer_by_node.get(str(target))
        if source_layer is None or target_layer != source_layer + 1:
            continue
        overlay.add_edge(source, target, **dict(attributes), controlled_motif=False)

    if not nx.is_directed_acyclic_graph(overlay):
        raise ValueError("DAG overlay construction produced a cycle")
    if any(overlay.out_degree(node) for node in layer_3):
        raise ValueError("Layer 3 nodes must be terminal in the audit overlay")
    return DagOverlay(graph=overlay, layers=layers)


def graph_statistics(graph: nx.DiGraph) -> dict[str, int | float]:
    """Compute graph statistics with path metrics on the undirected LWCC."""
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    components = list(nx.weakly_connected_components(graph)) if node_count else []
    largest = (
        max(components, key=lambda nodes: (len(nodes), tuple(sorted(map(str, nodes)))))
        if components
        else set()
    )
    projection = graph.subgraph(largest).to_undirected()
    diameter = nx.diameter(projection) if projection.number_of_nodes() > 1 else 0
    average_path = (
        nx.average_shortest_path_length(projection)
        if projection.number_of_nodes() > 1
        else 0.0
    )
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "average_degree": (2.0 * edge_count / node_count) if node_count else 0.0,
        "weak_component_count": len(components),
        "diameter_lwcc_undirected": int(diameter),
        "average_shortest_path_lwcc_undirected": float(average_path),
    }
