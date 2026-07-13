"""Appendix B: PRM800K necessary-condition diagnosis.

This script intentionally does not promote PRM800K to the main experiment.
It reads the locked PRM800K validation and structure-only control reports and
emits a bounded diagnostic showing when undirected/sparse structural signals do
not support the structural-label premise.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "prm800k_strong_baselines"
LOCKED_REPORT = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash" / "locked_validation_report.json"
GRAPH_REPORT = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash" / "graph_necessity_analysis.json"
STRUCTURE_REPORT = PROJECT_ROOT / "outputs" / "structure_only_baseline" / "structure_only_baseline_report.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required locked report not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _round(value: float | int | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return round(value, digits)


def build_diagnosis(
    *,
    bootstrap_samples: int,
    locked_path: Path = LOCKED_REPORT,
    graph_path: Path = GRAPH_REPORT,
    structure_path: Path = STRUCTURE_REPORT,
) -> dict[str, Any]:
    locked = _read_json(locked_path)
    graph = _read_json(graph_path)
    structure = _read_json(structure_path)

    locked_metrics = locked["metrics"]["mean_spearman"]
    structure_results = structure["results"]
    tfidf_high = graph["by_trace_length"]["tfidf_graph_necessity"]["trace_length_high"]
    tfidf_overall = graph["overall"]["tfidf_graph_necessity"]

    return {
        "appendix": "Appendix B",
        "title": "Necessary Condition Diagnosis",
        "purpose": (
            "Boundary evidence for the structural-label extractor: SC-FMA-style "
            "structural labels require directed dependency flows with at least "
            "moderate logical edge density. PRM800K is retained only as a "
            "negative-condition diagnostic."
        ),
        "bootstrap_samples_requested": int(bootstrap_samples),
        "source_reports": {
            "locked_validation_report": str(locked_path),
            "graph_necessity_analysis": str(graph_path),
            "structure_only_baseline_report": str(structure_path),
        },
        "locked_prm800k": {
            "n_samples": int(locked["n_samples"]),
            "n_steps": int(locked["n_steps"]),
            "w_struct_spearman": _round(locked_metrics["w_struct"]),
            "raw_local_utility_spearman": _round(locked_metrics["raw_local_utility"]),
            "relative_position_spearman": _round(locked_metrics["relative_position"]),
        },
        "necessary_condition_proxy": {
            "requested_condition": "Trace Length > 20 and graph density < 0.05",
            "direct_joint_stratum_available": False,
            "proxy_used": (
                "locked high trace-length stratum with sparse TF-IDF graph-only "
                "necessity from the archived graph_necessity_analysis report"
            ),
            "graph_density_threshold": 0.05,
            "trace_length_threshold": 20,
            "tfidf_graph_only_rho_overall": _round(tfidf_overall),
            "tfidf_graph_only_rho_high_trace_length_proxy": _round(tfidf_high),
            "boundary_interpretation": (
                "In the locked PRM800K process-annotation route, undirected TF-IDF "
                "similarity lacks directed flow structure and collapses to near-zero "
                "rank correlation. This bounds the framework: structural labels are "
                "appropriate when logical dependency edges are present, not when the "
                "graph constructor supplies only sparse or directionless similarity."
            ),
        },
        "strong_baselines_context": {
            "w_struct": {
                "spearman": _round(structure_results["w_struct"]["mean_spearman"]),
                "mass_at_25": _round(structure_results["w_struct"]["mean_mass_at_25"]),
            },
            "structure_graph_position": {
                "spearman": _round(structure_results["structure_graph_position"]["mean_spearman"]),
                "mass_at_25": _round(structure_results["structure_graph_position"]["mean_mass_at_25"]),
            },
            "structure_graph_only": {
                "spearman": _round(structure_results["structure_graph"]["mean_spearman"]),
                "mass_at_25": _round(structure_results["structure_graph"]["mean_mass_at_25"]),
            },
            "raw_local_utility": {
                "spearman": _round(structure_results["raw_local_utility"]["mean_spearman"]),
                "mass_at_25": _round(structure_results["raw_local_utility"]["mean_mass_at_25"]),
            },
        },
        "claim_boundary": {
            "allowed": [
                "PRM800K necessary-condition boundary evidence",
                "graph-only failure under sparse or directionless similarity",
                "same-supervision context for w_struct and structure-only controls",
            ],
            "forbidden": [
                "main experiment",
                "production KG validation",
                "human usefulness",
                "causal effect",
                "structural-label robustness to arbitrary KG noise",
            ],
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    context = report["strong_baselines_context"]
    proxy = report["necessary_condition_proxy"]
    lines = [
        "# Appendix B: Necessary Condition Diagnosis",
        "",
        str(report["purpose"]),
        "",
        "## Locked PRM800K context",
        "",
        f"- Samples: {report['locked_prm800k']['n_samples']:,}",
        f"- Steps: {report['locked_prm800k']['n_steps']:,}",
        f"- w_struct Spearman: {report['locked_prm800k']['w_struct_spearman']:.4f}",
        "",
        "## Necessary-condition proxy",
        "",
        f"- Requested condition: {proxy['requested_condition']}",
        f"- Direct joint stratum available: {proxy['direct_joint_stratum_available']}",
        f"- TF-IDF graph-only rho, overall: {proxy['tfidf_graph_only_rho_overall']:.4f}",
        "- TF-IDF graph-only rho, high trace-length proxy: "
        f"{proxy['tfidf_graph_only_rho_high_trace_length_proxy']:.4f}",
        "",
        str(proxy["boundary_interpretation"]),
        "",
        "## Strong baseline context",
        "",
        "| Method | Spearman rho | Mass@25% |",
        "|---|---:|---:|",
    ]
    for key in ("w_struct", "structure_graph_position", "structure_graph_only", "raw_local_utility"):
        row = context[key]
        lines.append(f"| {key} | {row['spearman']:.4f} | {row['mass_at_25']:.4f} |")
    lines.append("")
    lines.append(
        "This appendix is boundary evidence only; it is not reported as a main structural-label result."
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = build_diagnosis(bootstrap_samples=args.bootstrap_samples)
    json_path = args.output_dir / "prm800k_necessary_condition_diagnosis.json"
    md_path = args.output_dir / "prm800k_necessary_condition_diagnosis.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "appendix": report["appendix"],
                "title": report["title"],
                "tfidf_graph_only_high_trace_length_proxy": report["necessary_condition_proxy"][
                    "tfidf_graph_only_rho_high_trace_length_proxy"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
