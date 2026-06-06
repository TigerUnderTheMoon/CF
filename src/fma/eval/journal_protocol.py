"""Journal-grade evaluation protocol specifications for FMA.

This module defines only the evaluation contract. It does not change CIU/FMA
estimation, add training objectives, or introduce stronger interpretation.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping


PROTOCOL_VERSION = "journal_step_impact_v2_3"
CLAIM_LABELS = (
    "supported",
    "confirmed",
    "confirmed_weak",
    "qualified",
    "projection-dependent",
    "stratum-dependent",
    "unsupported",
    "insufficient_samples",
)

PERTURBATION_BASELINES = frozenset(
    {
        "random masking",
        "token dropout",
        "span masking",
        "graph removal",
        "edge dropout",
        "neighborhood rewiring",
        "full randomization",
    }
)
HIGH_IMPACT_Q = (10, 20)
BOOTSTRAP_CI = (2.5, 97.5)
MIN_BOOTSTRAP_RESAMPLES = 1000

PROJECTION_FAMILY: tuple[dict[str, str], ...] = (
    {
        "id": "pi_1",
        "name": "sum_normalized_pooling",
        "definition": "For each trace step, sum evidence over tokens or units assigned to that step and divide by total absolute evidence mass in the trace.",
        "formula": "score_j = sum_{a in step_j} e_a / sum_a abs(e_a)",
        "output": "step_level_score_vector",
    },
    {
        "id": "pi_2",
        "name": "mean_pooling",
        "definition": "For each trace step, average token-level or activation-level evidence assigned to that step.",
        "formula": "score_j = mean_{a in step_j} e_a",
        "output": "step_level_score_vector",
    },
    {
        "id": "pi_3",
        "name": "l2_norm_pooling",
        "definition": "For each trace step, compute the L2 norm of token-level or activation-level evidence assigned to that step.",
        "formula": "score_j = sqrt(sum_{a in step_j} e_a^2)",
        "output": "step_level_score_vector",
    },
    {
        "id": "pi_4",
        "name": "length_normalized_attribution_mass",
        "definition": "For each trace step, sum absolute evidence mass and divide by the number of tokens or units assigned to that step.",
        "formula": "score_j = sum_{a in step_j} abs(e_a) / max(1, length(step_j))",
        "output": "step_level_score_vector",
    },
)

METRIC_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "spearman_rho",
        "target": "rank agreement between s_B(r_i) and Delta_U(r_i)",
        "required_summary": ("mean", "std", "bootstrap_ci95"),
    },
    {
        "id": "kendall_tau",
        "target": "pairwise rank concordance between s_B(r_i) and Delta_U(r_i)",
        "required_summary": ("mean", "std", "bootstrap_ci95"),
    },
    {
        "id": "ndcg_at_k",
        "target": "top-k ranking quality for observed step-impact magnitude",
        "required_summary": ("mean", "std", "bootstrap_ci95"),
        "k_rule": "k must be fixed before Stage 2 validation.",
    },
    {
        "id": "auc_high_impact",
        "target": "classification of high-impact steps.",
        "required_summary": ("mean", "std", "bootstrap_ci95"),
        "high_impact_q": list(HIGH_IMPACT_Q),
    },
)

BASELINE_MAPPING_ROWS: tuple[dict[str, str], ...] = (
    {
        "class": "Structural-free perturbation",
        "baseline": "random masking",
        "status": "primary",
        "raw_evidence": "controlled perturbation response",
        "step_level_mapping": "Assign each controlled masking response to the perturbed trace step and emit one score per step.",
        "projection_required": "no",
        "allowed_use": "primary step-impact predictor",
        "rejection_rule": "Reject if perturbation changes trace-step alignment or token structure outside the controlled step.",
    },
    {
        "class": "Structural-free perturbation",
        "baseline": "token dropout",
        "status": "primary",
        "raw_evidence": "token dropout sensitivity",
        "step_level_mapping": "Aggregate dropout response by original trace-step membership through every projection in Pi.",
        "projection_required": "yes",
        "allowed_use": "primary step-impact predictor",
        "rejection_rule": "Reject raw token-dropout scores that are not projected to step vectors.",
    },
    {
        "class": "Structural-free perturbation",
        "baseline": "span masking",
        "status": "primary",
        "raw_evidence": "span-level masking sensitivity",
        "step_level_mapping": "Map each masked span to the owning trace step and preserve one score per trace step.",
        "projection_required": "conditional",
        "allowed_use": "primary step-impact predictor",
        "rejection_rule": "Reject span scores that cannot be aligned to trace steps.",
    },
    {
        "class": "Attribution baselines",
        "baseline": "gradient attribution",
        "status": "primary_if_white_box_access_exists",
        "raw_evidence": "token-level gradient evidence",
        "step_level_mapping": "Aggregate token evidence to trace steps through all projections in Pi.",
        "projection_required": "yes",
        "allowed_use": "white-box step-impact predictor",
        "rejection_rule": "Reject unprojected gradient vectors.",
    },
    {
        "class": "Attribution baselines",
        "baseline": "integrated gradients",
        "status": "primary_if_white_box_access_exists",
        "raw_evidence": "token-level path attribution evidence",
        "step_level_mapping": "Aggregate token evidence to trace steps through all projections in Pi.",
        "projection_required": "yes",
        "allowed_use": "white-box step-impact predictor",
        "rejection_rule": "Reject any result reported for only selected projections.",
    },
    {
        "class": "Attribution baselines",
        "baseline": "attention rollout",
        "status": "primary_if_white_box_access_exists",
        "raw_evidence": "token-level attention flow evidence",
        "step_level_mapping": "Aggregate token evidence to trace steps through all projections in Pi.",
        "projection_required": "yes",
        "allowed_use": "white-box step-impact predictor",
        "rejection_rule": "Reject raw attention weights as final method outputs.",
    },
    {
        "class": "Attribution baselines",
        "baseline": "activation attribution",
        "status": "primary_if_white_box_access_exists",
        "raw_evidence": "activation-level evidence",
        "step_level_mapping": "Assign activation evidence to token or step spans, then aggregate through all projections in Pi.",
        "projection_required": "yes",
        "allowed_use": "white-box step-impact predictor",
        "rejection_rule": "Reject unprojected activation values.",
    },
    {
        "class": "Structure controls",
        "baseline": "graph removal",
        "status": "primary_diagnostic",
        "raw_evidence": "node or edge removal response on trace-step dependency graph",
        "step_level_mapping": "Emit per-step scores from controlled graph-element removal while preserving trace-step identity.",
        "projection_required": "no",
        "allowed_use": "structural sensitivity diagnostic",
        "rejection_rule": "Reject if graph corruption is not level-tagged L0-L3.",
    },
    {
        "class": "Structure controls",
        "baseline": "edge dropout",
        "status": "primary_diagnostic",
        "raw_evidence": "controlled edge dropout response",
        "step_level_mapping": "Attribute response to affected incident trace steps and report the induced step-score vector.",
        "projection_required": "no",
        "allowed_use": "structural sensitivity diagnostic",
        "rejection_rule": "Reject if dropout fraction is chosen after Stage 2 results.",
    },
    {
        "class": "Structure controls",
        "baseline": "neighborhood rewiring",
        "status": "primary_diagnostic",
        "raw_evidence": "local graph rewiring response",
        "step_level_mapping": "Assign response to rewired neighborhood steps and emit one score per trace step.",
        "projection_required": "no",
        "allowed_use": "structural sensitivity diagnostic",
        "rejection_rule": "Reject unlabeled rewiring that cannot be reproduced.",
    },
    {
        "class": "Structure controls",
        "baseline": "full randomization",
        "status": "primary_diagnostic",
        "raw_evidence": "fully randomized graph response",
        "step_level_mapping": "Compute step scores after full dependency randomization with original step ids retained.",
        "projection_required": "no",
        "allowed_use": "structural sensitivity diagnostic",
        "rejection_rule": "Reject if original trace-step ids are not retained.",
    },
    {
        "class": "Generative feedback systems",
        "baseline": "self-refine",
        "status": "secondary_comparator_not_attribution_baseline",
        "raw_evidence": "localized edits or response deltas",
        "step_level_mapping": "Map via step edit localization, response delta sensitivity, or perturbation recovery distance.",
        "projection_required": "no",
        "allowed_use": "secondary comparator only",
        "rejection_rule": "Reject as an attribution baseline.",
    },
    {
        "class": "Generative feedback systems",
        "baseline": "reflexion",
        "status": "secondary_comparator_not_attribution_baseline",
        "raw_evidence": "localized feedback or recovery deltas",
        "step_level_mapping": "Map via step edit localization, response delta sensitivity, or perturbation recovery distance.",
        "projection_required": "no",
        "allowed_use": "secondary comparator only",
        "rejection_rule": "Reject as an attribution baseline.",
    },
)


def build_baseline_mapping_rows() -> tuple[dict[str, str], ...]:
    """Return baseline mappings with the Stage 2 target-reuse policy attached."""
    return tuple(
        {
            **row,
            "target_reuse_policy": _target_reuse_policy(row),
        }
        for row in BASELINE_MAPPING_ROWS
    )


def _target_reuse_policy(row: Mapping[str, str]) -> str:
    baseline = row["baseline"]
    if baseline in PERTURBATION_BASELINES:
        return (
            "Forbidden except explicitly labeled oracle/control rows: s_B(r_i) "
            "must come from a frozen baseline-specific scoring rule and must not "
            "copy Stage 2 y_i = Delta_U(r_i)."
        )
    if row["class"] == "Attribution baselines":
        return (
            "s_B(r_i) must be projected from token-level or activation-level "
            "evidence through Pi; direct Stage 2 target reuse is forbidden."
        )
    return (
        "s_B(r_i) must be derived from edit localization, response delta "
        "sensitivity, or recovery distance; direct Stage 2 target reuse is forbidden."
    )


def build_experiment_matrix() -> dict[str, Any]:
    """Return the pre-registered evaluation matrix schema."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "scope": "evaluation_protocol_only",
        "method_definition_preserved": True,
        "evaluation_target": build_step_target_definition(),
        "primary_question": "How well does each method predict or rank observed step-level utility change under controlled perturbation?",
        "required_cell_keys": [
            "model",
            "trace_regime",
            "task_distribution",
            "stage",
            "stratum",
            "projection",
            "baseline",
            "seed",
            "q_high_impact",
        ],
        "stages": {
            "stage_1_screening": {
                "use": "screening_only",
                "allowed_outputs": ["stability_strata", "pilot_distribution_checks"],
                "forbidden_use": "confirmatory_claims",
            },
            "stage_2_held_out_validation": {
                "use": "confirmatory_validation",
                "held_out_requirement": "disjoint traces or disjoint tasks relative to Stage 1",
                "required_strata": [
                    "S_high",
                    "S_mid",
                    "S_low",
                    "S_rand",
                ],
            },
        },
        "projection_family": [projection["id"] for projection in PROJECTION_FAMILY],
        "baseline_statuses": sorted(
            {row["status"] for row in BASELINE_MAPPING_ROWS}
        ),
        "primary_metrics": [metric["id"] for metric in METRIC_DEFINITIONS],
        "high_impact_q": list(HIGH_IMPACT_Q),
        "bootstrap": {
            "resample_unit": "trace",
            "minimum_resamples": MIN_BOOTSTRAP_RESAMPLES,
            "ci_percentiles": list(BOOTSTRAP_CI),
        },
        "claim_labels": list(CLAIM_LABELS),
        "cell_template": {
            "model": "<pre_registered_model_id>",
            "trace_regime": "<pre_registered_trace_regime>",
            "task_distribution": "<task_distribution_D>",
            "stage": "stage_2_held_out_validation",
            "stratum": "S_high|S_mid|S_low|S_rand",
            "projection": "pi_1|pi_2|pi_3|pi_4",
            "baseline": "<baseline_id>",
            "seed": "<fixed_before_stage_2>",
            "q_high_impact": "10|20",
            "outputs": {
                "step_scores": "s_B(r_i) in R^{|R|}",
                "ground_truth": "Delta_U(r_i)",
                "metrics": "mean/std/bootstrap_ci95 for all primary metrics",
            },
        },
    }


