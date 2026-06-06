"""Hydra-style layered configuration helpers for FMA runs."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Mapping, MutableMapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "configs"


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    output_root: Path = Path("outputs")
    data_root: Path = Path("data")
    claim_registry: Path = Path("paper/claim_registry.md")
    run_dir: Path | None = None


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = "fma_experiment"
    objective: str | None = None


class ClaimRegistryConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: Path = Path("paper/claim_registry.md")
    claim_id: str | None = None
    claim: str | None = None


class PilotConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    api_model: str | None = None
    cost_ceiling_usd: PositiveFloat | None = None
    dedup_keys: list[str] = Field(default_factory=list)


class Phase5Config(BaseModel):
    model_config = ConfigDict(extra="allow")

    ablation_strategies: list[str] = Field(default_factory=list)
    scoring_rules: dict[str, Any] = Field(default_factory=dict)


class Phase6Config(BaseModel):
    model_config = ConfigDict(extra="allow")

    edge_rules: list[str] = Field(default_factory=list)
    intervention_modes: list[str] = Field(default_factory=list)
    default_intervention_mode: str | None = None


class Phase7Config(BaseModel):
    model_config = ConfigDict(extra="allow")

    redundancy_threshold: float | None = None
    compensation_threshold: float | None = None
    bottleneck_threshold: float | None = None


class FMAConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    paths: PathsConfig = Field(default_factory=PathsConfig)
    random_seed: int = 20260606
    logging_level: str = "INFO"
    experiment: ExperimentConfig = Field(default_factory=ExperimentConfig)
    claim_registry: ClaimRegistryConfig = Field(default_factory=ClaimRegistryConfig)
    pilot: PilotConfig | None = None
    phase5: Phase5Config | None = None
    phase6: Phase6Config | None = None
    phase7: Phase7Config | None = None


def load_config(
    config_name: str | Path = "base",
    *,
    overrides: Sequence[str] | None = None,
    configs_dir: str | Path = DEFAULT_CONFIG_DIR,
    create_run_dir: bool = False,
    output_root: str | Path | None = None,
    timestamp: str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Load, compose, validate, and optionally snapshot a Hydra-style config.

    ``config_name`` accepts either a Hydra-style name such as ``phase6/graph`` or
    a direct YAML path for legacy callers.
    """

    overrides = list(overrides or [])
    config_root = Path(configs_dir)
    payload = _compose_config(config_name, config_root)
    for override in overrides:
        _apply_override(payload, override)

    if output_root is not None:
        payload.setdefault("paths", {})["output_root"] = str(output_root)

    if validate:
        validate_config(payload)

    if create_run_dir:
        _write_run_snapshots(payload, overrides=overrides, timestamp=timestamp)
        if validate:
            validate_config(payload)

    return payload


def validate_config(
    config: Mapping[str, Any],
    *,
    validate_claim_registry: bool = True,
) -> FMAConfig:
    """Validate config types and claim/objective consistency."""

    payload = deepcopy(dict(config))
    _validate_recursive_cost_ceilings(payload)
    model = FMAConfig.model_validate(payload)
    _validate_claim_objective(model, validate_claim_registry=validate_claim_registry)
    return model


