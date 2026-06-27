from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
COMMON_FIELDS = {
    "claim_boundary",
    "evidence_level",
    "zero_api_calls",
    "seed_list",
    "output_dir",
    "source_artifacts",
    "known_limitations",
}


def run_script(script_name: str, output_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / script_name),
            "--output-dir",
            str(output_dir),
            *args,
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_report(output_dir: Path, file_name: str) -> dict:
    path = output_dir / file_name
    assert path.exists(), f"Missing report: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_common_report_fields(report: dict, output_dir: Path, evidence_level: str) -> None:
    missing = COMMON_FIELDS - set(report)
    assert not missing, f"Missing common fields: {missing}"
    assert report["claim_boundary"] == "real_prm800k_audit_prioritization_only"
    assert report["evidence_level"] == evidence_level
    assert report["zero_api_calls"] is True
    assert report["output_dir"] == str(output_dir.resolve())
    assert isinstance(report["seed_list"], list)
    assert isinstance(report["source_artifacts"], list)
    assert isinstance(report["known_limitations"], list)


def test_graph_construction_ablation_fixture_outputs_reports(tmp_path: Path) -> None:
    output_dir = tmp_path / "graph_construction_ablation"
    result = run_script(
        "run_graph_construction_ablation.py",
        output_dir,
        "--fixture",
        "--fixture-size",
        "12",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_report(output_dir, "graph_construction_ablation.json")
    assert_common_report_fields(report, output_dir, "mechanism_ablation")
    assert set(report["variants"]) == {
        "tfidf_topical",
        "temporal_only",
        "jaccard_topical",
        "embedding_topical",
        "shuffled_topical",
    }
    for metrics in report["variants"].values():
        assert metrics["status"] in {"ok", "blocked"}
        if metrics["status"] == "blocked":
            assert metrics["blocked_reason"]
            continue
        assert {
            "spearman",
            "kendall",
            "structural_faithfulness_pearson",
            "mean_necessity",
            "max_necessity",
            "redundancy_density",
            "bottleneck_count",
            "reachable_ratio",
            "bridge_node_fraction",
            "influence_depth",
        } <= set(metrics)
    embedding = report["variants"]["embedding_topical"]
    assert embedding["status"] == "ok"
    assert embedding["embedding_model"] == "fixture-hashed-embedding"
    assert embedding["embedding_dimension"] == 384
    assert "embedding_topical" in report["graph_constructor_metadata"]

    md_path = output_dir / "graph_construction_ablation.md"
    assert md_path.exists()
    markdown = md_path.read_text(encoding="utf-8")
    assert "Graph Construction Ablation" in markdown
    assert "validated_kbs_workflow=false" in markdown
    assert "human_efficiency_claim=false" in markdown


def test_graph_construction_ablation_embedding_blocked_is_explicit(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "graph_construction_ablation_blocked"
    result = run_script(
        "run_graph_construction_ablation.py",
        output_dir,
        "--fixture",
        "--fixture-size",
        "12",
        "--embedding-backend",
        "blocked",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_report(output_dir, "graph_construction_ablation.json")
    embedding = report["variants"]["embedding_topical"]
    assert embedding["status"] == "blocked"
    assert "blocked_reason" in embedding
    assert "fallback" not in embedding.get("blocked_reason", "").lower()


def test_audit_card_auto_validation_fixture_outputs_oracle_ir_metrics(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "audit_card_auto_validation"
    result = run_script(
        "run_audit_card_auto_validation.py",
        output_dir,
        "--fixture",
        "--fixture-size",
        "80",
        "--bootstrap-samples",
        "100",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_report(output_dir, "audit_card_auto_validation.json")
    assert_common_report_fields(report, output_dir, "oracle_auto_audit_validation")
    assert report["human_subjects"] is False
    assert report["human_efficiency_claim"] is False
    assert report["validated_kbs_workflow"] is False
    assert report["experiment"] == "audit_card_auto_validation"
    assert set(report["targets"]) == {
        "bottleneck_protection",
        "redundancy_consolidation",
        "weak_utility_anchor",
        "structural_over_correction",
    }
    assert set(report["methods"]) == {"w_struct_only", "scfma_decomposition"}
    for method in report["methods"].values():
        assert {
            "mean_recall_at_budget",
            "mean_ndcg_at_budget",
            "mean_mrr",
            "mean_top1_failure_mode_hit",
            "mean_inspection_cost_proxy",
            "bootstrap_ci",
        } <= set(method)
    assert report["available_fields"]["w_struct_only"] == ["w_struct_scalar"]
    assert {
        "fidelity",
        "necessity",
        "redundancy",
        "bottleneck",
        "recommended_action",
    } <= set(report["available_fields"]["scfma_decomposition"])

    md_path = output_dir / "audit_card_auto_validation.md"
    csv_path = output_dir / "audit_card_auto_validation.csv"
    assert md_path.exists()
    assert csv_path.exists()
    markdown = md_path.read_text(encoding="utf-8")
    assert "Oracle-based Auto Audit-Target Validation" in markdown
    assert "human_subjects=false" in markdown
    assert "human_efficiency_claim=false" in markdown


def test_scu_component_contribution_fixture_outputs_multiseed_table(tmp_path: Path) -> None:
    output_dir = tmp_path / "scu_component_contribution"
    result = run_script(
        "run_scu_component_contribution.py",
        output_dir,
        "--samples-per-seed",
        "12",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_report(output_dir, "scu_component_contribution.json")
    assert_common_report_fields(report, output_dir, "mechanism_ablation")
    assert report["seed_list"] == [42, 123, 456, 789, 1024]
    assert set(report["variants"]) == {
        "full_scu",
        "no_fidelity",
        "no_structure",
        "no_redundancy",
        "no_bottleneck",
    }
    for metrics in report["variants"].values():
        assert {
            "spearman_mean",
            "spearman_std",
            "spearman_bootstrap_ci",
            "kendall_mean",
            "kendall_std",
            "kendall_bootstrap_ci",
            "convergence_rate",
            "delta_spearman_vs_full",
            "effect_size_vs_full",
        } <= set(metrics)
        assert {"ci_lower", "ci_upper"} <= set(metrics["spearman_bootstrap_ci"])
        assert {"ci_lower", "ci_upper"} <= set(metrics["kendall_bootstrap_ci"])

    md_path = output_dir / "scu_component_contribution.md"
    assert md_path.exists()
    assert "Component Contribution of the SCU Objective" in md_path.read_text(
        encoding="utf-8"
    )


def test_scu_hyperparameter_sensitivity_fixture_outputs_gamma_delta_grid(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "scu_hyperparameter_sensitivity"
    result = run_script(
        "run_scu_hyperparameter_sensitivity.py",
        output_dir,
        "--samples-per-seed",
        "8",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_report(output_dir, "scu_hyperparameter_sensitivity.json")
    assert_common_report_fields(report, output_dir, "mechanism_ablation")
    assert report["gamma_values"] == [0.0, 0.1, 0.2, 0.5, 0.8]
    assert report["delta_values"] == [0.0, 0.05, 0.1, 0.2, 0.4]
    assert report["recommended_default"] == {
        "gamma": 0.2,
        "delta": 0.1,
        "selection_role": "synthetic structural-stress default for QP diagnostics",
    }
    assert len(report["grid"]) == 25
    for row in report["grid"]:
        assert {
            "gamma",
            "delta",
            "spearman_mean",
            "spearman_std",
            "kendall_mean",
            "kendall_std",
            "convergence_rate",
            "delta_spearman_vs_default",
        } <= set(row)

    csv_path = output_dir / "gamma_delta_grid.csv"
    assert csv_path.exists()
    assert "gamma,delta,spearman_mean" in csv_path.read_text(encoding="utf-8")

    md_path = output_dir / "scu_hyperparameter_sensitivity.md"
    assert md_path.exists()
    markdown = md_path.read_text(encoding="utf-8").lower()
    assert "hyperparameter sensitivity" in markdown
    assert "not positive external validation" in markdown


def test_failure_taxonomy_fixture_outputs_labels_and_cases(tmp_path: Path) -> None:
    output_dir = tmp_path / "failure_taxonomy"
    result = run_script(
        "build_failure_taxonomy.py",
        output_dir,
        "--fixture",
        "--fixture-size",
        "80",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_report(output_dir, "failure_taxonomy.json")
    assert_common_report_fields(report, output_dir, "diagnostic_support")
    assert {
        "structural_over_correction",
        "redundancy_misclassification",
        "bottleneck_over_protection",
        "weak_utility_anchor",
        "low_signal_or_tie",
    } <= set(report["taxonomy_counts"])
    assert 3 <= len(report["representative_cases"]) <= 5
    for case in report["representative_cases"]:
        assert {
            "sample_id",
            "taxonomy_labels",
            "primary_label",
            "diagnostic_explanation",
            "step_level",
        } <= set(case)
        assert case["step_level"]
        assert {
            "step_text_excerpt",
            "label",
            "w_struct",
            "scfma_qp",
            "scfma_ridge",
        } <= set(case["step_level"][0])

    md_path = output_dir / "failure_taxonomy.md"
    assert md_path.exists()
    assert "Failure Taxonomy" in md_path.read_text(encoding="utf-8")


def test_failure_taxonomy_accepts_locked_cli_and_outputs_appendix(tmp_path: Path) -> None:
    output_dir = tmp_path / "failure_taxonomy_locked_cli"
    input_artifact = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash" / "audit_prioritization_report.json"
    result = run_script(
        "build_failure_taxonomy.py",
        output_dir,
        "--fixture",
        "--fixture-size",
        "80",
        "--input-artifact",
        str(input_artifact),
        "--taxonomy-rules",
        "structural_over_correction,redundancy_misclassification,bottleneck_over_protection,weak_utility_anchor,low_signal_or_tie",
        "--max-cases",
        "5",
        "--output-format",
        "appendix_page",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_report(output_dir, "failure_taxonomy.json")
    assert_common_report_fields(report, output_dir, "diagnostic_support")
    expected_labels = {
        "structural_over_correction",
        "redundancy_misclassification",
        "bottleneck_over_protection",
        "weak_utility_anchor",
        "low_signal_or_tie",
    }
    assert expected_labels <= set(report["taxonomy_counts"])
    assert expected_labels <= set(report["taxonomy_percentages"])
    assert report["taxonomy_rules_enabled"] == [
        "structural_over_correction",
        "redundancy_misclassification",
        "bottleneck_over_protection",
        "weak_utility_anchor",
        "low_signal_or_tie",
    ]
    assert len(report["representative_cases"]) == 5
    for case in report["representative_cases"]:
        assert {
            "step_text_excerpt",
            "labels",
            "raw_utility",
            "w_struct",
            "scfma_qp",
            "scfma_ridge",
            "taxonomy_label",
            "diagnostic_explanation",
        } <= set(case)
        assert len(str(case["step_text_excerpt"]).split()) <= 100
    appendix = output_dir / "failure_taxonomy_appendix.md"
    assert appendix.exists()
    appendix_text = appendix.read_text(encoding="utf-8")
    assert "variant selection guidance" in appendix_text
    assert "method failure" not in appendix_text.lower()


def test_runtime_reproducibility_fixture_records_environment(tmp_path: Path) -> None:
    output_dir = tmp_path / "runtime_reproducibility"
    result = run_script(
        "collect_runtime_reproducibility.py",
        output_dir,
        "--fixture",
    )
    assert result.returncode == 0, result.stderr + result.stdout

    report = load_report(output_dir, "runtime_reproducibility.json")
    assert_common_report_fields(report, output_dir, "diagnostic_support")
    assert report["experiments"]
    required = {
        "command",
        "output_directory",
        "git_commit",
        "git_dirty",
        "python_version",
        "platform",
        "cpu",
        "peak_memory_mb",
        "seed_list",
        "n_traces",
        "n_steps",
        "elapsed_seconds",
        "bootstrap_samples",
        "api_calls",
        "frozen_artifacts_used",
        "known_deviations",
    }
    for row in report["experiments"]:
        assert required <= set(row)
        assert row["api_calls"] == 0

    md_path = output_dir / "runtime_reproducibility.md"
    assert md_path.exists()
    assert "Runtime & Reproducibility Summary" in md_path.read_text(encoding="utf-8")
