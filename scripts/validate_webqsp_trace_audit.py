"""Validate WebQSP trace-audit trace artifacts."""

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
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--replay-results", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    traces = load_records(args.traces)
    replay = load_records(args.replay_results) if args.replay_results else []
    audit = audit_traces(traces, replay)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
