"""Stage 2 held-out validation for the FMA journal protocol.

The module implements a confirmatory evaluation layer over stored step-level
artifacts. It does not change the FMA method definition, tune thresholds, or
use Stage 2 outcome metrics for design choices.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from fma.eval.journal_protocol import (
    BASELINE_MAPPING_ROWS,
    BOOTSTRAP_CI,
    HIGH_IMPACT_Q,
    METRIC_DEFINITIONS,
    MIN_BOOTSTRAP_RESAMPLES,
    PERTURBATION_BASELINES,
    PROJECTION_FAMILY,
    PROTOCOL_VERSION,
    build_baseline_mapping_rows,
)


FMA_VERSION = "v1.2"
STAGE2_PROTOCOL_VERSION = "fma_v1_2_stage2_confirmatory"
STAGE1_FRACTION = 0.65
STAGE2_FRACTION = 0.35
SPLIT_SEED = 20260530
STRATUM_SEED = 20260531
BOOTSTRAP_SEED = 20260532
MIN_STAGE2_STRATUM_SIZE = 30
NDCG_K_VALUES = (3, 5, "ceil_10pct")
REQUIRED_STAGE2_STRATA = ("S_high", "S_mid", "S_low", "S_rand")
PARTITION_STAGE2_STRATA = ("S_low", "S_mid", "S_high")
AUDIT_STAGE2_STRATA = ("S_rand",)
PRIMARY_METHOD_ID = "fma_v1_2_step_attribution"

ALLOWED_STRATUM_INPUTS = (
    "trace_length",
    "number_of_steps",
    "task_type",
    "trace_regime",
    "model_family",
    "unperturbed_graph_density",
    "unperturbed_dependency_degree",
    "unperturbed_redundancy_density",
    "taxonomy_category_metadata",
)

FORBIDDEN_STRATUM_INPUTS = (
    "stage2_delta_u",
    "stage2_spearman_rho",
    "stage2_kendall_tau",
    "stage2_ndcg",
    "stage2_auc",
    "stage2_projection_performance",
    "stage2_baseline_performance",
    "post_perturbation_metric",
)


def write_stage2_validation_outputs(
    output_dir: str | Path,
    *,
    necessity_scores_path: str | Path | None = None,
    reflection_graph_path: str | Path | None = None,
) -> dict[str, Path]:
    """Write all required Stage 2 validation artifacts."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    necessity_path = Path(necessity_scores_path) if necessity_scores_path else root / "necessity_scores.jsonl"
    graph_path = Path(reflection_graph_path) if reflection_graph_path else root / "reflection_graph.json"

    paths = {
        "stage2_frozen_protocol": root / "stage2_frozen_protocol.json",
        "stage2_split_manifest": root / "stage2_split_manifest.json",
        "stage2_holdout_validation": root / "stage2_holdout_validation.json",
        "stage2_projection_audit": root / "stage2_projection_audit.json",
        "stage2_stratified_metrics": root / "stage2_stratified_metrics.json",
        "stage2_baseline_results": root / "stage2_baseline_results.json",
        "stage2_baseline_leakage_audit": root / "stage2_baseline_leakage_audit.json",
        "stage2_claim_gating_summary": root / "stage2_claim_gating_summary.md",
        "stage2_leakage_audit": root / "stage2_leakage_audit.json",
    }

    records = load_stage2_step_records(necessity_path, graph_path)
    protocol = build_stage2_frozen_protocol()
    _write_json(paths["stage2_frozen_protocol"], protocol)

    split_manifest = build_stage2_split_manifest(records, protocol)
    _write_json(paths["stage2_split_manifest"], split_manifest)

    metric_outputs = evaluate_stage2_holdout(records, split_manifest, protocol)
    baseline_results = build_stage2_baseline_results(protocol, split_manifest)
    baseline_leakage_audit = build_stage2_baseline_leakage_audit(
        protocol,
        split_manifest,
        baseline_results,
    )
    leakage_audit = build_stage2_leakage_audit(protocol, split_manifest, metric_outputs)
    claim_markdown = build_stage2_claim_gating_summary_markdown(metric_outputs)
    support_markdown = build_stage2_claim_support_summary_markdown(metric_outputs)

    _write_json(paths["stage2_holdout_validation"], metric_outputs["holdout_validation"])
    _write_json(paths["stage2_projection_audit"], metric_outputs["projection_audit"])
    _write_json(paths["stage2_stratified_metrics"], metric_outputs["stratified_metrics"])
    _write_json(paths["stage2_baseline_results"], baseline_results)
    _write_json(paths["stage2_baseline_leakage_audit"], baseline_leakage_audit)
    paths["stage2_claim_gating_summary"].write_text(claim_markdown, encoding="utf-8")
    _write_json(paths["stage2_leakage_audit"], leakage_audit)
    (root / "claim_support_summary.md").write_text(support_markdown, encoding="utf-8")
    return paths


def load_stage2_step_records(
    necessity_scores_path: str | Path,
    reflection_graph_path: str | Path,
) -> list[dict[str, Any]]:
    """Load and join step-level prediction and target records."""
    necessity_rows = _read_jsonl(Path(necessity_scores_path))
    graph_metadata = _load_graph_metadata(Path(reflection_graph_path))

    records: list[dict[str, Any]] = []
    for row in necessity_rows:
        trace_id = str(row["trace_id"])
        step_idx = int(row["step_idx"])
        trace_meta = graph_metadata.get(trace_id, _default_trace_metadata(trace_id))
        node_meta = trace_meta["nodes_by_step"].get(step_idx, {})
        records.append(
            {
                "trace_id": trace_id,
                "step_idx": step_idx,
                "node_id": node_meta.get("node_id", f"{trace_id}::r{step_idx:03d}"),
                "delta_u": float(row.get("necessity", row.get("utility_delta", 0.0))),
                "prediction": float(row.get("attribution_score", row.get("utility_score", 0.0))),
                "task_type": trace_meta["task_type"],
                "trace_regime": trace_meta["trace_regime"],
                "model_family": trace_meta["model_family"],
                "dataset_source": trace_meta["dataset_source"],
                "trace_length": trace_meta["trace_length"],
                "number_of_steps": trace_meta["trace_length"],
                "unperturbed_graph_density": trace_meta["unperturbed_graph_density"],
                "unperturbed_dependency_degree": trace_meta["unperturbed_dependency_degree"],
                "unperturbed_redundancy_density": trace_meta["unperturbed_redundancy_density"],
                "taxonomy_label": str(
                    node_meta.get("taxonomy_label", row.get("taxonomy_label", "UNKNOWN"))
                ),
                "taxonomy_categories": trace_meta["taxonomy_categories"],
                "structural_stability_proxy": trace_meta["structural_stability_proxy"],
            }
        )
    return sorted(records, key=lambda item: (item["trace_id"], item["step_idx"]))


