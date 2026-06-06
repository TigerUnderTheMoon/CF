"""Prepare DVC-compatible synthetic trace inputs from existing JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path


def convert_json_array_to_jsonl(source: Path, output: Path) -> int:
    """Convert a JSON array file to JSON Lines format.

    Args:
        source: path to a JSON file containing an array of objects.
        output: destination JSONL path.

    Returns:
        Number of records written.
    """
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{source} must contain a JSON array")

    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in data]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Convert synthetic traces JSON to JSONL")
    parser.add_argument("--source", type=Path, default=Path("data/traces/synthetic_100x8.json"))
    parser.add_argument("--output", type=Path, default=Path("data/synthetic_traces.jsonl"))
    args = parser.parse_args(argv)

    count = convert_json_array_to_jsonl(args.source, args.output)
    print(f"Wrote {count} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
