from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from jiis_countries_kg_validation_core import (  # noqa: E402
    DEFAULT_SEED,
    build_countries_kg_label_validation,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs" / "countries_kg_label_validation")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    random.seed(args.seed)
    try:
        import numpy as np

        np.random.seed(args.seed)
    except Exception:
        pass
    report = build_countries_kg_label_validation(seed=args.seed, output_dir=args.output_dir)
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "seed": args.seed,
        "bottleneck_f1": report["countries_kg"]["bottleneck_f1"],
        "redundancy_f1": report["countries_kg"]["redundancy_f1"],
        "articulation_point_bottleneck_f1": report["countries_kg"]["articulation_point_bottleneck_f1"],
        "redundancy_positive_count": report["countries_kg"]["redundancy_positive_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
