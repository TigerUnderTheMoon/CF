"""Contracts for the real_task_v3.5 PRM800K real-data validation route."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "real_task_v3_5_prm800k_validation.yaml"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_real_task_v3_5_prm800k_validation.py"


def test_v3_5_config_is_prm800k_phase2_and_output_isolated() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["route"]["id"] == "real_task_v3_5_prm800k"
    assert config["data"]["source"]["dataset"] == "openai/prm800k"
    assert config["data"]["source"]["file"] == "phase2_train.jsonl"
    assert config["data"]["dev"]["start_row"] == 0
    assert config["data"]["locked"]["start_row"] > config["data"]["dev"]["end_row"]
    assert config["outputs"]["root"] == "outputs/real_task_v3_5_prm800k"
    assert config["claim_policy"]["permits_real_step_ranking_claim"] is True
    assert config["claim_policy"]["permits_gsm8k_hotpotqa_replay_claim"] is False
    assert config["claim_policy"]["forbidden_claims"] == [
        "F_REAL_TASK_SC_FMA",
        "F_PRM_TRAINING",
        "deterministic_replay_claim",
        "causal_identification_claim",
    ]


def test_prm800k_parser_builds_label_safe_samples() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.run_real_task_v3_5_prm800k_validation import (  # noqa: PLC0415
        FORBIDDEN_FEATURE_FIELD_NAMES,
        build_samples,
        feature_names,
    )

    row = {
        "question": {"problem": "Compute 2+2.", "ground_truth_answer": "4"},
        "label": {
            "steps": [
                {
                    "completions": [{"text": "Let x = 2 + 2.", "rating": 1, "flagged": False}],
                    "chosen_completion": 0,
                },
                {
                    "completions": [{"text": "Then x = 5.", "rating": -1, "flagged": False}],
                    "chosen_completion": 0,
                },
                {
                    "completions": [{"text": "Therefore the answer is 4.", "rating": 1, "flagged": False}],
                    "chosen_completion": 0,
                },
            ]
        },
    }

    samples = build_samples([row], split_name="fixture")

    assert len(samples) == 1
    assert samples[0].labels == (1.0, 0.0, 1.0)
    assert samples[0].sample_id.startswith("prm800k_fixture_")
    assert samples[0].source_kind == "real_prm800k_phase2"
    assert all(name not in FORBIDDEN_FEATURE_FIELD_NAMES for name in feature_names())
    assert "rating" not in json.dumps(samples[0].feature_rows, sort_keys=True)
    assert "ground_truth" not in json.dumps(samples[0].feature_rows, sort_keys=True)


def test_decision_report_forbids_replay_claim_even_when_locked_passes() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.run_real_task_v3_5_prm800k_validation import build_decision_report  # noqa: PLC0415

    report = build_decision_report(
        dev_report={
            "status": "pass",
            "leakage_audit": {"pass": True},
            "stability": {"pass": True},
        },
        locked_report={
            "status": "pass",
            "gates": {
                "locked_min_samples": {"pass": True},
                "locked_min_steps": {"pass": True},
                "w_struct_beats_raw_ci": {"pass": True},
                "w_struct_beats_heuristics": {"pass": True},
                "holm_primary_pass": {"pass": True},
            },
        },
    )

    assert report["status"] == "pass"
    assert report["claim_permissions"]["M_STEP_RANKING_REAL_PRM800K"] is True
    assert report["claim_permissions"]["F_REAL_TASK_SC_FMA"] is False
    assert report["claim_permissions"]["F_PRM_TRAINING"] is False
    assert report["next_allowed_step"] == "UPDATE_STEP_RANKING_CLAIM_WITH_V3_5_ARTIFACT"


def test_script_runs_fixture_smoke_without_manual_pythonpath(tmp_path: Path) -> None:
    output_dir = tmp_path / "v3_5_fixture"
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
    smoke_report = json.loads((output_dir / "fixture_smoke_report.json").read_text(encoding="utf-8"))
    assert smoke_report["status"] == "pass"
    assert smoke_report["source_kind"] == "real_prm800k_phase2"
    assert smoke_report["claim_boundary"] == "fixture_smoke_only_not_validation"
