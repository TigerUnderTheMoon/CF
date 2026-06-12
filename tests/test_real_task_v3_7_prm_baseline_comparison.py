"""Contracts for the v3.7 PRM baseline contamination-audit route."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "real_task_v3_7_prm_baseline_comparison.yaml"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_real_task_v3_7_prm_baseline_comparison.py"
REQUIRED_CSV_COLUMNS = [
    "artifact_name",
    "artifact_type",
    "hf_or_repo_id",
    "uses_prm800k",
    "usage_mode",
    "source_url",
    "evidence_strength",
    "notes",
]


def test_v3_7_config_is_isolated_and_in_distribution_bounded() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["route"]["id"] == "real_task_v3_7_prm_baseline_comparison"
    assert config["source_route"]["id"] == "real_task_v3_6_prm800k_hash"
    assert config["data"]["target_dataset"] == "openai/prm800k/phase2_train.jsonl"
    assert config["data"]["target_dataset_provenance"]["row_range"] == "5000-16999"
    assert config["outputs"]["root"] == "outputs/real_task_v3_7_prm_baseline_comparison"
    assert config["claim_policy"]["external_generalization_claim_allowed"] is False
    assert config["claim_policy"]["in_distribution_prm_baseline_context_allowed"] is True
    assert "external PRM generalization" in config["claim_policy"]["forbidden_claims"]
    assert "validates PRM training" in config["claim_policy"]["forbidden_claims"]


def test_build_training_overlap_audit_requires_reverse_scan() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.run_real_task_v3_7_prm_baseline_comparison import (  # noqa: PLC0415
        build_training_overlap_audit,
    )

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config["reverse_prm800k_usage_scan"] = []

    with pytest.raises(ValueError, match="reverse_prm800k_usage_scan"):
        build_training_overlap_audit(config)


def test_overlap_or_unknown_blocks_external_generalization() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.run_real_task_v3_7_prm_baseline_comparison import (  # noqa: PLC0415
        build_training_overlap_audit,
    )

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config["claim_policy"]["external_generalization_claim_allowed"] = True

    with pytest.raises(ValueError, match="external generalization"):
        build_training_overlap_audit(config)


def test_known_no_requires_primary_source_url() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.run_real_task_v3_7_prm_baseline_comparison import (  # noqa: PLC0415
        build_training_overlap_audit,
    )

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config["candidate_prm_models"] = [
        {
            "model_name": "clean-model",
            "hf_id": "example/clean-model",
            "uses_prm800k": "known_no",
            "evidence_type": "model_card",
            "source_url": "",
            "claim_boundary": "external_generalization_candidate",
        }
    ]
    config["reverse_prm800k_usage_scan"] = [
        {
            "public_model_or_dataset": "clean-model",
            "artifact_type": "model",
            "hf_or_repo_id": "example/clean-model",
            "uses_prm800k": "known_no",
            "usage_mode": "not_used",
            "source_url": "",
            "evidence_type": "model_card",
            "evidence_strength": "primary",
            "notes": "fixture",
        }
    ]

    with pytest.raises(ValueError, match="known_no"):
        build_training_overlap_audit(config)


def test_script_writes_bidirectional_audit_and_decision(tmp_path: Path) -> None:
    output_dir = tmp_path / "v3_7_audit"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--stage",
            "all",
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    audit = json.loads((output_dir / "training_overlap_audit.json").read_text(encoding="utf-8"))
    decision = json.loads((output_dir / "decision_report.json").read_text(encoding="utf-8"))

    assert audit["target_dataset"] == "openai/prm800k/phase2_train.jsonl"
    assert audit["reverse_prm800k_usage_scan"]
    assert any(
        row["uses_prm800k"] in {"known_yes", "known_yes_or_unclear_by_public_sources", "unknown"}
        for row in audit["reverse_prm800k_usage_scan"]
    )
    assert audit["decision"]["external_generalization_claim_allowed"] is False
    assert audit["decision"]["in_distribution_prm_baseline_context_allowed"] is True
    assert decision["claim_permissions"]["M_BASELINE_COMPARISON"] is False
    assert decision["claim_permissions"]["M_BASELINE_COMPARISON_CONTEXT_ONLY"] is True
    assert decision["claim_permissions"]["external_generalization_claim_allowed"] is False
    assert decision["claim_permissions"]["in_distribution_prm_baseline_context_allowed"] is True
    assert "in-distribution baseline comparison" in decision["required_claim_text"]


def test_reverse_scan_csv_has_required_columns(tmp_path: Path) -> None:
    output_dir = tmp_path / "v3_7_audit"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--stage",
            "contamination_audit",
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    with (output_dir / "reverse_prm800k_usage_scan.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == REQUIRED_CSV_COLUMNS
        rows = list(reader)

    assert rows
    assert any(row["artifact_name"] == "Math-Shepherd" for row in rows)
    assert any(row["artifact_name"] == "ProcessBench" for row in rows)
