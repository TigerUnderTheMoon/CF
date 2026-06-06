from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_OUTPUTS = (
    "outputs/counterfactual_summary.json",
    "outputs/structural_diagnostics.json",
)


def file_hashes(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    return {
        "md5": hashlib.md5(raw).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


@pytest.mark.regression
def test_historical_artifact_hashes(data_regression) -> None:
    payload: dict[str, dict[str, str]] = {}
    for rel_path in HISTORICAL_OUTPUTS:
        path = ROOT / rel_path
        assert path.exists(), f"Historical artifact is missing: {rel_path}"
        payload[rel_path] = file_hashes(path)

    try:
        data_regression.check(payload)
    except AssertionError as exc:
        raise AssertionError(
            "Historical output hashes changed; a code or artifact modification broke frozen "
            "counterfactual/structural diagnostic results."
        ) from exc