def build_step_target_definition() -> dict[str, Any]:
    """Return the unified step-impact prediction target."""
    return {
        "unit": "trace_step",
        "ground_truth": {
            "symbol": "y_i",
            "definition": "Delta_U(r_i)",
            "description": "Observed step-level utility change under controlled perturbation.",
        },
        "method_output": {
            "symbol": "s_B(r_i)",
            "type": "real-valued vector with length equal to the number of trace steps",
            "requirement": "Every baseline must output step-level scores before metric computation.",
        },
        "invalid_outputs": [
            "raw_token_scores",
            "raw_attention_weights",
            "unprojected_activation_values",
        ],
    }


def build_projection_robustness_spec() -> dict[str, Any]:
    """Return projection-family audit rules."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "projection_family": list(PROJECTION_FAMILY),
        "audit_scope": "All token-level and activation-level evidence must be mapped through every projection in Pi.",
        "primary_conclusion_rule": {
            "sign_invariance": "Primary conclusions require invariant effect direction across pi_1, pi_2, pi_3, and pi_4.",
            "projection_dependent": "If ranking or effect direction changes across projections, label the conclusion projection-dependent.",
            "selected_projection_claims": "Forbidden: treating two selected projections as a robustness audit.",
        },
        "result_schema": {
            "baseline": "<baseline_id>",
            "projection": "pi_1|pi_2|pi_3|pi_4",
            "metric": "spearman_rho|kendall_tau|ndcg_at_k|auc_high_impact",
            "mean": "float",
            "std": "float",
            "ci95": ["float_low", "float_high"],
            "effect_direction": "positive|negative|zero|mixed",
            "claim_label": list(CLAIM_LABELS),
        },
        "results": [],
    }


def build_statistical_stability_spec() -> dict[str, Any]:
    """Return stability reporting contract."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "target_distribution": "P(spearman_rho | model, trace_regime)",
        "required_group_keys": ["model", "trace_regime"],
        "required_outputs": [
            "mean_rho",
            "std_rho",
            "bootstrap_ci95_rho",
            "full_distribution_plot",
        ],
        "bootstrap": {
            "resample_unit": "trace",
            "minimum_resamples": MIN_BOOTSTRAP_RESAMPLES,
            "ci_percentiles": list(BOOTSTRAP_CI),
        },
        "descriptive_labels": {
            "allowed": ["unstable", "partial", "stable"],
            "restriction": "Labels summarize distributions only; they are not primary claims.",
        },
        "result_schema": {
            "model": "<model_id>",
            "trace_regime": "<trace_regime>",
            "baseline": "<baseline_id>",
            "projection": "pi_1|pi_2|pi_3|pi_4|not_applicable",
            "n_traces": "int",
            "mean_rho": "float",
            "std_rho": "float",
            "bootstrap_ci95_rho": ["float_low", "float_high"],
            "distribution_plot": "outputs/figures/stability_distributions/<file>.png",
            "label": "unstable|partial|stable",
        },
        "results": [],
    }


