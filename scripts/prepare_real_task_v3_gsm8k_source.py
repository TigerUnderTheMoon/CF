"""Prepare the declared fresh GSM8K train source for real_task_v3 manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records


DECLARED_GSM8K_DATASET_ID = "openai/gsm8k"
DECLARED_GSM8K_CONFIG = "main"
DECLARED_GSM8K_SPLIT = "train"
DECLARED_GSM8K_REVISION = "e53f048856ff4f594e959d75785d2c2d37b678ee"
DEFAULT_OUTPUT_DIR = Path("data") / "real_task_v3"
DECLARED_JSONL_NAME = "gsm8k_openai_main_train_declared.jsonl"
DECLARED_PROVENANCE_NAME = "gsm8k_openai_main_train_declared_provenance.json"
DEFAULT_AUDIT_DIR = Path("outputs") / "real_task_v3"
SOURCE_PREPARATION_FAILURE_STATUS = "source_preparation_failure_audit"
SOURCE_PREPARATION_SUCCESS_STATUS = "source_preparation_success_audit"
SOURCE_URLS = ["https://huggingface.co/datasets/openai/gsm8k"]


class SourcePreparationBlocked(RuntimeError):
    """Raised when declared source preparation must freeze before manifest generation."""

    def __init__(self, audit: Mapping[str, Any]) -> None:
        self.audit = dict(audit)
        super().__init__(str(self.audit.get("failure_mode") or SOURCE_PREPARATION_FAILURE_STATUS))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the declared real_task_v3 fresh GSM8K train source."
    )
    parser.add_argument("--declared-revision", default=DECLARED_GSM8K_REVISION)
    parser.add_argument("--max-download-attempts", type=int, default=4)
    parser.add_argument("--backoff-base-seconds", type=float, default=5.0)
    parser.add_argument("--pre-materialized-jsonl", type=Path)
    parser.add_argument("--pre-materialized-provenance", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--allow-cache-reuse",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--failure-audit",
        type=Path,
        default=DEFAULT_AUDIT_DIR / "source_preparation_failure_audit.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.pre_materialized_jsonl or args.pre_materialized_provenance:
            if not args.pre_materialized_jsonl or not args.pre_materialized_provenance:
                raise SourcePreparationBlocked(
                    _failure_audit(
                        failure_mode="PREMATERIALIZED_VALIDATION_FAILED",
                        declared_revision=args.declared_revision,
                        reason="both --pre-materialized-jsonl and --pre-materialized-provenance are required",
                    )
                )
            result = validate_prematerialized_source(
                jsonl_path=args.pre_materialized_jsonl,
                provenance_path=args.pre_materialized_provenance,
                output_dir=args.output_dir,
                declared_revision=args.declared_revision,
            )
        else:
            result = prepare_declared_gsm8k_source(
                output_dir=args.output_dir,
                declared_revision=args.declared_revision,
                max_download_attempts=args.max_download_attempts,
                backoff_base_seconds=args.backoff_base_seconds,
                allow_cache_reuse=args.allow_cache_reuse,
            )
        print(json.dumps(result, sort_keys=True))
    except SourcePreparationBlocked as exc:
        _cleanup_standard_outputs(args.output_dir)
        _write_json(args.failure_audit, exc.audit)
        message = (
            "REAL_TASK_V3_SOURCE_PREPARATION_BLOCKED: "
            f"{exc.audit.get('failure_mode')}"
        )
        print(message, file=sys.stderr)
        print(json.dumps(exc.audit, sort_keys=True))
        raise SystemExit(1) from exc
    except Exception as exc:
        audit = _failure_audit(
            failure_mode="NETWORK_RETRY_EXHAUSTED",
            declared_revision=args.declared_revision,
            last_error_type=type(exc).__name__,
            reason=str(exc),
        )
        _cleanup_standard_outputs(args.output_dir)
        _write_json(args.failure_audit, audit)
        print(
            f"REAL_TASK_V3_SOURCE_PREPARATION_BLOCKED: {audit['failure_mode']}",
            file=sys.stderr,
        )
        print(json.dumps(audit, sort_keys=True))
        raise SystemExit(1) from exc


def prepare_declared_gsm8k_source(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    declared_revision: str = DECLARED_GSM8K_REVISION,
    cache_root: Path | None = None,
    allow_cache_reuse: bool = True,
    dataset_loader: Callable[..., Sequence[Mapping[str, Any]]] | None = None,
    revision_resolver: Callable[[str], str] | None = None,
    max_download_attempts: int = 4,
    backoff_base_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    audit_dir: Path | None = None,
) -> dict[str, Any]:
    """Prepare the declared source from cache or network, never from another revision."""

    revision = validate_declared_revision(declared_revision)
    loader = dataset_loader or _load_dataset_rows
    resolver = revision_resolver or _resolve_hf_revision
    output_path, provenance_path = declared_source_paths(output_dir)
    active_audit_dir = audit_dir or (DEFAULT_AUDIT_DIR if output_dir == DEFAULT_OUTPUT_DIR else output_dir)

    cache_path = (
        find_declared_revision_cache(cache_root or _default_hf_cache_root(), revision)
        if allow_cache_reuse
        else None
    )
    if cache_path is not None:
        raw_rows = list(
            loader(
                dataset_id=DECLARED_GSM8K_DATASET_ID,
                name=DECLARED_GSM8K_CONFIG,
                split=DECLARED_GSM8K_SPLIT,
                revision=revision,
                cache_path=cache_path,
                cache_only=True,
            )
        )
        return _materialize_success(
            raw_rows=raw_rows,
            output_path=output_path,
            provenance_path=provenance_path,
            resolved_revision=revision,
            cache_path=cache_path,
            cache_hit=True,
            retry_attempts=0,
            download_timestamp=None,
            audit_dir=active_audit_dir,
        )

    raw_rows, resolved_revision, retry_attempts, retry_log = _network_load_with_retry(
        revision=revision,
        resolver=resolver,
        loader=loader,
        max_download_attempts=max_download_attempts,
        backoff_base_seconds=backoff_base_seconds,
        sleep=sleep,
    )
    return _materialize_success(
        raw_rows=raw_rows,
        output_path=output_path,
        provenance_path=provenance_path,
        resolved_revision=resolved_revision,
        cache_path=None,
        cache_hit=False,
        retry_attempts=retry_attempts,
        download_timestamp=datetime.now(timezone.utc).isoformat(),
        audit_dir=active_audit_dir,
        retry_log=retry_log,
    )


def validate_prematerialized_source(
    *,
    jsonl_path: Path,
    provenance_path: Path,
    output_dir: Path,
    declared_revision: str = DECLARED_GSM8K_REVISION,
    audit_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate and copy a manually supplied declared GSM8K JSONL/provenance pair."""

    revision = validate_declared_revision(declared_revision)
    output_path, output_provenance_path = declared_source_paths(output_dir)
    active_audit_dir = audit_dir or (DEFAULT_AUDIT_DIR if output_dir == DEFAULT_OUTPUT_DIR else output_dir)
    try:
        provenance = _read_json(provenance_path)
        _validate_provenance_contract(provenance, declared_revision=revision)
        observed_hash = file_sha256(jsonl_path)
        if observed_hash != str(provenance.get("generated_file_hash") or ""):
            raise ValueError("generated_file_hash does not match JSONL SHA-256")
        rows = validate_declared_jsonl_schema(jsonl_path)
        if int(provenance.get("row_count", -1)) != len(rows):
            raise ValueError("provenance row_count does not match JSONL rows")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(jsonl_path, output_path)
        shutil.copyfile(provenance_path, output_provenance_path)
        success = _write_success_audit(
            audit_dir=active_audit_dir,
            output_path=output_path,
            provenance_path=output_provenance_path,
            generated_file_hash=file_sha256(output_path),
            row_count=len(rows),
            cache_hit=False,
            retry_attempts=0,
        )
        return {
            "status": "DECLARED_GSM8K_SOURCE_READY",
            "source_mode": "pre_materialized",
            "output_path": str(output_path),
            "provenance_path": str(output_provenance_path),
            "success_audit_path": success["success_audit_path"],
            "row_count": len(rows),
            "generated_file_hash": file_sha256(output_path),
            "current_status_remains": "PILOT_BLOCKED",
            "no_api_run": True,
        }
    except SourcePreparationBlocked:
        raise
    except Exception as exc:
        _cleanup_standard_outputs(output_dir)
        raise SourcePreparationBlocked(
            _failure_audit(
                failure_mode="PREMATERIALIZED_VALIDATION_FAILED",
                declared_revision=revision,
                reason=str(exc),
                last_error_type=type(exc).__name__,
                retry_attempts=0,
            )
        ) from exc


