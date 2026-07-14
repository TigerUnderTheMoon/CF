from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts import run_downstream_ranking


def test_m3_and_s1_reuse_downstream_synthetic_generator() -> None:
    from scripts import run_m3_ablation, run_s1_efficiency

    downstream = run_downstream_ranking._generate_synthetic_ranking_data(
        n_samples=200,
        seed=42,
    )
    m3 = run_m3_ablation.generate_synthetic_data(seed=42, n_samples=200)
    s1 = run_s1_efficiency.generate_synthetic_data(seed=42, n_samples=200)

    assert sum(int(sample["n_steps"]) for sample in downstream) == 1027
    assert [sample["n_steps"] for sample in m3] == [sample["n_steps"] for sample in downstream]
    assert [sample["n_steps"] for sample in s1] == [sample["n_steps"] for sample in downstream]
    assert m3[0]["span_lengths"] == downstream[0]["span_lengths"]
    assert s1[0]["span_lengths"] == downstream[0]["span_lengths"]


def test_processbench_trace_level_int_label_blocks_step_ranking_claim(tmp_path: Path) -> None:
    from scripts.run_s3_processbench_preview import build_label_shape_audit, write_guard_report

    rows = [
        {
            "problem": "Which reasoning step fails?",
            "steps": ["First step", "Second step"],
            "label": 1,
            "final_answer_correct": False,
        }
    ]

    audit = build_label_shape_audit(rows)
    out_path = write_guard_report(audit, tmp_path)

    assert audit["step_label_available"] is False
    assert audit["claim_boundary"] == "not_step_ranking_validation"
    assert "trace-level" in audit["failure_reason"]
    assert json.loads(out_path.read_text(encoding="utf-8"))["claim_boundary"] == (
        "not_step_ranking_validation"
    )