def build_structure_degradation_spec() -> dict[str, Any]:
    """Return structural corruption and degradation-curve contract."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "claim": "Step-impact prediction changes as a function of structural integrity.",
        "levels": [
            {
                "level": "L0",
                "corruption_index": 0,
                "modification": "original graph",
            },
            {
                "level": "L1",
                "corruption_index": 1,
                "modification": "edge dropout",
                "dropout_fraction_range": [0.10, 0.20],
            },
            {
                "level": "L2",
                "corruption_index": 2,
                "modification": "neighborhood rewiring",
            },
            {
                "level": "L3",
                "corruption_index": 3,
                "modification": "full randomization",
            },
        ],
        "degradation_curve": {
            "definition": "D_k = Delta_U_L0 - Delta_U_Lk",
            "required_points": ["L0", "L1", "L2", "L3"],
        },
        "sensitivity_slope": {
            "definition": "slope of Delta_U with respect to corruption_index over L0-L3",
            "estimator": "pre-registered linear slope or finite-difference slope; choice fixed before Stage 2",
        },
        "result_schema": {
            "model": "<model_id>",
            "trace_regime": "<trace_regime>",
            "baseline": "<baseline_id>",
            "level": "L0|L1|L2|L3",
            "delta_u_mean": "float",
            "delta_u_std": "float",
            "delta_u_ci95": ["float_low", "float_high"],
            "D_k": "float",
            "sensitivity_slope": "float",
            "curve_plot": "outputs/figures/structure_degradation/<file>.png",
        },
        "results": [],
    }


def build_stratified_validation_spec() -> dict[str, Any]:
    """Return held-out validation and anti-cherry-picking contract."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "stage_1": {
            "name": "screening_only",
            "inputs": "pilot traces with reduced seeds",
            "outputs": "stability strata only",
            "restriction": "No final claim may be made from Stage 1.",
        },
        "stage_2": {
            "name": "held_out_validation",
            "held_out_requirement": "Use disjoint held-out traces or held-out tasks.",
            "parameter_lock": "k, q, delta, projections, metrics, and strata rules must be fixed before Stage 2.",
        },
        "strata": {
            "S_high": "high-stability region under frozen g(T)",
            "S_mid": "median-stability region under frozen g(T)",
            "S_low": "low-stability region under frozen g(T)",
            "S_rand": "overlapping uniform random audit sample with a fixed seed",
        },
        "strata_semantics": {
            "partition_strata": ["S_low", "S_mid", "S_high"],
            "audit_strata": ["S_rand"],
            "overlap_allowed": {"S_rand": True},
            "partition_rule": "Only S_low, S_mid, and S_high are expected to sum to the Stage 2 trace count.",
        },
        "claim_rule": "All claims must hold across all strata or be labeled stratum-dependent.",
        "forbidden": [
            "reporting only stable subsets",
            "excluding unstable regimes",
            "choosing k, q, or delta after Stage 2 results",
            "treating Stage 1 as confirmatory evidence",
        ],
        "result_schema": {
            "model": "<model_id>",
            "trace_regime": "<trace_regime>",
            "stratum": "S_high|S_mid|S_low|S_rand",
            "n_traces": "int",
            "metrics": "all primary metrics with mean/std/bootstrap_ci95",
            "claim_label": list(CLAIM_LABELS),
        },
        "results": [],
    }


