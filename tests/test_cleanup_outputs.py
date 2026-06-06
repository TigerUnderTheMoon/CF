from __future__ import annotations

from pathlib import Path


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_cleanup_archives_failed_v2_routes_and_preserves_phase_core(tmp_path: Path) -> None:
    from fma.utils.cleanup import cleanup_outputs

    _write(tmp_path / "outputs" / "phase5" / "counterfactual_summary.json")
    _write(tmp_path / "outputs" / "phase6" / "structural_diagnostics.json")
    _write(tmp_path / "outputs" / "phase7" / "redundancy_analysis.json")
    _write(tmp_path / "outputs" / "figures" / "utility_distribution.png", "png")
    _write(tmp_path / "outputs" / "s_fma_v2_fresh_holdout" / "failed.json")
    _write(tmp_path / "outputs" / "s_fma_v2_2_fresh_holdout" / "failed.json")
    _write(tmp_path / "outputs" / "s_fma_v2_1_fresh_holdout" / "current.json")

    report = cleanup_outputs(tmp_path, keep_core=True, archive_failed=True)

    assert (tmp_path / "outputs" / "phase5" / "counterfactual_summary.json").exists()
    assert (tmp_path / "outputs" / "phase6" / "structural_diagnostics.json").exists()
    assert (tmp_path / "outputs" / "phase7" / "redundancy_analysis.json").exists()
    assert (tmp_path / "outputs" / "figures" / "utility_distribution.png").exists()
    assert not (tmp_path / "outputs" / "s_fma_v2_fresh_holdout").exists()
    assert not (tmp_path / "outputs" / "s_fma_v2_2_fresh_holdout").exists()
    assert (tmp_path / "outputs" / "archive" / "s_fma_v2_fresh_holdout" / "failed.json").exists()
    assert (tmp_path / "outputs" / "archive" / "s_fma_v2_2_fresh_holdout" / "failed.json").exists()
    assert (tmp_path / "outputs" / "s_fma_v2_1_fresh_holdout" / "current.json").exists()
    assert report.archived == [
        "outputs/s_fma_v2_fresh_holdout -> outputs/archive/s_fma_v2_fresh_holdout",
        "outputs/s_fma_v2_2_fresh_holdout -> outputs/archive/s_fma_v2_2_fresh_holdout",
    ]
    assert report.preserved_core == [
        "outputs/figures",
        "outputs/phase5",
        "outputs/phase6",
        "outputs/phase7",
    ]


def test_clean_outputs_cli_requires_explicit_action(tmp_path: Path) -> None:
    from fma.cli import main

    exit_code = main(["clean-outputs", "--repo-root", str(tmp_path)])

    assert exit_code == 2


def test_clean_outputs_cli_archives_failed_outputs(tmp_path: Path) -> None:
    from fma.cli import main

    _write(tmp_path / "outputs" / "phase5" / "counterfactual_summary.json")
    _write(tmp_path / "outputs" / "s_fma_v2_fresh_holdout" / "failed.json")

    exit_code = main(
        [
            "clean-outputs",
            "--repo-root",
            str(tmp_path),
            "--keep-core",
            "--archive-failed",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "outputs" / "phase5" / "counterfactual_summary.json").exists()
    assert (tmp_path / "outputs" / "archive" / "s_fma_v2_fresh_holdout" / "failed.json").exists()
