"""Contracts for v3.8 frozen PRM locked scoring."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "real_task_v3_8_prm_locked_scoring.yaml"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_real_task_v3_8_prm_locked_scoring.py"


def test_v3_8_config_points_to_v3_6_and_keeps_claim_boundary() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["route"]["id"] == "real_task_v3_8_prm_locked_scoring"
    assert config["source_route"]["id"] == "real_task_v3_6_prm800k_hash"
    assert config["subsets"]["primary"] == "locked"
    assert config["model"]["revision"] == "98d69606595eedbdbbbf0a7d28efdcd462ba6a67"
    assert config["model"]["step_score_semantics"] == "prefix_sequence_reward_probability"
    assert config["claim_policy"]["in_distribution_prm_baseline_context_allowed"] is True
    assert config["claim_policy"]["external_generalization_claim_allowed"] is False
    assert config["claim_policy"]["prm_training_claim_allowed"] is False


def test_fixture_smoke_runs_without_manual_pythonpath(tmp_path: Path) -> None:
    output_dir = tmp_path / "fixture"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--stage",
            "fixture_smoke",
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
    report = json.loads((output_dir / "fixture_smoke_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass_canary"
    assert report["gates"]["alignment_success_rate"]["pass"] is True
    assert report["model_revision"] == "98d69606595eedbdbbbf0a7d28efdcd462ba6a67"
    assert report["claim_boundary"] == "in_distribution_prm_baseline_context_only"


def test_mock_canary_scores_v3_6_locked_subset(tmp_path: Path) -> None:
    output_dir = tmp_path / "canary"
    source_file = tmp_path / "fixture_prm800k.jsonl"
    rows = []
    for idx in range(5):
        rows.append(
            {
                "question": {"problem": f"Compute {idx}+2.", "ground_truth_answer": str(idx + 2)},
                "label": {
                    "steps": [
                        {
                            "completions": [{"text": f"Let x = {idx} + 2.", "rating": 1, "flagged": False}],
                            "chosen_completion": 0,
                        },
                        {
                            "completions": [{"text": "Then x = 999.", "rating": -1, "flagged": False}],
                            "chosen_completion": 0,
                        },
                        {
                            "completions": [{"text": f"Therefore x = {idx + 2}.", "rating": 1, "flagged": False}],
                            "chosen_completion": 0,
                        },
                    ]
                },
            }
        )
    source_file.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    v3_6_config = {
        "data": {
            "source": {"url": source_file.as_uri()},
            "pool": {"start_row": 0, "row_count": 5},
            "split_strategy": {
                "salt": "fixture",
                "dev_mod_upper_exclusive": 50,
            },
        }
    }
    v3_6_config_path = tmp_path / "v3_6_fixture.yaml"
    v3_6_config_path.write_text(yaml.safe_dump(v3_6_config), encoding="utf-8")
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config["source_route"]["config"] = str(v3_6_config_path)
    config_path = tmp_path / "v3_8_fixture.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--config",
            str(config_path),
            "--stage",
            "canary",
            "--subset",
            "pool",
            "--scorer-backend",
            "mock",
            "--max-samples",
            "5",
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
    report = json.loads((output_dir / "canary_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass_canary"
    assert report["metrics"]["n_samples"] == 5
    assert report["metrics"]["n_aligned_samples"] == 5
    assert report["gates"]["nonconstant_scores"]["pass"] is True


def test_decision_keeps_prm_result_context_only(tmp_path: Path) -> None:
    output_dir = tmp_path / "decision"
    output_dir.mkdir()
    locked_report = {
        "status": "pass_weak",
        "claim_boundary": "in_distribution_prm_baseline_context_only",
    }
    (output_dir / "locked_prm_baseline_comparison_report.json").write_text(
        json.dumps(locked_report),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--stage",
            "decision",
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
    decision = json.loads((output_dir / "decision_report.json").read_text(encoding="utf-8"))
    assert decision["claim_permissions"]["M_BASELINE_COMPARISON"] is False
    assert decision["claim_permissions"]["M_BASELINE_COMPARISON_CONTEXT_ONLY"] is True
    assert decision["claim_permissions"]["external_generalization_claim_allowed"] is False
    assert decision["claim_permissions"]["F_PRM_TRAINING"] is False
