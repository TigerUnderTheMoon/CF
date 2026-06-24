"""Collect reviewer V2 runtime and reproducibility metadata.

This script records environment and command metadata for the reviewer V2
experiments. It does not run the experiments and makes zero API calls.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from reviewer_v2_common import (  # noqa: E402
    CLAIM_BOUNDARY,
    COMMON_LIMITATIONS,
    DEFAULT_OUTPUT_ROOT,
    SEED_LIST,
    Timer,
    common_metadata,
    environment_info,
    git_info,
    write_json,
    write_markdown,
)


DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "runtime_reproducibility"
FROZEN_AUDIT_REPORT = (
    PROJECT_ROOT
    / "outputs"
    / "real_task_v3_6_prm800k_hash"
    / "audit_prioritization_report.json"
)
EXPERIMENTS = {
    "scu_component_contribution": {
        "route": "SCU Component Contribution",
        "command": "python scripts/run_scu_component_contribution.py --samples-per-seed 200",
        "output_dir": DEFAULT_OUTPUT_ROOT / "scu_component_contribution",
        "report": DEFAULT_OUTPUT_ROOT / "scu_component_contribution" / "scu_component_contribution.json",
        "bootstrap_samples": 1000,
    },
    "graph_construction_ablation": {
        "route": "Graph Construction Ablation",
        "command": "python scripts/run_graph_construction_ablation.py",
        "output_dir": DEFAULT_OUTPUT_ROOT / "graph_construction_ablation",
        "report": DEFAULT_OUTPUT_ROOT / "graph_construction_ablation" / "graph_construction_ablation.json",
        "bootstrap_samples": 0,
    },
    "failure_taxonomy": {
        "route": "Failure Taxonomy",
        "command": (
            "python scripts/build_failure_taxonomy.py "
            "--input-artifact D:/CF/outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json "
            "--output-dir D:/CF/outputs/reviewer_v2_experiments/failure_taxonomy/ "
            "--taxonomy-rules structural_over_correction,redundancy_misclassification,"
            "bottleneck_over_protection,weak_utility_anchor,low_signal_or_tie "
            "--max-cases 5 --output-format appendix_page"
        ),
        "output_dir": DEFAULT_OUTPUT_ROOT / "failure_taxonomy",
        "report": DEFAULT_OUTPUT_ROOT / "failure_taxonomy" / "failure_taxonomy.json",
        "bootstrap_samples": 0,
    },
}
DEFAULT_FIELDS = [
    "command",
    "output_dir",
    "git_commit",
    "python_version",
    "os_platform",
    "cpu_model",
    "core_count",
    "peak_memory",
    "seed_list",
    "n_traces",
    "n_steps",
    "elapsed_seconds",
    "bootstrap_samples",
    "api_calls",
    "frozen_artifacts",
    "known_deviations",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--experiments",
        default=",".join(EXPERIMENTS),
        help="Comma-separated reviewer V2 experiment names to summarize.",
    )
    parser.add_argument(
        "--fields",
        default=",".join(DEFAULT_FIELDS),
        help="Comma-separated fields to include in each structured row.",
    )
    parser.add_argument("--fixture", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    timer = Timer.start()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    env = _runtime_environment()
    git = git_info()
    selected = _parse_csv(args.experiments)
    fields = _parse_csv(args.fields)
    experiments = [
        _experiment_row(
            name,
            config=EXPERIMENTS[name],
            env=env,
            git=git,
            fields=fields,
            fixture=args.fixture,
        )
        for name in selected
    ]
    report = {
        **common_metadata(
            output_dir=args.output_dir,
            evidence_level="diagnostic_support",
            source_artifacts=[
                "git",
                "python_runtime",
                "platform_runtime",
                str(FROZEN_AUDIT_REPORT),
            ],
        ),
        "experiment": "runtime_reproducibility",
        "requested_experiments": selected,
        "requested_fields": fields,
        "git_commit": git["git_commit"],
        "git_dirty": git["git_dirty"],
        "zero_api_calls": True,
        "elapsed_seconds": timer.elapsed(),
        "experiments": experiments,
    }
    write_json(args.output_dir / "runtime_reproducibility.json", report)
    write_markdown(
        args.output_dir / "runtime_reproducibility.md",
        _render_markdown(report),
    )
    print(f"Wrote {args.output_dir / 'runtime_reproducibility.json'}")
    print(f"Wrote {args.output_dir / 'runtime_reproducibility.md'}")


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _runtime_environment() -> dict[str, Any]:
    env = environment_info()
    env.update(
        {
            "python_version": _python_version(),
            "os_platform": platform.platform(),
            "cpu_model": platform.processor()
            or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
            "core_count": os.cpu_count() or 0,
            "peak_memory": _peak_memory(),
        }
    )
    return env


def _python_version() -> str:
    result = subprocess.run(
        [sys.executable, "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return (result.stdout or result.stderr).strip() or sys.version.split()[0]


def _peak_memory() -> str:
    try:
        import psutil  # type: ignore[import-not-found]

        memory = psutil.Process().memory_info()
        peak = getattr(memory, "peak_wset", None)
        if peak:
            return f"{round(float(peak) / (1024.0 * 1024.0), 3)} MB"
    except Exception:
        pass
    return "N/A"


def _experiment_row(
    name: str,
    *,
    config: Mapping[str, Any],
    env: Mapping[str, Any],
    git: Mapping[str, Any],
    fields: Sequence[str],
    fixture: bool,
) -> dict[str, Any]:
    if name not in EXPERIMENTS:
        raise ValueError(f"Unknown experiment: {name}")
    report = _read_json(Path(config["report"]))
    stats = _experiment_stats(name, report, fixture=fixture)
    known_deviations = list(stats["known_deviations"])
    if env["peak_memory"] != "N/A":
        known_deviations.append(
            "Peak memory reflects the reproducibility collection process via psutil; "
            "the original experiment reports did not log historical per-run peak memory."
        )
    full_row = {
        "name": name,
        "route": config["route"],
        "command": config["command"],
        "output_dir": str(Path(config["output_dir"]).resolve()),
        "output_directory": str(Path(config["output_dir"]).resolve()),
        "git_commit": f"{git['git_commit']} ({'dirty' if git['git_dirty'] else 'clean'})",
        "git_dirty": git["git_dirty"],
        "python_version": env["python_version"],
        "os_platform": env["os_platform"],
        "platform": env["os_platform"],
        "cpu_model": env["cpu_model"],
        "cpu": env["cpu_model"],
        "core_count": env["core_count"],
        "peak_memory": env["peak_memory"],
        "peak_memory_mb": env.get("peak_memory_mb"),
        "seed_list": stats["seed_list"],
        "n_traces": stats["n_traces"],
        "n_steps": stats["n_steps"],
        "elapsed_seconds": stats["elapsed_seconds"],
        "bootstrap_samples": config["bootstrap_samples"],
        "api_calls": 0,
        "api_calls_label": "zero",
        "frozen_artifacts": stats["frozen_artifacts"],
        "frozen_artifacts_used": stats["frozen_artifacts"],
        "known_deviations": known_deviations,
    }
    compatibility_fields = [
        "output_directory",
        "git_dirty",
        "platform",
        "cpu",
        "peak_memory_mb",
        "frozen_artifacts_used",
    ]
    ordered_fields = list(dict.fromkeys(["name", "route", *fields, *compatibility_fields]))
    return {key: full_row[key] for key in ordered_fields if key in full_row}


def _experiment_stats(
    name: str,
    report: Mapping[str, Any],
    *,
    fixture: bool,
) -> dict[str, Any]:
    source_artifacts = [str(Path(item).resolve()) if Path(item).exists() else str(item) for item in report.get("source_artifacts", [])]
    if name == "graph_construction_ablation":
        return {
            "seed_list": list(report.get("seed_list", SEED_LIST)),
            "n_traces": int(report.get("n_traces", 0)),
            "n_steps": int(report.get("n_steps", 0)),
            "elapsed_seconds": report.get("elapsed_seconds"),
            "frozen_artifacts": source_artifacts,
            "known_deviations": [
                "Mechanism ablation on the existing synthetic structural attribution artifacts.",
                "Topical-edge comparisons are diagnostic and are not production scalability claims.",
            ],
        }
    if name == "scu_component_contribution":
        samples_per_seed = int(report.get("samples_per_seed", 0))
        seeds = list(report.get("seed_list", SEED_LIST))
        steps_by_seed = _scu_steps_by_seed(seeds, samples_per_seed)
        return {
            "seed_list": seeds,
            "n_traces": samples_per_seed,
            "n_steps": round(sum(steps_by_seed.values()) / len(steps_by_seed)) if steps_by_seed else 0,
            "n_steps_by_seed": steps_by_seed,
            "elapsed_seconds": report.get("elapsed_seconds"),
            "frozen_artifacts": source_artifacts,
            "known_deviations": [
                "Uses deterministic synthetic SCU component-contribution samples generated inside the script.",
                "Reported n_steps is the mean generated step count per seed.",
                "This summary is not a production scalability claim.",
            ],
        }
    if name == "failure_taxonomy":
        audit = _read_json(FROZEN_AUDIT_REPORT)
        artifacts = [str(FROZEN_AUDIT_REPORT.resolve()), *source_artifacts]
        return {
            "seed_list": [],
            "n_traces": int(report.get("n_samples", audit.get("n_samples", 0))),
            "n_steps": int(audit.get("n_steps", 0)),
            "elapsed_seconds": report.get("elapsed_seconds"),
            "frozen_artifacts": list(dict.fromkeys(artifacts)),
            "known_deviations": [
                "Data-driven diagnostic taxonomy over the locked PRM800K split.",
                "Representative cases support variant selection guidance only.",
                "Frozen artifacts are read-only inputs.",
                "This summary is not a production scalability claim.",
            ],
        }
    raise ValueError(f"Unsupported experiment: {name}")


def _scu_steps_by_seed(seeds: Sequence[int], samples_per_seed: int) -> dict[int, int]:
    from run_scu_component_contribution import generate_synthetic_data

    counts: dict[int, int] = {}
    for seed in seeds:
        samples = generate_synthetic_data(seed=int(seed), n_samples=samples_per_seed)
        counts[int(seed)] = int(sum(len(sample["ground_truth"]) for sample in samples))
    return counts


def _render_markdown(report: Mapping[str, Any]) -> list[str]:
    git_state = "dirty" if report["git_dirty"] else "clean"
    lines = [
        "# Runtime & Reproducibility Summary",
        "",
        f"- Claim boundary: `{CLAIM_BOUNDARY}`",
        "- Evidence level: `diagnostic_support`",
        "- API calls: `zero` for all reviewer V2 experiments.",
        f"- Git commit: `{report['git_commit']}` ({git_state})",
        "- Scope: reproducibility and audit transparency only; not a production scalability claim.",
        "",
        "| Route | Samples | Steps | Seeds | Elapsed (s) | Hardware | API Calls |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for row in report["experiments"]:
        seeds = "N/A" if not row.get("seed_list") else str(len(row["seed_list"]))
        hardware = f"CPU ({row['core_count']} cores)"
        lines.append(
            f"| {row['route']} | {row['n_traces']:,} | {row['n_steps']:,} | {seeds} | "
            f"{float(row['elapsed_seconds']):.4f} | {hardware} | zero |"
        )
    lines.extend(
        [
            "",
            "## Detailed Records",
            "",
            "| Route | Command | Output directory | Python | OS/platform | CPU model | Peak memory | Frozen artifacts | Known deviations |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in report["experiments"]:
        artifacts = "<br>".join(f"`{item}`" for item in row["frozen_artifacts"])
        deviations = "<br>".join(row["known_deviations"])
        lines.append(
            f"| {row['route']} | `{row['command']}` | `{row['output_dir']}` | "
            f"{row['python_version']} | {row['os_platform']} | {row['cpu_model']} | "
            f"{row['peak_memory']} | {artifacts} | {deviations} |"
        )
    lines.extend(["", "Known limitations:"])
    lines.extend(f"- {item}" for item in COMMON_LIMITATIONS)
    return lines


if __name__ == "__main__":
    main()
