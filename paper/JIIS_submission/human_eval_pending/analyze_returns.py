"""Analyze real returned JIIS human-evaluation sheets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--returns-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.returns_dir.glob("evaluator_*/rating_sheet_evaluator_*.csv"))
    rows = []
    for path in files:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                row["source_file"] = str(path)
                rows.append(row)
    result = {
        "status": "pending_real_returns",
        "n_files": len(files),
        "n_rows": len(rows),
        "file_hashes": {str(path): sha256(path) for path in files},
        "claim_boundary": "do_not_report_without_real_return_provenance",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if files else 1


if __name__ == "__main__":
    raise SystemExit(main())
