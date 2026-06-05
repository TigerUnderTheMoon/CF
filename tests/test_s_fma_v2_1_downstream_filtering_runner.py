from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _runner():
    try:
        return importlib.import_module("scripts.run_s_fma_v2_1_downstream_filtering_validation")
    except ModuleNotFoundError as exc:
        pytest.fail(f"downstream filtering runner missing: {exc}")


def test_runner_paths_are_confined_to_downstream_filtering_prefix() -> None:
    runner = _runner()

    paths = runner.v2_1_downstream_filtering_paths(
        Path("outputs") / "s_fma_v2_1_fresh_holdout"
    )

    assert paths["preregistration"].name == "v2_1_downstream_filtering_preregistration.json"
    assert paths["report"].name == "v2_1_downstream_filtering_report.json"
    assert paths["attempts"].name == "v2_1_downstream_filtering_attempts.jsonl"
    assert paths["traces"].name == "v2_1_downstream_filtering_traces.jsonl"
    assert paths["cost"].name == "v2_1_downstream_filtering_cost_report.json"
    for key, path in paths.items():
        if key == "cost":
            assert path.parent.name == "logs"
        else:
            assert path.parent.name == "s_fma_v2_1_fresh_holdout"
        assert "full_stochastic" not in path.name
        assert "v2_2" not in path.name
        assert "v2_4" not in path.name


def test_runner_argument_parser_requires_mode_or_api_guard() -> None:
    runner = _runner()

    prereg_args = runner.parse_args(["--write-preregistration-only"])
    assert prereg_args.write_preregistration_only is True
    assert prereg_args.allow_downstream_filtering_validation_only is False

    run_args = runner.parse_args(
        ["--allow-downstream-filtering-validation-only", "--approved-budget-usd", "5"]
    )
    assert run_args.allow_downstream_filtering_validation_only is True
    assert run_args.approved_budget_usd == 5.0
