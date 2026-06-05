"""Audit the real_task_v3 preregistration package without live execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.validation_v3 import (
    REAL_TASK_V3_PREREGISTRATION_ONLY,
    audit_v3_config_contract,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the real_task_v3 preregistration boundary."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "real_task_v3_validation.yaml",
    )
    parser.add_argument(
        "--task-scope",
        default=REAL_TASK_V3_PREREGISTRATION_ONLY,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    _assert_current_task_boundary(config, task_scope=args.task_scope)
    audit = audit_v3_config_contract(config)
    print(json.dumps(audit, sort_keys=True))


def _assert_current_task_boundary(
    config: Mapping[str, Any],
    *,
    task_scope: str,
) -> None:
    if task_scope != REAL_TASK_V3_PREREGISTRATION_ONLY:
        raise RuntimeError(f"task_scope must be {REAL_TASK_V3_PREREGISTRATION_ONLY}")
    experiment = _mapping(config.get("experiment"))
    if experiment.get("current_task_scope") != REAL_TASK_V3_PREREGISTRATION_ONLY:
        raise RuntimeError("experiment.current_task_scope must remain REAL_TASK_V3_PREREGISTRATION_ONLY")
    required_true = (
        "no_api_execution_without_user_approval",
        "no_api_run_in_current_task",
        "no_manifest_generation_in_current_task",
        "no_full_api_generation_in_current_task",
        "no_replay_in_current_task",
        "no_scoring_in_current_task",
        "no_prm_filtering_in_current_task",
    )
    for key in required_true:
        if experiment.get(key) is not True:
            raise RuntimeError(f"experiment.{key} must be true")
    if experiment.get("user_approved_budget_usd") is not None:
        raise RuntimeError("experiment.user_approved_budget_usd must remain unset")
    execution = _mapping(config.get("execution_boundary"))
    required_false = (
        "api_execution_allowed",
        "manifest_generation_authorized",
        "replay_authorized",
        "scoring_authorized",
        "prm_filtering_authorized",
    )
    for key in required_false:
        if execution.get(key) is not False:
            raise RuntimeError(f"execution_boundary.{key} must be false")
    claim_policy = _mapping(config.get("claim_policy"))
    if claim_policy.get("current_status_remains") != "PILOT_BLOCKED":
        raise RuntimeError("claim_policy.current_status_remains must be PILOT_BLOCKED")
    if claim_policy.get("validation_or_pass_claim_allowed") is not False:
        raise RuntimeError("claim_policy.validation_or_pass_claim_allowed must be false")
    if claim_policy.get("prm_filtering_improvement_claim_allowed") is not False:
        raise RuntimeError("claim_policy.prm_filtering_improvement_claim_allowed must be false")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    main()
