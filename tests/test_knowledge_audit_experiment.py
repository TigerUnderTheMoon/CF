from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fma.eval.knowledge_audit import (
    build_2wiki_trace,
    build_musique_trace,
    build_knowledge_audit_report,
    hash_split,
    validate_knowledge_audit_trace,
)


def _fixture_record() -> dict[str, object]:
    return {
        "_id": "2wiki-fixture-1",
        "question": "Which city is the birthplace of the author of Example Book?",
        "answer": "Paris",
        "evidences": [
            ["Example Book", "author", "Jane Doe"],
            ["Jane Doe", "place of birth", "Paris"],
        ],
        "supporting_facts": [
            ["Example Book", 0],
            ["Jane Doe", 0],
        ],
        "context": [
            [
                "Example Book",
                ["Example Book was written by Jane Doe.", "It was published in 1999."],
            ],
            [
                "Jane Doe",
                ["Jane Doe was born in Paris.", "She later moved to Rome."],
            ],
            [
                "Distractor",
                ["Distractor text mentions London but does not answer the question."],
            ],
        ],
    }


def test_build_2wiki_trace_has_required_schema_and_step_labels() -> None:
    trace = build_2wiki_trace(_fixture_record(), source_index=7, split="locked")

    validate_knowledge_audit_trace(trace)

    assert trace["sample_id"] == "2wiki-fixture-1"
    assert trace["split"] == "locked"
    assert trace["label_source"] == "2wikimultihopqa_evidence_path_constructed_audit_labels"
    assert trace["provenance"]["api_calls"] == 0
    assert trace["provenance"]["validated_kbs_workflow"] is False
    assert len(trace["steps"]) == len(trace["audit_label"])
    assert len(trace["steps"]) >= 7
    assert {0.0, 1.0, 2.0}.issubset(set(trace["audit_label"]))
    assert trace["typed_edges"]


def test_hash_split_is_reproducible_and_approximately_30_70() -> None:
    splits = [hash_split(f"sample-{idx}", dev_percent=30, salt="unit") for idx in range(200)]

    assert splits == [
        hash_split(f"sample-{idx}", dev_percent=30, salt="unit") for idx in range(200)
    ]
    dev_fraction = splits.count("dev") / len(splits)
    assert 0.20 <= dev_fraction <= 0.40


def test_report_uses_locked_split_for_final_metrics_without_locked_tuning() -> None:
    traces = [
        build_2wiki_trace(_fixture_record() | {"_id": f"2wiki-fixture-{idx}"}, idx, "dev")
        for idx in range(12)
    ] + [
        build_2wiki_trace(_fixture_record() | {"_id": f"2wiki-fixture-{idx}"}, idx, "locked")
        for idx in range(12, 44)
    ]

    report = build_knowledge_audit_report(
        traces,
        n_bootstrap=25,
        bootstrap_seed=123,
        min_delta_ndcg=0.05,
    )

    assert report["claim_boundary"] == "kbs_style_audit_prioritization_evidence_only"
    assert report["validated_kbs_workflow"] is False
    assert report["api_calls"] == 0
    assert report["dev_samples"] == 12
    assert report["locked_samples"] == 32
    assert report["leakage_audit"]["target_leakage_status"] == "clean"
    assert report["leakage_audit"]["locked_labels_used_for_scoring"] is False
    assert report["leakage_audit"]["forbidden_fields_used"] == []
    assert "retrieval_overlap" in report["methods"]
    assert "scfma_qp" in report["methods"]
    assert "support_condition_met" in report["support_decision"]


def test_trace_schema_rejects_trace_level_scalar_label() -> None:
    trace = build_2wiki_trace(_fixture_record(), source_index=0, split="locked")
    trace["audit_label"] = 1

    with pytest.raises(ValueError, match="step-level audit_label"):
        validate_knowledge_audit_trace(trace)


