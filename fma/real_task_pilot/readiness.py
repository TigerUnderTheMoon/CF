"""Readiness gates for deciding whether to scale beyond the pilot."""

from __future__ import annotations

from typing import Any, Mapping

from .coverage import all_coverage_passes, coverage_gates


FAILURE_CODES = (
    "PREFLIGHT_FAIL_MODEL",
    "PREFLIGHT_FAIL_SCHEMA",
    "PREFLIGHT_FAIL_TAG",
    "PREFLIGHT_FAIL_DRIFT",
    "PREFLIGHT_FAIL_COST",
    "PILOT_FAIL_COVERAGE",
    "PILOT_FAIL_SPAN",
    "PILOT_FAIL_REPLAY",
    "PILOT_FAIL_SIGNAL",
)


def build_readiness_audit(
    *,
    preflight_report: Mapping[str, Any],
    valid_trace_count: int,
    span_validity_rate: float,
    replay_success_rate: float,
    baseline_leakage_clean: bool,
    cost_report_complete: bool,
    tests_passed: bool,
    hygiene_clean: bool,
    signal_report: Mapping[str, Any] | None = None,
    artifact_coverage: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    codes = list(preflight_report.get("failure_codes", []))
    if valid_trace_count < 300 or span_validity_rate < 0.90:
        codes.append("PILOT_FAIL_SPAN")
    coverage_gate = coverage_gates(artifact_coverage)
    coverage_pass = all_coverage_passes(artifact_coverage)
    if artifact_coverage is not None and not coverage_pass:
        codes.append("PILOT_FAIL_COVERAGE")
    if replay_success_rate < 0.85 or not coverage_gate["replay_coverage"]:
        codes.append("PILOT_FAIL_REPLAY")
    signal_gate = _signal_gate(signal_report or {})
    if not signal_gate["expand_to_top_tier_scale"]:
        codes.append("PILOT_FAIL_SIGNAL")
    if not baseline_leakage_clean:
        codes.append("PILOT_FAIL_BASELINE_LEAKAGE")
    if not cost_report_complete:
        codes.append("PREFLIGHT_FAIL_COST")
    if not tests_passed:
        codes.append("PILOT_FAIL_TESTS")
    if not hygiene_clean:
        codes.append("PILOT_FAIL_HYGIENE")
    unique_codes = sorted(set(codes))
    pilot_pass = not unique_codes
    return {
        "status": "PILOT_PASS" if pilot_pass else "PILOT_BLOCKED",
        "pilot_pass": pilot_pass,
        "failure_codes": unique_codes,
        "artifact_coverage": dict(artifact_coverage or {}),
        "gates": {
            "preflight": preflight_report.get("status") == "pass",
            "valid_trace_count": valid_trace_count >= 300,
            "span_validity_rate": span_validity_rate >= 0.90,
            "replay_success_rate": replay_success_rate >= 0.85 and coverage_gate["replay_coverage"],
            "baseline_leakage_clean": baseline_leakage_clean,
            "cost_report_complete": cost_report_complete,
            "tests_passed": tests_passed,
            "hygiene_clean": hygiene_clean,
            **coverage_gate,
            **signal_gate,
        },
    }


def _signal_gate(signal_report: Mapping[str, Any]) -> dict[str, bool]:
    per_task = signal_report.get("per_task", {})
    task_passes = [
        bool(metrics.get("spearman_ci_lower_gt_zero"))
        for metrics in per_task.values()
        if isinstance(metrics, Mapping)
    ]
    pooled = signal_report.get("pooled", {})
    pooled_pass = bool(pooled.get("spearman_ci_lower_gt_zero"))
    at_least_one_task = any(task_passes)
    all_tasks = bool(task_passes) and all(task_passes)
    return {
        "all_task_ci_lower_gt_zero": all_tasks,
        "pooled_ci_lower_gt_zero": pooled_pass,
        "at_least_one_task_pass": at_least_one_task,
        "expand_to_top_tier_scale": all_tasks or (pooled_pass and at_least_one_task),
    }
