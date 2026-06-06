from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_dvc_yaml_defines_phase_pipeline_contract() -> None:
    pipeline = yaml.safe_load((ROOT / "dvc.yaml").read_text(encoding="utf-8"))
    stages = pipeline["stages"]

    assert stages["phase5"]["deps"] == ["data/synthetic_traces.jsonl"]
    assert stages["phase5"]["outs"] == ["outputs/phase5"]
    assert stages["phase6"]["deps"] == ["outputs/phase5"]
    assert stages["phase6"]["outs"] == ["outputs/phase6"]
    assert stages["phase7"]["deps"] == ["outputs/phase6"]
    assert stages["phase7"]["outs"] == ["outputs/phase7"]
    assert stages["figures"]["deps"] == ["outputs/phase7"]
    assert stages["figures"]["outs"] == ["outputs/figures"]


def test_dvcignore_does_not_hide_data_or_outputs_from_dvc() -> None:
    lines = (ROOT / ".dvcignore").read_text(encoding="utf-8").splitlines()
    active_patterns = {
        line.strip().rstrip("/")
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "data" not in active_patterns
    assert "outputs" not in active_patterns


def test_prepare_dvc_synthetic_traces_writes_jsonl(tmp_path: Path) -> None:
    from scripts.prepare_dvc_synthetic_traces import convert_json_array_to_jsonl

    source = tmp_path / "source.json"
    output = tmp_path / "synthetic_traces.jsonl"
    source.write_text(
        json.dumps([{"sample_id": "a", "value": 1}, {"sample_id": "b", "value": 2}]),
        encoding="utf-8",
    )

    count = convert_json_array_to_jsonl(source, output)

    assert count == 2
    assert output.read_text(encoding="utf-8").splitlines() == [
        '{"sample_id": "a", "value": 1}',
        '{"sample_id": "b", "value": 2}',
    ]
