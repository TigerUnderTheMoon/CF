from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fma.trace_audit import (
    AgreementScorer,
    RuleReplayEngine,
    RuleTraceGenerator,
    VerificationGraphBuilder,
    WebQSPLoader,
    WebQSPPreprocessor,
    audit_traces,
    build_experiment_report,
    compare_datasets,
    final_dataset_decision,
    validate_trace,
)
from fma.trace_audit.pipeline import run_pipeline
from fma.trace_audit.separability import build_separability_report


def _webqsp_fixture() -> dict[str, object]:
    return {
        "QuestionId": "WebQSP.test.1",
        "ProcessedQuestion": "Who directed Inception?",
        "Parses": [
            {
                "Sparql": (
                    "SELECT ?x WHERE { ns:m.inception ns:film.film.directed_by ?x . }"
                ),
                "TopicEntityMid": "m.inception",
                "TopicEntityName": "Inception",
                "InferentialChain": ["film.film.directed_by"],
                "Answers": [
                    {"AnswerArgument": "m.nolan", "EntityName": "Christopher Nolan"}
                ],
            }
        ],
    }


def test_final_dataset_decision_is_webqsp_and_rejects_grailqa_for_audit_scope() -> None:
    comparison = compare_datasets()
    decision = final_dataset_decision()

    assert decision["recommended_dataset"] == "WebQSP"
    assert comparison["GrailQA"]["risk_of_kgqa_interpretation"] > comparison["WebQSP"]["risk_of_kgqa_interpretation"]
    assert "KGQA" in decision["rejected_dataset_rationale"]
    assert "audit" in decision["rationale"].lower()


def test_preprocessor_builds_leakage_safe_local_kg_sample() -> None:
    sample = WebQSPPreprocessor().build_sample(_webqsp_fixture(), source_split="test")

    assert sample["sample_id"] == "WebQSP.test.1"
    assert sample["dataset"] == "webqsp"
    assert sample["answers"] == [{"id": "m.nolan", "name": "Christopher Nolan"}]
    assert sample["local_kg"]["triples"] == [
        {
            "subject": "m.inception",
            "relation": "film.film.directed_by",
            "object": "m.nolan",
        }
    ]
    assert sample["provenance"]["semantic_parser_used"] is False
    assert "Christopher Nolan" not in sample["leakage_safe_question"]


def test_loader_accepts_windows_utf8_bom_json(tmp_path: Path) -> None:
    path = tmp_path / "webqsp_bom.json"
    payload = json.dumps({"Questions": [_webqsp_fixture()]})
    path.write_text("\ufeff" + payload, encoding="utf-8")

    records = WebQSPLoader().load(path)

    assert records[0]["QuestionId"] == "WebQSP.test.1"


def test_rule_trace_generator_outputs_required_executable_steps_without_shortest_path() -> None:
    sample = WebQSPPreprocessor().build_sample(_webqsp_fixture(), source_split="test")
    trace = RuleTraceGenerator().generate(sample)

    validate_trace(trace)

    assert trace["generation_policy"] == "deterministic_rule_execution"
    assert trace["provenance"]["llm_used_for_trace_generation"] is False
    assert [step["step_type"] for step in trace["steps"]] == [
        "entity_linking",
        "relation_traversal",
        "candidate_generation",
        "candidate_verification",
        "ambiguity_resolution",
        "answer_verification",
    ]
    assert all("shortest_path" not in step["operation"] for step in trace["steps"])
    assert trace["final_answer"] == [{"id": "m.nolan", "name": "Christopher Nolan"}]


def test_data_audit_detects_duplicates_disconnected_subgraphs_and_answer_leakage() -> None:
    sample = WebQSPPreprocessor().build_sample(_webqsp_fixture(), source_split="test")
    trace = RuleTraceGenerator().generate(sample)
    duplicate = dict(trace)
    duplicate["trace_id"] = "duplicate-id"
    duplicate["steps"] = [dict(step) for step in trace["steps"]]
    leaky = dict(trace)
    leaky["trace_id"] = "leaky"
    leaky["steps"] = [dict(step) for step in trace["steps"]]
    leaky["steps"][0]["leakage_safe_text"] = "Christopher Nolan appears too early."
    disconnected = dict(trace)
    disconnected["trace_id"] = "disconnected"
    disconnected["steps"] = [dict(step) for step in trace["steps"]]
    disconnected["local_kg"] = {"triples": []}

    audit = audit_traces([trace, duplicate, leaky, disconnected])

    assert audit["duplicate_trace_count"] == 1
    assert audit["answer_leakage_count"] == 1
    assert audit["disconnected_subgraph_count"] == 1
    assert audit["missing_entity_count"] == 0


