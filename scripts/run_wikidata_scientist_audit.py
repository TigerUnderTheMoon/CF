from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fma.eval.wikidata_scientist_audit_runner import run_wikidata_scientist_audit  # noqa: E402


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Wikidata scientist controlled knowledge-maintenance experiment."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "wikidata_scientist_audit.yaml",
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("experiment config must be a YAML mapping")
    config["output_dir"] = _project_path(config["output_dir"])
    config["countries_report_path"] = _project_path(config["countries_report_path"])
    config["extraction"]["cache_path"] = _project_path(config["extraction"]["cache_path"])
    return config


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    report = run_wikidata_scientist_audit(load_config(args.config))
    print(
        json.dumps(
            {
                "output_dir": str(load_config(args.config)["output_dir"]),
                "source_mode": report["source"]["mode"],
                "nodes": report["graph_statistics"]["raw_graph"]["node_count"],
                "edges": report["graph_statistics"]["raw_graph"]["edge_count"],
                "revision_cases": len(report["case_studies"]),
            },
            indent=2,
        )
    )


def _project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    main()
