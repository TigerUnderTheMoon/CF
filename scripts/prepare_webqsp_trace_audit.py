"""Prepare WebQSP samples and local KG slices for trace audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fma.io import write_records  # noqa: E402
from fma.trace_audit import WebQSPLoader, WebQSPPreprocessor  # noqa: E402

DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "webqsp"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--source-split", choices=("train", "test"), default="train")
    parser.add_argument("--max-records", type=int, default=None)
    args = parser.parse_args(argv)

    source = args.source or _default_source(args.source_split)
    output_dir = args.output_dir or _default_output_dir(args.source_split)
    rows = WebQSPLoader().load(source, max_records=args.max_records)
    samples = [WebQSPPreprocessor().build_sample(row, source_split=args.source_split) for row in rows]
    write_records(samples, output_dir / "samples.jsonl")
    write_records([{"sample_id": row["sample_id"], "local_kg": row["local_kg"]} for row in samples], output_dir / "local_kg_slices.jsonl")
    print(f"Prepared {len(samples)} WebQSP trace-audit samples -> {output_dir}")
    return 0


def _default_source(source_split: str) -> Path:
    suffix = "train" if source_split == "train" else "test"
    return DEFAULT_RAW_DIR / f"WebQSP.{suffix}.json"


def _default_output_dir(source_split: str) -> Path:
    suffix = "train" if source_split == "train" else "test"
    return PROJECT_ROOT / "data" / "processed" / f"webqsp_trace_audit_v1_{suffix}"


if __name__ == "__main__":
    raise SystemExit(main())
