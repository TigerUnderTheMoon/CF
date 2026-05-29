"""Write journal-grade FMA evaluation protocol artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.eval.journal_protocol import write_journal_protocol_outputs
from fma.eval.stage2_validation import write_stage2_validation_outputs


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic journal evaluation protocol artifacts.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--protocol-only",
        action="store_true",
        help="Write only protocol specification artifacts, without Stage 2 validation outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = write_journal_protocol_outputs(args.output_dir)
    if not args.protocol_only:
        paths.update(write_stage2_validation_outputs(args.output_dir))
    print(
        json.dumps(
            {name: str(path) for name, path in paths.items()},
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