def build_claim_support_summary_markdown() -> str:
    """Return the claim-support summary template."""
    lines = [
        "# Claim Support Summary",
        "",
        f"Protocol version: `{PROTOCOL_VERSION}`",
        "",
        "## Claim Decision Labels",
        "",
        "| Label | Required condition |",
        "|---|---|",
        "| `supported` | Stage 1 exploratory support only; never a final claim. |",
        "| `confirmed` | Stage 2 held-out results satisfy all metric, projection, stratum, and structure-degradation gates. |",
        "| `confirmed_weak` | Final-paper wording for Stage 2 confirmation with small effect size. |",
        "| `qualified` | Stage 2 supports the claim with pre-declared limits that do not change direction across projections or strata. |",
        "| `projection-dependent` | Ranking or effect direction changes across `pi_1`, `pi_2`, `pi_3`, and `pi_4`. |",
        "| `stratum-dependent` | The claim holds in some required strata but not all. |",
        "| `unsupported` | Required evidence is missing, unstable, contradictory, or fails any audit gate. |",
        "| `insufficient_samples` | One or more required Stage 2 strata is underfilled. |",
        "",
        "## Audit Gates",
        "",
        "| Gate | Status before Stage 2 results |",
        "|---|---|",
        "| Baselines mapped to step-level vectors | pending evidence |",
        "| Baseline target-leakage audit completed | pending evidence |",
        "| Projection audit across all `Pi` | pending evidence |",
        "| Held-out Stage 2 validation | pending evidence |",
        "| High, mid, low, and random strata included | pending evidence |",
        "| Rank metrics and AUC include bootstrap CIs | pending evidence |",
        "| Structure degradation curves included | pending evidence |",
        "| No single-run or single-projection conclusion | pending evidence |",
        "",
        "## Forbidden Analysis Modes",
        "",
        "- Raw token scores, raw attention weights, or unprojected activation values as final method outputs.",
        "- Projection robustness claimed from only selected projections.",
        "- Self-refine or reflexion treated as attribution baselines.",
        "- Stage 1 screening treated as confirmatory evidence.",
        "- Stage 1 `supported` wording used as Stage 2 confirmation.",
        "- Stable-only reporting or exclusion of unstable regimes.",
        "- Post-result selection of `k`, `q`, or `delta`.",
        "- New training or RL objectives introduced as part of the evaluation.",
        "- Stronger causal interpretation than the protocol supports.",
        "- Filtering unsupported or unstable results out of the report.",
        "",
        "## Current Claim Table",
        "",
        "| Claim ID | Claim | Decision | Evidence files | Notes |",
        "|---|---|---|---|---|",
        "| none_registered | No Stage 2 claim registered yet. | `unsupported` | none | Protocol artifacts define the gates; confirmatory results have not been filled. |",
    ]
    return "\n".join(lines) + "\n"


