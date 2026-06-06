"""Preregistration-safe helpers for the real_task_v3 validation route."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .fresh_holdout import (
    BLOCKED_INSUFFICIENT_FRESH_ROWS,
    MANIFEST_OVERLAP_CLEAN,
    OVERLAP_AUDIT_FAIL,
    alias_hash,
    build_current_pilot_overlap_index,
    dataset_config_split_source_index,
    has_non_empty_aliases,
    normalized_text_hash,
)
from .metrics import normalize_gsm8k_answer, normalized_token_f1


REAL_TASK_V3_PREREGISTRATION_ONLY = "REAL_TASK_V3_PREREGISTRATION_ONLY"
REAL_TASK_V3_CONTRACT_CLEAN = "REAL_TASK_V3_CONTRACT_CLEAN"
REAL_TASK_V3_CONTRACT_BLOCKED = "REAL_TASK_V3_CONTRACT_BLOCKED"
V3_DENSE_TARGET_RELIABILITY_PASS = "V3_DENSE_TARGET_RELIABILITY_PASS"
V3_DENSE_TARGET_RELIABILITY_FAIL = "V3_DENSE_TARGET_RELIABILITY_FAIL"
V3_GLOBAL_PASS = "REAL_TASK_V3_GLOBAL_PASS"
V3_TASK_SPECIFIC_ONLY = "REAL_TASK_V3_TASK_SPECIFIC_ONLY"
V3_VALIDATION_FAIL = "REAL_TASK_V3_VALIDATION_FAIL"

EXPECTED_V3_HARD_CAPS = {
    "route_api_calls_max": 90000,
    "smoke_api_calls_max": 6500,
    "dev_api_calls_max": 32000,
    "locked_api_calls_max": 52000,
    "downstream_api_calls_max": 10000,
    "route_cost_usd_max": 5000,
    "per_call_timeout_seconds": 90,
    "max_repair_attempts_per_failed_request": 2,
    "total_repair_fraction_max": 0.03,
}

GSM8K_WEIGHTS = {
    "repeated_numeric_exact": 0.60,
    "numeric_proximity": 0.40,
}

HOTPOTQA_WEIGHTS = {
    "alias_token_f1": 0.50,
    "reference_only_f1": 0.2777777778,
    "support_overlap": 0.2222222222,
}

HOTPOTQA_SURFACE_MATCH_THRESHOLDS = {
    "alias_token_f1_gt": 0.8,
    "support_overlap_lt": 0.2,
}

DENSE_TARGET_THRESHOLDS = {
    "unique_utility_values_min": 10,
    "fractional_utility_fraction_min": 0.25,
    "residual_variance_fraction_min": 0.15,
    "nonzero_delta_fraction_min_by_task": {
        "gsm8k": 0.25,
        "hotpotqa": 0.35,
    },
}

W_STRUCT_ALLOWED_FEATURES = {
    "raw_local_utility",
    "structural_necessity",
    "raw_structural_interaction",
    "redundancy",
    "compensation",
    "bottleneck_flag",
    "span_type",
    "relative_position",
    "span_length",
    "task_type",
    "question_difficulty_proxy",
}

W_STRUCT_FORBIDDEN_SOURCE_FIELDS = {
    "correctness",
    "original_utility",
    "intervened_utility",
    "delta_u",
    "replay_outcome",
    "final_answer",
    "reference_similarity_after_generation",
    "rank_metric",
    "rank_signal",
    "original_score",
    "intervened_score",
    "reference_answer_similarity_after_generation",
}

V3_REQUIRED_NON_OVERLAP_KEYS = (
    "sample_id",
    "task_id",
    "dataset_config_split_source_index",
    "normalized_question_hash",
    "reference_answer_hash",
    "non_empty_alias_hash",
)

V3_MANIFEST_FIELDS = (
    "dataset",
    "config",
    "split",
    "source_index",
    "sample_id",
    "task_id",
    "dataset_config_split_source_index",
    "normalized_question_hash",
    "reference_answer_hash",
    "non_empty_alias_hash",
    "question",
    "reference_answer",
    "aliases",
    "task_type",
    "split_role",
    "target_name",
    "selection_seed",
    "manifest_item_hash",
)

NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def audit_v3_config_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the v3 config remains preregistration-only and claim-safe."""

    experiment = _mapping(config.get("experiment"))
    hard_caps = _mapping(config.get("hard_caps"))
    splits = _mapping(config.get("splits"))
    locked = _mapping(splits.get("locked_validation"))
    claim_policy = _mapping(config.get("claim_policy"))
    execution = _mapping(config.get("execution_boundary"))

    observed_caps = {key: hard_caps.get(key) for key in EXPECTED_V3_HARD_CAPS}
    checks = {
        "scope": experiment.get("current_task_scope") == REAL_TASK_V3_PREREGISTRATION_ONLY,
        "current_status": claim_policy.get("current_status_remains") == "PILOT_BLOCKED",
        "hard_caps": observed_caps == EXPECTED_V3_HARD_CAPS,
        "locked_scale": locked.get("sample_count_by_task")
        == {"gsm8k": 1000, "hotpotqa": 1000},
        "api_disabled": execution.get("api_execution_allowed") is False,
        "validation_claim_disabled": claim_policy.get("validation_or_pass_claim_allowed") is False,
        "prm_claim_disabled": claim_policy.get("prm_filtering_improvement_claim_allowed") is False,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "status": REAL_TASK_V3_CONTRACT_CLEAN if not blockers else REAL_TASK_V3_CONTRACT_BLOCKED,
        "scope": experiment.get("current_task_scope"),
        "current_status_remains": claim_policy.get("current_status_remains"),
        "api_execution_allowed": execution.get("api_execution_allowed"),
        "validation_or_pass_claim_allowed": claim_policy.get("validation_or_pass_claim_allowed"),
        "prm_filtering_improvement_claim_allowed": claim_policy.get(
            "prm_filtering_improvement_claim_allowed"
        ),
        "hard_caps": observed_caps,
        "checks": checks,
        "blockers": blockers,
    }