def test_data_audit_does_not_flag_answer_substrings_inside_safe_words() -> None:
    sample = WebQSPPreprocessor().build_sample(
        _webqsp_fixture()
        | {
            "QuestionId": "WebQSP.test.short-answer",
            "Parses": [
                {
                    "Sparql": "SELECT ?x WHERE { ns:m.topic ns:film.film.genre ?x . }",
                    "TopicEntityMid": "m.topic",
                    "TopicEntityName": "Topic",
                    "InferentialChain": ["film.film.genre"],
                    "Answers": [{"AnswerArgument": "m.red", "EntityName": "Red"}],
                }
            ],
        },
        source_split="test",
    )
    trace = RuleTraceGenerator().generate(sample)

    audit = audit_traces([trace])

    assert audit["answer_leakage_count"] == 0


def test_preprocessor_uses_executable_chain_when_sparql_fragment_is_disconnected() -> None:
    record = _webqsp_fixture() | {
        "QuestionId": "WebQSP.train.disconnected-fragment",
        "ProcessedQuestion": "Which family member died first?",
        "Parses": [
            {
                "Sparql": (
                    "SELECT ?x WHERE { ns:m.other_family ns:people.family.members ?x . "
                    "?x ns:people.deceased_person.date_of_death ?d . }"
                ),
                "TopicEntityMid": "m.family",
                "TopicEntityName": "Example family",
                "InferentialChain": [
                    "people.family.members",
                    "people.deceased_person.date_of_death",
                ],
                "Answers": [{"AnswerArgument": "m.answer", "EntityName": "Answer"}],
            }
        ],
    }

    sample = WebQSPPreprocessor().build_sample(record, source_split="train")
    trace = RuleTraceGenerator().generate(sample)
    audit = audit_traces([trace])

    assert audit["disconnected_subgraph_count"] == 0
    assert trace["steps"][1]["output_entities"] == ["m.answer"]


def test_pipeline_reports_skipped_partial_records_without_generating_partial_traces(tmp_path: Path) -> None:
    source_path = tmp_path / "WebQSP.train.json"
    partial = _webqsp_fixture() | {
        "QuestionId": "WebQSP.train.partial",
        "Parses": [
            {
                "Sparql": "SELECT ?x WHERE { ns:m.topic ns:film.film.genre ?x . }",
                "TopicEntityMid": "m.topic",
                "TopicEntityName": "Topic",
                "InferentialChain": ["film.film.genre"],
                "Answers": [],
            }
        ],
    }
    source_path.write_text(
        json.dumps({"Questions": [_webqsp_fixture(), partial]}),
        encoding="utf-8",
    )

    report = run_pipeline(source=source_path, output_dir=tmp_path / "out", source_split="train")

    assert report["trace_count"] == 1
    assert report["input"]["skip_reasons"]["partial_parse_or_missing_answer"] == 1


def test_rule_replay_and_agreement_produce_continuous_importance_scores() -> None:
    sample = WebQSPPreprocessor().build_sample(_webqsp_fixture(), source_split="test")
    trace = RuleTraceGenerator().generate(sample)
    replay_rows = RuleReplayEngine().replay_trace(trace)
    scored = AgreementScorer().score_trace(trace, replay_rows)

    by_type = {row["step_type"]: row for row in scored}

    assert by_type["answer_verification"]["importance_target"] == pytest.approx(1.0)
    assert by_type["relation_traversal"]["importance_target"] > by_type["candidate_generation"]["importance_target"]
    assert all(0.0 <= row["importance_target"] <= 1.0 for row in scored)
    assert all(0.0 <= row["agreement_score"] <= 1.0 for row in scored)


