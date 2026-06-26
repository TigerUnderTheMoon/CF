"""Run data-audit checks for a completed WebQSP trace-audit route."""

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
from fma.trace_audit import audit_traces  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs" / "webqsp_trace_audit_v1")
    args = parser.parse_args(argv)

    traces_path = args.output_dir / "traces" / "reasoning_traces.jsonl"
    replay_path = args.output_dir / "replay" / "replay_results.jsonl"
    audit = audit_traces(
        load_records(traces_path),
        load_records(replay_path) if replay_path.exists() else [],
    )
    metrics_dir = args.output_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "data_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    print(f"WebQSP trace-audit data audit -> {metrics_dir / 'data_audit.json'}")
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
