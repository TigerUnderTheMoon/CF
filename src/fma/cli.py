"""Small project CLI for reproducible FMA demo runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from fma.utils.config import load_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    try:
        result = run_cli(argv)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 1
    if isinstance(result, str):
        print(result, end="")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_cli(argv: Sequence[str] | None = None, *, timestamp: str | None = None) -> dict[str, Any] | str:
    parser = argparse.ArgumentParser(prog="fma", description="Run FMA demo phases.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser(
        "run",
        help="Compose a Hydra-style experiment config and create a run directory.",
    )
    run.add_argument("--config-name", default="base")
    run.set_defaults(func=run_config_command)

    run_pilot = subparsers.add_parser(
        "run-pilot",
        help="Compose a guarded pilot config and create a run directory.",
    )
    run_pilot.add_argument("--config-name", default="pilot/v2_1")
    run_pilot.set_defaults(func=run_config_command)

    phase5 = subparsers.add_parser("run-phase5", help="Run Phase 5 counterfactual attribution.")
    phase5.add_argument("--config", type=Path, required=True)
    phase5.add_argument("--dry-run", action="store_true")
    phase5.set_defaults(func=run_phase5_command)

    phase6 = subparsers.add_parser("run-phase6", help="Run Phase 6 structural diagnostics.")
    phase6.add_argument("--input", type=Path, required=True, help="Phase 5 output directory.")
    phase6.add_argument("--config", type=Path, default=Path("configs/demo.yaml"))
    phase6.add_argument("--dry-run", action="store_true")
    phase6.set_defaults(func=run_phase6_command)

    clean = subparsers.add_parser("clean-outputs", help="Archive legacy and failed outputs.")
    clean.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    clean.add_argument("--keep-core", action="store_true", help="Preserve outputs/phase{5,6,7}.")
    clean.add_argument("--archive-failed", action="store_true", help="Archive failed pilot routes.")
    clean.add_argument("--no-archive-legacy", action="store_true", help="Skip archiving other legacy outputs.")
    clean.set_defaults(func=run_clean_outputs_command)

    audit = subparsers.add_parser("audit", help="Query structured pilot audit logs.")
    audit_subparsers = audit.add_subparsers(dest="audit_command", required=True)

    audit_list = audit_subparsers.add_parser("list", help="List audit events.")
    audit_list.add_argument("--status", choices=["PASS", "FAIL", "WARN"])
    audit_list.add_argument("--route")
    audit_list.add_argument("--db", type=Path, default=Path("outputs") / "audit.db")
    audit_list.set_defaults(func=run_audit_command)

    audit_report = audit_subparsers.add_parser("report", help="Render an audit report.")
    audit_report.add_argument("--route", required=True)
    audit_report.add_argument("--format", choices=["markdown"], default="markdown")
    audit_report.add_argument("--db", type=Path, default=Path("outputs") / "audit.db")
    audit_report.set_defaults(func=run_audit_command)

    audit_stats = audit_subparsers.add_parser("stats", help="Aggregate audit statistics by route.")
    audit_stats.add_argument("--db", type=Path, default=Path("outputs") / "audit.db")
    audit_stats.set_defaults(func=run_audit_command)

    args, overrides = parser.parse_known_args(list(argv) if argv is not None else None)
    if args.command not in {"run", "run-pilot"} and overrides:
        parser.error(f"unrecognized arguments: {' '.join(overrides)}")
    return args.func(args, overrides=overrides, timestamp=timestamp)


def run_config_command(
    args: argparse.Namespace,
    *,
    overrides: Sequence[str],
    timestamp: str | None,
) -> dict[str, Any]:
    config = load_config(
        args.config_name,
        overrides=overrides,
        create_run_dir=True,
        timestamp=timestamp,
    )
    return {
        "command": args.command,
        "config_name": args.config_name,
        "experiment_name": config["experiment"]["name"],
        "objective": config["experiment"].get("objective"),
        "run_dir": config["paths"]["run_dir"],
        "overrides": list(overrides),
    }


def run_phase5_command(
    args: argparse.Namespace,
    *,
    overrides: Sequence[str],
    timestamp: str | None,
) -> dict[str, Any]:
    config = _load_config(args.config)
    section = _section(config, "phase5")
    runner_args = argparse.Namespace(
        traces=_path(section.get("traces", "data/traces/synthetic_100x8.json")),
        utility_annotations=_path(
            section.get("utility_annotations", "outputs/utility_annotations.jsonl")
        ),
        output_dir=_path(section.get("output_dir", "outputs/phase5")),
        figures_dir=_path(section.get("figures_dir", "outputs/phase5/figures")),
        seed=int(section.get("seed", 42)),
        utility_threshold=float(section.get("utility_threshold", 0.9)),
        dry_run=bool(args.dry_run),
    )
    _ensure_project_on_path()
    from scripts.run_counterfactual_attribution import run

    summary = run(runner_args)
    return {
        "phase": 5,
        "output_dir": str(runner_args.output_dir),
        "summary": summary,
    }


def run_clean_outputs_command(
    args: argparse.Namespace,
    *,
    overrides: Sequence[str],
    timestamp: str | None,
) -> dict[str, Any]:
    if not args.keep_core and not args.archive_failed:
        raise SystemExit(2)

    from fma.utils.cleanup import cleanup_outputs

    report = cleanup_outputs(
        args.repo_root,
        keep_core=args.keep_core,
        archive_failed=args.archive_failed,
        archive_legacy=not args.no_archive_legacy,
    )
    return {
        "command": "clean-outputs",
        "archived": report.archived,
        "preserved_core": report.preserved_core,
        "skipped": report.skipped,
    }


def run_phase6_command(
    args: argparse.Namespace,
    *,
    overrides: Sequence[str],
    timestamp: str | None,
) -> dict[str, Any]:
    config = _load_config(args.config)
    section = _section(config, "phase6")
    input_dir = _path(args.input)
    output_dir = _path(section.get("output_dir", "outputs/phase6"))
    figures_dir = _path(section.get("figures_dir", output_dir / "figures"))
    traces = _path(section.get("traces", "data/traces/synthetic_100x8.json"))
    necessity_scores = input_dir / "necessity_scores.jsonl"
    counterfactual_summary = input_dir / "counterfactual_summary.json"

    _ensure_project_on_path()
    from scripts.run_structural_attribution import run as run_structural_attribution
    from fma.graph.diagnostics import run_structural_diagnostics

    attribution_args = argparse.Namespace(
        traces=traces,
        necessity_scores=necessity_scores,
        counterfactual_summary=counterfactual_summary,
        output_dir=output_dir,
        figures_dir=figures_dir,
        utility_threshold=float(section.get("utility_threshold", 0.9)),
        removal_mode=str(section.get("removal_mode", "PRUNE")),
        dry_run=bool(args.dry_run),
    )
    phase6_summary = run_structural_attribution(attribution_args)

    diagnostics_args = argparse.Namespace(
        traces=traces,
        necessity_scores=necessity_scores,
        output_json=output_dir / "structural_diagnostics.json",
        output_md=output_dir / "structural_diagnostics.md",
        figures_dir=figures_dir,
    )
    diagnostics_summary = {} if args.dry_run else run_structural_diagnostics(diagnostics_args)

    return {
        "phase": 6,
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "structural_attribution": phase6_summary,
        "structural_diagnostics": {
            "num_graphs": diagnostics_summary.get("summary", {}).get("num_graphs", 0),
            "mean_zero_structural_necessity_fraction": diagnostics_summary.get(
                "cross_mode", {}
            ).get("mean_zero_structural_necessity_fraction", 0.0),
        },
    }


def run_audit_command(
    args: argparse.Namespace,
    *,
    overrides: Sequence[str],
    timestamp: str | None,
) -> str:
    from fma.pilot.audit import AuditLogger, format_event_list, format_route_stats

    logger = AuditLogger(db_path=args.db)
    if args.audit_command == "list":
        return format_event_list(logger.list_events(status=args.status, route_id=args.route))
    if args.audit_command == "report":
        return logger.render_markdown_report(args.route)
    if args.audit_command == "stats":
        return format_route_stats(logger.iter_route_summaries())
    raise SystemExit(f"Unsupported audit command: {args.audit_command}")


def _load_config(path: Path) -> dict[str, Any]:
    resolved = _path(path)
    if not resolved.exists():
        raise SystemExit(f"Config not found: {resolved}")
    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Config must be a mapping: {resolved}")
    return payload


def _section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name, {})
    if not isinstance(value, Mapping):
        raise SystemExit(f"Config section must be a mapping: {name}")
    return value


def _path(value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(str(value))
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _ensure_project_on_path() -> None:
    src_root = PROJECT_ROOT / "src"
    for path in (src_root, PROJECT_ROOT):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)


if __name__ == "__main__":
    raise SystemExit(main())