def test_verification_graph_uses_networkx_and_three_edge_categories() -> None:
    sample = WebQSPPreprocessor().build_sample(_webqsp_fixture(), source_split="test")
    trace = RuleTraceGenerator().generate(sample)
    replay_rows = RuleReplayEngine().replay_trace(trace)
    scored = AgreementScorer().score_trace(trace, replay_rows)
    graph_record = VerificationGraphBuilder().build(trace, scored)

    assert graph_record["graph_backend"] == "networkx"
    assert len(graph_record["nodes"]) == 6
    assert {edge["edge_category"] for edge in graph_record["edges"]} <= {
        "Temporal",
        "Dependency",
        "Support",
    }
    assert graph_record["is_dag"] is True


def test_report_contract_is_trace_audit_not_kgqa_benchmark() -> None:
    sample = WebQSPPreprocessor().build_sample(_webqsp_fixture(), source_split="test")
    trace = RuleTraceGenerator().generate(sample)
    replay_rows = RuleReplayEngine().replay_trace(trace)
    scored = AgreementScorer().score_trace(trace, replay_rows)
    report = build_experiment_report([trace], [scored], [VerificationGraphBuilder().build(trace, scored)])

    assert report["route_id"] == "webqsp_trace_audit_v1"
    assert report["claim"] == "SC-FMA ranks functionally indispensable reasoning steps ahead of recoverable reasoning steps."
    assert report["not_a_kgqa_benchmark"] is True
    assert report["validated_kbs_workflow"] is False
    assert report["metrics"]["mean_ndcg_at_25"] >= 0.0
    assert "KGQA benchmark result" in report["forbidden_claims"]


