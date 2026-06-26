"""Analyze fixed-schema separability in WebQSP trace-audit outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fma.io import load_records  # noqa: E402
from fma.trace_audit.separability import write_separability_report  # noqa: E402


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--importance-targets",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "webqsp_trace_audit_v1_test" / "replay" / "importance_targets.jsonl",
    )
    parser.add_argument(
        "--ranking-results",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "webqsp_trace_audit_v1_test" / "ranking" / "ranking_results.json",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "webqsp_trace_audit_v1_test" / "diagnostics" / "separability_report.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "webqsp_trace_audit_v1_test" / "diagnostics" / "separability_report.md",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    ranking = json.loads(args.ranking_results.read_text(encoding="utf-8"))
    report = write_separability_report(
        load_records(args.importance_targets),
        ranking,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "trace_count": report["trace_count"],
                "step_type_binary_separable": report["step_type_binary_separable"],
                "recommended_positioning": report["recommended_positioning"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
