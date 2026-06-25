from __future__ import annotations

import json
from pathlib import Path


def test_scu_stress_test_default_design_has_material_structural_deltas(tmp_path: Path) -> None:
    from scripts import run_scu_stress_test

    output_dir = tmp_path / "scu_stress_test"
    run_scu_stress_test.main(
        [
            "--output-dir",
            str(output_dir),
            "--samples-per-seed",
            "60",
        ]
    )

    report = json.loads((output_dir / "scu_stress_test.json").read_text(encoding="utf-8"))
    full = report["variants"]["full_scu"]["spearman_mean"]
    no_redundancy = report["variants"]["no_redundancy"]["spearman_mean"]
    no_bottleneck = report["variants"]["no_bottleneck"]["spearman_mean"]

    assert full - no_redundancy >= 0.03
    assert full - no_bottleneck >= 0.03