def test_processbench_raw_loader_supports_label_shape_guard(tmp_path: Path, monkeypatch) -> None:
    from scripts import run_s3_processbench_preview

    raw_dir = tmp_path / "outputs" / "s3_processbench_preview" / "raw_data"
    raw_dir.mkdir(parents=True)
    raw_path = raw_dir / "all_processbench.json"
    raw_path.write_text(
        json.dumps(
            [
                {
                    "problem": "Trace-level ProcessBench row",
                    "steps": ["first", "second"],
                    "label": 1,
                    "final_answer_correct": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_s3_processbench_preview, "PROJECT_ROOT", tmp_path)

    raw_rows = run_s3_processbench_preview.load_processbench_raw_rows()
    audit = run_s3_processbench_preview.build_label_shape_audit(raw_rows)

    assert audit["step_label_available"] is False
    assert audit["trace_level_records"] == 1
    assert audit["claim_boundary"] == "not_step_ranking_validation"


def test_s1_efficiency_results_are_json_serializable() -> None:
    from scripts import run_s1_efficiency

    samples = run_s1_efficiency.generate_synthetic_data(seed=42, n_samples=5)
    result = run_s1_efficiency.time_method(samples, "span_length", n_repeats=1)
    total_steps = run_s1_efficiency.total_synthetic_steps(samples)
    summary = {
        "experiment": "S1_efficiency_benchmark",
        "seed": 42,
        "n_samples": len(samples),
        "n_total_steps": total_steps,
        "methods": {"span_length": result},
    }

    assert isinstance(result["n_total_steps"], int)
    assert isinstance(total_steps, int)
    json.dumps(summary)


def test_kbs_style_audit_builder_schema_and_split() -> None:
    from fma.eval.kbs_style_audit import build_kbs_audit_traces

    rows = [
        {
            "sample_id": f"hotpotqa-train-{index:05d}",
            "question": f"Question {index} about Entity {index}?",
            "reference_answer": f"Answer {index}",
            "aliases": [f"Alias {index}"],
            "supporting_facts": [[f"Entity {index}", 0], [f"Bridge {index}", 0]],
            "dataset": "hotpot_qa",
            "config": "distractor",
            "split": "train",
            "source_index": index,
        }
        for index in range(12)
    ]

    traces = build_kbs_audit_traces(rows, dev_mod_upper=30)

    assert traces
    assert {trace["split"] for trace in traces} <= {"dev", "locked"}
    assert {"dev", "locked"}.issubset({trace["split"] for trace in traces})
    for trace in traces:
        assert {
            "sample_id",
            "question",
            "answer",
            "steps",
            "typed_edges",
            "audit_label",
            "label_source",
            "split",
            "provenance",
        }.issubset(trace)
        assert len(trace["steps"]) == len(trace["audit_label"])
        assert all("step_id" in step and "step_type" in step and "text" in step for step in trace["steps"])
        assert all(0.0 <= float(label) <= 1.0 for label in trace["audit_label"])
        assert trace["label_source"] == "hotpotqa_supporting_fact_constructed_audit_labels"
        assert trace["provenance"]["validated_kbs_workflow"] is False


def test_kbs_style_audit_metrics_are_finite_and_claim_bounded() -> None:
    from fma.eval.kbs_style_audit import build_kbs_audit_traces, evaluate_kbs_audit_traces

    rows = [
        {
            "sample_id": f"hotpotqa-train-{index:05d}",
            "question": f"Which bridge fact identifies Answer {index}?",
            "reference_answer": f"Answer {index}",
            "aliases": [f"Alias {index}"],
            "supporting_facts": [[f"Bridge fact {index}", 0], [f"Answer source {index}", 0]],
            "dataset": "hotpot_qa",
            "config": "distractor",
            "split": "train",
            "source_index": index,
        }
        for index in range(24)
    ]
    traces = build_kbs_audit_traces(rows, dev_mod_upper=30)

    report = evaluate_kbs_audit_traces(traces, n_bootstrap=100, seed=11)

    assert report["claim_boundary"] == "kbs_style_audit_prioritization_evidence_only"
    assert report["validated_kbs_workflow"] is False
    assert report["leakage_audit"]["target_leakage_status"] == "clean"
    assert report["locked_samples"] > 0
    assert {"random", "relative_position", "span_length", "raw_local_utility"}.issubset(
        report["methods"]
    )
    assert {"scfma_ridge", "scfma_qp", "w_struct", "simple_average", "retrieval_overlap"}.issubset(
        report["methods"]
    )
    for method in report["methods"].values():
        for key in ("mean_ndcg_at_25", "mean_top1_hit", "mean_mass_at_25", "mean_auprc"):
            assert np.isfinite(float(method[key]))
    assert np.isfinite(float(report["support_decision"]["best_scfma_delta_vs_best_control"]))
    assert abs(
        float(report["support_decision"]["bootstrap_ci"]["mean"])
        - float(report["support_decision"]["best_scfma_delta_vs_best_control"])
    ) < 1e-9


def test_kbs_style_audit_runner_writes_offline_artifacts(tmp_path: Path) -> None:
    from scripts import run_kbs_style_audit

    source_path = tmp_path / "hotpotqa_declared.jsonl"
    rows = [
        {
            "sample_id": f"hotpotqa-train-{index:05d}",
            "question": f"Which support chain identifies Answer {index}?",
            "reference_answer": f"Answer {index}",
            "aliases": [f"Alias {index}"],
            "supporting_facts": [[f"Bridge fact {index}", 0], [f"Answer page {index}", 0]],
            "dataset": "hotpot_qa",
            "config": "distractor",
            "split": "train",
            "source_index": index,
        }
        for index in range(36)
    ]
    source_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "kbs_style_audit"
    report = run_kbs_style_audit.run(
        source_path=source_path,
        fallback_source_path=source_path,
        output_dir=output_dir,
        max_rows=36,
        n_bootstrap=50,
        seed=13,
    )

    traces_path = output_dir / "kbs_audit_traces.jsonl"
    report_path = output_dir / "kbs_audit_report.json"
    summary_path = output_dir / "kbs_audit_summary.md"

    assert traces_path.exists()
    assert report_path.exists()
    assert summary_path.exists()
    assert report["claim_boundary"] == "kbs_style_audit_prioritization_evidence_only"
    assert report["validated_kbs_workflow"] is False
    assert report["api_calls"] == 0
    assert report["config"]["max_rows"] == 36
    assert report["artifacts"]["traces_path"].endswith("kbs_audit_traces.jsonl")
    assert len(traces_path.read_text(encoding="utf-8").strip().splitlines()) == (
        report["dev_samples"] + report["locked_samples"]
    )
