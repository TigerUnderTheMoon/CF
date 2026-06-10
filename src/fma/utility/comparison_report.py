"""Comparison report generation for FMA vs PRM vs baselines."""

from __future__ import annotations

import json
from pathlib import Path

from .filtering_experiment import ComparisonReport


def write_report(
    report: ComparisonReport,
    output_dir: str | Path,
) -> Path:
    """Write a ComparisonReport to disk as JSON + human-readable summary."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "comparison_report.json"
    summary_path = output_path / "comparison_summary.txt"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(report.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)

    summary = _format_summary(report)
    summary_path.write_text(summary, encoding="utf-8")

    return json_path


def _format_summary(report: ComparisonReport) -> str:
    lines: list[str] = []
    lines.append(f"=== {report.experiment_name} ===")
    lines.append(f"Traces: {report.total_traces}  Spans: {report.total_spans}")
    lines.append(f"Methods: {', '.join(report.methods)}")
    lines.append(f"Keep ratios: {', '.join(f'{r:.2f}' for r in report.keep_ratios)}")
    lines.append("")

    lines.append("--- Accuracy by Method and Keep Ratio ---")
    for method in sorted(report.accuracy_by_method_and_ratio):
        ratio_dict = report.accuracy_by_method_and_ratio[method]
        parts = [f"{k}={v:.3f}" for k, v in sorted(ratio_dict.items())]
        lines.append(f"  {method}: {', '.join(parts)}")
    lines.append("")

    if report.rank_correlations:
        lines.append("--- Rank Correlations ---")
        for pair_name, corr_dict in report.rank_correlations.items():
            parts = [f"{k}={v:.4f}" for k, v in sorted(corr_dict.items())]
            lines.append(f"  {pair_name}: {', '.join(parts)}")
        lines.append("")

    if report.agreement_kappa:
        lines.append("--- Agreement (Cohen's kappa) ---")
        for pair_name, kappa in report.agreement_kappa.items():
            lines.append(f"  {pair_name}: {kappa:.4f}")
        lines.append("")

    lines.append("--- Claims Allowed ---")
    for claim, allowed in sorted(report.claims_allowed.items()):
        status = "ALLOWED" if allowed else "FORBIDDEN"
        lines.append(f"  {claim}: {status}")
    lines.append("")

    if not report.claims_allowed.get("prm_superiority", False):
        lines.append("NOTE: PRM superiority claims are FORBIDDEN.")
    if not report.claims_allowed.get("fma_superiority", False):
        lines.append("NOTE: FMA superiority claims are FORBIDDEN.")
    lines.append("This report only describes correlations and ranking agreement.")

    return "\n".join(lines)


def print_report_summary(report: ComparisonReport) -> None:
    """Print a human-readable summary to stdout."""
    print(_format_summary(report))


__all__ = ["ComparisonReport", "print_report_summary", "write_report"]
