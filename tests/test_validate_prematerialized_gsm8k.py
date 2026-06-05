from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fma.io import write_records
from scripts.prepare_real_task_v3_gsm8k_source import (
    DECLARED_GSM8K_REVISION,
    build_declared_gsm8k_rows,
    file_sha256,
)


SCRIPT = Path("scripts") / "validate_prematerialized_gsm8k.py"


def test_validate_prematerialized_gsm8k_accepts_valid_pair(tmp_path: Path) -> None:
    jsonl_path, provenance_path = _write_pair(tmp_path)

    result = _run_validator(jsonl_path, provenance_path)

    assert result.returncode == 0
    assert result.stdout.strip() == "PREMATERIALIZED_VALIDATION_PASSED"
    assert result.stderr == ""


def test_validate_prematerialized_gsm8k_rejects_missing_jsonl_field(tmp_path: Path) -> None:
    jsonl_path, provenance_path = _write_pair(tmp_path)
    rows = build_declared_gsm8k_rows([{"question": "What is 1 + 1?", "answer": "#### 2"}])
    rows[0].pop("hf_row_index")
    write_records(rows, jsonl_path)
    _write_provenance(jsonl_path, provenance_path, row_count=1)

    result = _run_validator(jsonl_path, provenance_path)

    assert result.returncode == 1
    assert "PREMATERIALIZED_VALIDATION_FAILED:" in result.stderr
    assert "hf_row_index" in result.stderr


def test_validate_prematerialized_gsm8k_rejects_wrong_sample_id(tmp_path: Path) -> None:
    jsonl_path, provenance_path = _write_pair(tmp_path)
    rows = build_declared_gsm8k_rows([{"question": "What is 1 + 1?", "answer": "#### 2"}])
    rows[0]["sample_id"] = "wrong"
    write_records(rows, jsonl_path)
    _write_provenance(jsonl_path, provenance_path, row_count=1)

    result = _run_validator(jsonl_path, provenance_path)

    assert result.returncode == 1
    assert "sample_id" in result.stderr


def test_validate_prematerialized_gsm8k_rejects_hash_mismatch(tmp_path: Path) -> None:
    jsonl_path, provenance_path = _write_pair(tmp_path)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["generated_file_hash"] = "0" * 64
    provenance_path.write_text(json.dumps(provenance, sort_keys=True), encoding="utf-8")

    result = _run_validator(jsonl_path, provenance_path)

    assert result.returncode == 1
    assert "generated_file_hash" in result.stderr


def test_validate_prematerialized_gsm8k_rejects_wrong_revision(tmp_path: Path) -> None:
    jsonl_path, provenance_path = _write_pair(tmp_path)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["full_revision"] = "0" * 40
    provenance_path.write_text(json.dumps(provenance, sort_keys=True), encoding="utf-8")

    result = _run_validator(jsonl_path, provenance_path)

    assert result.returncode == 1
    assert "full_revision" in result.stderr


def _write_pair(tmp_path: Path) -> tuple[Path, Path]:
    jsonl_path = tmp_path / "gsm8k_openai_main_train_declared.jsonl"
    provenance_path = tmp_path / "gsm8k_openai_main_train_declared_provenance.json"
    rows = build_declared_gsm8k_rows([{"question": "What is 1 + 1?", "answer": "#### 2"}])
    write_records(rows, jsonl_path)
    _write_provenance(jsonl_path, provenance_path, row_count=len(rows))
    return jsonl_path, provenance_path


def _write_provenance(jsonl_path: Path, provenance_path: Path, *, row_count: int) -> None:
    provenance = {
        "dataset_id": "openai/gsm8k",
        "config": "main",
        "split": "train",
        "full_revision": DECLARED_GSM8K_REVISION,
        "generated_file_hash": file_sha256(jsonl_path),
        "row_count": row_count,
        "row_order_policy": "source_index equals raw HF row index",
    }
    provenance_path.write_text(json.dumps(provenance, sort_keys=True), encoding="utf-8")


def _run_validator(jsonl_path: Path, provenance_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--jsonl-path",
            str(jsonl_path),
            "--provenance-path",
            str(provenance_path),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
    )
