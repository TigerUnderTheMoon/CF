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
        "src/fma/diagnostics/__init__.py",
        "src/fma/pilot/__init__.py",
        "src/fma/utils/__init__.py",
    ]

    missing = [rel_path for rel_path in expected_files if not (project_root / rel_path).exists()]

    assert missing == []


def test_public_skeleton_exports_are_importable() -> None:
    from fma.attribution import AttributionResult, compute_attribution
    from fma.diagnostics import DiagnosticResult, summarize_diagnostics
    from fma.graph import GraphIntervention, run_structural_diagnostics
    from fma.pilot import PilotRunConfig, run_pilot
    from fma.utils import load_config

    assert AttributionResult is not None
    assert compute_attribution is not None
    assert DiagnosticResult is not None
    assert summarize_diagnostics is not None
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