def build_file_output_spec() -> dict[str, Any]:
    """Return the required file contract."""
    return {
        "required_files": [
            "outputs/experiment_matrix.json",
            "outputs/baseline_mapping_table.csv",
            "outputs/projection_robustness.json",
            "outputs/statistical_stability.json",
            "outputs/structure_degradation_curves.json",
            "outputs/stratified_validation_results.json",
            "outputs/claim_support_summary.md",
            "outputs/stage2_frozen_protocol.json",
            "outputs/stage2_split_manifest.json",
            "outputs/stage2_holdout_validation.json",
            "outputs/stage2_projection_audit.json",
            "outputs/stage2_stratified_metrics.json",
            "outputs/stage2_baseline_results.json",
            "outputs/stage2_baseline_leakage_audit.json",
            "outputs/stage2_claim_gating_summary.md",
            "outputs/stage2_leakage_audit.json",
        ],
        "required_directories": [
            "outputs/figures/stability_distributions/",
            "outputs/figures/structure_degradation/",
        ],
        "json_result_policy": "Use empty results arrays until Stage 2 measurements are available; do not fabricate confirmatory values.",
        "encoding": "utf-8",
    }


def build_protocol_bundle() -> dict[str, Any]:
    """Return all protocol sections requested by the journal upgrade."""
    return {
        "projection_family_definition": list(PROJECTION_FAMILY),
        "step_level_target_definition": build_step_target_definition(),
        "baseline_mapping_table": list(build_baseline_mapping_rows()),
        "metric_definitions": list(METRIC_DEFINITIONS),
        "high_impact_step_definition": {
            "definition": "top q percent of abs(Delta_U)",
            "q_values": list(HIGH_IMPACT_Q),
            "parameter_lock": "q fixed before Stage 2 validation.",
        },
        "structure_corruption_protocol": build_structure_degradation_spec(),
        "stratified_held_out_validation_protocol": build_stratified_validation_spec(),
        "robustness_audit_checklist": [
            "all baselines mapped to step-level vectors",
            "baseline target-leakage audit completed",
            "perturbation baselines do not reuse Stage 2 Delta_U targets except labeled oracle/control rows",
            "all token/activation baselines evaluated under pi_1 through pi_4",
            "primary conclusions sign-invariant across all projections",
            "Stage 2 uses held-out traces or tasks",
            "S_high, S_mid, S_low, and S_rand included",
            "Spearman, Kendall, nDCG@k, and AUC reported with mean/std/bootstrap CI",
            "q in {10, 20} reported for high-impact classification",
            "L0-L3 structure degradation curves included",
            "claim labels assigned without filtering unsupported results",
        ],
        "forbidden_analysis_modes": [
            "raw token scores as final method outputs",
            "raw attention weights as final method outputs",
            "unprojected activation values as final method outputs",
            "projection robustness from selected projections only",
            "Stage 1 confirmatory claims",
            "Stage 1 supported wording as final evidence",
            "stable-only reporting",
            "post-result parameter selection",
            "new training or RL objectives",
            "stronger causal interpretation than the protocol supports",
        ],
        "file_output_specification": build_file_output_spec(),
    }


