from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import scripts.jiis_countries_kg_validation_core as audit_core
from fma.graph.reflection_graph import ReflectionEdge, ReflectionGraph, ReflectionNode


ROOT = Path(__file__).resolve().parents[1]
LABEL_SCRIPT = ROOT / "scripts" / "run_countries_kg_label_validation.py"
AUDIT_SCRIPT = ROOT / "scripts" / "run_jiis_audit_case.py"


def _toy_trace(
    node_rows: list[dict[str, object]],
    edges: list[tuple[str, str]],
) -> dict[str, object]:
    graph = ReflectionGraph(
        "toy",
        nodes=[
            ReflectionNode(
                node_id=str(row["node_id"]),
                trace_id="toy",
                step_index=int(row.get("step_index", index + 1)),
                taxonomy_label="VERIFICATION",
                utility_score=0.0,
                structural_influence=0.0,
                content=str(row["node_id"]),
            )
            for index, row in enumerate(node_rows)
        ],
        edges=[
            ReflectionEdge(source=source, target=target, edge_type="verifies")
            for source, target in edges
        ],
    )
    return {"trace_id": "toy", "nodes": node_rows, "graph": graph.to_dict()}


def test_lsf_and_random_stratified_share_eligible_candidate_universe() -> None:
    trace = _toy_trace(
        [
            {
                "node_id": "root",
                "step_index": 0,
                "auditable": False,
                "is_bottleneck": True,
                "is_redundant": False,
                "redundancy_group_id": None,
                "downstream_impact_count": 3,
                "degree": 2,
            },
            {
                "node_id": "eligible-a",
                "auditable": True,
                "is_bottleneck": False,
                "is_redundant": False,
                "redundancy_group_id": None,
                "downstream_impact_count": 2,
                "degree": 2,
            },
            {
                "node_id": "eligible-b",
                "auditable": True,
                "is_bottleneck": True,
                "is_redundant": True,
                "redundancy_group_id": "rg-1",
                "downstream_impact_count": 1,
                "degree": 2,
            },
        ],
        [("root", "eligible-a"), ("eligible-a", "eligible-b")],
    )

    randomized = audit_core._randomize_structural_labels_within_eligible(trace, seed=7)
    ineligible_before = next(row for row in trace["nodes"] if row["node_id"] == "root")
    ineligible_after = next(row for row in randomized["nodes"] if row["node_id"] == "root")
    assert ineligible_after == ineligible_before

    eligible_before = [row for row in trace["nodes"] if row["auditable"]]
    eligible_after = [row for row in randomized["nodes"] if row["auditable"]]
    assert sorted(bool(row["is_bottleneck"]) for row in eligible_after) == sorted(
        bool(row["is_bottleneck"]) for row in eligible_before
    )
    assert sorted(str(row["redundancy_group_id"]) for row in eligible_after) == sorted(
        str(row["redundancy_group_id"]) for row in eligible_before
    )

    expected = {"eligible-a", "eligible-b"}
    lsf = audit_core.life_saving_first_selection(trace, budget=2, seed=7)
    stratified = audit_core.random_stratified_selection(trace, budget=2, seed=7)
    assert set(lsf["selected_node_ids"]) <= expected
    assert set(stratified["selected_node_ids"]) <= expected
    assert lsf["candidate_universe"]["candidate_ids"] == sorted(expected)
    assert stratified["candidate_universe"] == lsf["candidate_universe"]
    assert "root" not in lsf["selected_node_ids"]


def test_greedy_maximum_coverage_avoids_overlapping_second_choice() -> None:
    trace = _toy_trace(
        [
            {"node_id": "a", "auditable": True, "downstream_impact_count": 4, "degree": 2},
            {"node_id": "b", "auditable": True, "downstream_impact_count": 3, "degree": 2},
            {"node_id": "c", "auditable": True, "downstream_impact_count": 1, "degree": 1},
            {"node_id": "x", "auditable": True, "downstream_impact_count": 0, "degree": 2},
            {"node_id": "y", "auditable": True, "downstream_impact_count": 0, "degree": 2},
            {"node_id": "z", "auditable": True, "downstream_impact_count": 0, "degree": 1},
        ],
        [("a", "x"), ("a", "y"), ("b", "x"), ("b", "y"), ("c", "z")],
    )

    first = audit_core.greedy_maximum_coverage_selection(trace, budget=2)
    second = audit_core.greedy_maximum_coverage_selection(trace, budget=2)

    assert first["selected_node_ids"] == ["a", "c"]
    assert second == first
    assert first["marginal_coverage_counts"] == [2, 1]
    assert first["candidate_universe"]["candidate_ids"] == ["a", "b", "c", "x", "y", "z"]