def score_gsm8k_v3_utility(
    *,
    predictions: Sequence[str],
    reference_answer: str,
) -> dict[str, Any]:
    """Score GSM8K with the preregistered v3 dense utility target."""

    if not predictions:
        return {
            "utility": 0.0,
            "repeated_numeric_exact": 0.0,
            "numeric_proximity": 0.0,
            "weights": dict(GSM8K_WEIGHTS),
            "prediction_count": 0,
        }
    ref_norm = normalize_gsm8k_answer(reference_answer)
    exact_values = []
    proximity_values = []
    for prediction in predictions:
        pred_norm = normalize_gsm8k_answer(str(prediction))
        exact_values.append(1.0 if pred_norm == ref_norm else 0.0)
        proximity_values.append(_numeric_proximity(pred_norm, ref_norm))
    repeated_exact = _mean(exact_values)
    proximity = _mean(proximity_values)
    utility = (
        GSM8K_WEIGHTS["repeated_numeric_exact"] * repeated_exact
        + GSM8K_WEIGHTS["numeric_proximity"] * proximity
    )
    return {
        "utility": float(utility),
        "repeated_numeric_exact": repeated_exact,
        "numeric_proximity": proximity,
        "weights": dict(GSM8K_WEIGHTS),
        "prediction_count": len(predictions),
    }


def score_hotpotqa_v3_utility(
    *,
    prediction: str,
    reference_answer: str,
    aliases: Iterable[str] | None = None,
    predicted_supports: Iterable[str] | None = None,
    reference_supports: Iterable[str] | None = None,
    semantic_equivalence: float = 0.0,
) -> dict[str, Any]:
    """Score HotpotQA with the preregistered v3 dense utility target."""

    prediction_text = str(prediction)
    references = [str(reference_answer), *[str(alias) for alias in aliases or [] if str(alias).strip()]]
    alias_token_f1 = max(
        (normalized_token_f1(prediction_text, reference) for reference in references),
        default=0.0,
    )
    reference_only_f1 = normalized_token_f1(prediction_text, str(reference_answer))
    support_overlap = _support_overlap(predicted_supports or [], reference_supports or [])
    utility = (
        HOTPOTQA_WEIGHTS["alias_token_f1"] * alias_token_f1
        + HOTPOTQA_WEIGHTS["reference_only_f1"] * reference_only_f1
        + HOTPOTQA_WEIGHTS["support_overlap"] * support_overlap
    )
    return {
        "utility": float(utility),
        "alias_token_f1": float(alias_token_f1),
        "reference_only_f1": float(reference_only_f1),
        "support_overlap": float(support_overlap),
        "semantic_judge_gate": "disabled_by_target_revision",
        "weights": dict(HOTPOTQA_WEIGHTS),
    }


def build_hotpotqa_surface_match_risk_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    thresholds: Mapping[str, float] | None = None,
    max_examples: int = 20,
) -> dict[str, Any]:
    """Report high lexical match with weak support overlap after removing semantic judge."""

    active = dict(HOTPOTQA_SURFACE_MATCH_THRESHOLDS)
    if thresholds:
        active.update({key: float(value) for key, value in thresholds.items()})
    risk_rows = []
    for row in rows:
        alias_score = float(row.get("alias_token_f1", 0.0) or 0.0)
        support_score = float(row.get("support_overlap", 0.0) or 0.0)
        if (
            alias_score > float(active["alias_token_f1_gt"])
            and support_score < float(active["support_overlap_lt"])
        ):
            risk_rows.append(
                {
                    "sample_id": row.get("sample_id"),
                    "task_id": row.get("task_id"),
                    "alias_token_f1": alias_score,
                    "support_overlap": support_score,
                }
            )
    return {
        "artifact": "hotpotqa_surface_match_risk_report",
        "thresholds": active,
        "row_count": len(rows),
        "risk_count": len(risk_rows),
        "risk_fraction": len(risk_rows) / len(rows) if rows else 0.0,
        "examples": risk_rows[:max_examples],
        "claim_boundary": "diagnostic_risk_only",
    }


