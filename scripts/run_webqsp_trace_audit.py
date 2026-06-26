"""Run the WebQSP reasoning-trace audit experiment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fma.trace_audit.pipeline import run_pipeline  # noqa: E402

DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "webqsp"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--source-split", choices=("train", "test"), default="train")
    parser.add_argument("--max-records", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source or _default_source(args.source_split)
    output_dir = args.output_dir or _default_output_dir(args.source_split)
    report = run_pipeline(
        source=source,
        output_dir=output_dir,
        source_split=args.source_split,
        max_records=args.max_records,
    )
    print(f"WebQSP trace-audit route -> {output_dir}")
    print(f"Traces: {report['trace_count']} Steps: {report['step_count']}")
    return 0


def _default_source(source_split: str) -> Path:
    suffix = "train" if source_split == "train" else "test"
    return DEFAULT_RAW_DIR / f"WebQSP.{suffix}.json"


def _default_output_dir(source_split: str) -> Path:
    suffix = "train" if source_split == "train" else "test"
    return PROJECT_ROOT / "outputs" / f"webqsp_trace_audit_v1_{suffix}"


if __name__ == "__main__":
    raise SystemExit(main())