def test_lsf_supports_one_layer_off_ablation() -> None:
    trace = _toy_trace(
        [
            {
                "node_id": "bottleneck",
                "auditable": True,
                "is_bottleneck": True,
                "is_redundant": False,
                "redundancy_group_id": None,
                "downstream_impact_count": 2,
                "degree": 2,
            },
            {
                "node_id": "unique",
                "auditable": True,
                "is_bottleneck": False,
                "is_redundant": False,
                "redundancy_group_id": None,
                "downstream_impact_count": 1,
                "degree": 1,
            },
            {
                "node_id": "redundant",
                "auditable": True,
                "is_bottleneck": False,
                "is_redundant": True,
                "redundancy_group_id": "rg-1",
                "downstream_impact_count": 0,
                "degree": 1,
            },
        ],
        [("bottleneck", "unique"), ("unique", "redundant")],
    )

    no_bottleneck = audit_core.life_saving_first_selection(
        trace,
        budget=1,
        seed=7,
        disabled_layers={"critical_bottleneck"},
    )
    no_unique = audit_core.life_saving_first_selection(
        trace,
        budget=1,
        seed=7,
        disabled_layers={"unique_evidence"},
    )
    no_redundancy = audit_core.life_saving_first_selection(
        trace,
        budget=3,
        seed=7,
        disabled_layers={"redundancy_group_samples"},
    )

    assert no_bottleneck["selected_node_ids"] == ["unique"]
    assert no_unique["selected_node_ids"] == ["bottleneck"]
    assert "redundancy_group_samples" not in no_redundancy["selected_layers"]
    assert no_redundancy["disabled_layers"] == ["redundancy_group_samples"]