def build_v3_split_manifest(
    source_rows_by_task: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    config: Mapping[str, Any],
    split_name: str,
    sample_count_by_task: Mapping[str, int],
    overlap_sources: Mapping[str, Iterable[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build a target-blind v3 split manifest and six-key non-overlap audit."""

    overlap_index = build_current_pilot_overlap_index(overlap_sources)
    seed = int(config.get("experiment", {}).get("seed", 0) or 0)
    target_name = str(config.get("utility_target", {}).get("target_name") or "dense_real_task_delta_u_v3")

    selected_by_task: dict[str, list[dict[str, Any]]] = {}
    task_reports: dict[str, dict[str, Any]] = {}
    overlap_counts = {key: 0 for key in V3_REQUIRED_NON_OVERLAP_KEYS}
    selected_overlap_counts = {key: 0 for key in V3_REQUIRED_NON_OVERLAP_KEYS}
    overlap_examples: dict[str, list[dict[str, Any]]] = {
        key: [] for key in V3_REQUIRED_NON_OVERLAP_KEYS
    }

    for task_type in sorted(sample_count_by_task):
        candidates = [
            _v3_candidate_manifest_item(
                row,
                task_type=task_type,
                split_name=split_name,
                seed=seed,
                target_name=target_name,
            )
            for row in source_rows_by_task.get(task_type, [])
        ]
        candidates.sort(key=lambda item: (str(item.get("task_type")), int(item.get("source_index", 0))))
        eligible = []
        excluded = 0
        for item in candidates:
            overlaps = _v3_overlaps_for_item(item, overlap_index)
            if overlaps:
                excluded += 1
                for key, hits in overlaps.items():
                    overlap_counts[key] += 1
                    if len(overlap_examples[key]) < 10:
                        overlap_examples[key].append(
                            {
                                "sample_id": item.get("sample_id"),
                                "task_id": item.get("task_id"),
                                "overlap_key": key,
                                "source_hits": list(hits)[:5],
                            }
                        )
                continue
            eligible.append(item)

        required = int(sample_count_by_task[task_type])
        selected = eligible[:required]
        selected_by_task[task_type] = selected
        for item in selected:
            for key in _v3_overlaps_for_item(item, overlap_index):
                selected_overlap_counts[key] += 1

        if len(eligible) < required:
            task_status = BLOCKED_INSUFFICIENT_FRESH_ROWS
        elif any(selected_overlap_counts.values()):
            task_status = OVERLAP_AUDIT_FAIL
        else:
            task_status = MANIFEST_OVERLAP_CLEAN
        task_reports[task_type] = {
            "configured_sample_count": required,
            "source_row_count": len(candidates),
            "excluded_overlap_count": excluded,
            "eligible_count": len(eligible),
            "selected_count": len(selected),
            "status": task_status,
        }

    insufficient = any(
        report["status"] == BLOCKED_INSUFFICIENT_FRESH_ROWS for report in task_reports.values()
    )
    selected_overlap = any(selected_overlap_counts.values())
    if insufficient:
        status = BLOCKED_INSUFFICIENT_FRESH_ROWS
        manifest: list[dict[str, Any]] = []
    elif selected_overlap:
        status = OVERLAP_AUDIT_FAIL
        manifest = []
    else:
        status = MANIFEST_OVERLAP_CLEAN
        manifest = [
            _v3_finalize_manifest_item(item)
            for task_type in sorted(selected_by_task)
            for item in selected_by_task[task_type]
        ]

    audit = {
        "status": status,
        "split_name": split_name,
        "overlap_clean": status == MANIFEST_OVERLAP_CLEAN,
        "hard_stop": status != MANIFEST_OVERLAP_CLEAN,
        "blocker": status if status != MANIFEST_OVERLAP_CLEAN else None,
        "current_status_remains": "PILOT_BLOCKED",
        "route": "real_task_v3",
        "manifest_rows": len(manifest),
        "target_name": target_name,
        "no_api_run": True,
        "no_replay": True,
        "no_scoring": True,
        "no_prm_filtering_claim": True,
        "validation_or_pass_claim_allowed": False,
        "required_non_overlap_keys": list(V3_REQUIRED_NON_OVERLAP_KEYS),
        "fresh_manifest_fields": list(V3_MANIFEST_FIELDS),
        "selection_seed": seed,
        "tasks": task_reports,
        "overlap_sources": overlap_index["source_reports"],
        "overlap_summary": {
            "candidate_pool_overlaps_by_key": overlap_counts,
            "selected_overlaps_by_key": selected_overlap_counts,
            "total_overlaps_by_key": overlap_counts,
        },
        "overlap_examples": overlap_examples,
    }
    return manifest, audit


def build_v3_route_manifests(
    source_rows_by_task: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    config: Mapping[str, Any],
    split_sample_counts: Mapping[str, Mapping[str, int]],
    overlap_sources: Mapping[str, Iterable[Mapping[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Build disjoint v3 split manifests in order, adding prior splits to exclusions."""

    manifests: dict[str, list[dict[str, Any]]] = {}
    split_audits: dict[str, dict[str, Any]] = {}
    active_overlap_sources: dict[str, Iterable[Mapping[str, Any]]] = dict(overlap_sources)

    for split_name, sample_count_by_task in split_sample_counts.items():
        manifest, audit = build_v3_split_manifest(
            source_rows_by_task,
            config=config,
            split_name=split_name,
            sample_count_by_task=sample_count_by_task,
            overlap_sources=active_overlap_sources,
        )
        manifests[split_name] = manifest
        split_audits[split_name] = audit
        active_overlap_sources[f"real_task_v3_{split_name}"] = manifest

    blocker_splits = [
        split
        for split, audit in split_audits.items()
        if audit.get("status") != MANIFEST_OVERLAP_CLEAN
    ]
    blocker_statuses = {
        split: str(split_audits[split].get("status"))
        for split in blocker_splits
    }
    if not blocker_splits:
        status = MANIFEST_OVERLAP_CLEAN
    elif any(value == OVERLAP_AUDIT_FAIL for value in blocker_statuses.values()):
        status = OVERLAP_AUDIT_FAIL
    else:
        status = BLOCKED_INSUFFICIENT_FRESH_ROWS
    return manifests, {
        "status": status,
        "route": "real_task_v3",
        "hard_stop": bool(blocker_splits),
        "blocker_splits": blocker_splits,
        "blocker_statuses": blocker_statuses,
        "split_audits": split_audits,
        "required_non_overlap_keys": list(V3_REQUIRED_NON_OVERLAP_KEYS),
        "current_status_remains": "PILOT_BLOCKED",
    }


def build_dense_target_reliability_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit whether dense utility adds enough target variation before full validation."""

    active_thresholds = dict(DENSE_TARGET_THRESHOLDS)
    if thresholds:
        active_thresholds.update(thresholds)
    by_task: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[str(row.get("task_type") or "unknown")].append(row)

    per_task = {}
    for task_type in sorted(by_task):
        task_rows = by_task[task_type]
        utilities = [float(row.get("utility", 0.0) or 0.0) for row in task_rows]
        binary = [bool(row.get("binary_correct", False)) for row in task_rows]
        deltas = [float(row.get("delta_u", 0.0) or 0.0) for row in task_rows]
        nonzero_threshold = _nonzero_threshold(active_thresholds, task_type)
        unique_count = len({round(value, 12) for value in utilities})
        fractional_fraction = _fraction(
            value for value in utilities if not math.isclose(value, 0.0) and not math.isclose(value, 1.0)
        )
        fractional_fraction /= len(utilities) if utilities else 1
        nonzero_delta_fraction = _fraction(abs(delta) > 0.0 for delta in deltas)
        nonzero_delta_fraction /= len(deltas) if deltas else 1
        residual_variance = _residual_variance_fraction(utilities, binary)
        checks = {
            "unique_utility_values": unique_count
            >= int(active_thresholds["unique_utility_values_min"]),
            "fractional_utility_fraction": fractional_fraction
            >= float(active_thresholds["fractional_utility_fraction_min"]),
            "nonzero_delta_fraction": nonzero_delta_fraction >= nonzero_threshold,
            "residual_variance_fraction": residual_variance
            >= float(active_thresholds["residual_variance_fraction_min"]),
        }
        per_task[task_type] = {
            "n": len(task_rows),
            "unique_utility_values": unique_count,
            "fractional_utility_fraction": float(fractional_fraction),
            "nonzero_delta_fraction": float(nonzero_delta_fraction),
            "residual_variance_fraction": float(residual_variance),
            "nonzero_delta_fraction_min": nonzero_threshold,
            "gate_pass": all(checks.values()),
            "checks": checks,
        }
    pass_all = bool(per_task) and all(task["gate_pass"] for task in per_task.values())
    return {
        "status": V3_DENSE_TARGET_RELIABILITY_PASS
        if pass_all
        else V3_DENSE_TARGET_RELIABILITY_FAIL,
        "thresholds": active_thresholds,
        "per_task": per_task,
    }


def validate_w_struct_feature_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Reject w_struct rows that use target-side fields or unregistered features."""

    checks = []
    target_leaking = False
    feature_contract_failed = False
    for row in rows:
        features = _mapping(row.get("features"))
        feature_names = set(features)
        unknown_features = sorted(feature_names.difference(W_STRUCT_ALLOWED_FEATURES))
        used_fields = set(row.get("source_fields_used") or [])
        forbidden = sorted(used_fields.intersection(W_STRUCT_FORBIDDEN_SOURCE_FIELDS))
        target_leaking = target_leaking or bool(forbidden)
        feature_contract_failed = feature_contract_failed or bool(unknown_features)
        checks.append(
            {
                "sample_id": row.get("sample_id"),
                "span_index": row.get("span_index"),
                "unknown_features": unknown_features,
                "forbidden_source_fields_used": forbidden,
                "status": "target_leaking"
                if forbidden
                else ("feature_contract_failed" if unknown_features else "clean"),
            }
        )
    if target_leaking:
        status = "target_leaking"
    elif feature_contract_failed:
        status = "feature_contract_failed"
    else:
        status = "clean"
    return {
        "status": status,
        "allowed_features": sorted(W_STRUCT_ALLOWED_FEATURES),
        "forbidden_source_fields": sorted(W_STRUCT_FORBIDDEN_SOURCE_FIELDS),
        "checks": checks,
    }


def build_w_struct_stability_report(
    *,
    folds: Sequence[Mapping[str, Any]],
    zero_rate_by_task: Mapping[str, float],
) -> dict[str, Any]:
    """Apply sparse-aware dev calibration gates for the structural profile block."""

    raw_positive = sum(
        1 for fold in folds if float(fold.get("raw_local_utility_direction", 0.0) or 0.0) > 0.0
    )
    structural_nonnegative = sum(
        1 for fold in folds if float(fold.get("structural_profile_direction", 0.0) or 0.0) >= 0.0
    )
    structural_positive_ci = sum(
        1
        for fold in folds
        if _ci_lower(fold.get("structural_profile_ci95")) > 0.0
    )
    mean_spearman = _mean(
        [float(fold.get("spearman_diff_over_raw", 0.0) or 0.0) for fold in folds]
    )
    mean_brier = _mean(
        [float(fold.get("brier_improvement_over_base_rate", 0.0) or 0.0) for fold in folds]
    )
    calibration_slopes = [
        float(fold.get("calibration_slope", 0.0) or 0.0) for fold in folds
    ]
    zero_rates = {str(task): float(value) for task, value in zero_rate_by_task.items()}
    task_zero_rates = {
        task: value for task, value in zero_rates.items() if task != "pooled"
    }
    pooled_zero_rate = (
        zero_rates["pooled"]
        if "pooled" in zero_rates
        else _mean(list(task_zero_rates.values()))
    )
    zero_rate_gate_pass = bool(task_zero_rates) and pooled_zero_rate <= 0.90 and all(
        value <= 0.90 for value in task_zero_rates.values()
    )
    checks = {
        "raw_local_utility_positive_folds": raw_positive >= 4,
        "structural_profile_nonnegative_folds": structural_nonnegative >= 4,
        "structural_profile_positive_ci_folds": structural_positive_ci >= 2,
        "structural_profile_zero_rate": zero_rate_gate_pass,
        "structural_profile_zero_rate_pooled": bool(task_zero_rates)
        and pooled_zero_rate <= 0.90,
        "structural_profile_zero_rate_per_task": bool(task_zero_rates)
        and all(value <= 0.90 for value in task_zero_rates.values()),
        "mean_spearman_diff_over_raw": mean_spearman > 0.03,
        "brier_improvement_over_base_rate": mean_brier >= 0.01,
        "calibration_slope": bool(calibration_slopes)
        and all(0.7 <= value <= 1.3 for value in calibration_slopes),
    }
    return {
        "artifact": "w_struct_stability_report",
        "gate_pass": all(checks.values()),
        "checks": checks,
        "fold_counts": {
            "raw_local_utility_positive": raw_positive,
            "structural_profile_nonnegative": structural_nonnegative,
            "structural_profile_positive_ci": structural_positive_ci,
            "folds": len(folds),
        },
        "mean_spearman_diff_over_raw": mean_spearman,
        "brier_improvement_over_base_rate": mean_brier,
        "pooled_zero_rate": pooled_zero_rate,
        "zero_rate_by_task": zero_rates,
        "sparse_signal_warning": pooled_zero_rate > 0.80
        or any(value > 0.80 for value in task_zero_rates.values()),
    }


def build_synthetic_real_profile_alignment_report(
    *,
    synthetic_profile: Mapping[str, Any],
    real_task_profile: Mapping[str, Any],
    sparse_warning_zero_rate: float = 0.80,
) -> dict[str, Any]:
    """Compare synthetic structural diagnostics to real-task dev profiles."""

    profile_comparisons = {
        "zero_rate": _profile_metric_comparison(
            synthetic_profile,
            real_task_profile,
            synthetic_key="structural_zero_rate",
            real_key="structural_zero_rate",
        ),
        "bottleneck_ratio": _profile_metric_comparison(
            synthetic_profile,
            real_task_profile,
            synthetic_key="bottleneck_ratio",
            real_key="bottleneck_ratio",
        ),
        "redundancy_density": _profile_metric_comparison(
            synthetic_profile,
            real_task_profile,
            synthetic_key="redundancy_density",
            real_key="redundancy_density",
        ),
        "compensation": _profile_metric_comparison(
            synthetic_profile,
            real_task_profile,
            synthetic_key="compensation",
            real_key="compensation",
        ),
        "local_utility_alignment": _profile_metric_comparison(
            synthetic_profile,
            real_task_profile,
            synthetic_key="local_utility_alignment",
            real_key="local_utility_alignment",
        ),
    }
    zero_rate = profile_comparisons["zero_rate"]
    return {
        "artifact": "synthetic_vs_real_structural_profile_alignment",
        "profile_comparisons": profile_comparisons,
        "zero_rate": zero_rate,
        "bottleneck_ratio": profile_comparisons["bottleneck_ratio"],
        "redundancy_density": profile_comparisons["redundancy_density"],
        "compensation": profile_comparisons["compensation"],
        "local_utility_alignment": profile_comparisons["local_utility_alignment"],
        "sparse_signal_warning_threshold": sparse_warning_zero_rate,
        "sparse_signal_warning": zero_rate["real_task"] > sparse_warning_zero_rate,
        "claim_boundary": "migration_validity_diagnostic_only",
    }


def build_v3_decision_report(
    *,
    task_gate_pass: Mapping[str, bool],
    pooled_gate_pass: bool,
    paired_improvement_ci95: Sequence[float],
    blockers: Sequence[str],
    task_blockers: Mapping[str, Sequence[str]] | None = None,
    holm_corrected_task_gate_pass: Mapping[str, bool] | None = None,
    explicit_task_specific_downstream_allowed: bool = False,
    downstream_gate_pass: bool | None = None,
) -> dict[str, Any]:
    """Apply the preregistered v3 locked-validation decision tree."""

    ci_lower = float(paired_improvement_ci95[0]) if paired_improvement_ci95 else 0.0
    paired_pass = ci_lower > 0.0
    task_pass_values = {str(task): bool(value) for task, value in task_gate_pass.items()}
    all_tasks_pass = bool(task_pass_values) and all(task_pass_values.values())
    passing_tasks = [task for task, passed in task_pass_values.items() if passed]
    any_task_pass = bool(passing_tasks)
    blocker_list = list(blockers)
    task_blocker_values = {
        str(task): [str(blocker) for blocker in values]
        for task, values in (task_blockers or {}).items()
    }
    holm_values = {
        str(task): bool(value)
        for task, value in (holm_corrected_task_gate_pass or task_pass_values).items()
    }
    strict_scenario_b_pass = False
    if len(passing_tasks) == 1:
        passing_task = passing_tasks[0]
        failed_tasks = [task for task, passed in task_pass_values.items() if not passed]
        strict_scenario_b_pass = (
            bool(failed_tasks)
            and all(not task_blocker_values.get(task) for task in failed_tasks)
            and holm_values.get(passing_task, False)
        )

    if blocker_list or not paired_pass or not pooled_gate_pass or not any_task_pass:
        status = V3_VALIDATION_FAIL
    elif all_tasks_pass:
        status = V3_GLOBAL_PASS
    elif strict_scenario_b_pass:
        status = V3_TASK_SPECIFIC_ONLY
    else:
        status = V3_VALIDATION_FAIL

    diagnostic_allowed = status in {V3_GLOBAL_PASS, V3_TASK_SPECIFIC_ONLY}
    global_allowed = status == V3_GLOBAL_PASS
    downstream_request_allowed = global_allowed or (
        status == V3_TASK_SPECIFIC_ONLY and explicit_task_specific_downstream_allowed
    )
    downstream_allowed = bool(downstream_gate_pass) and global_allowed
    return {
        "status": status,
        "task_gate_pass": task_pass_values,
        "task_blockers": task_blocker_values,
        "holm_corrected_task_gate_pass": holm_values,
        "pooled_gate_pass": bool(pooled_gate_pass),
        "paired_improvement_ci95": list(paired_improvement_ci95),
        "paired_improvement_gate_pass": paired_pass,
        "strict_scenario_b_gate_pass": strict_scenario_b_pass,
        "blockers": blocker_list,
        "diagnostic_validation_claim_allowed": diagnostic_allowed,
        "task_specific_claim_allowed": diagnostic_allowed,
        "global_claim_allowed": global_allowed,
        "downstream_gate_request_allowed": downstream_request_allowed,
        "prm_filtering_improvement_claim_allowed": downstream_allowed,
        "downstream_gate_pass": bool(downstream_gate_pass),
        "claim_boundary": "diagnostic_only"
        if diagnostic_allowed and not downstream_allowed
        else ("downstream_allowed" if downstream_allowed else "no_validation_claim"),
    }


def _numeric_proximity(prediction: str, reference: str) -> float:
    pred_value = _last_number(prediction)
    ref_value = _last_number(reference)
    if pred_value is None or ref_value is None:
        return 0.0
    ratio = (abs(pred_value) + 1.0) / (abs(ref_value) + 1.0)
    return _clamp01(math.exp(-abs(math.log(ratio))))


def _v3_candidate_manifest_item(
    row: Mapping[str, Any],
    *,
    task_type: str,
    split_name: str,
    seed: int,
    target_name: str,
) -> dict[str, Any]:
    source_index = int(row.get("source_index", 0) or 0)
    dataset = str(row.get("dataset") or row.get("source_dataset") or task_type)
    dataset_config = str(row.get("config") or row.get("source_config") or "")
    split = str(row.get("split") or row.get("source_split") or "")
    sample_id = str(row.get("sample_id") or f"{task_type}-{source_index:05d}")
    task_id = str(row.get("task_id") or row.get("id") or row.get("_id") or sample_id)
    aliases = list(row.get("aliases") or [])
    question = str(row.get("question") or "")
    reference_answer = str(row.get("reference_answer") or row.get("answer") or "")
    item = {
        "dataset": dataset,
        "config": dataset_config,
        "split": split,
        "source_index": source_index,
        "sample_id": sample_id,
        "task_id": task_id,
        "question": question,
        "reference_answer": reference_answer,
        "aliases": aliases,
        "task_type": task_type,
        "split_role": split_name,
        "target_name": target_name,
        "selection_seed": seed,
    }
    item["dataset_config_split_source_index"] = dataset_config_split_source_index(item)
    item["normalized_question_hash"] = normalized_text_hash(question)
    item["reference_answer_hash"] = normalized_text_hash(reference_answer)
    item["non_empty_alias_hash"] = alias_hash(aliases) if has_non_empty_aliases(aliases) else ""
    return item


def _v3_finalize_manifest_item(item: Mapping[str, Any]) -> dict[str, Any]:
    finalized = {key: item.get(key) for key in V3_MANIFEST_FIELDS if key != "manifest_item_hash"}
    finalized["manifest_item_hash"] = normalized_text_hash(
        "|".join(str(finalized.get(key, "")) for key in V3_MANIFEST_FIELDS if key != "manifest_item_hash")
    )
    return finalized


def _v3_overlaps_for_item(
    item: Mapping[str, Any],
    overlap_index: Mapping[str, Any],
) -> dict[str, list[str]]:
    index = overlap_index["index"]
    keys = {
        "sample_id": str(item.get("sample_id") or ""),
        "task_id": str(item.get("task_id") or ""),
        "dataset_config_split_source_index": str(item.get("dataset_config_split_source_index") or ""),
        "normalized_question_hash": str(item.get("normalized_question_hash") or ""),
        "reference_answer_hash": str(item.get("reference_answer_hash") or ""),
    }
    if has_non_empty_aliases(item.get("aliases")):
        keys["non_empty_alias_hash"] = str(item.get("non_empty_alias_hash") or "")
    overlaps = {}
    for key, value in keys.items():
        index_key = "alias_hash" if key == "non_empty_alias_hash" else key
        if value and value in index.get(index_key, {}):
            overlaps[key] = sorted(index[index_key][value])
    return overlaps


def build_circuit_breaker_report(
    attempts: Sequence[Mapping[str, Any]],
    *,
    consecutive_infra_error_limit: int = 10,
    rolling_window: int = 50,
    rolling_infra_error_fraction_max: float = 0.20,
) -> dict[str, Any]:
    """Return whether endpoint health must stop due infrastructure errors."""

    normalized = [str(attempt.get("error_class") or "success") for attempt in attempts]
    rolling_error_fraction = 0.0
    if len(normalized) >= rolling_window:
        window = normalized[-rolling_window:]
        rolling_error_fraction = sum(1 for value in window if value == "infra_error") / rolling_window
        if rolling_error_fraction > rolling_infra_error_fraction_max:
            return {
                "hard_stop": True,
                "reason": "rolling_infra_error_fraction",
                "rolling_window": rolling_window,
                "rolling_infra_error_fraction": rolling_error_fraction,
            }

    consecutive = 0
    max_consecutive = 0
    for value in normalized:
        if value == "infra_error":
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
    if max_consecutive >= consecutive_infra_error_limit:
        return {
            "hard_stop": True,
            "reason": "consecutive_infra_errors",
            "consecutive_infra_errors": max_consecutive,
        }
    return {
        "hard_stop": False,
        "reason": None,
        "consecutive_infra_errors": max_consecutive,
        "rolling_infra_error_fraction": rolling_error_fraction,
    }


def build_smoke_calibrated_cost_forecast(
    *,
    smoke_attempts: Sequence[Mapping[str, Any]],
    planned_request_counts: Mapping[str, int],
    route_cost_cap_usd: float,
    input_price_per_million_tokens: float = 0.14,
    output_price_per_million_tokens: float = 0.28,
) -> dict[str, Any]:
    """Forecast v3 route costs from observed smoke token usage."""

    prompt_tokens = [
        int(_mapping(attempt.get("usage")).get("prompt_tokens", 0) or 0)
        for attempt in smoke_attempts
    ]
    completion_tokens = [
        int(_mapping(attempt.get("usage")).get("completion_tokens", 0) or 0)
        for attempt in smoke_attempts
    ]
    token_quantiles = {
        "prompt_tokens": _quantile_report(prompt_tokens),
        "completion_tokens": _quantile_report(completion_tokens),
    }
    stage_forecasts = {}
    total_p95 = 0.0
    for stage, request_count in planned_request_counts.items():
        p95_cost = _request_cost(
            token_quantiles["prompt_tokens"]["p95"],
            token_quantiles["completion_tokens"]["p95"],
            input_price_per_million_tokens=input_price_per_million_tokens,
            output_price_per_million_tokens=output_price_per_million_tokens,
        ) * int(request_count)
        stage_forecasts[str(stage)] = {
            "planned_requests": int(request_count),
            "p95_cost_usd": p95_cost,
        }
        total_p95 += p95_cost
    return {
        "artifact": "smoke_calibrated_cost_forecast",
        "token_quantiles": token_quantiles,
        "stage_forecasts": stage_forecasts,
        "route_p95_cost_usd": total_p95,
        "route_cost_cap_usd": float(route_cost_cap_usd),
        "cost_gate_pass": total_p95 <= float(route_cost_cap_usd),
    }


def build_locked_cost_checkpoint(
    *,
    requests_completed: int,
    cost_used_usd: float,
    planned_locked_requests: int,
    locked_stage_cost_cap_usd: float,
) -> dict[str, Any]:
    """Freeze locked validation if observed spend projects over the stage cap."""

    completed = max(1, int(requests_completed))
    projected_locked_cost = float(cost_used_usd) / completed * int(planned_locked_requests)
    over_cap = projected_locked_cost > float(locked_stage_cost_cap_usd)
    return {
        "artifact": "locked_cost_checkpoint",
        "requests_completed": int(requests_completed),
        "cost_used_usd": float(cost_used_usd),
        "planned_locked_requests": int(planned_locked_requests),
        "locked_stage_cost_cap_usd": float(locked_stage_cost_cap_usd),
        "projected_locked_cost_usd": projected_locked_cost,
        "status": "cost-exceeded partial locked" if over_cap else "cost_checkpoint_pass",
        "freeze_locked": over_cap,
        "pass_claim_allowed": False if over_cap else None,
    }


def _last_number(text: str) -> float | None:
    matches = NUMBER_RE.findall(str(text))
    if not matches:
        return None
    return float(matches[-1].replace(",", ""))


def _ci_lower(value: Any) -> float:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and value:
        return float(value[0])
    return 0.0


def _support_overlap(predicted: Iterable[str], reference: Iterable[str]) -> float:
    predicted_set = {_normalize_support(value) for value in predicted if _normalize_support(value)}
    reference_set = {_normalize_support(value) for value in reference if _normalize_support(value)}
    if not reference_set:
        return 0.0
    return float(len(predicted_set.intersection(reference_set)) / len(reference_set))


def _normalize_support(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _residual_variance_fraction(values: Sequence[float], binary: Sequence[bool]) -> float:
    if not values:
        return 0.0
    array = np.asarray(values, dtype=float)
    total_variance = float(np.var(array))
    if total_variance == 0.0:
        return 0.0
    group_means = {}
    for label in {False, True}:
        group_values = [value for value, current in zip(values, binary) if current is label]
        group_means[label] = _mean(group_values) if group_values else _mean(values)
    residual = np.asarray(
        [float(value) - group_means[bool(label)] for value, label in zip(values, binary)],
        dtype=float,
    )
    return _clamp01(float(np.var(residual) / total_variance))


def _nonzero_threshold(thresholds: Mapping[str, Any], task_type: str) -> float:
    by_task = thresholds.get("nonzero_delta_fraction_min_by_task", {})
    if isinstance(by_task, Mapping):
        return float(by_task.get(task_type, by_task.get("default", 0.0)) or 0.0)
    return 0.0


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mean(values: Sequence[float]) -> float:
    return float(sum(float(value) for value in values) / len(values)) if values else 0.0


def _quantile_report(values: Sequence[int]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0}
    array = np.asarray(values, dtype=float)
    return {
        "p50": float(np.quantile(array, 0.50)),
        "p90": float(np.quantile(array, 0.90)),
        "p95": float(np.quantile(array, 0.95)),
    }


def _request_cost(
    prompt_tokens: float,
    completion_tokens: float,
    *,
    input_price_per_million_tokens: float,
    output_price_per_million_tokens: float,
) -> float:
    return float(
        (prompt_tokens / 1_000_000.0 * input_price_per_million_tokens)
        + (completion_tokens / 1_000_000.0 * output_price_per_million_tokens)
    )


def _profile_metric_comparison(
    synthetic_profile: Mapping[str, Any],
    real_task_profile: Mapping[str, Any],
    *,
    synthetic_key: str,
    real_key: str,
) -> dict[str, float]:
    synthetic_value = float(synthetic_profile.get(synthetic_key, 0.0) or 0.0)
    real_value = float(real_task_profile.get(real_key, 0.0) or 0.0)
    return {
        "synthetic": synthetic_value,
        "real_task": real_value,
        "difference_real_minus_synthetic": real_value - synthetic_value,
    }


def _fraction(values: Iterable[Any]) -> float:
    return float(sum(1 for value in values if bool(value)))


def _clamp01(value: float) -> float:
    if not math.isfinite(float(value)):
        return 0.0
    return min(1.0, max(0.0, float(value)))


__all__ = [
    "DENSE_TARGET_THRESHOLDS",
    "EXPECTED_V3_HARD_CAPS",
    "HOTPOTQA_SURFACE_MATCH_THRESHOLDS",
    "REAL_TASK_V3_CONTRACT_CLEAN",
    "REAL_TASK_V3_PREREGISTRATION_ONLY",
    "V3_MANIFEST_FIELDS",
    "V3_REQUIRED_NON_OVERLAP_KEYS",
    "V3_GLOBAL_PASS",
    "V3_TASK_SPECIFIC_ONLY",
    "W_STRUCT_ALLOWED_FEATURES",
    "W_STRUCT_FORBIDDEN_SOURCE_FIELDS",
    "audit_v3_config_contract",
    "build_circuit_breaker_report",
    "build_dense_target_reliability_report",
    "build_hotpotqa_surface_match_risk_report",
    "build_locked_cost_checkpoint",
    "build_smoke_calibrated_cost_forecast",
    "build_synthetic_real_profile_alignment_report",
    "build_w_struct_stability_report",
    "build_v3_route_manifests",
    "build_v3_split_manifest",
    "build_v3_decision_report",
    "score_gsm8k_v3_utility",
    "score_hotpotqa_v3_utility",
    "validate_w_struct_feature_rows",
]
