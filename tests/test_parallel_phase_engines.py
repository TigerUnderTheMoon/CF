from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from fma.attribution.engine import IncrementalAttributionEngine, ParallelAttributionEngine
from fma.eval.counterfactual_attribution import (
    ABLATION_STRATEGIES,
    dataclass_to_dict,
    run_single_step_ablations,
)
from fma.eval.utility_annotation import (
    AttributionAlignment,
    OutcomeDelta,
    UtilityAnnotation,
    UtilityLabel,
)
from fma.graph.engine import ParallelGraphInterventionEngine
from fma.graph.reflection_graph import RemovalMode, ReflectionGraph, ReflectionNode
from fma.utils.benchmark import benchmark_function


def make_annotation(trace_id: str, idx: int, attribution_type: str) -> UtilityAnnotation:
    return UtilityAnnotation(
        trace_id=trace_id,
        reflection_idx=idx,
        utility=UtilityLabel.HELPFUL if idx == 0 else UtilityLabel.NEUTRAL,
        outcome_delta=OutcomeDelta.UNCHANGED,
        degradation_score=0.0,
        annotation_confidence=1.0,
        attribution_type=attribution_type,
        attribution_alignment=AttributionAlignment.PARTIAL,
        intervention_type="delete",
        reflection_category="VERIFICATION",
        correctness_preserved=True,
    )


def make_trace(trace_id: str) -> dict[str, object]:
    return {
        "trace_id": trace_id,
        "reflection_chain": [
            {"category": "VERIFICATION", "text": f"{trace_id} check"},
            {"category": "PLANNING", "text": f"{trace_id} plan"},
        ],
        "reflection_categories": ["VERIFICATION", "PLANNING"],
        "reflection_spans": [
            {"content": f"{trace_id} check", "step_index": 0},
            {"content": f"{trace_id} plan", "step_index": 1},
        ],
        "reasoning_trace": f"{trace_id} check {trace_id} plan",
        "reflection_text": f"{trace_id} check {trace_id} plan",
    }


def make_phase5_inputs() -> tuple[list[dict[str, object]], list[UtilityAnnotation]]:
    traces = [make_trace(f"t{i}") for i in range(5)]
    annotations = [
        make_annotation(f"t{i}", 0, "factual_error")
        for i in range(5)
    ] + [
        make_annotation(f"t{i}", 1, "irrelevant")
        for i in range(5)
    ]
    return traces, annotations


def graph_node(node_id: str, step: int, utility: float = 1.0) -> ReflectionNode:
    return ReflectionNode(
        node_id=node_id,
        trace_id="g1",
        step_index=step,
        taxonomy_label="VERIFICATION",
        utility_score=utility,
        structural_influence=0.0,
        content=node_id,
    )


def make_graph(graph_id: str) -> ReflectionGraph:
    graph = ReflectionGraph(graph_id)
    graph.add_node(graph_node(f"{graph_id}:a", 0, 1.0))
    graph.add_node(graph_node(f"{graph_id}:b", 1, 1.0))
    graph.add_node(graph_node(f"{graph_id}:c", 2, 1.0))
    graph.add_edge(f"{graph_id}:a", f"{graph_id}:b", "verifies")
    graph.add_edge(f"{graph_id}:b", f"{graph_id}:c", "verifies")
    graph.freeze_sources([f"{graph_id}:a"])
    return graph


def test_parallel_attribution_matches_serial_output_order() -> None:
    traces, annotations = make_phase5_inputs()
    serial = run_single_step_ablations(traces, annotations, seed=17, strategies=ABLATION_STRATEGIES)

    engine = ParallelAttributionEngine(
        seed=17,
        chunk_size=2,
        n_jobs=2,
        backend="threading",
        show_progress=False,
    )

    parallel = engine.run_single_step_ablations(traces, annotations)

    assert [dataclass_to_dict(row) for row in parallel] == [
        dataclass_to_dict(row) for row in serial
    ]


def test_incremental_attribution_writes_chunks_and_resumes(tmp_path) -> None:
    traces, annotations = make_phase5_inputs()
    engine = IncrementalAttributionEngine(
        output_dir=tmp_path,
        seed=23,
        chunk_size=2,
        n_jobs=2,
        backend="threading",
        show_progress=False,
    )

    first = engine.run(traces, annotations)
    first_chunk = tmp_path / "chunk_00000.jsonl"
    first_chunk_text = first_chunk.read_text(encoding="utf-8")
    (tmp_path / "chunk_00001.jsonl").unlink()

    resumed = engine.run(traces, annotations, resume=True)

    assert [dataclass_to_dict(row) for row in resumed] == [
        dataclass_to_dict(row) for row in first
    ]
    assert first_chunk.read_text(encoding="utf-8") == first_chunk_text
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["completed_chunks"] == [0, 1, 2]
    assert checkpoint["chunk_size"] == 2


def test_parallel_graph_intervention_runs_all_removal_modes_without_mutation() -> None:
    graph = make_graph("g1")
    before = graph.to_dict()
    engine = ParallelGraphInterventionEngine(max_workers=2, show_progress=False)

    report = engine.run([graph], modes=(RemovalMode.PRUNE, RemovalMode.CASCADE, RemovalMode.BYPASS))

    assert graph.to_dict() == before
    assert set(report.by_mode) == {"PRUNE", "CASCADE", "BYPASS"}
    for mode, batch in report.by_mode.items():
        assert len(batch.node_necessity) == 3
        assert {row.removal_mode for row in batch.node_necessity} == {mode}
        assert batch.edge_necessity
        assert batch.subgraph_necessity
        assert batch.structural_metrics


def test_benchmark_function_writes_phase5_benchmark_json(tmp_path) -> None:
    output_path = tmp_path / "phase5_benchmark.json"

    def work() -> int:
        return sum(range(10))

    result, benchmark = benchmark_function("phase5_smoke", work, output_path=output_path)

    assert result == 45
    assert benchmark.name == "phase5_smoke"
    assert benchmark.elapsed_seconds >= 0.0
    assert benchmark.peak_memory_mb >= 0.0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["benchmarks"][0] == asdict(benchmark)
