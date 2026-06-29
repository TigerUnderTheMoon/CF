from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "verify_feature_list.py"


def write_fixture_files(tmp_path: Path, feature_names: list[str], manuscript_list: str) -> tuple[Path, Path]:
    model_path = tmp_path / "model.json"
    manuscript_path = tmp_path / "manuscript.tex"
    model_path.write_text(
        json.dumps({"feature_names": feature_names}),
        encoding="utf-8",
    )
    manuscript_path.write_text(
        "\n".join(
            [
                "Before.",
                "% w_struct_feature_list_begin",
                manuscript_list,
                "% w_struct_feature_list_end",
                "After.",
            ]
        ),
        encoding="utf-8",
    )
    return model_path, manuscript_path


def run_verifier(model_path: Path, manuscript_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model",
            str(model_path),
            "--manuscript",
            str(manuscript_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_verify_feature_list_accepts_exact_ordered_latex_texttt_list(tmp_path: Path) -> None:
    model_path, manuscript_path = write_fixture_files(
        tmp_path,
        ["raw_local_utility", "relative_position", "trace_step_count"],
        r"\texttt{raw\_local\_utility}, \texttt{relative\_position}, \texttt{trace\_step\_count}",
    )

    result = run_verifier(model_path, manuscript_path)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Feature list matches" in result.stdout


def test_verify_feature_list_rejects_mismatch(tmp_path: Path) -> None:
    model_path, manuscript_path = write_fixture_files(
        tmp_path,
        ["raw_local_utility", "relative_position"],
        r"\texttt{raw\_local\_utility}, \texttt{wrong\_feature}",
    )

    result = run_verifier(model_path, manuscript_path)

    assert result.returncode == 1
    combined_output = result.stderr + result.stdout
    assert "Feature list mismatch" in combined_output
    assert "wrong_feature" in combined_output
    assert "relative_position" in combined_output
