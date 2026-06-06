from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_uses_cached_poetry_builder_and_non_root_runtime() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.11-slim AS builder" in dockerfile
    assert "FROM python:3.11-slim AS runtime" in dockerfile
    assert "pip install --no-cache-dir poetry" in dockerfile
    assert "poetry lock --no-interaction" in dockerfile
    assert "COPY pyproject.toml poetry.lock* ./" in dockerfile
    assert "COPY --from=builder /opt/venv /opt/venv" in dockerfile
    assert "useradd" in dockerfile
    assert "USER fma" in dockerfile

    dependency_copy = dockerfile.index("COPY pyproject.toml poetry.lock* ./")
    source_copy = dockerfile.index("COPY --chown=fma:fma . .")
    assert dependency_copy < source_copy

    runtime_stage = dockerfile.split("FROM python:3.11-slim AS runtime", maxsplit=1)[1]
    assert "poetry install" not in runtime_stage
    assert "pip install" not in runtime_stage


def test_compose_defines_core_and_pilot_services_with_guarded_defaults() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert set(services) == {"fma-core", "fma-pilot"}

    core = services["fma-core"]
    assert core["build"]["target"] == "runtime"
    assert "./outputs:/app/outputs" in core["volumes"]
    assert "OPENAI_API_KEY" not in core.get("environment", {})
    assert "pytest" not in " ".join(core["command"])

    pilot = services["fma-pilot"]
    assert pilot["build"]["target"] == "runtime"
    assert ".env" in pilot["env_file"]
    assert "./outputs:/app/outputs" in pilot["volumes"]
    assert pilot["environment"]["OPENAI_MAX_RETRIES"] == "1"
    assert pilot["environment"]["OPENAI_TIMEOUT"] == "45"
    assert "OPENAI_API_KEY" in pilot["environment"]
    pilot_command = " ".join(pilot["command"])
    assert "COST_CEILING_USD" in pilot_command
    assert "--allow-pilot-stochastic-validation-only" in pilot_command


def test_env_example_and_makefile_cover_required_entrypoints() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in ("OPENAI_API_KEY", "BASE_URL", "MODEL_NAME", "COST_CEILING_USD"):
        assert f"{name}=" in env_example

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("install", "test", "lint", "docker-core", "docker-pilot"):
        assert f"{target}:" in makefile

    assert "poetry install" in makefile
    assert "pytest -q" in makefile
    assert "ruff check" in makefile
    assert "black --check" in makefile
    assert "docker compose run --rm fma-core" in makefile
    assert "docker compose run --rm fma-pilot" in makefile
