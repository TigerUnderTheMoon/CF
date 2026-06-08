"""Prepare GSM8K train split for real_task_v3 manifest generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DECLARED_GSM8K_REVISION = "e53f048856ff4f594e959d75785d2c2d37b678ee"
DECLARED_JSONL_NAME = "gsm8k_openai_main_train_declared.jsonl"
DECLARED_PROVENANCE_NAME = "gsm8k_openai_main_train_declared_provenance.json"
OUTPUT_DIR = Path("data") / "real_task_v3"


def normalize_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").strip().lower().encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    from datasets import load_dataset

    ds = load_dataset(
        "openai/gsm8k",
        "main",
        split="train",
        revision=DECLARED_GSM8K_REVISION,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUTPUT_DIR / DECLARED_JSONL_NAME
    rows = []

    for i, raw in enumerate(ds):
        question = str(raw.get("question", ""))
        answer = str(raw.get("answer", ""))

        row = {
            "dataset": "openai/gsm8k",
            "config": "main",
            "split": "train",
            "source_index": i,
            "hf_row_index": i,
            "sample_id": f"gsm8k-train-{i:05d}",
            "task_id": f"gsm8k-train-{i:05d}",
            "question": question,
            "reference_answer": answer,
            "aliases": [],
            "task_type": "gsm8k",
        }
        row["source_row_hash"] = normalize_hash(f"{question}|{answer}")
        rows.append(row)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    generated_hash = file_sha256(jsonl_path)

    provenance = {
        "artifact": "real_task_v3_declared_gsm8k_source_provenance",
        "dataset_id": "openai/gsm8k",
        "config": "main",
        "split": "train",
        "full_revision": DECLARED_GSM8K_REVISION,
        "revision": DECLARED_GSM8K_REVISION,
        "resolved_revision": DECLARED_GSM8K_REVISION,
        "row_count": len(rows),
        "row_order_policy": "source_index equals raw HF row index",
        "source_urls": ["https://huggingface.co/datasets/openai/gsm8k"],
        "generated_jsonl_path": str(jsonl_path),
        "generated_file_hash": generated_hash,
        "generated_jsonl_sha256": generated_hash,
        "status": "source_preparation_success_audit",
        "observed_previous_gsm8k_sources": [],
        "current_status_remains": "PILOT_BLOCKED",
        "no_api_run": True,
    }

    provenance_path = OUTPUT_DIR / DECLARED_PROVENANCE_NAME
    with open(provenance_path, "w", encoding="utf-8") as f:
        json.dump(provenance, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Prepared {len(rows)} rows")
    print(f"JSONL: {jsonl_path}")
    print(f"Provenance: {provenance_path}")


if __name__ == "__main__":
    main()
