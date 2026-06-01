"""Rank-signal diagnostics for the real-task pilot."""

from __future__ import annotations

import random
from typing import Any, Mapping, Sequence

from fma.eval.diagnostics.correlation_metrics import spearman

from .candidate_score import CANDIDATE_FORBIDDEN_SOURCE_FIELDS, SCORE_NAME
from .coverage import audit_key_coverage, expected_span_keys


def build_rank_signal_report(
    records: Sequence[Mapping[str, Any]],
    *,
    delta_rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]] | None = None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Build rank diagnostics without promoting baselines to candidate evidence."""

    max_spans = int(config.get("replay", {}).get("max_spans_per_trace", 3))
    expected_keys = expected_span_keys(records, max_spans_per_trace=max_spans)
    delta_by_key = {
        _span_key(row): row
        for row in delta_rows
        if row.get("sample_id") is not None and "span_index" in row
    }
    baseline_by_key = {
        _span_key(row): row
        for row in baseline_rows
        if row.get("sample_id") is not None and "span_index" in row
    }
    candidate_by_key = {
        _span_key(row): row
        for row in candidate_rows or []
        if row.get("sample_id") is not None and "span_index" in row
    }
    clean_candidate_by_key = {
        key: row for key, row in candidate_by_key.items() if _candidate_row_is_clean(row)
    }
    observed_keys = set(delta_by_key).intersection(baseline_by_key)
    if candidate_rows is not None:
        observed_keys = observed_keys.intersection(clean_candidate_by_key)
    observed_rows = [{"sample_id": key[0], "span_index": key[1]} for key in sorted(observed_keys)]
    coverage = audit_key_coverage(expected_keys, observed_rows, artifact_name="rank_signal")

    bootstrap_config = config.get("nondeterministic_protocol", {}).get("bootstrap", {})
    resamples = int(bootstrap_config.get("resamples", 10000))
    confidence_level = float(bootstrap_config.get("confidence_level", 0.95))
    seed = int(bootstrap_config.get("random_seed", 20260530))
    baseline_diagnostics = _baseline_diagnostics(
        delta_by_key,
        baseline_by_key,
        resamples=resamples,
        confidence_level=confidence_level,
        seed=seed,
    )
    task_types = sorted({str(record.get("task_type") or "unknown") for record in records})
    primary_signal, pooled, per_task = _candidate_signal_diagnostics(
        delta_by_key,
        clean_candidate_by_key,
        candidate_rows=candidate_rows,
        coverage=coverage,
        task_types=task_types,
        resamples=resamples,
        confidence_level=confidence_level,
        seed=seed + 1000,
    )
    return {
        "coverage": coverage,
        "primary_signal": primary_signal,
        "pooled": pooled,
        "per_task": per_task,
        "baseline_diagnostics": baseline_diagnostics,
        "bootstrap": {
            "resamples": resamples,
            "confidence_level": confidence_level,
            "random_seed": seed,
        },
    }


def _candidate_signal_diagnostics(
    delta_by_key: Mapping[tuple[str, int], Mapping[str, Any]],
    candidate_by_key: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    candidate_rows: Sequence[Mapping[str, Any]] | None,
    coverage: Mapping[str, Any],
    task_types: Sequence[str],
    resamples: int,
    confidence_level: float,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if candidate_rows is None:
        return _missing_candidate_signal(task_types, "primary candidate score missing")
    if not coverage.get("coverage_pass"):
        return _missing_candidate_signal(
            task_types,
            "candidate score coverage incomplete or contains target leakage",
        )

    paired = []
    for key in sorted(set(delta_by_key).intersection(candidate_by_key)):
        score = _candidate_score(candidate_by_key[key])
        if score is None:
            continue
        delta = float(delta_by_key[key].get("delta_u", 0.0))
        task_type = str(delta_by_key[key].get("task_type") or candidate_by_key[key].get("task_type") or "unknown")
        paired.append((score, delta, task_type))

    primary_signal = {
        "name": "structurally_calibrated_fma",
        "available": True,
        "n": len(paired),
        "candidate_artifact": "structurally_calibrated_fma_scores.jsonl",
        "score_field": _candidate_score_field(candidate_by_key.values()),
        "target_leakage_status": "clean",
    }
    pooled_pairs = [(score, delta) for score, delta, _task_type in paired]
    pooled = _candidate_spearman_metrics(
        pooled_pairs,
        resamples=resamples,
        confidence_level=confidence_level,
        seed=seed,
    )
    per_task = {}
    for task_index, task_type in enumerate(task_types):
        task_pairs = [
            (score, delta)
            for score, delta, row_task_type in paired
            if row_task_type == task_type
        ]
        per_task[task_type] = _candidate_spearman_metrics(
            task_pairs,
            resamples=resamples,
            confidence_level=confidence_level,
            seed=seed + task_index + 1,
        )
    return primary_signal, pooled, per_task


def _missing_candidate_signal(
    task_types: Sequence[str],
    reason: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        {
            "name": "structurally_calibrated_fma",
            "available": False,
            "reason": reason,
        },
        {
            "spearman_ci_lower_gt_zero": False,
            "reason": reason,
        },
        {
            task_type: {
                "spearman_ci_lower_gt_zero": False,
                "reason": reason,
            }
            for task_type in task_types
        },
    )


def _candidate_spearman_metrics(
    paired: Sequence[tuple[float, float]],
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    left = [item[0] for item in paired]
    right = [item[1] for item in paired]
    rho = spearman(left, right) if len(paired) >= 2 else 0.0
    ci95 = _bootstrap_spearman_ci(
        paired,
        resamples=resamples,
        confidence_level=confidence_level,
        seed=seed,
    )
    return {
        "n": len(paired),
        "spearman_rho": rho,
        "spearman_ci95": ci95,
        "spearman_ci_lower_gt_zero": bool(ci95[0] > 0.0),
    }


def _candidate_row_is_clean(row: Mapping[str, Any]) -> bool:
    score_name = row.get("score_name") or row.get("candidate_name") or SCORE_NAME
    if score_name != SCORE_NAME:
        return False
    leakage_status = row.get("leakage_status") or row.get("target_leakage_status") or "clean"
    if leakage_status != "clean":
        return False
    used = set(row.get("source_fields_used") or [])
    if used.intersection(CANDIDATE_FORBIDDEN_SOURCE_FIELDS):
        return False
    if row.get("forbidden_fields_used"):
        return False
    return _candidate_score(row) is not None


def _candidate_score(row: Mapping[str, Any]) -> float | None:
    if "score" in row:
        return float(row["score"])
    if "candidate_score" in row:
        return float(row["candidate_score"])
    return None


def _candidate_score_field(rows: Sequence[Mapping[str, Any]]) -> str:
    return "score" if all("score" in row for row in rows) else "candidate_score"


def build_bootstrap_ci_report(rank_signal_report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the standalone bootstrap CI report written beside rank signal."""

    return {
        "primary_signal": dict(rank_signal_report.get("primary_signal", {})),
        "baseline_diagnostics": dict(rank_signal_report.get("baseline_diagnostics", {})),
        "bootstrap": dict(rank_signal_report.get("bootstrap", {})),
    }