def flatten_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic dotted-key snapshot for audit use."""

    flattened: dict[str, Any] = {}

    def visit(prefix: str, value: Any) -> None:
        if isinstance(value, Mapping):
            for key in sorted(value):
                child_key = f"{prefix}.{key}" if prefix else str(key)
                visit(child_key, value[key])
            return
        flattened[prefix] = _snapshot_value(value)

    visit("", config)
    return flattened


def _compose_config(config_name: str | Path, configs_dir: Path) -> dict[str, Any]:
    selected_path = _config_path(config_name, configs_dir)
    direct_legacy_path = Path(config_name).suffix in {".yaml", ".yml"} and selected_path.exists()
    if selected_path.name == "base.yaml" or direct_legacy_path:
        return _read_yaml_mapping(selected_path)

    base_path = configs_dir / "base.yaml"
    if not base_path.exists():
        raise FileNotFoundError(f"Missing base config: {base_path}")
    merged = _read_yaml_mapping(base_path)
    selected = _read_yaml_mapping(selected_path)
    _deep_merge(merged, selected)
    return merged


def _config_path(config_name: str | Path, configs_dir: Path) -> Path:
    raw_path = Path(config_name)
    if raw_path.suffix in {".yaml", ".yml"}:
        candidate = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
        if candidate.exists():
            return candidate
        candidate = configs_dir / raw_path
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Config file not found: {config_name}")

    relative = Path(str(config_name))
    candidate = configs_dir / relative.with_suffix(".yaml")
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Config name not found under {configs_dir}: {config_name}")


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    return payload


def _deep_merge(target: MutableMapping[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], MutableMapping)
            and isinstance(value, Mapping)
        ):
            _deep_merge(target[key], value)
            continue
        target[key] = deepcopy(value)


def _apply_override(config: MutableMapping[str, Any], override: str) -> None:
    if "=" not in override:
        raise ValueError(f"Override must use key=value syntax: {override}")
    raw_key, raw_value = override.split("=", 1)
    key = raw_key.lstrip("+")
    if not key:
        raise ValueError(f"Override key is empty: {override}")
    value = yaml.safe_load(raw_value)
    parts = key.split(".")
    cursor: MutableMapping[str, Any] = config
    for part in parts[:-1]:
        child = cursor.setdefault(part, {})
        if not isinstance(child, MutableMapping):
            raise ValueError(f"Cannot apply nested override into scalar key: {key}")
        cursor = child
    cursor[parts[-1]] = value


def _write_run_snapshots(
    config: MutableMapping[str, Any],
    *,
    overrides: Sequence[str],
    timestamp: str | None,
) -> Path:
    experiment = config.setdefault("experiment", {})
    paths = config.setdefault("paths", {})
    experiment_name = _slug(str(experiment.get("name") or "fma_experiment"))
    run_timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = Path(paths.get("output_root", "outputs"))
    run_dir = output_root / f"{run_timestamp}_{experiment_name}"
    paths["run_dir"] = str(run_dir)
    experiment["output_dir"] = str(run_dir)

    hydra_dir = run_dir / ".hydra"
    hydra_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(hydra_dir / "config.yaml", config)
    _write_yaml(hydra_dir / "overrides.yaml", list(overrides))
    _write_yaml(run_dir / "config_snapshot.yaml", flatten_config(config))
    return run_dir


def _write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=False, sort_keys=True),
        encoding="utf-8",
    )


def _validate_recursive_cost_ceilings(payload: Mapping[str, Any]) -> None:
    def visit(path: str, value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                visit(child_path, child)
            return
        if path.endswith("cost_ceiling_usd"):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{path} must be a float > 0.")

    visit("", payload)


def _validate_claim_objective(
    model: FMAConfig,
    *,
    validate_claim_registry: bool,
) -> None:
    objective = model.experiment.objective
    claim_id = model.claim_registry.claim_id or model.claim_registry.claim
    if objective and claim_id and objective != claim_id:
        raise ValueError(
            "claim_registry.claim_id must match experiment.objective "
            f"({claim_id!r} != {objective!r})."
        )
    if not validate_claim_registry or not objective:
        return

    registry_path = _resolve_project_path(model.claim_registry.path or model.paths.claim_registry)
    if not registry_path.exists():
        raise FileNotFoundError(f"claim_registry path does not exist: {registry_path}")
    registry_text = registry_path.read_text(encoding="utf-8")
    if objective not in registry_text:
        raise ValueError(
            f"experiment.objective {objective!r} is not present in {registry_path}."
        )


def _resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def _snapshot_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_snapshot_value(item) for item in value]
    return value


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return slug.strip("_") or "fma_experiment"


__all__ = [
    "FMAConfig",
    "flatten_config",
    "load_config",
    "validate_config",
]