def validate_declared_revision(revision: str) -> str:
    value = str(revision).strip().lower()
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("declared GSM8K revision must be a 40-character hex commit hash")
    return value


def find_declared_revision_cache(cache_root: Path, revision: str) -> Path | None:
    revision = validate_declared_revision(revision)
    root = Path(cache_root)
    candidates = [
        root / "datasets--openai--gsm8k" / "snapshots" / revision,
        root / "hub" / "datasets--openai--gsm8k" / "snapshots" / revision,
        root / "datasets" / "openai__gsm8k" / "snapshots" / revision,
        root / "datasets" / "openai--gsm8k" / "snapshots" / revision,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if root.exists():
        for path in root.rglob(revision):
            text = str(path).replace("\\", "/").lower()
            if path.is_dir() and ("openai--gsm8k" in text or "openai__gsm8k" in text):
                return path
    return None


def backoff_delay_seconds(attempt_index: int, backoff_base_seconds: float) -> float:
    if attempt_index <= 1:
        return 0
    return float(backoff_base_seconds) * (3 ** (attempt_index - 2))


def build_declared_gsm8k_rows(raw_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for hf_row_index, row in enumerate(raw_rows):
        question = str(row.get("question") or "")
        answer = str(row.get("answer") or row.get("reference_answer") or "")
        declared = {
            "dataset": DECLARED_GSM8K_DATASET_ID,
            "config": DECLARED_GSM8K_CONFIG,
            "split": DECLARED_GSM8K_SPLIT,
            "source_index": hf_row_index,
            "hf_row_index": hf_row_index,
            "sample_id": f"gsm8k-train-{hf_row_index:05d}",
            "task_id": f"gsm8k-train-{hf_row_index:05d}",
            "question": question,
            "reference_answer": answer,
            "aliases": [],
            "task_type": "gsm8k",
        }
        declared["source_row_hash"] = row_sha256(declared)
        rows.append(declared)
    return rows


def validate_declared_jsonl_schema(path: Path) -> list[dict[str, Any]]:
    rows = load_records(path)
    for index, row in enumerate(rows):
        for key in (
            "dataset",
            "config",
            "split",
            "source_index",
            "hf_row_index",
            "sample_id",
            "task_id",
            "question",
            "reference_answer",
            "aliases",
            "task_type",
            "source_row_hash",
        ):
            if key not in row:
                raise ValueError(f"{path}:{index + 1} missing {key}")
        hf_row_index = row["hf_row_index"]
        if not isinstance(hf_row_index, int):
            raise ValueError(f"{path}:{index + 1} hf_row_index must be integer")
        expected_id = f"gsm8k-train-{hf_row_index:05d}"
        checks = {
            "dataset": row["dataset"] == DECLARED_GSM8K_DATASET_ID,
            "config": row["config"] == DECLARED_GSM8K_CONFIG,
            "split": row["split"] == DECLARED_GSM8K_SPLIT,
            "source_index": row["source_index"] == hf_row_index,
            "sample_id": row["sample_id"] == expected_id,
            "task_id": row["task_id"] == expected_id,
            "aliases": row["aliases"] == [],
            "task_type": row["task_type"] == "gsm8k",
            "source_row_hash": row["source_row_hash"] == row_sha256(row),
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            raise ValueError(f"{path}:{index + 1} schema mismatch: {', '.join(failed)}")
    return rows


def row_sha256(row: Mapping[str, Any]) -> str:
    question = str(row.get("question") or "")
    answer = str(row.get("reference_answer") or row.get("answer") or "")
    return hashlib.sha256(f"{question}|{answer}".encode("utf-8")).hexdigest()


def records_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def declared_source_paths(output_dir: Path) -> tuple[Path, Path]:
    output_root = Path(output_dir)
    return output_root / DECLARED_JSONL_NAME, output_root / DECLARED_PROVENANCE_NAME


def provenance_path_for(source_path: Path) -> Path:
    return source_path.with_name(f"{source_path.stem}_provenance.json")


def build_declared_source_provenance(
    *,
    rows: Sequence[Mapping[str, Any]],
    output_path: Path,
    generated_file_hash: str,
    resolved_revision: str,
    cache_path: Path | None,
    observed_previous_gsm8k_sources: Sequence[Mapping[str, Any]],
    cache_hit: bool,
    retry_attempts: int,
    download_timestamp: str | None,
    retry_log: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved = validate_declared_revision(resolved_revision)
    generated_hash = str(generated_file_hash)
    observed_sources = list(observed_previous_gsm8k_sources)
    return {
        "artifact": "real_task_v3_declared_gsm8k_source_provenance",
        "dataset_id": DECLARED_GSM8K_DATASET_ID,
        "config": DECLARED_GSM8K_CONFIG,
        "split": DECLARED_GSM8K_SPLIT,
        "full_revision": DECLARED_GSM8K_REVISION,
        "revision": DECLARED_GSM8K_REVISION,
        "resolved_revision": resolved,
        "row_count": len(rows),
        "aggregate_source_hash": generated_hash,
        "row_order_policy": "source_index equals raw HF row index",
        "source_urls": list(SOURCE_URLS),
        "cache_path": None if cache_path is None else str(cache_path),
        "cache_hit": bool(cache_hit),
        "generated_jsonl_path": str(output_path),
        "generated_file_hash": generated_hash,
        "generated_jsonl_sha256": generated_hash,
        "conversion_script_hash": file_sha256(Path(__file__)),
        "observed_previous_gsm8k_sources": observed_sources,
        "previous_gsm8k_sources": observed_sources,
        "schema_mapping": {
            "question": "question",
            "reference_answer": "answer",
            "source_index": "raw Hugging Face row index",
        },
        "download_timestamp": download_timestamp,
        "retry_attempts": int(retry_attempts),
        "retry_log": list(retry_log or []),
        "current_status_remains": "PILOT_BLOCKED",
        "no_api_run": True,
    }


def collect_previous_gsm8k_sources(
    paths: Mapping[str, Path] | None = None,
) -> list[dict[str, Any]]:
    source_paths = paths or {
        "real_task_pilot": Path("outputs") / "real_task_pilot" / "sample_manifest.json",
        "s_fma_v2": Path("outputs") / "s_fma_v2_fresh_holdout" / "fresh_manifest.json",
        "s_fma_v2_1": Path("outputs") / "s_fma_v2_1_fresh_holdout" / "fresh_manifest.json",
        "s_fma_v2_2": Path("outputs") / "s_fma_v2_2_fresh_holdout" / "fresh_manifest.json",
    }
    reports = []
    for name, path in source_paths.items():
        if not path.exists():
            continue
        rows = [
            row
            for row in load_records(path)
            if str(row.get("task_type") or "").lower() == "gsm8k"
            or str(row.get("dataset") or "").lower() == "gsm8k"
        ]
        reports.append(
            {
                "name": name,
                "path": str(path),
                "gsm8k_row_count": len(rows),
                "datasets": sorted({str(row.get("dataset") or "") for row in rows if row.get("dataset")}),
                "configs": sorted({str(row.get("config") or "") for row in rows if row.get("config")}),
                "splits": sorted({str(row.get("split") or "") for row in rows if row.get("split")}),
            }
        )
    return reports


def _network_load_with_retry(
    *,
    revision: str,
    resolver: Callable[[str], str],
    loader: Callable[..., Sequence[Mapping[str, Any]]],
    max_download_attempts: int,
    backoff_base_seconds: float,
    sleep: Callable[[float], None],
) -> tuple[list[Mapping[str, Any]], str, int, list[dict[str, Any]]]:
    attempts = max(1, int(max_download_attempts))
    retry_log: list[dict[str, Any]] = []
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        delay = backoff_delay_seconds(attempt, backoff_base_seconds)
        if delay:
            sleep(delay)
        try:
            resolved_revision = validate_declared_revision(resolver(revision))
            if resolved_revision != revision:
                raise SourcePreparationBlocked(
                    _failure_audit(
                        failure_mode="REVISION_MISMATCH",
                        declared_revision=revision,
                        resolved_revision=resolved_revision,
                        retry_attempts=attempt,
                    )
                )
            rows = list(
                loader(
                    dataset_id=DECLARED_GSM8K_DATASET_ID,
                    name=DECLARED_GSM8K_CONFIG,
                    split=DECLARED_GSM8K_SPLIT,
                    revision=revision,
                    cache_path=None,
                    cache_only=False,
                )
            )
            return rows, resolved_revision, attempt, retry_log
        except SourcePreparationBlocked:
            raise
        except Exception as exc:
            last_error = exc
            retry_log.append(
                {
                    "attempt": attempt,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    raise SourcePreparationBlocked(
        _failure_audit(
            failure_mode="NETWORK_RETRY_EXHAUSTED",
            declared_revision=revision,
            last_error_type=type(last_error).__name__ if last_error else None,
            reason=str(last_error) if last_error else "unknown network failure",
            retry_attempts=attempts,
            retry_log=retry_log,
        )
    )


def _materialize_success(
    *,
    raw_rows: Iterable[Mapping[str, Any]],
    output_path: Path,
    provenance_path: Path,
    resolved_revision: str,
    cache_path: Path | None,
    cache_hit: bool,
    retry_attempts: int,
    download_timestamp: str | None,
    audit_dir: Path,
    retry_log: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = build_declared_gsm8k_rows(raw_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_provenance = provenance_path.with_suffix(provenance_path.suffix + ".tmp")
    try:
        write_records(rows, tmp_output)
        validate_declared_jsonl_schema(tmp_output)
        generated_hash = file_sha256(tmp_output)
        provenance = build_declared_source_provenance(
            rows=rows,
            output_path=output_path,
            generated_file_hash=generated_hash,
            resolved_revision=resolved_revision,
            cache_path=cache_path,
            observed_previous_gsm8k_sources=collect_previous_gsm8k_sources(),
            cache_hit=cache_hit,
            retry_attempts=retry_attempts,
            download_timestamp=download_timestamp,
            retry_log=retry_log,
        )
        _write_json(tmp_provenance, provenance)
        tmp_output.replace(output_path)
        tmp_provenance.replace(provenance_path)
        success = _write_success_audit(
            audit_dir=audit_dir,
            output_path=output_path,
            provenance_path=provenance_path,
            generated_file_hash=generated_hash,
            row_count=len(rows),
            cache_hit=cache_hit,
            retry_attempts=retry_attempts,
        )
        return {
            "status": "DECLARED_GSM8K_SOURCE_READY",
            "source_mode": "cache" if cache_hit else "network",
            "output_path": str(output_path),
            "provenance_path": str(provenance_path),
            "success_audit_path": success["success_audit_path"],
            "row_count": len(rows),
            "full_revision": DECLARED_GSM8K_REVISION,
            "resolved_revision": resolved_revision,
            "generated_file_hash": generated_hash,
            "cache_hit": bool(cache_hit),
            "retry_attempts": int(retry_attempts),
            "ready_for_manifest": True,
            "current_status_remains": "PILOT_BLOCKED",
            "no_api_run": True,
        }
    except Exception as exc:
        for path in (tmp_output, tmp_provenance, output_path, provenance_path):
            if path.exists():
                path.unlink()
        raise SourcePreparationBlocked(
            _failure_audit(
                failure_mode="SCHEMA_VALIDATION_FAILED",
                declared_revision=DECLARED_GSM8K_REVISION,
                reason=str(exc),
                last_error_type=type(exc).__name__,
                retry_attempts=retry_attempts,
            )
        ) from exc


def _validate_provenance_contract(
    provenance: Mapping[str, Any],
    *,
    declared_revision: str,
) -> None:
    required = (
        "dataset_id",
        "config",
        "split",
        "full_revision",
        "row_count",
        "row_order_policy",
        "source_urls",
        "schema_mapping",
        "generated_file_hash",
        "resolved_revision",
    )
    missing = [key for key in required if key not in provenance]
    if missing:
        raise ValueError(f"provenance missing required fields: {', '.join(missing)}")
    checks = {
        "dataset_id": provenance["dataset_id"] == DECLARED_GSM8K_DATASET_ID,
        "config": provenance["config"] == DECLARED_GSM8K_CONFIG,
        "split": provenance["split"] == DECLARED_GSM8K_SPLIT,
        "full_revision": provenance["full_revision"] == declared_revision,
        "resolved_revision": provenance["resolved_revision"] == declared_revision,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"provenance mismatch: {', '.join(failed)}")


def _write_success_audit(
    *,
    audit_dir: Path,
    output_path: Path,
    provenance_path: Path,
    generated_file_hash: str,
    row_count: int,
    cache_hit: bool,
    retry_attempts: int,
) -> dict[str, Any]:
    path = Path(audit_dir) / "source_preparation_success_audit.json"
    payload = {
        "status": SOURCE_PREPARATION_SUCCESS_STATUS,
        "ready_for_manifest": True,
        "output_path": str(output_path),
        "provenance_path": str(provenance_path),
        "generated_file_hash": generated_file_hash,
        "row_count": int(row_count),
        "cache_hit": bool(cache_hit),
        "retry_attempts": int(retry_attempts),
        "current_status_remains": "PILOT_BLOCKED",
        "no_api_run": True,
    }
    _write_json(path, payload)
    return {**payload, "success_audit_path": str(path)}


def _failure_audit(
    *,
    failure_mode: str,
    declared_revision: str,
    reason: str | None = None,
    last_error_type: str | None = None,
    retry_attempts: int = 0,
    retry_log: Sequence[Mapping[str, Any]] | None = None,
    resolved_revision: str | None = None,
) -> dict[str, Any]:
    return {
        "status": SOURCE_PREPARATION_FAILURE_STATUS,
        "failure_mode": failure_mode,
        "declared_revision": str(declared_revision),
        "resolved_revision": resolved_revision,
        "last_error_type": last_error_type,
        "reason": reason,
        "retry_attempts": int(retry_attempts),
        "retry_log": list(retry_log or []),
        "current_status_remains": "PILOT_BLOCKED",
        "no_api_run": True,
        "no_replay": True,
        "no_scoring": True,
        "no_prm_filtering_claim": True,
    }


def _load_dataset_rows(
    *,
    dataset_id: str,
    name: str,
    split: str,
    revision: str,
    cache_path: Path | None,
    cache_only: bool,
) -> Sequence[Mapping[str, Any]]:
    from datasets import DownloadConfig, load_dataset

    download_config = DownloadConfig(local_files_only=cache_only) if cache_only else None
    dataset = load_dataset(
        dataset_id,
        name=name,
        split=split,
        revision=revision,
        download_mode="reuse_cache_if_exists",
        download_config=download_config,
    )
    return [dict(row) for row in dataset]


def _resolve_hf_revision(revision: str) -> str:
    from huggingface_hub import HfApi

    info = HfApi().dataset_info(DECLARED_GSM8K_DATASET_ID, revision=revision)
    sha = getattr(info, "sha", None)
    return validate_declared_revision(str(sha or ""))


def _default_hf_cache_root() -> Path:
    return Path.home() / ".cache" / "huggingface"


def _cleanup_standard_outputs(output_dir: Path) -> None:
    output_path, provenance_path = declared_source_paths(output_dir)
    for path in (output_path, provenance_path):
        if path.exists():
            path.unlink()


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