def write_journal_protocol_outputs(output_dir: str | Path) -> dict[str, Path]:
    """Write deterministic protocol artifacts under the requested output dir."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    figure_stability = root / "figures" / "stability_distributions"
    figure_structure = root / "figures" / "structure_degradation"
    figure_stability.mkdir(parents=True, exist_ok=True)
    figure_structure.mkdir(parents=True, exist_ok=True)

    paths = {
        "experiment_matrix": root / "experiment_matrix.json",
        "baseline_mapping_table": root / "baseline_mapping_table.csv",
        "projection_robustness": root / "projection_robustness.json",
        "statistical_stability": root / "statistical_stability.json",
        "structure_degradation_curves": root / "structure_degradation_curves.json",
        "stratified_validation_results": root / "stratified_validation_results.json",
        "claim_support_summary": root / "claim_support_summary.md",
    }

    _write_json(paths["experiment_matrix"], build_experiment_matrix())
    _write_csv(paths["baseline_mapping_table"], build_baseline_mapping_rows())
    _write_json(paths["projection_robustness"], build_projection_robustness_spec())
    _write_json(paths["statistical_stability"], build_statistical_stability_spec())
    _write_json(paths["structure_degradation_curves"], build_structure_degradation_spec())
    _write_json(paths["stratified_validation_results"], build_stratified_validation_spec())
    paths["claim_support_summary"].write_text(
        build_claim_support_summary_markdown(),
        encoding="utf-8",
    )
    return paths


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: tuple[dict[str, str], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "class",
        "baseline",
        "status",
        "raw_evidence",
        "step_level_mapping",
        "projection_required",
        "allowed_use",
        "rejection_rule",
        "target_reuse_policy",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


__all__ = [
    "BASELINE_MAPPING_ROWS",
    "PERTURBATION_BASELINES",
    "CLAIM_LABELS",
    "HIGH_IMPACT_Q",
    "METRIC_DEFINITIONS",
    "PROJECTION_FAMILY",
    "PROTOCOL_VERSION",
    "build_baseline_mapping_rows",
    "build_claim_support_summary_markdown",
    "build_experiment_matrix",
    "build_file_output_spec",
    "build_projection_robustness_spec",
    "build_protocol_bundle",
    "build_statistical_stability_spec",
    "build_step_target_definition",
    "build_stratified_validation_spec",
    "build_structure_degradation_spec",
    "write_journal_protocol_outputs",
]
