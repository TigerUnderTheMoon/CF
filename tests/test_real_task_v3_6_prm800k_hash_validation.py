"""Contracts for the v3.6 hash-stratified PRM800K validation route."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "real_task_v3_6_prm800k_hash_validation.yaml"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_real_task_v3_6_prm800k_hash_validation.py"


def test_v3_6_config_uses_unseen_hash_split_pool() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["route"]["id"] == "real_task_v3_6_prm800k_hash"
    assert config["data"]["source"]["dataset"] == "openai/prm800k"
    assert config["data"]["pool"]["start_row"] == 5000
    assert config["data"]["pool"]["row_count"] == 12000
    assert config["data"]["split_strategy"]["name"] == "sha256_hash_mod"
    assert config["data"]["split_strategy"]["dev_mod_upper_exclusive"] == 50
    assert config["outputs"]["root"] == "outputs/real_task_v3_6_prm800k_hash"
    assert config["claim_policy"]["permits_real_step_ranking_claim"] is True
    assert config["claim_policy"]["permits_gsm8k_hotpotqa_replay_claim"] is False


def test_hash_split_is_deterministic_and_exclusive() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.run_real_task_v3_6_prm800k_hash_validation import assign_split  # noqa: PLC0415

    first = assign_split("sample-a", salt="fixed", dev_mod_upper_exclusive=50)
    second = assign_split("sample-a", salt="fixed", dev_mod_upper_exclusive=50)
    other_salt = assign_split("sample-a", salt="other", dev_mod_upper_exclusive=50)

    assert first == second
    assert first in {"dev", "locked"}
    assert other_salt in {"dev", "locked"}


def test_v3_6_decision_names_v3_6_artifact() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.run_real_task_v3_6_prm800k_hash_validation import route_decision_report  # noqa: PLC0415

    decision = route_decision_report(
        {
            "status": "pass",
            "claim_permissions": {
                "M_STEP_RANKING_REAL_PRM800K": True,
                "M_STEP_RANKING": True,
                "F_REAL_TASK_SC_FMA": False,
                "F_PRM_TRAINING": False,
            },
            "next_allowed_step": "UPDATE_STEP_RANKING_CLAIM_WITH_V3_5_ARTIFACT",
        },
        route_id="real_task_v3_6_prm800k_hash",
    )

    assert decision["next_allowed_step"] == "UPDATE_STEP_RANKING_CLAIM_WITH_V3_6_ARTIFACT"


def test_script_runs_fixture_smoke_without_manual_pythonpath(tmp_path: Path) -> None:
    output_dir = tmp_path / "v3_6_fixture"
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
    assert smoke_report["claim_boundary"] == "fixture_smoke_only_not_validation"
