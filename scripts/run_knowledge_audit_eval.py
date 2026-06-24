"""Run the offline KBS real knowledge-audit prioritization experiment."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fma.eval.knowledge_audit import (  # noqa: E402
    build_2wiki_traces,
    build_knowledge_audit_report,
    load_json_records,
    render_summary,
    write_jsonl,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "kbs_real_audit_v1"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None, help="Local 2Wiki-style JSON/JSONL file.")
    parser.add_argument("--hf-dataset", type=str, default=None, help="Optional Hugging Face dataset id.")
    parser.add_argument("--hf-config", type=str, default=None, help="Optional Hugging Face dataset config.")
    parser.add_argument("--hf-split", type=str, default="train", help="Hugging Face split to read.")
    parser.add_argument(
        "--source-format",
        type=str,
        choices=("auto", "2wiki", "musique"),
        default="auto",
        help="Record schema to convert into traces.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-records", type=int, default=2000)
    parser.add_argument("--dev-percent", type=int, default=30)
    parser.add_argument("--split-salt", type=str, default="kbs-real-audit-v1")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    parser.add_argument("--min-delta-ndcg", type=float, default=0.05)
    parser.add_argument(
        "--shuffle-seed",
        type=int,
        default=None,
        help="Deterministically shuffle records before truncating to --max-records.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    records, source_info = load_records_from_args(args)
    traces = build_traces(records, args.source_format, dev_percent=args.dev_percent, salt=args.split_salt)
    report = build_knowledge_audit_report(
        traces,
        n_bootstrap=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
        min_delta_ndcg=args.min_delta_ndcg,
    )
    report["input"] = {
        **source_info,
        "rows_read": len(records),
        "traces_built": len(traces),
    }
    report["artifacts"] = {
        "traces_path": str(args.output_dir / "knowledge_audit_traces.jsonl"),
        "report_path": str(args.output_dir / "knowledge_audit_report.json"),
        "summary_path": str(args.output_dir / "knowledge_audit_summary.md"),
    }
    report["elapsed_seconds"] = round(time.time() - started, 2)

    traces_path = args.output_dir / "knowledge_audit_traces.jsonl"
    report_path = args.output_dir / "knowledge_audit_report.json"
    summary_path = args.output_dir / "knowledge_audit_summary.md"
    manifest_path = args.output_dir / "dataset_manifest.json"

    write_jsonl(traces_path, traces)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(render_summary(report), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "route_id": report["route_id"],
                "data_source": report["data_source"],
                "api_calls": 0,
                "dev_samples": report["dev_samples"],
                "locked_samples": report["locked_samples"],
                "locked_steps": report["locked_steps"],
                "source": source_info,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print(f"Knowledge audit traces -> {traces_path}")
    print(f"Knowledge audit report -> {report_path}")
    print(f"Knowledge audit summary -> {summary_path}")
    return 0


def load_records_from_args(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if args.source is not None:
        records = load_json_records(
            args.source,
            max_records=None if args.shuffle_seed is not None else args.max_records,
        )
        if args.shuffle_seed is not None:
            rng = random.Random(args.shuffle_seed)
            rng.shuffle(records)
            records = records[: args.max_records]
        return records, {
            "source_type": "local_json",
            "source_path": str(args.source),
            "max_records": args.max_records,
            "shuffle_seed": args.shuffle_seed,
        }
    if args.hf_dataset:
        records = load_hf_records(
            args.hf_dataset,
            config=args.hf_config,
            split=args.hf_split,
            max_records=args.max_records,
            shuffle_seed=args.shuffle_seed,
        )
        return records, {
            "source_type": "huggingface_dataset",
            "dataset": args.hf_dataset,
            "config": args.hf_config,
            "split": args.hf_split,
            "max_records": args.max_records,
            "shuffle_seed": args.shuffle_seed,
        }
    raise SystemExit("Provide either --source or --hf-dataset.")


def build_traces(
    records: Sequence[dict[str, Any]],
    source_format: str,
    *,
    dev_percent: int,
    salt: str,
) -> list[dict[str, Any]]:
    if source_format == "auto":
        source_format = infer_source_format(records)
    if source_format == "2wiki":
        return build_2wiki_traces(records, dev_percent=dev_percent, salt=salt)
    if source_format == "musique":
        from fma.eval.knowledge_audit import build_musique_traces

        return build_musique_traces(records, dev_percent=dev_percent, salt=salt)
    raise SystemExit(f"Unsupported source format: {source_format}")


def infer_source_format(records: Sequence[dict[str, Any]]) -> str:
    if not records:
        return "2wiki"
    row = records[0]
    if "question_decomposition" in row and "paragraphs" in row:
        return "musique"
    return "2wiki"


def load_hf_records(
    dataset_id: str,
    *,
    config: str | None,
    split: str,
    max_records: int,
    shuffle_seed: int | None,
) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset  # type: ignore[import-untyped]
    except ImportError as exc:
        raise SystemExit("datasets package is required for --hf-dataset.") from exc

    if config:
        dataset = load_dataset(dataset_id, config, split=split)
    else:
        dataset = load_dataset(dataset_id, split=split)
    if shuffle_seed is not None:
        dataset = dataset.shuffle(seed=shuffle_seed)
    rows = []
    for idx, row in enumerate(dataset):
        if idx >= max_records:
            break
        rows.append(dict(row))
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
