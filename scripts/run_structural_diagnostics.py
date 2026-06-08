"""CLI entry point for structural reflection diagnostics.

All business logic lives in ``fma.graph.diagnostics``. This script only
parses arguments and delegates to the installable package.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fma.graph.diagnostics import PROJECT_ROOT, main, run_structural_diagnostics


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Delegate parsed arguments to the package implementation."""
    return run_structural_diagnostics(args)


def run_from_config(
    *,
    config_name: str = "phase6/graph",
    overrides: list[str] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Compose a config and delegate through the script-level runner."""
    from fma.utils.config import load_config

    config = load_config(
        config_name,
        overrides=overrides or [],
        create_run_dir=True,
        timestamp=timestamp,
    )
    phase6 = config.get("phase6", {})
    inputs = phase6.get("inputs", {}) if isinstance(phase6, dict) else {}
    outputs = phase6.get("outputs", {}) if isinstance(phase6, dict) else {}
    run_dir = Path(config["paths"]["run_dir"])
    figures_dir = Path(outputs.get("figures_dir", "figures"))
    if not figures_dir.is_absolute():
        figures_dir = run_dir / figures_dir
    removal_mode = str(
        config.get("intervention_mode") or phase6.get("default_intervention_mode", "PRUNE")
    )
    args = argparse.Namespace(
        traces=_project_path(inputs.get("traces", "data/traces/synthetic_100x8.json")),
        necessity_scores=_project_path(
            inputs.get("necessity_scores", "outputs/necessity_scores.jsonl")
        ),
        output_json=run_dir
        / outputs.get("structural_diagnostics_json", "structural_diagnostics.json"),
        output_md=run_dir / outputs.get("structural_diagnostics_md", "structural_diagnostics.md"),
        figures_dir=figures_dir,
        removal_mode=removal_mode,
        interactive=bool(phase6.get("interactive", False)),
    )
    return run(args)


def _project_path(value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(str(value))
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


if __name__ == "__main__":
    result = main(sys.argv[1:])
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0)