def _baseline_diagnostics(
    delta_by_key: Mapping[tuple[str, int], Mapping[str, Any]],
    baseline_by_key: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    score_names = sorted(
        {
            score_name
            for row in baseline_by_key.values()
            for score_name in (row.get("scores") or {})
        }
    )
    diagnostics = {}
    for score_name in score_names:
        paired = []
        for key in sorted(set(delta_by_key).intersection(baseline_by_key)):
            scores = baseline_by_key[key].get("scores") or {}
            if score_name not in scores:
                continue
            paired.append((float(scores[score_name]), float(delta_by_key[key].get("delta_u", 0.0))))
        left = [item[0] for item in paired]
        right = [item[1] for item in paired]
        rho = spearman(left, right) if len(paired) >= 2 else 0.0
        ci95 = _bootstrap_spearman_ci(
            paired,
            resamples=resamples,
            confidence_level=confidence_level,
            seed=seed + len(diagnostics),
        )
        diagnostics[score_name] = {
            "n": len(paired),
            "spearman_rho": rho,
            "spearman_ci95": ci95,
            "spearman_ci_lower_gt_zero": bool(ci95[0] > 0.0),
            "used_as_primary_signal": False,
        }
    return diagnostics


def _bootstrap_spearman_ci(
    paired: Sequence[tuple[float, float]],
    *,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> list[float]:
    if len(paired) < 2 or resamples <= 0:
        value = spearman([item[0] for item in paired], [item[1] for item in paired]) if paired else 0.0
        return [float(value), float(value)]
    rng = random.Random(seed)
    values = []
    for _index in range(resamples):
        sample = [paired[rng.randrange(len(paired))] for _item in paired]
        values.append(spearman([item[0] for item in sample], [item[1] for item in sample]))
    values.sort()
    alpha = max(0.0, min(1.0, 1.0 - confidence_level))
    low_index = int((alpha / 2.0) * (len(values) - 1))
    high_index = int((1.0 - alpha / 2.0) * (len(values) - 1))
    return [float(values[low_index]), float(values[high_index])]


def _span_key(row: Mapping[str, Any]) -> tuple[str, int]:
    return str(row.get("sample_id") or ""), int(row.get("span_index", 0) or 0)


__all__ = ["build_bootstrap_ci_report", "build_rank_signal_report"]
