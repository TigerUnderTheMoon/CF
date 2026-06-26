"""End-to-end pipeline for the WebQSP trace-audit route."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from fma.io import write_records
from fma.trace_audit import (
    AgreementScorer,
    RuleReplayEngine,
    RuleTraceGenerator,
    VerificationGraphBuilder,
    WebQSPLoader,
    WebQSPPreprocessor,
    audit_traces,
    build_experiment_report,
)
from fma.trace_audit.metrics import build_case_studies, render_case_studies


def run_pipeline(
    *,
    source: str | Path,
    output_dir: str | Path,
    source_split: str,
    max_records: int | None = None,
) -> dict[str, Any]:
    out = Path(output_dir)
    records = WebQSPLoader().load(source, max_records=max_records)
    preprocessor = WebQSPPreprocessor()
    generator = RuleTraceGenerator()
    replay = RuleReplayEngine()
    agreement = AgreementScorer()
    graph_builder = VerificationGraphBuilder()

    samples = [preprocessor.build_sample(record, source_split=source_split) for record in records]
    generation_samples = [
        sample
        for sample in samples
        if sample.get("parse_status") == "full"
    ]
    skip_reasons = Counter(
        _skip_reason(sample)
        for sample in samples
        if sample.get("parse_status") != "full"
    )
    traces = [generator.generate(sample) for sample in generation_samples]
    replay_rows = []
    scored_by_trace = []
    graphs = []
    for trace in traces:
        trace_replay = replay.replay_trace(trace)
        replay_rows.extend(trace_replay)
        scored = agreement.score_trace(trace, trace_replay)
        scored_by_trace.append(scored)
        graphs.append(graph_builder.build(trace, scored))

    data_audit = audit_traces(traces, replay_rows)
    report = build_experiment_report(traces, scored_by_trace, graphs)
    report["data_audit"] = data_audit
    report["input"] = {
        "source": str(source),
        "source_split": source_split,
        "records_read": len(records),
        "samples_built": len(samples),
        "traces_requested": len(generation_samples),
        "skip_reasons": dict(sorted(skip_reasons.items())),
    }

    case_studies = build_case_studies(traces, scored_by_trace, replay_rows)
    _write_outputs(
        out,
        samples,
        traces,
        replay_rows,
        scored_by_trace,
        graphs,
        report,
        case_studies,
    )
    return report


def _skip_reason(sample: dict[str, Any]) -> str:
    if not sample.get("answers"):
        return "partial_parse_or_missing_answer"
    if not sample.get("relations"):
        return "partial_parse_or_missing_relation"
    if not sample.get("entities"):
        return "partial_parse_or_missing_entity"
    return "partial_parse_or_missing_fields"


def _write_outputs(
    out: Path,
    samples: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    replay_rows: list[dict[str, Any]],
    scored_by_trace: list[list[dict[str, Any]]],
    graphs: list[dict[str, Any]],
    report: dict[str, Any],
    case_studies: dict[str, Any],
) -> None:
    write_records(samples, out / "data" / "samples.jsonl")
    write_records([{"sample_id": s["sample_id"], "local_kg": s["local_kg"]} for s in samples], out / "data" / "local_kg_slices.jsonl")
    write_records(traces, out / "traces" / "reasoning_traces.jsonl")
    write_records(replay_rows, out / "replay" / "replay_results.jsonl")
    write_records([row for scored in scored_by_trace for row in scored], out / "replay" / "importance_targets.jsonl")
    write_records(graphs, out / "graphs" / "verification_graphs.jsonl")
    ranking_dir = out / "ranking"
    ranking_dir.mkdir(parents=True, exist_ok=True)
    (ranking_dir / "ranking_results.json").write_text(
        json.dumps(report["ranking"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_case_studies(out, case_studies)
    _write_figures(out, report)
    metrics_dir = out / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "audit_metrics.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (metrics_dir / "data_audit.json").write_text(json.dumps(report["data_audit"], indent=2, sort_keys=True), encoding="utf-8")


def _write_case_studies(out: Path, case_studies: dict[str, Any]) -> None:
    case_dir = out / "case_studies"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case_studies.json").write_text(
        json.dumps(case_studies, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (case_dir / "case_studies.md").write_text(
        render_case_studies(case_studies),
        encoding="utf-8",
    )


def _write_figures(out: Path, report: dict[str, Any]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir = out / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    ranking = report.get("ranking", {})
    methods = ranking.get("methods", {})
    method_names = list(methods.keys())
    ndcg_values = [float(methods[name].get("ndcg_at_25", 0.0)) for name in method_names]

    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar(method_names, ndcg_values, color="#4C78A8")
    ax.set_ylabel("NDCG@25")
    ax.set_ylim(0.0, max([1.0, *ndcg_values]))
    ax.tick_params(axis="x", rotation=35, labelsize=8)
    ax.set_title("WebQSP Trace-Audit Method Comparison")
    fig.tight_layout()
    fig.savefig(figures_dir / "method_comparison.png", dpi=160)
    plt.close(fig)

    labels: list[float] = []
    for row in ranking.get("per_trace", []):
        labels.extend(float(value) for value in row.get("labels", []))
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    if labels:
        ax.hist(labels, bins=min(12, max(3, len(set(labels)))), color="#59A14F", edgecolor="white")
    else:
        ax.hist([0.0], bins=1, color="#59A14F", edgecolor="white")
    ax.set_xlabel("Importance target")
    ax.set_ylabel("Step count")
    ax.set_title("Replay-Derived Importance Distribution")
    fig.tight_layout()
    fig.savefig(figures_dir / "importance_distribution.png", dpi=160)
    plt.close(fig)
