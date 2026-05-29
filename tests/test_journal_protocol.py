from __future__ import annotations

import csv
import json

from fma.eval.journal_protocol import (
    BASELINE_MAPPING_ROWS,
    CLAIM_LABELS,
    HIGH_IMPACT_Q,
    PROJECTION_FAMILY,
    build_baseline_mapping_rows,
    build_experiment_matrix,
    build_protocol_bundle,
    write_journal_protocol_outputs,
)
from fma.eval.stage2_validation import (
    _build_claim_gating,
    _build_projection_audit,
    _effect_size_label,
    build_stage2_claim_gating_summary_markdown,
    write_stage2_validation_outputs,
)


def test_projection_family_has_required_four_step_mappings() -> None:
    assert [projection["id"] for projection in PROJECTION_FAMILY] == [
        "pi_1",
        "pi_2",
        "pi_3",
        "pi_4",
    ]
    assert all(projection["output"] == "step_level_score_vector" for projection in PROJECTION_FAMILY)


def test_baseline_rows_all_define_step_level_mapping() -> None:
    rows = build_baseline_mapping_rows()
    assert len(BASELINE_MAPPING_ROWS) >= 4
    assert all(row["step_level_mapping"] for row in rows)
    assert all(row["target_reuse_policy"] for row in rows)
    assert all("raw" not in row["allowed_use"].lower() for row in rows)


def test_experiment_matrix_requires_projection_and_strata_audits() -> None:
    matrix = build_experiment_matrix()

    assert matrix["method_definition_preserved"] is True
    assert matrix["projection_family"] == ["pi_1", "pi_2", "pi_3", "pi_4"]
    assert matrix["high_impact_q"] == list(HIGH_IMPACT_Q)
    assert matrix["stages"]["stage_2_held_out_validation"]["required_strata"] == [
        "S_high",
        "S_mid",
        "S_low",
        "S_rand",
    ]
    assert "confirmed" in CLAIM_LABELS
    assert "confirmed_weak" in CLAIM_LABELS
    assert "supported" in CLAIM_LABELS


def test_protocol_bundle_contains_requested_sections() -> None:
    bundle = build_protocol_bundle()

    assert set(bundle) == {
        "projection_family_definition",
        "step_level_target_definition",
        "baseline_mapping_table",
        "metric_definitions",
        "high_impact_step_definition",
        "structure_corruption_protocol",
        "stratified_held_out_validation_protocol",
        "robustness_audit_checklist",
        "forbidden_analysis_modes",
        "file_output_specification",
    }


def test_writer_materializes_required_protocol_files(tmp_path) -> None:
    paths = write_journal_protocol_outputs(tmp_path)

    assert set(paths) == {
        "experiment_matrix",
        "baseline_mapping_table",
        "projection_robustness",
        "statistical_stability",
        "structure_degradation_curves",
        "stratified_validation_results",
        "claim_support_summary",
    }
    for path in paths.values():
        assert path.exists()

    json.loads(paths["experiment_matrix"].read_text(encoding="utf-8"))
    json.loads(paths["projection_robustness"].read_text(encoding="utf-8"))
    json.loads(paths["statistical_stability"].read_text(encoding="utf-8"))
    json.loads(paths["structure_degradation_curves"].read_text(encoding="utf-8"))
    json.loads(paths["stratified_validation_results"].read_text(encoding="utf-8"))

    with paths["baseline_mapping_table"].open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["baseline"] == "random masking"
    assert (tmp_path / "figures" / "stability_distributions").is_dir()
    assert (tmp_path / "figures" / "structure_degradation").is_dir()


