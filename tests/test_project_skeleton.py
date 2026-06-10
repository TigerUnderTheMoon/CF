from __future__ import annotations

import argparse
from pathlib import Path


def test_requested_src_package_layout_exists() -> None:
    project_root = Path(__file__).resolve().parents[1]
    expected_files = [
        "src/fma/__init__.py",
        "src/fma/attribution/__init__.py",
        "src/fma/graph/__init__.py",
        "src/fma/graph/diagnostics.py",
        "src/fma/pilot/__init__.py",
        "src/fma/utils/__init__.py",
    ]

    missing = [rel_path for rel_path in expected_files if not (project_root / rel_path).exists()]

    assert missing == []


def test_public_skeleton_exports_are_importable() -> None:
    from fma.attribution import AttributionResult
    from fma.diagnostics import DiagnosticResult
    from fma.graph import GraphIntervention, run_structural_diagnostics
    from fma.pilot import PilotRunConfig, run_pilot
    from fma.utils import load_config

    assert AttributionResult is not None
    assert DiagnosticResult is not None
    assert GraphIntervention is not None
    assert run_structural_diagnostics is not None
    assert PilotRunConfig is not None
    assert run_pilot is not None
    assert load_config is not None


def test_structural_diagnostics_cli_delegates_to_package_runner(monkeypatch) -> None:
    import scripts.run_structural_diagnostics as cli

    args = argparse.Namespace(
        traces=Path("traces.json"),
        necessity_scores=Path("necessity.jsonl"),
        output_json=Path("diagnostics.json"),
        output_md=Path("diagnostics.md"),
        figures_dir=Path("figures"),
    )
    calls: list[argparse.Namespace] = []

    def fake_runner(received_args: argparse.Namespace) -> dict[str, bool]:
        calls.append(received_args)
        return {"delegated": True}

    monkeypatch.setattr(cli, "run_structural_diagnostics", fake_runner)

    assert cli.run(args) == {"delegated": True}
    assert calls == [args]


def test_pilot_run_wrapper_builds_cli_arguments(monkeypatch, tmp_path: Path) -> None:
    import fma.cli as cli
    from fma.pilot import PilotRunConfig, run_pilot

    calls: list[tuple[list[str], str | None]] = []

    def fake_run_cli(argv, *, timestamp=None):
        calls.append((list(argv), timestamp))
        return {"command": "run-pilot", "run_dir": str(tmp_path)}

    monkeypatch.setattr(cli, "run_cli", fake_run_cli)

    result = run_pilot(
        PilotRunConfig(
            config_name="pilot/v2_1",
            output_root=tmp_path,
            overrides=("experiment.seed=7",),
        ),
        timestamp="20260608_180000",
    )

    assert result["command"] == "run-pilot"
    assert calls == [
        (
            [
                "run-pilot",
                "--config-name=pilot/v2_1",
                "experiment.seed=7",
                f"paths.output_root={tmp_path.as_posix()}",
            ],
            "20260608_180000",
        )
    ]


def test_pilot_run_wrapper_rejects_non_mapping_result(monkeypatch) -> None:
    import fma.cli as cli
    from fma.pilot import run_pilot

    monkeypatch.setattr(cli, "run_cli", lambda argv, *, timestamp=None: "not-json")

    try:
        run_pilot()
    except TypeError as exc:
        assert "non-mapping" in str(exc)
    else:
        raise AssertionError("run_pilot should reject non-mapping CLI results")
