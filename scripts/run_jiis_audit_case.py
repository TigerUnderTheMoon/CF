from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from jiis_countries_kg_validation_core import (  # noqa: E402
    DEFAULT_SEED,
    build_jiis_audit_case,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "paper" / "JIIS_submission" / "reports" / "jiis_audit_case")
    parser.add_argument("--n-traces", type=int, default=600)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--budget", type=float, default=0.25)
    parser.add_argument(
        "--label-cache",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "countries_kg_label_validation" / "countries_kg_labels_cached.json",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    report = build_jiis_audit_case(
        label_cache=args.label_cache,
        output_dir=args.output_dir,
        n_traces=args.n_traces,
        seed=args.seed,
        budget_fraction=args.budget,
    )
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "protocol_version": report["protocol_version"],
        "n_traces": args.n_traces,
        "unique_source_units": report["statistical_units"]["unique_source_unit_count"],
        "impact_coverage_at_k": report["metrics"]["impact_coverage_at_k"]["mean"],
        "flat_top_k": report["baselines"]["flat_top_k"]["metrics"]["impact_coverage_at_k"]["mean"],
        "greedy_max_coverage": report["baselines"]["greedy_max_coverage"]["metrics"]["impact_coverage_at_k"]["mean"],
    }, indent=2))


if __name__ == "__main__":
    main()