def test_stage2_writer_materializes_required_holdout_files(tmp_path) -> None:
    graph_path = tmp_path / "reflection_graph.json"
    necessity_path = tmp_path / "necessity_scores.jsonl"

    graphs = []
    rows = []
    for trace_index in range(12):
        trace_id = f"trace_{trace_index:03d}"
        nodes = [
            {
                "node_id": f"{trace_id}::r{step:03d}",
                "step_index": step,
                "taxonomy_label": ["VERIFICATION", "PLANNING", "DECOMPOSITION"][step],
            }
            for step in range(3)
        ]
        graphs.append(
            {
                "graph_id": trace_id,
                "nodes": nodes,
                "edges": [
                    {"source": f"{trace_id}::r000", "target": f"{trace_id}::r001"},
                    {"source": f"{trace_id}::r001", "target": f"{trace_id}::r002"},
                ],
            }
        )
        for step in range(3):
            rows.append(
                {
                    "trace_id": trace_id,
                    "step_idx": step,
                    "necessity": float(2 - step),
                    "attribution_score": float(2 - step),
                }
            )

    graph_path.write_text(json.dumps({"graphs": graphs}), encoding="utf-8")
    necessity_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    paths = write_stage2_validation_outputs(
        tmp_path,
        necessity_scores_path=necessity_path,
        reflection_graph_path=graph_path,
    )

    assert set(paths) == {
        "stage2_frozen_protocol",
        "stage2_split_manifest",
        "stage2_holdout_validation",
        "stage2_projection_audit",
        "stage2_stratified_metrics",
        "stage2_baseline_results",
        "stage2_baseline_leakage_audit",
        "stage2_claim_gating_summary",
        "stage2_leakage_audit",
    }
    for path in paths.values():
        assert path.exists()

    protocol = json.loads(paths["stage2_frozen_protocol"].read_text(encoding="utf-8"))
    split = json.loads(paths["stage2_split_manifest"].read_text(encoding="utf-8"))
    leakage = json.loads(paths["stage2_leakage_audit"].read_text(encoding="utf-8"))
    baseline_results = json.loads(paths["stage2_baseline_results"].read_text(encoding="utf-8"))
    baseline_leakage = json.loads(
        paths["stage2_baseline_leakage_audit"].read_text(encoding="utf-8")
    )

    assert protocol["stratum_assignment_rule_g_T"]["required_strata"] == [
        "S_high",
        "S_mid",
        "S_low",
        "S_rand",
    ]
    assert protocol["no_stage2_tuning"] is True
    assert set(split["stage1_trace_ids"]).isdisjoint(split["stage2_trace_ids"])
    assert set(split["stage2_strata"]) == {"S_high", "S_mid", "S_low", "S_rand"}
    semantics = split["strata_semantics"]
    assert semantics["partition_strata"] == ["S_low", "S_mid", "S_high"]
    assert semantics["audit_strata"] == ["S_rand"]
    assert semantics["overlap_allowed"]["S_rand"] is True
    assert semantics["partition_trace_count"] == semantics["unique_stage2_trace_count"]
    assert semantics["total_stratum_memberships"] >= semantics["unique_stage2_trace_count"]
    assert leakage["checklist"]["stage2_metrics_used_for_strata"] is False
    assert leakage["checklist"]["stage2_target_y_i_reused_as_baseline_prediction"] is False
    assert leakage["baseline_evaluation_scope"]["not_evaluated"][0]["status"] == "not_evaluated_no_stage2_step_scores"
    assert baseline_results["summary"]["fabricated_baseline_scores"] is False
    assert baseline_results["summary"]["evaluated_baselines"] == 0
    assert baseline_results["baselines"][0]["target_leakage_status"] == "missing_artifact"
    assert baseline_leakage["checklist"]["stage2_target_y_i_reused_as_prediction"] is False
    assert baseline_leakage["baseline_checks"][0]["target_leakage_status"] == "missing_artifact"
    assert all(
        check["direct_target_reuse_detected"] is False
        for check in baseline_leakage["baseline_checks"]
    )


def test_effect_size_labels_mark_current_stage2_rho_as_small() -> None:
    assert _effect_size_label(0.09) == "negligible"
    assert _effect_size_label(0.1628) == "small"
    assert _effect_size_label(0.30) == "medium"
    assert _effect_size_label(0.50) == "large"


def test_claim_gating_downgrades_when_full_ci_contains_zero() -> None:
    full_metrics = _projection_metrics(mean=0.16, ci95=[-0.01, 0.24])
    stratum_metrics = {
        stratum: {
            "status": "ok",
            "metrics_by_projection": _projection_metrics(mean=0.16, ci95=[0.02, 0.24]),
        }
        for stratum in ["S_high", "S_mid", "S_low", "S_rand"]
    }

    claim_gating = _build_claim_gating(
        full_metrics,
        stratum_metrics,
        _build_projection_audit(full_metrics, stratum_metrics),
    )

    labels = {claim["claim_id"]: claim for claim in claim_gating["claims"]}
    assert labels["C1_rank_generalization"]["label"] == "qualified"
    assert labels["C1_rank_generalization"]["effect_size_label"] == "small"
    assert labels["C1_rank_generalization"]["ci_excludes_zero"] is False
    assert "CI includes zero" in labels["C1_rank_generalization"]["downgrade_reason"]
    assert labels["C2_projection_robustness"]["label"] == "qualified"


def test_confirmed_small_effect_uses_confirmed_weak_final_label() -> None:
    full_metrics = _projection_metrics(mean=0.16, ci95=[0.02, 0.24])
    stratum_metrics = {
        stratum: {
            "status": "ok",
            "metrics_by_projection": _projection_metrics(mean=0.16, ci95=[0.02, 0.24]),
        }
        for stratum in ["S_high", "S_mid", "S_low", "S_rand"]
    }

    claim_gating = _build_claim_gating(
        full_metrics,
        stratum_metrics,
        _build_projection_audit(full_metrics, stratum_metrics),
    )

    labels = {claim["claim_id"]: claim for claim in claim_gating["claims"]}
    assert labels["C1_rank_generalization"]["stage2_confirmation_label"] == "confirmed"
    assert labels["C1_rank_generalization"]["label"] == "confirmed_weak"