def build_stage2_frozen_protocol() -> dict[str, Any]:
    """Return the frozen Stage 2 protocol snapshot."""
    payload: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "fma_version": FMA_VERSION,
        "stage2_protocol_version": STAGE2_PROTOCOL_VERSION,
        "purpose": "Confirmatory Structural Generalization Test",
        "method_definition_preserved": True,
        "stage1_stage2_separation": {
            "stage1_fraction": STAGE1_FRACTION,
            "stage2_fraction": STAGE2_FRACTION,
            "stage1_allowed_use": "exploration, calibration, and protocol freezing only",
            "stage2_allowed_use": "held-out confirmation only",
            "stage2_forbidden_use": [
                "threshold_tuning",
                "projection_selection",
                "baseline_selection",
                "hyperparameter_adjustment",
                "stratum_definition",
                "metric_choice",
            ],
        },
        "projection_family": list(PROJECTION_FAMILY),
        "baseline_list_and_mapping_rules": list(build_baseline_mapping_rows()),
        "metric_definitions": list(METRIC_DEFINITIONS),
        "ndcg_k_values": list(NDCG_K_VALUES),
        "auc_high_impact_q": list(HIGH_IMPACT_Q),
        "bootstrap_settings": {
            "resample_unit": "trace",
            "minimum_resamples": MIN_BOOTSTRAP_RESAMPLES,
            "ci_percentiles": list(BOOTSTRAP_CI),
            "random_seed": BOOTSTRAP_SEED,
        },
        "random_seeds": {
            "split_seed": SPLIT_SEED,
            "stratum_seed": STRATUM_SEED,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "stratum_assignment_rule_g_T": {
            "name": "frozen_structural_stability_quantile_rule",
            "required_strata": list(REQUIRED_STAGE2_STRATA),
            "allowed_inputs": list(ALLOWED_STRATUM_INPUTS),
            "forbidden_inputs": list(FORBIDDEN_STRATUM_INPUTS),
            "score_formula": (
                "0.35*density_balance + 0.25*redundancy_density + "
                "0.20*dependency_balance + 0.20*taxonomy_entropy"
            ),
            "density_balance": "1 - min(1, abs(unperturbed_graph_density - 0.5) * 2)",
            "dependency_balance": "min(1, unperturbed_dependency_degree / max(1, trace_length))",
            "taxonomy_entropy": "normalized Shannon entropy over trace taxonomy labels",
            "assignment": (
                "Sort held-out traces by the frozen score plus fixed-seed hash tie breaker; "
                "slice into low, mid, and high tertiles. S_high, S_mid, and S_low "
                "are a mutually exclusive partition of Stage 2. S_rand is a fixed-seed "
                "uniform overlapping audit sample from all Stage 2 traces."
            ),
            "partition_strata": list(PARTITION_STAGE2_STRATA),
            "audit_strata": list(AUDIT_STAGE2_STRATA),
            "overlap_allowed": {"S_rand": True},
        },
        "minimum_stratum_size": MIN_STAGE2_STRATUM_SIZE,
        "effect_size_bins": {
            "negligible": "abs(rho) < 0.10",
            "small": "0.10 <= abs(rho) < 0.30",
            "medium": "0.30 <= abs(rho) < 0.50",
            "large": "abs(rho) >= 0.50",
            "policy": "Effect size is descriptive only and does not by itself determine confirmation.",
        },
        "claim_gating_rules": {
            "primary_metric": "spearman_rho",
            "confirmation_threshold": "mean spearman_rho > 0 and CI lower > 0 for the relevant full, projection, and stratum gates",
            "supported": "Stage 1 exploratory support only; never a Stage 2 or final-paper claim",
            "confirmed": "passes mean direction and CI-excludes-zero gates for the relevant claim",
            "confirmed_weak": "final-paper wording when Stage 2 is confirmed and the effect-size label is small",
            "qualified": "mean direction passes but one pre-registered CI gate includes zero",
            "projection_dependent": "effect direction or qualitative result changes across pi_1 through pi_4",
            "stratum_dependent": "full set passes but multiple strata fail CI gates or any stratum has systematic mean direction failure",
            "unsupported": "full Stage 2 set fails the pre-registered direction",
            "insufficient_samples": "any required stratum has fewer than minimum_stratum_size traces",
        },
        "registered_stage1_claims": [
            {
                "claim_id": "C1_rank_generalization",
                "claim": "FMA step-level attribution scores positively rank observed held-out step-level delta_u.",
                "stage1_allowed_label": "supported",
                "stage1_support_semantics": "exploratory only",
            },
            {
                "claim_id": "C2_projection_robustness",
                "claim": "The C1 direction is sign-consistent across pi_1 through pi_4 as a step-level representation audit.",
                "stage1_allowed_label": "supported",
                "stage1_support_semantics": "exploratory only",
            },
            {
                "claim_id": "C3_stratified_generalization",
                "claim": "The C1 direction holds across S_high, S_mid, S_low, and S_rand.",
                "stage1_allowed_label": "supported",
                "stage1_support_semantics": "exploratory only",
            },
        ],
        "fma_projection_policy": {
            "status": "preprojected_step_level_vector",
            "rule": (
                "FMA outputs are already step-level vectors. All four projections are still "
                "materialized in the audit, but they act as identity mappings for FMA rather "
                "than as selected token-to-step projections."
            ),
        },
        "no_adaptive_filtering": True,
        "no_stage2_tuning": True,
    }
    payload["protocol_hash"] = _payload_hash(payload)
    return payload