def _run_label_validation(tmp_path: Path) -> Path:
    output_dir = tmp_path / "labels"
    result = subprocess.run(
        [
            sys.executable,
            str(LABEL_SCRIPT),
            "--output-dir",
            str(output_dir),
            "--seed",
            "20260711",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    cache_path = output_dir / "countries_kg_labels_cached.json"
    assert cache_path.exists()
    return cache_path


def test_jiis_audit_case_uses_cached_labels_and_impact_coverage(tmp_path: Path) -> None:
    cache_path = _run_label_validation(tmp_path)
    output_dir = tmp_path / "audit_case"

    result = subprocess.run(
        [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--n-traces",
            "600",
            "--seed",
            "20260711",
            "--budget",
            "0.25",
            "--label-cache",
            str(cache_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads((output_dir / "jiis_audit_case_report.json").read_text(encoding="utf-8"))
    assert report["protocol_version"] == "fair-v1"
    assert report["label_cache"]["path"] == str(cache_path)
    assert report["label_cache"]["recomputed_label_count"] == 0
    assert report["table_2_title"].startswith("Impact Coverage@K")
    assert report["metrics"]["impact_coverage_at_k"]["mean"] >= 0.0
    assert report["metrics"]["average_path_length_to_covered_descendants"]["mean"] >= 0.0
    assert report["metrics"]["early_truncation_rate"]["mean"] >= 0.0
    assert report["baselines"]["flat_top_k"]["score_source"] == "raw_risk_score"
    assert report["baselines"]["random_stratified"]["score_source"] == "shuffled_structural_labels"
    assert report["baselines"]["greedy_max_coverage"]["score_source"] == "marginal_auditable_descendant_coverage"
    assert report["baselines"]["no_fallback_ablation"]["enabled"] is True
    assert isinstance(report["baselines"]["no_fallback_ablation"]["informative"], bool)
    assert report["baselines"]["no_fallback_ablation"]["selection_difference_count"] >= 0
    assert report["policy"]["name"] == "Life-Saving First"
    assert report["policy"]["layers"] == [
        "Critical Bottleneck",
        "Unique Evidence",
        "Redundancy Group Samples",
        "Fallback",
    ]
    assert report["policy"]["raw_risk_score_role"] == "tie_breaker_only_within_layer"
    assert report["policy"]["candidate_pool_rule"] == "auditable == true"
    assert report["metrics"]["impact_coverage_at_k"]["definition"] == "reachable_descendants_transitive_closure"
    assert {
        "greedy_max_coverage",
        "lsf_no_bottleneck",
        "lsf_no_redundancy",
        "lsf_no_unique",
    } <= set(report["methods"])
    assert report["statistical_units"] == {
        "unit": "source_trace",
        "unique_source_unit_count": 30,
        "repetitions": 600,
        "repetition_role": "monte_carlo_or_implementation_repeat_not_independent_unit",
    }
    assert set(report["layer_activation"]["counts"]) == {
        "critical_bottleneck",
        "unique_evidence",
        "redundancy_group_samples",
        "fallback",
    }
    assert report["layer_activation"]["unexercised_layers"] == [
        layer
        for layer, count in report["layer_activation"]["counts"].items()
        if count == 0
    ]
    schema = json.loads(
        (ROOT / "schemas" / "scar_audit_record.schema.json").read_text(encoding="utf-8")
    )
    audit_records_path = output_dir / "audit_records.jsonl"
    audit_records = [
        json.loads(line)
        for line in audit_records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert audit_records
    assert report["audit_records"]["path"] == str(audit_records_path)
    assert report["audit_records"]["record_count"] == len(audit_records)
    for record in audit_records:
        jsonschema.validate(record, schema)
        assert record["extractor_metadata"]["protocol_version"] == "fair-v1"

    trace = report["trace_reports"][0]
    assert trace["source_unit_id"] == trace["source_trace_id"]
    assert trace["replicate_id"] == 0
    assert trace["randomization_seed"] == 20260711
    universe = trace["candidate_universe"]
    assert universe["rule"] == "auditable == true"
    assert universe["candidate_ids"] == sorted(universe["candidate_ids"])
    expected_hash = hashlib.sha256(
        json.dumps(
            universe["candidate_ids"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert universe["sha256"] == expected_hash
    assert universe["count"] == len(universe["candidate_ids"])
    method_candidate_hashes = trace["method_candidate_universe_sha256"]
    assert set(method_candidate_hashes) == set(trace["method_selections"])
    assert set(method_candidate_hashes.values()) == {universe["sha256"]}
    for selected_ids in trace["method_selections"].values():
        assert set(selected_ids) <= set(universe["candidate_ids"])
    assert trace["selection"]["overflow_stopped_within_layer"] in {True, False}
    assert "selected_layers" in trace["selection"]
    assert "random_stratified" in trace["metrics"]

    random_draws_by_source: dict[str, set[tuple[str, ...]]] = {}
    stratified_draws_by_source: dict[str, set[str]] = {}
    seeds_by_source: dict[str, set[int]] = {}
    for row in report["trace_reports"]:
        source_id = row["source_unit_id"]
        assert row["randomization_seed"] == 20260711 + row["replicate_id"]
        seeds_by_source.setdefault(source_id, set()).add(row["randomization_seed"])
        random_draws_by_source.setdefault(source_id, set()).add(
            tuple(row["method_selections"]["random"])
        )
        stratified_draws_by_source.setdefault(source_id, set()).add(
            row["random_stratified_label_sha256"]
        )
        assert len(row["random_stratified_label_sha256"]) == 64
    assert all(len(seeds) == 20 for seeds in seeds_by_source.values())
    assert any(len(draws) > 1 for draws in random_draws_by_source.values())
    stratified_is_informative = any(
        len(draws) > 1 for draws in stratified_draws_by_source.values()
    )
    assert report["baselines"]["random_stratified"]["informative"] is stratified_is_informative