def test_stratified_claim_downgrades_when_one_stratum_ci_contains_zero() -> None:
    full_metrics = _projection_metrics(mean=0.16, ci95=[0.02, 0.24])
    stratum_metrics = {
        stratum: {
            "status": "ok",
            "metrics_by_projection": _projection_metrics(
                mean=0.16,
                ci95=[-0.01, 0.24] if stratum == "S_low" else [0.02, 0.24],
            ),
        }
        for stratum in ["S_high", "S_mid", "S_low", "S_rand"]
    }

    claim_gating = _build_claim_gating(
        full_metrics,
        stratum_metrics,
        _build_projection_audit(full_metrics, stratum_metrics),
    )

    claims = {claim["claim_id"]: claim for claim in claim_gating["claims"]}
    assert claims["C1_rank_generalization"]["label"] == "qualified"
    assert claims["C2_projection_robustness"]["label"] == "qualified"
    c3 = claims["C3_stratified_generalization"]
    assert c3["label"] == "qualified"
    assert c3["downgrade_reason"] == "One stratum Spearman CI includes zero: S_low"
    assert claim_gating["stratum_rho_gates"]["S_low"]["ci_includes_zero"] is True


def test_all_primary_claims_require_all_required_strata() -> None:
    full_metrics = _projection_metrics(mean=0.16, ci95=[0.02, 0.24])
    stratum_metrics = {
        stratum: {
            "status": "ok",
            "metrics_by_projection": _projection_metrics(
                mean=0.16,
                ci95=[-0.01, 0.24]
                if stratum in {"S_mid", "S_rand"}
                else [0.02, 0.24],
            ),
        }
        for stratum in ["S_high", "S_mid", "S_low", "S_rand"]
    }

    claim_gating = _build_claim_gating(
        full_metrics,
        stratum_metrics,
        _build_projection_audit(full_metrics, stratum_metrics),
    )

    claims = {claim["claim_id"]: claim for claim in claim_gating["claims"]}
    assert claims["C1_rank_generalization"]["label"] == "stratum-dependent"
    assert claims["C2_projection_robustness"]["label"] == "stratum-dependent"
    assert claims["C3_stratified_generalization"]["label"] == "stratum-dependent"
    assert "S_mid" in claims["C1_rank_generalization"]["downgrade_reason"]
    assert "S_rand" in claims["C2_projection_robustness"]["downgrade_reason"]


def test_claim_gating_summary_reports_rho_ci_effect_and_downgrade_reason() -> None:
    claim_gating = {
        "claims": [
            {
                "claim_id": "C1_rank_generalization",
                "label": "qualified",
                "rho_mean": 0.1628,
                "rho_ci95": [-0.01, 0.24],
                "ci_excludes_zero": False,
                "effect_size_label": "small",
                "passing_strata": 4,
                "projection_status": "sign_consistent_positive",
                "downgrade_reason": "Full Stage 2 Spearman CI includes zero.",
                "notes": "Full Stage 2 Spearman CI includes zero.",
            }
        ]
    }

    markdown = build_stage2_claim_gating_summary_markdown({"claim_gating": claim_gating})

    assert "rho_mean" in markdown
    assert "rho_ci95" in markdown
    assert "small" in markdown
    assert "Full Stage 2 Spearman CI includes zero." in markdown


def _projection_metrics(mean: float, ci95: list[float]) -> dict[str, dict[str, object]]:
    metrics = {}
    for projection in ["pi_1", "pi_2", "pi_3", "pi_4"]:
        metrics[projection] = {
            "group": "fake",
            "projection": projection,
            "projection_policy": "identity_for_preprojected_step_level_fma",
            "n_traces": 20,
            "n_steps": 60,
            "metrics": {
                "spearman_rho": {
                    "mean": mean,
                    "std": 0.1,
                    "ci95": ci95,
                    "n_traces": 20,
                    "n_steps": 60,
                    "bootstrap_resamples": 1000,
                    "mean_positive": mean > 0.0,
                    "ci_excludes_zero": ci95[0] > 0.0 or ci95[1] < 0.0,
                    "ci_lower_gt_zero": ci95[0] > 0.0,
                    "gate_pass": mean > 0.0 and ci95[0] > 0.0,
                    "effect_size_label": _effect_size_label(mean),
                }
            },
        }
    return metrics