def test_runner_writes_reproducible_artifacts(tmp_path: Path) -> None:
    source_path = tmp_path / "webqsp_fixture.json"
    source_path.write_text(
        json.dumps({"Questions": [_webqsp_fixture()]}, indent=2),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_webqsp_trace_audit.py",
            "--source",
            str(source_path),
            "--output-dir",
            str(output_dir),
            "--source-split",
            "test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "data" / "samples.jsonl").exists()
    assert (output_dir / "traces" / "reasoning_traces.jsonl").exists()
    assert (output_dir / "replay" / "replay_results.jsonl").exists()
    assert (output_dir / "graphs" / "verification_graphs.jsonl").exists()
    assert (output_dir / "metrics" / "audit_metrics.json").exists()
    report = json.loads((output_dir / "metrics" / "audit_metrics.json").read_text(encoding="utf-8"))
    assert report["route_id"] == "webqsp_trace_audit_v1"


def test_real_data_pipeline_separates_train_and_test_outputs(tmp_path: Path) -> None:
    train_source = tmp_path / "WebQSP.train.json"
    test_source = tmp_path / "WebQSP.test.json"
    train_source.write_text(
        json.dumps({"Questions": [_webqsp_fixture() | {"QuestionId": "WebQSP.train.1"}]}),
        encoding="utf-8",
    )
    test_source.write_text(
        json.dumps({"Questions": [_webqsp_fixture() | {"QuestionId": "WebQSP.test.1"}]}),
        encoding="utf-8",
    )

    train_report = run_pipeline(
        source=train_source,
        output_dir=tmp_path / "outputs" / "webqsp_trace_audit_v1_train",
        source_split="train",
    )
    test_report = run_pipeline(
        source=test_source,
        output_dir=tmp_path / "outputs" / "webqsp_trace_audit_v1_test",
        source_split="test",
    )

    assert train_report["input"]["source_split"] == "train"
    assert test_report["input"]["source_split"] == "test"
    assert (tmp_path / "outputs" / "webqsp_trace_audit_v1_train" / "ranking" / "ranking_results.json").exists()
    assert (tmp_path / "outputs" / "webqsp_trace_audit_v1_test" / "ranking" / "ranking_results.json").exists()


def test_ranking_metrics_case_studies_and_plots_are_written(tmp_path: Path) -> None:
    source_path = tmp_path / "WebQSP.train.json"
    records = []
    for idx in range(4):
        records.append(_webqsp_fixture() | {"QuestionId": f"WebQSP.train.{idx}"})
    source_path.write_text(json.dumps({"Questions": records}), encoding="utf-8")
    output_dir = tmp_path / "out"

    report = run_pipeline(source=source_path, output_dir=output_dir, source_split="train")

    ranking = json.loads((output_dir / "ranking" / "ranking_results.json").read_text(encoding="utf-8"))
    assert {"scfma_ridge", "scfma_qp", "random", "relative_position", "span_length", "candidate_count", "graph_degree", "raw_rule_delta"} <= set(ranking["methods"])
    for metric in (
        "spearman",
        "ndcg_at_25",
        "topk_recall",
        "pairwise_accuracy",
        "bootstrap_ci",
    ):
        assert metric in ranking["methods"]["scfma_ridge"]
        assert metric in ranking["methods"]["scfma_qp"]

    assert report["experiment_review"]["positioning"] in {
        "kbs_main_experiment_candidate",
        "supplementary_diagnostic_evidence",
        "future_work_only",
    }
    assert report["data_audit"]["replay_failure_rate_by_step_type"]
    assert (output_dir / "case_studies" / "case_studies.json").exists()
    assert (output_dir / "case_studies" / "case_studies.md").exists()
    assert (output_dir / "figures" / "method_comparison.png").exists()
    assert (output_dir / "figures" / "importance_distribution.png").exists()


def test_separability_report_identifies_fixed_schema_diagnostic_boundary() -> None:
    rows = []
    step_types = [
        "entity_linking",
        "relation_traversal",
        "candidate_generation",
        "candidate_verification",
        "ambiguity_resolution",
        "answer_verification",
    ]
    for trace_idx, low_value in enumerate((0.20, 0.10)):
        for step_idx, step_type in enumerate(step_types):
            rows.append(
                {
                    "trace_id": f"trace-{trace_idx}",
                    "sample_id": f"sample-{trace_idx}",
                    "step_id": f"s{step_idx}",
                    "step_index": step_idx,
                    "step_type": step_type,
                    "importance_target": 1.0 if step_type in {
                        "entity_linking",
                        "relation_traversal",
                        "answer_verification",
                    } else low_value,
                    "rule_delta": 1.0 if step_type in {
                        "entity_linking",
                        "relation_traversal",
                        "answer_verification",
                    } else low_value,
                }
            )
    ranking = {
        "methods": {
            "relative_position": {"ndcg_at_25": 1.0, "pairwise_accuracy": 2.0 / 3.0},
            "raw_rule_delta": {"ndcg_at_25": 1.0, "pairwise_accuracy": 1.0},
            "scfma_ridge": {"ndcg_at_25": 1.0, "pairwise_accuracy": 1.0},
        }
    }

    report = build_separability_report(rows, ranking)

    assert report["analysis_scope"] == "diagnostic_fixed_schema_separability"
    assert report["not_a_kgqa_benchmark"] is True
    assert report["step_type_binary_separable"] is True
    assert report["step_type_continuous_value_perfect"] is False
    assert report["metric_artifacts"]["ndcg_at_25_keep_count_for_six_step_trace"] == 2
    assert report["metric_artifacts"]["top_budget_is_deterministic_indispensable_prefix"] is True
    assert report["method_diagnostics"]["scfma_ridge_matches_raw_delta_pairwise"] is True
    assert report["recommended_positioning"] == "supplementary_diagnostic_evidence"


def test_separability_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    source_path = tmp_path / "WebQSP.train.json"
    source_path.write_text(
        json.dumps({"Questions": [_webqsp_fixture()]}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    run_pipeline(source=source_path, output_dir=output_dir, source_split="train")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_webqsp_separability.py",
            "--importance-targets",
            str(output_dir / "replay" / "importance_targets.jsonl"),
            "--ranking-results",
            str(output_dir / "ranking" / "ranking_results.json"),
            "--output-json",
            str(output_dir / "diagnostics" / "separability_report.json"),
            "--output-md",
            str(output_dir / "diagnostics" / "separability_report.md"),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output_dir / "diagnostics" / "separability_report.json").read_text(encoding="utf-8"))
    assert report["recommended_positioning"] == "supplementary_diagnostic_evidence"
    assert "fixed-schema separability" in (output_dir / "diagnostics" / "separability_report.md").read_text(encoding="utf-8")