def test_build_musique_trace_uses_decomposition_and_paragraph_provenance() -> None:
    record = {
        "id": "musique-fixture-1",
        "question": "Where was the author of Example Book born?",
        "answer": "Paris",
        "question_decomposition": [
            {"question": "Who wrote Example Book?", "answer": "Jane Doe"},
            {"question": "Where was Jane Doe born?", "answer": "Paris"},
        ],
        "paragraphs": [
            {
                "idx": 0,
                "title": "Example Book",
                "paragraph_text": "Example Book was written by Jane Doe.",
                "is_supporting": True,
            },
            {
                "idx": 1,
                "title": "Jane Doe",
                "paragraph_text": "Jane Doe was born in Paris.",
                "is_supporting": True,
            },
            {
                "idx": 2,
                "title": "Distractor",
                "paragraph_text": "Distractor text mentions London.",
                "is_supporting": False,
            },
        ],
    }

    trace = build_musique_trace(record, source_index=3, split="locked")

    validate_knowledge_audit_trace(trace)
    assert trace["sample_id"] == "musique-fixture-1"
    assert trace["label_source"] == "musique_decomposition_constructed_audit_labels"
    assert trace["provenance"]["source_dataset"] == "musique"
    assert len(trace["steps"]) == len(trace["audit_label"])
    assert max(trace["audit_label"]) == 2.0
    assert 0.0 in trace["audit_label"]
    labels_by_type = {
        step["step_type"]: label
        for step, label in zip(trace["steps"], trace["audit_label"])
    }
    assert labels_by_type["answer_synthesis"] > labels_by_type["evidence_check"]
    assert len(set(trace["audit_label"])) > 4


def test_report_preserves_musique_source_and_label_boundary() -> None:
    records = []
    for idx in range(30):
        row = {
            "id": f"musique-report-{idx}",
            "question": "Where was the author of Example Book born?",
            "answer": "Paris",
            "question_decomposition": [
                {"question": "Who wrote Example Book?", "answer": "Jane Doe"},
                {"question": "Where was Jane Doe born?", "answer": "Paris"},
            ],
            "paragraphs": [
                {"idx": 0, "title": "Example Book", "paragraph_text": "...", "is_supporting": True},
                {"idx": 1, "title": "Jane Doe", "paragraph_text": "...", "is_supporting": True},
                {"idx": 2, "title": "Distractor", "paragraph_text": "...", "is_supporting": False},
            ],
        }
        records.append(row)
    traces = [
        build_musique_trace(record, idx, "dev" if idx < 10 else "locked")
        for idx, record in enumerate(records)
    ]

    report = build_knowledge_audit_report(traces, n_bootstrap=5, bootstrap_seed=1)

    assert report["data_source"] == "MuSiQue decomposition evidence-chain traces"
    assert report["label_source"] == "musique_decomposition_constructed_audit_labels"


def test_report_json_round_trips(tmp_path: Path) -> None:
    traces = [
        build_2wiki_trace(_fixture_record() | {"_id": f"2wiki-fixture-{idx}"}, idx, "dev")
        for idx in range(6)
    ] + [
        build_2wiki_trace(_fixture_record() | {"_id": f"2wiki-fixture-{idx}"}, idx, "locked")
        for idx in range(6, 18)
    ]
    report = build_knowledge_audit_report(traces, n_bootstrap=10, bootstrap_seed=7)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded["route_id"] == "kbs_real_knowledge_audit_v1"
    assert loaded["locked_steps"] > 0


def test_runner_writes_offline_artifacts(tmp_path: Path) -> None:
    source_path = tmp_path / "2wiki_fixture.jsonl"
    records = []
    for idx in range(40):
        row = _fixture_record()
        row["_id"] = f"2wiki-runner-{idx}"
        records.append(row)
    source_path.write_text(
        "\n".join(json.dumps(row) for row in records) + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_knowledge_audit_eval.py",
            "--source",
            str(source_path),
            "--output-dir",
            str(output_dir),
            "--max-records",
            "40",
            "--bootstrap-samples",
            "10",
            "--shuffle-seed",
            "9",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output_dir / "knowledge_audit_report.json").read_text(encoding="utf-8"))
    assert (output_dir / "knowledge_audit_traces.jsonl").exists()
    assert (output_dir / "knowledge_audit_summary.md").exists()
    assert report["api_calls"] == 0
    assert report["locked_samples"] > 0
    assert report["support_decision"]["required_interpretation"].startswith("KBS-style")
