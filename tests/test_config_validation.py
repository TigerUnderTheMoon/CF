"""Tests for Pydantic v2 config schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from fma.utils.config import (
    ExperimentConfig,
    FMAConfig,
    Phase5Config,
    Phase6Config,
    Phase7Config,
    load_config,
    validate_config,
)


class TestPhase5Config:
    def test_defaults(self) -> None:
        config = Phase5Config()
        assert config.seed == 42
        assert config.utility_threshold == 0.9
        assert config.traces is None
        assert config.ablation_strategies == []

    def test_path_resolution_from_string(self) -> None:
        config = Phase5Config.model_validate({
            "traces": "data/traces.jsonl",
            "utility_annotations": "outputs/annotations.jsonl",
            "output_dir": "outputs/phase5",
        })
        assert config.traces == Path("data/traces.jsonl")
        assert config.utility_annotations == Path("outputs/annotations.jsonl")
        assert config.output_dir == Path("outputs/phase5")

    def test_seed_must_be_int(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Phase5Config.model_validate({"seed": "not_an_int"})
        assert "seed" in str(exc_info.value)
        assert "integer" in str(exc_info.value).lower()

    def test_utility_threshold_must_be_float(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Phase5Config.model_validate({"utility_threshold": "bad"})
        assert "utility_threshold" in str(exc_info.value)

    def test_extra_fields_allowed(self) -> None:
        config = Phase5Config.model_validate({
            "custom_field": "value",
            "another": 123,
        })
        assert config.custom_field == "value"


class TestPhase6Config:
    def test_defaults(self) -> None:
        config = Phase6Config()
        assert config.utility_threshold == 0.9
        assert config.edge_rules == []
        assert config.intervention_modes == []

    def test_path_resolution(self) -> None:
        config = Phase6Config.model_validate({
            "traces": "data/traces.jsonl",
            "output_dir": "outputs/phase6",
            "removal_mode": "PRUNE",
        })
        assert config.traces == Path("data/traces.jsonl")
        assert config.removal_mode == "PRUNE"


class TestFMAConfig:
    def test_full_validation(self) -> None:
        result = validate_config({
            "experiment": {"name": "test"},
            "phase5": {
                "traces": "data/traces.jsonl",
                "seed": 42,
                "utility_threshold": 0.9,
            },
            "phase6": {
                "traces": "data/traces.jsonl",
                "utility_threshold": 0.95,
                "removal_mode": "CASCADE",
            },
        }, validate_claim_registry=False)

        assert isinstance(result, FMAConfig)
        assert result.phase5 is not None
        assert result.phase5.seed == 42
        assert result.phase6 is not None
        assert result.phase6.removal_mode == "CASCADE"

    def test_validation_error_contains_field_path(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            validate_config({
                "phase5": {"seed": "invalid"},
            }, validate_claim_registry=False)

        error_str = str(exc_info.value)
        assert "phase5" in error_str
        assert "seed" in error_str

    def test_demo_yaml_validates(self, tmp_path: Path) -> None:
        demo_config = {
            "experiment": {
                "name": "fma_demo",
                "description": "Demo config",
            },
            "phase5": {
                "traces": "data/synthetic_traces.jsonl",
                "utility_annotations": "outputs/utility_annotations.jsonl",
                "output_dir": "outputs/phase5",
                "figures_dir": "outputs/phase5/figures",
                "seed": 42,
                "utility_threshold": 0.9,
            },
            "phase6": {
                "traces": "data/synthetic_traces.jsonl",
                "output_dir": "outputs/phase6",
                "figures_dir": "outputs/phase6/figures",
                "utility_threshold": 0.9,
                "removal_mode": "PRUNE",
            },
        }

        result = validate_config(demo_config, validate_claim_registry=False)
        assert result.phase5 is not None
        assert result.phase5.traces == Path("data/synthetic_traces.jsonl")
        assert result.phase6 is not None
        assert result.phase6.removal_mode == "PRUNE"


class TestLoadConfig:
    def test_load_config_with_dict_passthrough(self) -> None:
        """Pre-loaded dict should bypass file I/O."""
        config_dict = {
            "experiment": {"name": "dict_test"},
            "phase5": {"seed": 99},
        }

        result = load_config(config_dict, validate=True)
        assert result["experiment"]["name"] == "dict_test"
        assert result["phase5"]["seed"] == 99

    def test_load_config_with_yaml_path(self) -> None:
        """YAML path should still work."""
        result = load_config("base", validate=False)
        assert result["experiment"]["name"] == "fma_default"

    def test_load_config_with_overrides(self) -> None:
        result = load_config(
            "base",
            overrides=["experiment.name=override_test", "+phase5.seed=123"],
            validate=False,
        )
        assert result["experiment"]["name"] == "override_test"
        assert result["phase5"]["seed"] == 123

    def test_validation_error_message_format(self) -> None:
        """Error messages must contain specific field names."""
        with pytest.raises(ValidationError) as exc_info:
            validate_config({
                "phase5": {
                    "seed": "not_int",
                    "utility_threshold": "not_float",
                },
            }, validate_claim_registry=False)

        error_str = str(exc_info.value)
        assert "phase5.seed" in error_str or "seed" in error_str
        assert "phase5.utility_threshold" in error_str or "utility_threshold" in error_str