def build_stage2_split_manifest(
    records: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    """Create deterministic Stage 1/Stage 2 split and Stage 2 strata."""
    trace_metadata = _trace_metadata_from_records(records)
    grouped: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for trace_id, meta in trace_metadata.items():
        key = (
            str(meta["task_type"]),
            str(meta["trace_regime"]),
            str(meta["model_family"]),
            str(meta["dataset_source"]),
        )
        grouped[key].append(trace_id)

    stage1_ids: set[str] = set()
    stage2_ids: set[str] = set()
    split_groups: list[dict[str, Any]] = []
    for key, ids in sorted(grouped.items(), key=lambda item: item[0]):
        ordered = sorted(ids, key=lambda trace_id: _stable_float(f"split:{SPLIT_SEED}:{trace_id}"))
        stage2_count = _stage2_count(len(ordered))
        group_stage2 = set(ordered[:stage2_count])
        group_stage1 = set(ordered[stage2_count:])
        stage1_ids.update(group_stage1)
        stage2_ids.update(group_stage2)
        split_groups.append(
            {
                "stratification_key": {
                    "task_type": key[0],
                    "trace_regime": key[1],
                    "model_family": key[2],
                    "dataset_source": key[3],
                },
                "total_traces": len(ordered),
                "stage1_traces": len(group_stage1),
                "stage2_traces": len(group_stage2),
            }
        )

    strata = assign_stage2_strata(trace_metadata, sorted(stage2_ids))
    strata_semantics = _build_strata_semantics(sorted(stage2_ids), strata)
    assignments: list[dict[str, Any]] = []
    for trace_id, meta in sorted(trace_metadata.items()):
        stage = "stage_2" if trace_id in stage2_ids else "stage_1"
        assignments.append(
            {
                "trace_id": trace_id,
                "stage": stage,
                "stage2_strata": [
                    name
                    for name, report in strata.items()
                    if trace_id in set(report["trace_ids"])
                ]
                if stage == "stage_2"
                else [],
                "stratification_key": {
                    "task_type": meta["task_type"],
                    "trace_regime": meta["trace_regime"],
                    "model_family": meta["model_family"],
                    "dataset_source": meta["dataset_source"],
                },
                "allowed_g_T_inputs": {
                    "trace_length": meta["trace_length"],
                    "number_of_steps": meta["number_of_steps"],
                    "unperturbed_graph_density": meta["unperturbed_graph_density"],
                    "unperturbed_dependency_degree": meta["unperturbed_dependency_degree"],
                    "unperturbed_redundancy_density": meta["unperturbed_redundancy_density"],
                    "taxonomy_categories": meta["taxonomy_categories"],
                    "structural_stability_proxy": meta["structural_stability_proxy"],
                },
            }
        )

    return {
        "protocol_version": protocol["protocol_version"],
        "fma_version": protocol["fma_version"],
        "stage2_protocol_version": protocol["stage2_protocol_version"],
        "protocol_hash": protocol["protocol_hash"],
        "split_rule": {
            "stage1_fraction": STAGE1_FRACTION,
            "stage2_fraction": STAGE2_FRACTION,
            "split_seed": SPLIT_SEED,
            "stratified_by": ["task_type", "trace_regime", "model_family", "dataset_source"],
            "stage2_selection": "fixed-seed hash order within each stratification cell",
        },
        "counts": {
            "total_traces": len(trace_metadata),
            "stage1_traces": len(stage1_ids),
            "stage2_traces": len(stage2_ids),
            "stage1_fraction_observed": _safe_ratio(len(stage1_ids), len(trace_metadata)),
            "stage2_fraction_observed": _safe_ratio(len(stage2_ids), len(trace_metadata)),
        },
        "split_groups": split_groups,
        "stage1_trace_ids": sorted(stage1_ids),
        "stage2_trace_ids": sorted(stage2_ids),
        "stage2_strata": strata,
        "strata_semantics": strata_semantics,
        "assignments": assignments,
        "non_leakage_statement": (
            "Split and strata use only trace ids plus allowed pre-perturbation metadata; "
            "no Stage 2 metric, projection performance, or baseline performance is used."
        ),
    }


def _build_strata_semantics(
    stage2_trace_ids: Sequence[str],
    strata: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    partition_ids: set[str] = set()
    for stratum in PARTITION_STAGE2_STRATA:
        partition_ids.update(strata.get(stratum, {}).get("trace_ids", []))
    audit_membership_count = sum(
        len(strata.get(stratum, {}).get("trace_ids", []))
        for stratum in AUDIT_STAGE2_STRATA
    )
    total_memberships = sum(len(report.get("trace_ids", [])) for report in strata.values())
    return {
        "partition_strata": list(PARTITION_STAGE2_STRATA),
        "audit_strata": list(AUDIT_STAGE2_STRATA),
        "overlap_allowed": {"S_rand": True},
        "unique_stage2_trace_count": len(set(stage2_trace_ids)),
        "partition_trace_count": len(partition_ids),
        "audit_membership_count": audit_membership_count,
        "total_stratum_memberships": total_memberships,
        "partition_matches_stage2_total": len(partition_ids) == len(set(stage2_trace_ids)),
        "interpretation": (
            "Only partition_trace_count is expected to equal unique_stage2_trace_count. "
            "S_rand is an overlapping non-adaptive audit layer, so total_stratum_memberships "
            "may exceed the Stage 2 trace count."
        ),
    }


def assign_stage2_strata(
    trace_metadata: Mapping[str, Mapping[str, Any]],
    stage2_trace_ids: Sequence[str],
    *,
    minimum_size: int = MIN_STAGE2_STRATUM_SIZE,
) -> dict[str, dict[str, Any]]:
    """Assign Stage 2 traces into frozen structural strata."""
    ordered = sorted(
        stage2_trace_ids,
        key=lambda trace_id: (
            float(trace_metadata[trace_id]["structural_stability_proxy"]),
            _stable_float(f"stratum:{STRATUM_SEED}:{trace_id}"),
            trace_id,
        ),
    )
    sizes = _near_equal_sizes(len(ordered), 3)
    low_end = sizes[0]
    mid_end = low_end + sizes[1]
    low_ids = ordered[:low_end]
    mid_ids = ordered[low_end:mid_end]
    high_ids = ordered[mid_end:]
    rand_size = min(sizes) if sizes else 0
    rand_ids = sorted(ordered, key=lambda trace_id: _stable_float(f"rand:{STRATUM_SEED}:{trace_id}"))[:rand_size]

    return {
        "S_high": _stratum_report(high_ids, minimum_size),
        "S_mid": _stratum_report(mid_ids, minimum_size),
        "S_low": _stratum_report(low_ids, minimum_size),
        "S_rand": _stratum_report(rand_ids, minimum_size),
    }


def evaluate_stage2_holdout(
    records: Sequence[Mapping[str, Any]],
    split_manifest: Mapping[str, Any],
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate Stage 2 records and return all metric-bearing outputs."""
    stage2_ids = set(split_manifest["stage2_trace_ids"])
    records_by_trace = _records_by_trace(
        [record for record in records if str(record["trace_id"]) in stage2_ids]
    )
    trace_metadata = _trace_metadata_from_records(records)

    full_metrics = _evaluate_group_for_all_projections("full_stage2", sorted(stage2_ids), records_by_trace)
    per_model = {
        model: _evaluate_group_for_all_projections(
            f"model:{model}",
            sorted(trace_id for trace_id in stage2_ids if trace_metadata[trace_id]["model_family"] == model),
            records_by_trace,
        )
        for model in sorted({trace_metadata[trace_id]["model_family"] for trace_id in stage2_ids})
    }
    per_trace_regime = {
        regime: _evaluate_group_for_all_projections(
            f"trace_regime:{regime}",
            sorted(trace_id for trace_id in stage2_ids if trace_metadata[trace_id]["trace_regime"] == regime),
            records_by_trace,
        )
        for regime in sorted({trace_metadata[trace_id]["trace_regime"] for trace_id in stage2_ids})
    }

    strata = split_manifest["stage2_strata"]
    stratum_metrics = {
        stratum: {
            "status": report["status"],
            "bucket_size": report["bucket_size"],
            "required": report["required"],
            "metrics_by_projection": _evaluate_group_for_all_projections(
                stratum,
                report["trace_ids"],
                records_by_trace,
            ),
        }
        for stratum, report in strata.items()
    }
    for payload in stratum_metrics.values():
        payload["spearman_gate_by_projection"] = _spearman_gate_by_projection(
            payload["metrics_by_projection"]
        )
    rho_variance = _rho_variance_across_strata(stratum_metrics)
    projection_audit = _build_projection_audit(full_metrics, stratum_metrics)
    claim_gating = _build_claim_gating(full_metrics, stratum_metrics, projection_audit)

    holdout_validation = {
        "protocol_version": protocol["protocol_version"],
        "fma_version": protocol["fma_version"],
        "stage2_protocol_version": protocol["stage2_protocol_version"],
        "protocol_hash": protocol["protocol_hash"],
        "method": PRIMARY_METHOD_ID,
        "target": "delta_u",
        "prediction": "fma_step_level_attribution_score",
        "projection_policy": protocol["fma_projection_policy"],
        "projection_identity_interpretation": (
            "Identity projection is expected because FMA is already represented as a "
            "step-level vector. Projection audit therefore checks reporting completeness "
            "rather than claiming nontrivial token-to-step robustness."
        ),
        "full_stage2": full_metrics,
        "per_model_aggregate": per_model,
        "per_trace_regime_aggregate": per_trace_regime,
        "claim_gating": claim_gating,
        "design_constraints": {
            "confirmatory_only": True,
            "no_stage2_threshold_tuning": True,
            "no_projection_selection": True,
            "no_adaptive_filtering": True,
        },
    }
    stratified_metrics = {
        "protocol_version": protocol["protocol_version"],
        "fma_version": protocol["fma_version"],
        "stage2_protocol_version": protocol["stage2_protocol_version"],
        "required_strata": list(REQUIRED_STAGE2_STRATA),
        "strata_semantics": split_manifest["strata_semantics"],
        "strata": stratum_metrics,
        "variance_of_rho_across_strata": rho_variance,
        "underfilled_strata": [
            {
                "stratum": stratum,
                "status": report["status"],
                "bucket_size": report["bucket_size"],
                "required": report["required"],
            }
            for stratum, report in strata.items()
            if report["status"] == "insufficient_samples"
        ],
    }
    projection_audit["claim_gating"] = claim_gating
    return {
        "holdout_validation": holdout_validation,
        "projection_audit": projection_audit,
        "stratified_metrics": stratified_metrics,
        "claim_gating": claim_gating,
    }


def build_stage2_leakage_audit(
    protocol: Mapping[str, Any],
    split_manifest: Mapping[str, Any],
    metric_outputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a no-leakage audit checklist for the Stage 2 run."""
    not_evaluated_baselines = _not_evaluated_baseline_rows()
    return {
        "protocol_version": protocol["protocol_version"],
        "fma_version": protocol["fma_version"],
        "stage2_protocol_version": protocol["stage2_protocol_version"],
        "protocol_hash": protocol["protocol_hash"],
        "split_manifest_hash": _payload_hash(split_manifest),
        "holdout_validation_hash": _payload_hash(metric_outputs["holdout_validation"]),
        "checklist": {
            "frozen_protocol_saved": True,
            "stage1_stage2_disjoint": _disjoint(
                split_manifest["stage1_trace_ids"],
                split_manifest["stage2_trace_ids"],
            ),
            "stage2_metrics_used_for_split": False,
            "stage2_metrics_used_for_strata": False,
            "stage2_metrics_used_for_threshold_tuning": False,
            "stage2_metrics_used_for_projection_selection": False,
            "stage2_metrics_used_for_baseline_selection": False,
            "stage2_target_y_i_reused_as_baseline_prediction": False,
            "adaptive_filtering": False,
            "underfilled_strata_reported_not_dropped": True,
        },
        "allowed_stratum_inputs_used": list(ALLOWED_STRATUM_INPUTS),
        "forbidden_stratum_inputs_used": [],
        "forbidden_inputs_checked": list(FORBIDDEN_STRATUM_INPUTS),
        "evaluation_order": [
            "build frozen protocol",
            "hash-based stratified split",
            "metadata-only stratum assignment",
            "held-out metric evaluation",
            "projection audit",
            "claim gating",
            "baseline availability report",
            "baseline target-leakage audit",
        ],
        "baseline_artifacts": {
            "results": "outputs/stage2_baseline_results.json",
            "target_leakage_audit": "outputs/stage2_baseline_leakage_audit.json",
        },
        "baseline_evaluation_scope": {
            "evaluated": [PRIMARY_METHOD_ID],
            "not_evaluated": not_evaluated_baselines,
        },
        "notes": [
            "FMA was evaluated as a preprojected step-level vector.",
            "Projection entries are materialized for pi_1 through pi_4; no best projection was selected.",
            "Unavailable baselines are explicit audit entries rather than synthetic measurements.",
        ],
    }


def build_stage2_baseline_results(
    protocol: Mapping[str, Any],
    split_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Return Stage 2 baseline availability and result status."""
    not_evaluated_baselines = _not_evaluated_baseline_rows()
    return {
        "protocol_version": protocol["protocol_version"],
        "fma_version": protocol["fma_version"],
        "stage2_protocol_version": protocol["stage2_protocol_version"],
        "protocol_hash": protocol["protocol_hash"],
        "split_manifest_hash": _payload_hash(split_manifest),
        "evaluation_target": {
            "ground_truth": "y_i = Delta_U(r_i)",
            "required_method_output": "s_B(r_i) in R^{|R|}",
            "metrics": [
                "spearman_rho",
                "kendall_tau",
                "ndcg_at_3",
                "ndcg_at_5",
                "ndcg_at_ceil_10pct",
                "auc_high_impact_q10",
                "auc_high_impact_q20",
            ],
        },
        "primary_fma_reference": {
            "method": PRIMARY_METHOD_ID,
            "status": "evaluated_as_fma_method_not_baseline",
            "results_file": "outputs/stage2_holdout_validation.json",
        },
        "baselines": not_evaluated_baselines,
        "summary": {
            "total_registered_baselines": len(not_evaluated_baselines),
            "evaluated_baselines": 0,
            "not_evaluated_baselines": len(not_evaluated_baselines),
            "fabricated_baseline_scores": False,
        },
        "result_policy": (
            "No baseline metric is reported unless an independent held-out "
            "step-level prediction vector is present. Missing baselines remain "
            "explicit unavailable rows."
        ),
    }


def build_stage2_baseline_leakage_audit(
    protocol: Mapping[str, Any],
    split_manifest: Mapping[str, Any],
    baseline_results: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a baseline-specific audit against direct Stage 2 target reuse."""
    rows = list(build_baseline_mapping_rows())
    baseline_checks = []
    for row in rows:
        baseline = row["baseline"]
        is_perturbation = baseline in PERTURBATION_BASELINES
        baseline_checks.append(
            {
                "baseline": baseline,
                "class": row["class"],
                "status": "not_evaluated_no_stage2_step_scores",
                "target_leakage_status": "missing_artifact",
                "is_perturbation_baseline": is_perturbation,
                "target_reuse_policy": row["target_reuse_policy"],
                "stage2_prediction_vector_available": False,
                "direct_target_reuse_detected": False,
                "oracle_or_control_exception": False,
                "inspected_prediction_artifacts": [],
                "conclusion": (
                    "No independent held-out s_B(r_i) vector artifact was available; "
                    "the baseline is unavailable rather than filled from y_i."
                ),
            }
        )
    return {
        "protocol_version": protocol["protocol_version"],
        "fma_version": protocol["fma_version"],
        "stage2_protocol_version": protocol["stage2_protocol_version"],
        "protocol_hash": protocol["protocol_hash"],
        "split_manifest_hash": _payload_hash(split_manifest),
        "baseline_results_hash": _payload_hash(baseline_results),
        "target_symbol": "y_i = Delta_U(r_i)",
        "score_symbol": "s_B(r_i)",
        "checklist": {
            "baseline_scores_fabricated": False,
            "stage2_target_y_i_reused_as_prediction": False,
            "perturbation_baselines_reuse_target": False,
            "oracle_control_rows_labeled": True,
            "stage2_baseline_performance_used_for_strata": False,
            "stage2_baseline_performance_used_for_projection_selection": False,
            "unavailable_baselines_reported_not_imputed": True,
        },
        "target_leakage_status_values": [
            "clean",
            "target_leaking",
            "unclear",
            "missing_artifact",
        ],
        "baseline_checks": baseline_checks,
        "notes": [
            "Perturbation baselines may estimate step sensitivity only through frozen baseline-specific scoring rules.",
            "Direct reuse of Stage 2 Delta_U as s_B is forbidden unless a row is explicitly labeled oracle/control.",
            "No oracle/control baseline rows were evaluated in this run.",
        ],
    }


def _not_evaluated_baseline_rows() -> list[dict[str, Any]]:
    rows = []
    for row in build_baseline_mapping_rows():
        rows.append(
            {
                "baseline": row["baseline"],
                "class": row["class"],
                "registered_status": row["status"],
                "status": "not_evaluated_no_stage2_step_scores",
                "target_leakage_status": "missing_artifact",
                "step_level_mapping": row["step_level_mapping"],
                "target_reuse_policy": row["target_reuse_policy"],
                "reason": (
                    "No held-out baseline prediction vector artifact was available; "
                    "values were not fabricated."
                ),
            }
        )
    return rows


def build_stage2_claim_gating_summary_markdown(metric_outputs: Mapping[str, Any]) -> str:
    """Return a Markdown summary of Stage 2 claim labels."""
    claims = metric_outputs["claim_gating"]["claims"]
    lines = [
        "# Stage 2 Claim Gating Summary",
        "",
        f"Protocol version: `{PROTOCOL_VERSION}`",
        f"Stage 2 protocol version: `{STAGE2_PROTOCOL_VERSION}`",
        "",
        "Stage 2 is confirmatory. Labels are assigned without Stage 2 threshold tuning, projection selection, or adaptive filtering. `confirmed_weak` is final-paper wording for Stage 2 confirmation with small effect size.",
        "",
        "| Claim ID | Label | rho_mean | rho_ci95 | CI excludes 0 | Effect size | Passing strata | Projection status | Downgrade reason | Notes |",
        "|---|---|---:|---|---|---|---:|---|---|---|",
    ]
    for claim in claims:
        lines.append(
            "| {claim_id} | `{label}` | {rho} | {ci95} | {ci_excludes_zero} | {effect_size} | {passing}/4 | {projection_status} | {downgrade_reason} | {notes} |".format(
                claim_id=claim["claim_id"],
                label=claim["label"],
                rho=_format_optional_float(claim.get("rho_mean")),
                ci95=_format_ci95(claim.get("rho_ci95")),
                ci_excludes_zero=str(bool(claim.get("ci_excludes_zero"))).lower(),
                effect_size=claim.get("effect_size_label", "unavailable"),
                passing=claim.get("passing_strata", 0),
                projection_status=claim.get("projection_status", "not_applicable"),
                downgrade_reason=claim.get("downgrade_reason", "none"),
                notes=claim.get("notes", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Leakage Controls",
            "",
            "- Stage 2 split uses fixed-seed hashing within frozen stratification cells.",
            "- Strata use only allowed pre-perturbation metadata and a fixed random seed.",
            "- S_high, S_mid, and S_low are a mutually exclusive partition; S_rand is an overlapping non-adaptive audit layer.",
            "- Effect-size labels are descriptive only: rho in [0.10, 0.30) is `small`.",
            "- Underfilled strata are labeled `insufficient_samples` rather than dropped.",
            "- Baselines without held-out step-level vectors are marked unavailable, not imputed.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_stage2_claim_support_summary_markdown(metric_outputs: Mapping[str, Any]) -> str:
    """Return the package-level claim support summary after Stage 2 runs."""
    claims = metric_outputs["claim_gating"]["claims"]
    lines = [
        "# Claim Support Summary",
        "",
        f"Protocol version: `{PROTOCOL_VERSION}`",
        f"Stage 2 protocol version: `{STAGE2_PROTOCOL_VERSION}`",
        "",
        "## Claim Decision Labels",
        "",
        "| Label | Required condition |",
        "|---|---|",
        "| `supported` | Stage 1 exploratory support only; never a final claim. |",
        "| `confirmed` | Stage 2 held-out results satisfy all pre-registered metric, projection, and stratum gates. |",
        "| `confirmed_weak` | Final-paper wording for Stage 2 confirmation with small effect size. |",
        "| `qualified` | Stage 2 supports the claim with pre-declared limits. |",
        "| `projection-dependent` | Direction or ranking changes across `pi_1`, `pi_2`, `pi_3`, and `pi_4`. |",
        "| `stratum-dependent` | The claim holds in some required strata but not all. |",
        "| `unsupported` | Required evidence is missing, unstable, contradictory, or fails an audit gate. |",
        "| `insufficient_samples` | One or more required Stage 2 strata is underfilled. |",
        "",
        "## Audit Gates",
        "",
        "| Gate | Status after Stage 2 run |",
        "|---|---|",
        "| Frozen protocol snapshot saved | complete: `outputs/stage2_frozen_protocol.json` |",
        "| Stratified Stage 1 / Stage 2 split saved | complete: `outputs/stage2_split_manifest.json` |",
        "| Projection audit across all `Pi` | complete: `outputs/stage2_projection_audit.json` |",
        "| Held-out Stage 2 validation | complete: `outputs/stage2_holdout_validation.json` |",
        "| High, mid, low, and random strata included | complete: `outputs/stage2_stratified_metrics.json` |",
        "| Stage 2 baseline results saved | complete: `outputs/stage2_baseline_results.json` |",
        "| Baseline target-leakage audit saved | complete: `outputs/stage2_baseline_leakage_audit.json` |",
        "| Leakage audit checklist saved | complete: `outputs/stage2_leakage_audit.json` |",
        "| Claim gating summary saved | complete: `outputs/stage2_claim_gating_summary.md` |",
        "",
        "## Current Claim Table",
        "",
        "| Claim ID | Decision | rho_mean | rho_ci95 | Effect size | Evidence files | Notes |",
        "|---|---|---:|---|---|---|---|",
    ]
    for claim in claims:
        lines.append(
            "| {claim_id} | `{label}` | {rho} | {ci95} | {effect_size} | `stage2_holdout_validation.json`; `stage2_projection_audit.json`; `stage2_stratified_metrics.json` | {notes} |".format(
                claim_id=claim["claim_id"],
                label=claim["label"],
                rho=_format_optional_float(claim.get("rho_mean")),
                ci95=_format_ci95(claim.get("rho_ci95")),
                effect_size=claim.get("effect_size_label", "unavailable"),
                notes=claim.get("notes", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Scope Note",
            "",
            "The Stage 2 run evaluates the available preprojected FMA step-level vector. Baselines without held-out step-level prediction vectors are explicitly marked unavailable in the leakage audit rather than imputed.",
        ]
    )
    return "\n".join(lines) + "\n"


def _evaluate_group_for_all_projections(
    group_name: str,
    trace_ids: Sequence[str],
    records_by_trace: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    return {
        projection["id"]: _evaluate_group(group_name, trace_ids, records_by_trace, projection["id"])
        for projection in PROJECTION_FAMILY
    }


def _evaluate_group(
    group_name: str,
    trace_ids: Sequence[str],
    records_by_trace: Mapping[str, Sequence[Mapping[str, Any]]],
    projection_id: str,
) -> dict[str, Any]:
    trace_metrics: list[dict[str, float]] = []
    n_steps = 0
    for trace_id in sorted(trace_ids):
        rows = list(records_by_trace.get(trace_id, ()))
        if not rows:
            continue
        y_true = [float(row["delta_u"]) for row in rows]
        y_score = _apply_projection(
            [float(row["prediction"]) for row in rows],
            projection_id,
        )
        n_steps += len(rows)
        trace_metrics.append(_trace_metrics(y_true, y_score))

    metric_names = _stage2_metric_names(trace_metrics)
    summaries = {
        metric: _summarize_metric(
            [trace_metric[metric] for trace_metric in trace_metrics],
            n_steps=n_steps,
            seed=_metric_seed(group_name, projection_id, metric),
        )
        for metric in metric_names
    }
    if "spearman_rho" in summaries:
        summaries["spearman_rho"].update(_spearman_gate(summaries["spearman_rho"]))
    return {
        "group": group_name,
        "projection": projection_id,
        "projection_policy": "identity_for_preprojected_step_level_fma",
        "n_traces": len(trace_metrics),
        "n_steps": n_steps,
        "metrics": summaries,
    }


def _trace_metrics(y_true: Sequence[float], y_score: Sequence[float]) -> dict[str, float]:
    metrics = {
        "spearman_rho": _spearman(y_true, y_score),
        "kendall_tau": _kendall_tau_b(y_true, y_score),
    }
    for k_value in NDCG_K_VALUES:
        metric_name = f"ndcg_at_{k_value}"
        metrics[metric_name] = _ndcg(y_true, y_score, _resolve_k(k_value, len(y_true)))
    for q_value in HIGH_IMPACT_Q:
        metrics[f"auc_high_impact_q{q_value}"] = _auc_high_impact(y_true, y_score, q_value)
    return metrics


def _build_projection_audit(
    full_metrics: Mapping[str, Any],
    stratum_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    metric_names = _stage2_metric_names_from_projection_metrics(full_metrics)
    projection_specific_table: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for metric in metric_names:
        means = []
        for projection_id, result in full_metrics.items():
            mean_value = result["metrics"][metric]["mean"]
            means.append(float(mean_value) if mean_value is not None else 0.0)
            projection_specific_table.append(
                {
                    "group": "full_stage2",
                    "projection": projection_id,
                    "metric": metric,
                    "mean": mean_value,
                    "std": result["metrics"][metric]["std"],
                    "ci95": result["metrics"][metric]["ci95"],
                    "ci_excludes_zero": result["metrics"][metric].get("ci_excludes_zero"),
                    "gate_pass": result["metrics"][metric].get("gate_pass"),
                    "effect_size_label": result["metrics"][metric].get("effect_size_label"),
                    "n_traces": result["n_traces"],
                    "n_steps": result["n_steps"],
                }
            )
        worst_index = min(range(len(means)), key=lambda index: means[index]) if means else 0
        projection_ids = list(full_metrics)
        signs = [_sign(value) for value in means]
        summary[metric] = {
            "metric_mean_across_pi": _mean(means),
            "metric_variance_across_pi": _variance(means),
            "worst_case_projection": projection_ids[worst_index] if projection_ids else None,
            "worst_case_projection_performance": means[worst_index] if means else None,
            "signs": dict(zip(projection_ids, signs, strict=True)),
            "sign_consistency": len(set(signs)) <= 1,
            "ci_excludes_zero_all_projections": all(
                bool(full_metrics[projection_id]["metrics"][metric].get("ci_excludes_zero"))
                for projection_id in projection_ids
            ),
            "gate_pass_all_projections": all(
                bool(full_metrics[projection_id]["metrics"][metric].get("gate_pass"))
                for projection_id in projection_ids
            ),
        }
    return {
        "protocol_version": PROTOCOL_VERSION,
        "fma_version": FMA_VERSION,
        "stage2_protocol_version": STAGE2_PROTOCOL_VERSION,
        "projection_family": [projection["id"] for projection in PROJECTION_FAMILY],
        "projection_policy": "identity_for_preprojected_step_level_fma",
        "projection_identity_interpretation": (
            "FMA scores are already step-level vectors. The identity projection is expected "
            "behavior for this method and is reported as a step-level representation audit, "
            "not as evidence of nontrivial token-to-step projection robustness."
        ),
        "metric_summary_across_pi": summary,
        "projection_specific_metric_table": projection_specific_table,
        "stratum_projection_rows": _stratum_projection_rows(stratum_metrics),
        "baseline_projection_status": {
            "evaluated": [
                {
                    "method": PRIMARY_METHOD_ID,
                    "status": "evaluated",
                    "projection_policy": "identity_for_preprojected_step_level_fma",
                }
            ],
            "not_evaluated": [
                {
                    "baseline": row["baseline"],
                    "status": "not_available_no_stage2_prediction_vector",
                }
                for row in BASELINE_MAPPING_ROWS
            ],
        },
        "forbidden_selection_check": {
            "best_projection_selected_for_main_table": False,
            "worst_case_projection_reported": True,
            "all_four_projections_reported": True,
        },
    }


def _spearman_gate_by_projection(metrics_by_projection: Mapping[str, Any]) -> dict[str, Any]:
    return {
        projection: {
            "rho_mean": result["metrics"]["spearman_rho"]["mean"],
            "rho_ci95": result["metrics"]["spearman_rho"]["ci95"],
            "ci_excludes_zero": result["metrics"]["spearman_rho"].get("ci_excludes_zero", False),
            "gate_pass": result["metrics"]["spearman_rho"].get("gate_pass", False),
            "effect_size_label": result["metrics"]["spearman_rho"].get("effect_size_label"),
        }
        for projection, result in sorted(metrics_by_projection.items())
    }


def _build_claim_gating(
    full_metrics: Mapping[str, Any],
    stratum_metrics: Mapping[str, Any],
    projection_audit: Mapping[str, Any],
) -> dict[str, Any]:
    full_gate_by_projection = _spearman_gate_by_projection(full_metrics)
    full_gate = _combine_projection_gates(full_gate_by_projection)
    projection_signs = projection_audit["metric_summary_across_pi"]["spearman_rho"]["signs"]
    projection_status = (
        "sign_consistent_positive"
        if full_gate["all_mean_positive"] and set(projection_signs.values()) == {"positive"}
        else "projection-dependent"
        if len(set(projection_signs.values())) > 1
        else "not_positive"
    )
    underfilled = [
        stratum
        for stratum, payload in stratum_metrics.items()
        if payload["status"] == "insufficient_samples"
    ]
    stratum_gate_details: dict[str, dict[str, Any]] = {}
    for stratum, payload in stratum_metrics.items():
        gate = _combine_projection_gates(
            _spearman_gate_by_projection(payload["metrics_by_projection"])
        )
        gate["status"] = payload["status"]
        gate["passed"] = payload["status"] == "ok" and gate["all_gate_pass"]
        gate["mean_direction_failure"] = not gate["all_mean_positive"]
        gate["ci_includes_zero"] = gate["all_mean_positive"] and not gate["all_ci_lower_gt_zero"]
        stratum_gate_details[stratum] = gate
    stratum_passes = {
        stratum: bool(gate["passed"])
        for stratum, gate in stratum_gate_details.items()
    }
    passing_strata = sum(1 for passed in stratum_passes.values() if passed)

    c3_label, c3_reason = _stratified_claim_label(full_gate, underfilled, stratum_gate_details)
    c1_base_label, c1_base_reason = _rank_claim_label(full_gate)
    c2_base_label, c2_base_reason = _projection_claim_label(projection_status, full_gate)
    c1_label, c1_reason = _apply_required_strata_gate(
        c1_base_label,
        c1_base_reason,
        c3_label,
        c3_reason,
    )
    c2_label, c2_reason = _apply_required_strata_gate(
        c2_base_label,
        c2_base_reason,
        c3_label,
        c3_reason,
    )
    c1_final_label = _final_paper_claim_label(c1_label, full_gate["effect_size_label"])
    c2_final_label = _final_paper_claim_label(c2_label, full_gate["effect_size_label"])
    c3_final_label = _final_paper_claim_label(c3_label, full_gate["effect_size_label"])

    claims = [
        {
            "claim_id": "C1_rank_generalization",
            "label": c1_final_label,
            "stage2_confirmation_label": c1_label,
            "rho_mean": full_gate["rho_mean"],
            "rho_ci95": full_gate["rho_ci95"],
            "ci_excludes_zero": full_gate["ci_excludes_zero"],
            "effect_size_label": full_gate["effect_size_label"],
            "downgrade_reason": c1_reason,
            "full_stage2_spearman_mean": full_gate["rho_mean"],
            "passing_strata": passing_strata,
            "projection_status": projection_status,
            "notes": _claim_notes(c1_final_label, c1_reason),
        },
        {
            "claim_id": "C2_projection_robustness",
            "label": c2_final_label,
            "stage2_confirmation_label": c2_label,
            "rho_mean": full_gate["rho_mean"],
            "rho_ci95": full_gate["rho_ci95"],
            "ci_excludes_zero": full_gate["ci_excludes_zero"],
            "effect_size_label": full_gate["effect_size_label"],
            "downgrade_reason": c2_reason,
            "full_stage2_spearman_mean": full_gate["rho_mean"],
            "passing_strata": passing_strata,
            "projection_status": projection_status,
            "notes": _claim_notes(c2_final_label, c2_reason),
        },
        {
            "claim_id": "C3_stratified_generalization",
            "label": c3_final_label,
            "stage2_confirmation_label": c3_label,
            "rho_mean": full_gate["rho_mean"],
            "rho_ci95": full_gate["rho_ci95"],
            "ci_excludes_zero": full_gate["ci_excludes_zero"],
            "effect_size_label": full_gate["effect_size_label"],
            "downgrade_reason": c3_reason,
            "full_stage2_spearman_mean": full_gate["rho_mean"],
            "passing_strata": passing_strata,
            "projection_status": projection_status,
            "notes": _claim_notes(c3_final_label, c3_reason),
        },
    ]
    return {
        "primary_metric": "spearman_rho",
        "full_stage2_pass": full_gate["all_gate_pass"],
        "full_stage2_rho_gate": full_gate,
        "projection_status": projection_status,
        "underfilled_strata": underfilled,
        "stratum_passes": stratum_passes,
        "stratum_rho_gates": stratum_gate_details,
        "claims": claims,
    }


def _combine_projection_gates(gates_by_projection: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    means = [float(gate.get("rho_mean") or 0.0) for gate in gates_by_projection.values()]
    lowers = [
        float(gate["rho_ci95"][0])
        for gate in gates_by_projection.values()
        if gate.get("rho_ci95") and gate["rho_ci95"][0] is not None
    ]
    uppers = [
        float(gate["rho_ci95"][1])
        for gate in gates_by_projection.values()
        if gate.get("rho_ci95") and gate["rho_ci95"][1] is not None
    ]
    rho_mean = _mean(means)
    rho_ci95 = [min(lowers), max(uppers)] if lowers and uppers else [None, None]
    all_mean_positive = all(value > 0.0 for value in means) if means else False
    all_ci_lower_gt_zero = all(value > 0.0 for value in lowers) if lowers else False
    return {
        "rho_mean": rho_mean,
        "rho_ci95": rho_ci95,
        "ci_excludes_zero": all_ci_lower_gt_zero,
        "all_mean_positive": all_mean_positive,
        "all_ci_lower_gt_zero": all_ci_lower_gt_zero,
        "all_gate_pass": all_mean_positive and all_ci_lower_gt_zero,
        "effect_size_label": _effect_size_label(rho_mean),
        "by_projection": dict(gates_by_projection),
    }


def _rank_claim_label(full_gate: Mapping[str, Any]) -> tuple[str, str]:
    if not full_gate["all_mean_positive"]:
        return "unsupported", "Full Stage 2 mean rho is not positive for every projection."
    if not full_gate["all_ci_lower_gt_zero"]:
        return "qualified", "Full Stage 2 Spearman CI includes zero."
    return "confirmed", "none"


def _final_paper_claim_label(stage2_label: str, effect_size_label: str) -> str:
    if stage2_label == "confirmed" and effect_size_label == "small":
        return "confirmed_weak"
    return stage2_label


def _projection_claim_label(
    projection_status: str,
    full_gate: Mapping[str, Any],
) -> tuple[str, str]:
    if projection_status == "projection-dependent":
        return "projection-dependent", "Projection effect direction is not sign-consistent."
    if projection_status != "sign_consistent_positive":
        return "unsupported", "Projection directions are sign-consistent but not positive."
    if not full_gate["all_ci_lower_gt_zero"]:
        return "qualified", "Projection directions are positive but at least one Spearman CI includes zero."
    return "confirmed", "none"


def _apply_required_strata_gate(
    base_label: str,
    base_reason: str,
    stratum_label: str,
    stratum_reason: str,
) -> tuple[str, str]:
    """Apply the global rule that confirmation requires all Stage 2 strata."""
    if base_label in {"unsupported", "projection-dependent", "insufficient_samples"}:
        return base_label, base_reason
    if stratum_label == "confirmed":
        return base_label, base_reason
    if stratum_label == "insufficient_samples":
        return "insufficient_samples", stratum_reason
    if base_label == "confirmed":
        return stratum_label, stratum_reason
    if base_label == "qualified":
        return "qualified", base_reason
    return base_label, base_reason


def _stratified_claim_label(
    full_gate: Mapping[str, Any],
    underfilled: Sequence[str],
    stratum_gate_details: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    if underfilled:
        return "insufficient_samples", "Underfilled strata: " + ", ".join(underfilled)
    if not full_gate["all_mean_positive"]:
        return "unsupported", "Full Stage 2 mean rho is not positive for every projection."
    if not full_gate["all_ci_lower_gt_zero"]:
        return "qualified", "Full Stage 2 Spearman CI includes zero."
    failures = [
        stratum
        for stratum, gate in stratum_gate_details.items()
        if not gate["passed"]
    ]
    mean_failures = [
        stratum
        for stratum, gate in stratum_gate_details.items()
        if gate["mean_direction_failure"]
    ]
    ci_failures = [
        stratum
        for stratum, gate in stratum_gate_details.items()
        if gate["ci_includes_zero"]
    ]
    if not failures:
        return "confirmed", "none"
    if len(failures) == 1 and not mean_failures:
        return "qualified", "One stratum Spearman CI includes zero: " + ", ".join(ci_failures)
    if mean_failures:
        return "stratum-dependent", "Mean direction failed in strata: " + ", ".join(mean_failures)
    return "stratum-dependent", "Multiple stratum Spearman CIs include zero: " + ", ".join(ci_failures)


def _claim_notes(label: str, downgrade_reason: str) -> str:
    if label == "insufficient_samples":
        return downgrade_reason
    if label == "confirmed":
        return "Pre-registered direction and CI gates hold; effect size remains descriptive."
    if label == "confirmed_weak":
        return "Stage 2 gates hold, but the confirmed effect size is small; final paper wording should use confirmed_weak."
    if label == "qualified":
        return downgrade_reason
    if label == "stratum-dependent":
        return downgrade_reason
    if label == "projection-dependent":
        return downgrade_reason
    return downgrade_reason


def _rho_variance_across_strata(stratum_metrics: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for projection in [projection["id"] for projection in PROJECTION_FAMILY]:
        values = []
        for payload in stratum_metrics.values():
            mean_value = payload["metrics_by_projection"][projection]["metrics"]["spearman_rho"]["mean"]
            if mean_value is not None:
                values.append(float(mean_value))
        output[projection] = {
            "variance": _variance(values),
            "num_strata": len(values),
        }
    return output


def _stratum_projection_rows(stratum_metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stratum, payload in sorted(stratum_metrics.items()):
        for projection, result in sorted(payload["metrics_by_projection"].items()):
            for metric, summary in sorted(result["metrics"].items()):
                rows.append(
                    {
                        "stratum": stratum,
                        "status": payload["status"],
                        "projection": projection,
                        "metric": metric,
                        "mean": summary["mean"],
                        "std": summary["std"],
                        "ci95": summary["ci95"],
                        "ci_excludes_zero": summary.get("ci_excludes_zero"),
                        "gate_pass": summary.get("gate_pass"),
                        "effect_size_label": summary.get("effect_size_label"),
                        "n_traces": summary["n_traces"],
                        "n_steps": summary["n_steps"],
                    }
                )
    return rows


def _load_graph_metadata(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata: dict[str, dict[str, Any]] = {}
    for graph in payload.get("graphs", []):
        trace_id = str(graph.get("graph_id"))
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        trace_length = len(nodes)
        graph_density = _safe_ratio(len(edges), max(1, trace_length * (trace_length - 1)))
        dependency_degree = _safe_ratio(len(edges), max(1, trace_length))
        degree_by_node = Counter()
        for edge in edges:
            degree_by_node[str(edge.get("source"))] += 1
            degree_by_node[str(edge.get("target"))] += 1
        redundancy_density = _safe_ratio(
            sum(1 for node in nodes if degree_by_node[str(node.get("node_id"))] > 1),
            max(1, trace_length),
        )
        taxonomy_categories = [
            str(node.get("taxonomy_label", "UNKNOWN"))
            for node in sorted(nodes, key=lambda item: int(item.get("step_index", 0)))
        ]
        taxonomy_entropy = _normalized_entropy(taxonomy_categories)
        density_balance = 1.0 - min(1.0, abs(graph_density - 0.5) * 2.0)
        dependency_balance = min(1.0, _safe_ratio(dependency_degree, max(1, trace_length)))
        structural_stability_proxy = (
            0.35 * density_balance
            + 0.25 * redundancy_density
            + 0.20 * dependency_balance
            + 0.20 * taxonomy_entropy
        )
        nodes_by_step = {
            int(node.get("step_index", 0)): {
                "node_id": str(node.get("node_id")),
                "taxonomy_label": str(node.get("taxonomy_label", "UNKNOWN")),
            }
            for node in nodes
        }
        metadata[trace_id] = {
            "trace_id": trace_id,
            "task_type": "synthetic_reflection",
            "trace_regime": _trace_regime(trace_length, graph_density, dependency_degree),
            "model_family": "deterministic_proxy",
            "dataset_source": "stored_phase5_phase6_artifacts",
            "trace_length": trace_length,
            "unperturbed_graph_density": graph_density,
            "unperturbed_dependency_degree": dependency_degree,
            "unperturbed_redundancy_density": redundancy_density,
            "taxonomy_categories": taxonomy_categories,
            "taxonomy_entropy": taxonomy_entropy,
            "structural_stability_proxy": structural_stability_proxy,
            "nodes_by_step": nodes_by_step,
        }
    return metadata


def _default_trace_metadata(trace_id: str) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "task_type": "unknown",
        "trace_regime": "unknown",
        "model_family": "unknown",
        "dataset_source": "unknown",
        "trace_length": 0,
        "unperturbed_graph_density": 0.0,
        "unperturbed_dependency_degree": 0.0,
        "unperturbed_redundancy_density": 0.0,
        "taxonomy_categories": [],
        "taxonomy_entropy": 0.0,
        "structural_stability_proxy": 0.0,
        "nodes_by_step": {},
    }


def _trace_metadata_from_records(records: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for record in records:
        trace_id = str(record["trace_id"])
        if trace_id in metadata:
            continue
        metadata[trace_id] = {
            "trace_id": trace_id,
            "task_type": str(record["task_type"]),
            "trace_regime": str(record["trace_regime"]),
            "model_family": str(record["model_family"]),
            "dataset_source": str(record["dataset_source"]),
            "trace_length": int(record["trace_length"]),
            "number_of_steps": int(record["number_of_steps"]),
            "unperturbed_graph_density": float(record["unperturbed_graph_density"]),
            "unperturbed_dependency_degree": float(record["unperturbed_dependency_degree"]),
            "unperturbed_redundancy_density": float(record["unperturbed_redundancy_density"]),
            "taxonomy_categories": list(record["taxonomy_categories"]),
            "structural_stability_proxy": float(record["structural_stability_proxy"]),
        }
    return metadata


def _records_by_trace(records: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["trace_id"])].append(record)
    return {
        trace_id: sorted(rows, key=lambda row: int(row["step_idx"]))
        for trace_id, rows in grouped.items()
    }


def _trace_regime(trace_length: int, graph_density: float, dependency_degree: float) -> str:
    density = "low" if graph_density < 0.40 else "mid" if graph_density < 0.75 else "high"
    degree = "low" if dependency_degree < 1.0 else "mid" if dependency_degree < 1.75 else "high"
    return f"steps_{trace_length}_density_{density}_degree_{degree}"


def _stage2_count(group_size: int) -> int:
    if group_size <= 1:
        return 0
    return max(1, min(group_size - 1, int(round(group_size * STAGE2_FRACTION))))


def _near_equal_sizes(total: int, buckets: int) -> list[int]:
    if buckets <= 0:
        return []
    base, remainder = divmod(total, buckets)
    return [base + (1 if index < remainder else 0) for index in range(buckets)]


def _stratum_report(trace_ids: Sequence[str], minimum_size: int) -> dict[str, Any]:
    return {
        "status": "ok" if len(trace_ids) >= minimum_size else "insufficient_samples",
        "bucket_size": len(trace_ids),
        "required": minimum_size,
        "trace_ids": sorted(trace_ids),
    }


def _apply_projection(scores: Sequence[float], projection_id: str) -> list[float]:
    if projection_id not in {projection["id"] for projection in PROJECTION_FAMILY}:
        raise ValueError(f"unknown projection_id={projection_id!r}")
    return [float(score) for score in scores]


def _stage2_metric_names(trace_metrics: Sequence[Mapping[str, float]]) -> list[str]:
    if trace_metrics:
        return sorted(trace_metrics[0])
    names = ["spearman_rho", "kendall_tau"]
    names.extend(f"ndcg_at_{k_value}" for k_value in NDCG_K_VALUES)
    names.extend(f"auc_high_impact_q{q_value}" for q_value in HIGH_IMPACT_Q)
    return sorted(names)


def _stage2_metric_names_from_projection_metrics(full_metrics: Mapping[str, Any]) -> list[str]:
    first = next(iter(full_metrics.values()))
    return sorted(first["metrics"])


def _summarize_metric(values: Sequence[float], *, n_steps: int, seed: int) -> dict[str, Any]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return {
            "mean": None,
            "std": None,
            "ci95": [None, None],
            "n_traces": 0,
            "n_steps": n_steps,
            "bootstrap_resamples": MIN_BOOTSTRAP_RESAMPLES,
        }
    return {
        "mean": _mean(finite),
        "std": _std(finite),
        "ci95": _bootstrap_ci(finite, seed),
        "n_traces": len(finite),
        "n_steps": n_steps,
        "bootstrap_resamples": MIN_BOOTSTRAP_RESAMPLES,
    }


def _spearman_gate(summary: Mapping[str, Any]) -> dict[str, Any]:
    mean_value = summary.get("mean")
    ci95 = summary.get("ci95", [None, None])
    lower = ci95[0] if isinstance(ci95, list) and len(ci95) == 2 else None
    upper = ci95[1] if isinstance(ci95, list) and len(ci95) == 2 else None
    if mean_value is None or lower is None or upper is None:
        return {
            "mean_positive": False,
            "ci_excludes_zero": False,
            "ci_lower_gt_zero": False,
            "gate_pass": False,
            "effect_size_label": "unavailable",
        }
    lower_float = float(lower)
    upper_float = float(upper)
    return {
        "mean_positive": float(mean_value) > 0.0,
        "ci_excludes_zero": lower_float > 0.0 or upper_float < 0.0,
        "ci_lower_gt_zero": lower_float > 0.0,
        "gate_pass": float(mean_value) > 0.0 and lower_float > 0.0,
        "effect_size_label": _effect_size_label(float(mean_value)),
    }


def _effect_size_label(rho: float) -> str:
    magnitude = abs(float(rho))
    if magnitude < 0.10:
        return "negligible"
    if magnitude < 0.30:
        return "small"
    if magnitude < 0.50:
        return "medium"
    return "large"


def _bootstrap_ci(values: Sequence[float], seed: int) -> list[float]:
    rng = random.Random(seed)
    if len(values) == 1:
        return [float(values[0]), float(values[0])]
    means = []
    for _ in range(MIN_BOOTSTRAP_RESAMPLES):
        sample = [values[rng.randrange(len(values))] for _index in range(len(values))]
        means.append(_mean(sample))
    means.sort()
    low = _percentile(means, BOOTSTRAP_CI[0])
    high = _percentile(means, BOOTSTRAP_CI[1])
    return [low, high]


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return _pearson(_average_ranks(left), _average_ranks(right))


def _kendall_tau_b(left: Sequence[float], right: Sequence[float]) -> float:
    concordant = discordant = ties_left = ties_right = 0
    n = len(left)
    for i in range(n):
        for j in range(i + 1, n):
            left_cmp = _compare(left[i], left[j])
            right_cmp = _compare(right[i], right[j])
            if left_cmp == 0 and right_cmp == 0:
                continue
            if left_cmp == 0:
                ties_left += 1
            elif right_cmp == 0:
                ties_right += 1
            elif left_cmp == right_cmp:
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt((concordant + discordant + ties_left) * (concordant + discordant + ties_right))
    if denominator == 0.0:
        return 0.0
    return float((concordant - discordant) / denominator)


def _ndcg(y_true: Sequence[float], y_score: Sequence[float], k: int) -> float:
    if not y_true:
        return 0.0
    relevance = [abs(float(value)) for value in y_true]
    order = sorted(range(len(y_score)), key=lambda index: (-float(y_score[index]), index))[:k]
    ideal = sorted(range(len(relevance)), key=lambda index: (-relevance[index], index))[:k]
    dcg = _dcg([relevance[index] for index in order])
    ideal_dcg = _dcg([relevance[index] for index in ideal])
    if ideal_dcg == 0.0:
        return 0.0
    return float(dcg / ideal_dcg)


def _auc_high_impact(y_true: Sequence[float], y_score: Sequence[float], q: int) -> float:
    n = len(y_true)
    if n <= 1:
        return 0.5
    top_count = max(1, int(math.ceil(n * (float(q) / 100.0))))
    relevance_order = sorted(range(n), key=lambda index: (-abs(float(y_true[index])), index))
    positives = set(relevance_order[:top_count])
    labels = [1 if index in positives else 0 for index in range(n)]
    n_pos = sum(labels)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    ranks = _average_ranks(y_score)
    sum_pos_ranks = sum(rank for rank, label in zip(ranks, labels, strict=True) if label == 1)
    auc = (sum_pos_ranks - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)


def _dcg(relevance: Sequence[float]) -> float:
    return float(
        sum(float(value) / math.log2(index + 2.0) for index, value in enumerate(relevance))
    )


def _resolve_k(k_value: int | str, n_items: int) -> int:
    if k_value == "ceil_10pct":
        return max(1, min(n_items, int(math.ceil(0.10 * n_items))))
    return max(1, min(n_items, int(k_value)))


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(float(value) for value in values), key=lambda item: (item[1], item[0]))
    ranks = [0.0 for _ in values]
    index = 0
    while index < len(indexed):
        end = index + 1
        while end < len(indexed) and indexed[end][1] == indexed[index][1]:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        for original_index, _value in indexed[index:end]:
            ranks[original_index] = average_rank
        index = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = _mean(left)
    right_mean = _mean(right)
    numerator = sum((l - left_mean) * (r - right_mean) for l, r in zip(left, right, strict=True))
    left_var = sum((l - left_mean) ** 2 for l in left)
    right_var = sum((r - right_mean) ** 2 for r in right)
    denominator = math.sqrt(left_var * right_var)
    if denominator == 0.0:
        return 0.0
    return float(numerator / denominator)


def _compare(left: float, right: float) -> int:
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stable_float(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(16**16 - 1)


def _metric_seed(group_name: str, projection_id: str, metric: str) -> int:
    digest = hashlib.sha256(f"{BOOTSTRAP_SEED}:{group_name}:{projection_id}:{metric}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    denominator = float(denominator)
    if denominator == 0.0:
        return 0.0
    return float(numerator) / denominator


def _mean(values: Sequence[float]) -> float:
    return float(sum(float(value) for value in values) / len(values)) if values else 0.0


def _variance(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean_value = _mean(values)
    return float(sum((float(value) - mean_value) ** 2 for value in values) / len(values))


def _std(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean_value = _mean(values)
    return float(math.sqrt(sum((float(value) - mean_value) ** 2 for value in values) / (len(values) - 1)))


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (percentile / 100.0) * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def _normalized_entropy(labels: Sequence[str]) -> float:
    if not labels:
        return 0.0
    counts = Counter(labels)
    total = sum(counts.values())
    entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
    max_entropy = math.log(max(2, len(counts)))
    return float(entropy / max_entropy) if max_entropy else 0.0


def _sign(value: float) -> str:
    if value > 0.0:
        return "positive"
    if value < 0.0:
        return "negative"
    return "zero"


def _disjoint(left: Iterable[str], right: Iterable[str]) -> bool:
    return set(left).isdisjoint(set(right))


def _format_optional_float(value: Any) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.4f}"


def _format_ci95(value: Any) -> str:
    if not isinstance(value, list) or len(value) != 2 or value[0] is None or value[1] is None:
        return "NA"
    return "[{low:.4f}, {high:.4f}]".format(low=float(value[0]), high=float(value[1]))


__all__ = [
    "FMA_VERSION",
    "MIN_STAGE2_STRATUM_SIZE",
    "PRIMARY_METHOD_ID",
    "REQUIRED_STAGE2_STRATA",
    "STAGE2_PROTOCOL_VERSION",
    "assign_stage2_strata",
    "build_stage2_baseline_leakage_audit",
    "build_stage2_baseline_results",
    "build_stage2_claim_gating_summary_markdown",
    "build_stage2_claim_support_summary_markdown",
    "build_stage2_frozen_protocol",
    "build_stage2_leakage_audit",
    "build_stage2_split_manifest",
    "evaluate_stage2_holdout",
    "load_stage2_step_records",
    "write_stage2_validation_outputs",
]
