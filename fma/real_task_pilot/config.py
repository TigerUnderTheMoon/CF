"""Configuration helpers for the real-task pilot."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("configs") / "real_task_pilot.yaml"


def load_pilot_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load the YAML pilot config with a clear dependency error."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("PyYAML is required to read configs/real_task_pilot.yaml.") from exc

    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping.")
    payload["_config_path"] = str(config_path)
    return payload


def output_dir(config: dict[str, Any]) -> Path:
    return Path(config.get("experiment", {}).get("output_dir", "outputs/real_task_pilot"))


def configured_seed(config: dict[str, Any]) -> int:
    return int(config.get("experiment", {}).get("seed", 20260530))
