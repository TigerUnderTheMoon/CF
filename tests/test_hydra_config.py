from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def test_phase6_config_composes_base_and_writes_run_snapshots(tmp_path: Path) -> None:
    from fma.utils import load_config

    config = load_config(
        "phase6/graph",
        overrides=["+intervention_mode=PRUNE"],
        create_run_dir=True,
        output_root=tmp_path,
        timestamp="20260606_190000",
    )

    assert config["experiment"]["name"] == "phase6_graph"
    assert config["experiment"]["objective"] == "C_DIAG_LOCAL_STRUCTURAL"
    assert config["random_seed"] == 20260606
    assert config["phase6"]["intervention_modes"] == ["PRUNE", "CASCADE", "BYPASS"]
    assert config["intervention_mode"] == "PRUNE"

    run_dir = Path(config["paths"]["run_dir"])
    assert run_dir == tmp_path / "20260606_190000_phase6_graph"
    assert (run_dir / ".hydra" / "config.yaml").exists()
    assert (run_dir / ".hydra" / "overrides.yaml").exists()
    assert (run_dir / "config_snapshot.yaml").exists()

    snapshot = yaml.safe_load((run_dir / "config_snapshot.yaml").read_text(encoding="utf-8"))
    assert snapshot["experiment.name"] == "phase6_graph"
    assert snapshot["phase6.default_intervention_mode"] == "PRUNE"


def test_validate_config_rejects_nonpositive_cost_ceiling() -> None:
    from fma.utils import validate_config

    with pytest.raises(ValueError, match="cost_ceiling_usd"):
        validate_config(
            {
                "experiment": {"name": "bad", "objective": "C_REAL_TASK_PILOT"},
                "claim_registry": {"claim_id": "C_REAL_TASK_PILOT"},
                "pilot": {
                    "api_model": "gpt-5.5",
                    "cost_ceiling_usd": 0,
                    "dedup_keys": ["sample_id"],
                },
            },
            validate_claim_registry=False,
        )


def test_validate_config_rejects_claim_objective_mismatch() -> None:
    from fma.utils import validate_config

    with pytest.raises(ValueError, match="experiment.objective"):
        validate_config(
            {
                "experiment": {"name": "bad", "objective": "C_REAL_TASK_PILOT"},
                "claim_registry": {"claim_id": "C_S_FMA_V2_1_EVIDENCE_TARGET"},
            },
            validate_claim_registry=False,
        )


def test_cli_run_pilot_creates_config_snapshots(tmp_path: Path) -> None:
    from fma.cli import run_cli

    result = run_cli(
        [
            "run-pilot",
            "--config-name=pilot/v2_1",
            f"paths.output_root={tmp_path.as_posix()}",
        ],
        timestamp="20260606_191500",
    )

    run_dir = tmp_path / "20260606_191500_s_fma_v2_1_fresh_holdout"
    assert result["command"] == "run-pilot"
    assert result["run_dir"] == str(run_dir)
    assert (run_dir / ".hydra" / "config.yaml").exists()
    assert (run_dir / ".hydra" / "overrides.yaml").exists()
    assert (run_dir / "config_snapshot.yaml").exists()


def test_structural_diagnostics_script_can_build_args_from_hydra_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import scripts.run_structural_diagnostics as cli

    calls = []

    def fake_runner(args):
        calls.append(args)
        return {"delegated": True, "output_json": str(args.output_json)}

    monkeypatch.setattr(cli, "run_structural_diagnostics", fake_runner)

    result = cli.run_from_config(
        config_name="phase6/graph",
        overrides=[f"paths.output_root={tmp_path.as_posix()}", "+intervention_mode=BYPASS"],
        timestamp="20260606_192000",
    )

    assert result["delegated"] is True
    assert calls[0].removal_mode == "BYPASS"
    assert calls[0].output_json == tmp_path / "20260606_192000_phase6_graph" / "structural_diagnostics.json"
