from __future__ import annotations

import hashlib
import math
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from fma.io import write_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.parsing import extract_reflection_spans
from fma.real_task_pilot.validation_v3 import (
    EXPECTED_V3_HARD_CAPS,
    HOTPOTQA_SURFACE_MATCH_THRESHOLDS,
    REAL_TASK_V3_PREREGISTRATION_ONLY,
    V3_GLOBAL_PASS,
    V3_TASK_SPECIFIC_ONLY,
    audit_v3_config_contract,
    build_circuit_breaker_report,
    build_v3_split_manifest,
    build_v3_route_manifests,
    build_hotpotqa_surface_match_risk_report,
    build_locked_cost_checkpoint,
    build_smoke_calibrated_cost_forecast,
    build_synthetic_real_profile_alignment_report,
    build_w_struct_stability_report,
    build_dense_target_reliability_report,
    build_v3_decision_report,
    score_gsm8k_v3_utility,
    score_hotpotqa_v3_utility,
    validate_w_struct_feature_rows,
)
from scripts.generate_real_task_v3_manifest import (
    _load_gsm8k_extra_source_metadata,
    _write_manifest_generation_package,
)
from scripts.generate_governance_diagnostic_report import (
    build_final_status_audit,
    build_governance_diagnostic_report,
    write_governance_diagnostic_outputs,
)
from scripts.plot_governance_diagnostic import build_governance_diagnostic_plot
from scripts.prepare_real_task_v3_gsm8k_source import (
    DECLARED_GSM8K_REVISION,
    SourcePreparationBlocked,
    backoff_delay_seconds,
    build_declared_gsm8k_rows,
    build_declared_source_provenance,
    file_sha256,
    find_declared_revision_cache,
    prepare_declared_gsm8k_source,
    records_sha256,
    validate_declared_jsonl_schema,
    validate_declared_revision,
    validate_prematerialized_source,
)
from scripts.prepare_real_task_v3_hotpotqa_source import (
    DECLARED_HOTPOTQA_REVISION,
    HotpotQASourcePreparationBlocked,
    build_declared_hotpotqa_rows,
    build_declared_hotpotqa_source_provenance,
    hotpotqa_declared_source_paths,
    prepare_declared_hotpotqa_source,
    validate_declared_hotpotqa_jsonl_schema,
    validate_hotpotqa_prematerialized_source,
)
from fma.real_task_pilot.chat_completions import (
    DEFAULT_CHAT_COMPLETIONS_ENDPOINT,
    DEFAULT_V3_MODEL,
    ChatCompletionsAdapter,
)
from scripts import run_real_task_v3_smoke as v3_smoke_runner
from scripts.generate_real_task_v3_manifest import _assert_current_task_boundary


MANIFEST_SCOPE = "REAL_TASK_V3_MANIFEST_GENERATION_ONLY"
EMPTY_STRING_HASH = hashlib.sha256(b"").hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _write_declared_gsm8k_pair(
    tmp_path: Path, row_count: int
) -> tuple[Path, Path, list[dict[str, Any]]]:
    jsonl_path = tmp_path / "gsm8k_openai_main_train_declared.jsonl"
    provenance_path = tmp_path / "gsm8k_openai_main_train_declared_provenance.json"
    rows = build_declared_gsm8k_rows(
        [
            {
                "question": f"What is {index} + 1?",
                "answer": f"#### {index + 1}",
            }
            for index in range(row_count)
        ]
    )
    write_records(rows, jsonl_path)
    provenance = build_declared_source_provenance(
        rows=rows,
        output_path=jsonl_path,
        generated_file_hash=file_sha256(jsonl_path),
        resolved_revision=DECLARED_GSM8K_REVISION,
        cache_path=None,
        observed_previous_gsm8k_sources=[],
        cache_hit=False,
        retry_attempts=0,
        download_timestamp=None,
    )
    _write_json(provenance_path, provenance)
    return jsonl_path, provenance_path, rows


def _write_hotpotqa_source(tmp_path: Path, row_count: int) -> tuple[Path, list[dict[str, Any]]]:
    path, provenance_path = hotpotqa_declared_source_paths(tmp_path)
    rows = build_declared_hotpotqa_rows(
        [
            {
                "id": f"raw-hotpotqa-{index:05d}",
                "question": f"Who is linked to entity {index}?",
                "answer": f"Entity {index}",
                "supporting_facts": [["Title", index]],
            }
            for index in range(row_count)
        ]
    )
    write_records(rows, path)
    provenance = build_declared_hotpotqa_source_provenance(
        rows=rows,
        output_path=path,
        generated_file_hash=file_sha256(path),
        resolved_revision=DECLARED_HOTPOTQA_REVISION,
        cache_path=None,
        observed_previous_hotpotqa_sources=[],
        cache_hit=True,
        retry_attempts=0,
        download_timestamp=None,
    )
    _write_json(provenance_path, provenance)
    return path, rows


def _run_manifest_gate(
    *,
    gsm8k_source: Path,
    hotpotqa_source: Path,
    exclusion_dir: Path,
    output_dir: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "scripts/generate_real_task_v3_manifest.py",
        "--allow-manifest-generation-only",
        "--task-scope",
        MANIFEST_SCOPE,
        "--gsm8k-extra-source",
        str(gsm8k_source),
        "--hotpotqa-extra-source",
        str(hotpotqa_source),
        "--exclusion-artifacts-dir",
        str(exclusion_dir),
        "--output-dir",
        str(output_dir),
        "--random-seed",
        "123",
    ]
    if extra_args:
        command.extend(extra_args)
    return subprocess.run(
        command,
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )


def _read_manifest_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _sample_blocked_manifest_audit() -> dict[str, Any]:
    return {
        "status": "BLOCKED_OVERLAP_DETECTED",
        "blocker": "overlap_detected",
        "total_excluded_rows": 10,
        "post_dedup_counts": {"gsm8k": 0, "hotpotqa": 0},
        "overlap_counts": {
            "pilot": {
                "sample_id": 2,
                "task_id": 0,
                "dataset_config_split_source_index": 2,
                "normalized_question_hash": 2,
                "reference_answer_hash": 3,
                "non_empty_alias_hash": 10,
            },
            "v2": {
                "sample_id": 2,
                "task_id": 2,
                "dataset_config_split_source_index": 2,
                "normalized_question_hash": 2,
                "reference_answer_hash": 1,
                "non_empty_alias_hash": 10,
            },
            "v2.1": {
                "sample_id": 2,
                "task_id": 2,
                "dataset_config_split_source_index": 2,
                "normalized_question_hash": 2,
                "reference_answer_hash": 1,
                "non_empty_alias_hash": 10,
            },
            "v2.2": {
                "sample_id": 2,
                "task_id": 2,
                "dataset_config_split_source_index": 2,
                "normalized_question_hash": 2,
                "reference_answer_hash": 1,
                "non_empty_alias_hash": 10,
            },
        },
        "overlap_examples": {
            "pilot": {
                "non_empty_alias_hash": [
                    {
                        "sample_id": "gsm8k-train-00000",
                        "task_type": "gsm8k",
                        "overlap_key": "non_empty_alias_hash",
                        "overlap_value": EMPTY_STRING_HASH,
                    }
                ],
                "sample_id": [
                    {
                        "sample_id": "hotpotqa-00064",
                        "task_type": "hotpotqa",
                        "overlap_key": "sample_id",
                        "overlap_value": "hotpotqa-00064",
                    }
                ],
            }
        },
        "split_counts": {
            "smoke": {"total": 200, "gsm8k": 100, "hotpotqa": 100},
            "dev": {"total": 1000, "gsm8k": 500, "hotpotqa": 500},
            "locked": {"total": 2000, "gsm8k": 1000, "hotpotqa": 1000},
        },
    }


def test_real_task_v3_config_locks_budget_scale_and_claim_boundary() -> None:
    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))

    audit = audit_v3_config_contract(config)

    assert audit["status"] == "REAL_TASK_V3_CONTRACT_CLEAN"
    assert audit["scope"] == REAL_TASK_V3_PREREGISTRATION_ONLY
    assert audit["current_status_remains"] == "PILOT_BLOCKED"
    assert audit["api_execution_allowed"] is False
    assert audit["validation_or_pass_claim_allowed"] is False
    assert audit["hard_caps"] == EXPECTED_V3_HARD_CAPS
    assert config["splits"]["locked_validation"]["sample_count_by_task"] == {
        "gsm8k": 1000,
        "hotpotqa": 1000,
    }
    assert config["source_contract"] == {
        "gsm8k": {
            "dataset_id": "openai/gsm8k",
            "config": "main",
            "split": "train",
            "revision": DECLARED_GSM8K_REVISION,
            "declared_jsonl": "data/real_task_v3/gsm8k_openai_main_train_declared.jsonl",
            "provenance": "data/real_task_v3/gsm8k_openai_main_train_declared_provenance.json",
        },
        "hotpotqa": {
            "dataset_id": "hotpot_qa",
            "config": "distractor",
            "split": "train",
            "revision": DECLARED_HOTPOTQA_REVISION,
            "declared_jsonl": "data/real_task_v3/hotpotqa_distractor_train_declared.jsonl",
            "provenance": "data/real_task_v3/hotpotqa_distractor_train_declared_provenance.json",
        },
    }


def test_real_task_v3_config_records_final_execution_guards() -> None:
    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))

    assert config["model"]["primary"] == DEFAULT_V3_MODEL
    assert config["api"]["chat_completions_endpoint"] == DEFAULT_CHAT_COMPLETIONS_ENDPOINT
    assert config["api"]["api_key_env"] == "OPENCODE_GO_KEY"
    assert config["api"]["health_check"]["counted_json_requests"] == 3
    assert config["api"]["circuit_breaker"] == {
        "consecutive_infra_errors_hard_stop": 20,
        "rolling_window_requests": 50,
        "rolling_infra_error_fraction_max": 0.25,
    }
    assert config["cost_controls"]["locked_checkpoint_interval_requests"] == 10000
    assert config["utility_target"]["hotpotqa"]["weights"] == {
        "alias_token_f1": 0.50,
        "reference_only_f1": 0.2777777778,
        "support_overlap": 0.2222222222,
    }
    assert (
        config["utility_target"]["hotpotqa"]["semantic_judge_gate"] == "disabled_by_target_revision"
    )
    assert config["utility_target"]["hotpotqa"]["surface_match_risk"] == {
        "alias_token_f1_gt": 0.8,
        "support_overlap_lt": 0.2,
    }
    assert "semantic_judge_human_audit_pairs" not in config["utility_target"]["reliability_gate"]


def test_v3_dense_utility_scoring_uses_locked_weights() -> None:
    gsm_score = score_gsm8k_v3_utility(
        predictions=["#### 100", "The answer is 80", "not parseable"],
        reference_answer="#### 100",
    )

    assert gsm_score["utility"] == (
        0.60 * (1 / 3) + 0.40 * ((1.0 + math.exp(-abs(math.log(81 / 101))) + 0.0) / 3)
    )
    assert gsm_score["repeated_numeric_exact"] == 1 / 3

    hotpot_score = score_hotpotqa_v3_utility(
        prediction="Shakespeare wrote Hamlet",
        reference_answer="William Shakespeare",
        aliases=["Shakespeare"],
        predicted_supports=["Hamlet"],
        reference_supports=["Hamlet", "Authorship"],
    )

    assert hotpot_score["weights"] == {
        "alias_token_f1": 0.50,
        "reference_only_f1": 0.2777777778,
        "support_overlap": 0.2222222222,
    }
    assert 0.0 < hotpot_score["utility"] <= 1.0
    assert hotpot_score["semantic_judge_gate"] == "disabled_by_target_revision"
    assert "semantic_equivalence" not in hotpot_score


def test_hotpotqa_surface_match_risk_uses_preregistered_predicate() -> None:
    report = build_hotpotqa_surface_match_risk_report(
        [
            {
                "sample_id": "hotpotqa-risk",
                "alias_token_f1": 0.9,
                "support_overlap": 0.1,
            },
            {
                "sample_id": "hotpotqa-clean",
                "alias_token_f1": 0.9,
                "support_overlap": 0.5,
            },
        ]
    )

    assert HOTPOTQA_SURFACE_MATCH_THRESHOLDS == {
        "alias_token_f1_gt": 0.8,
        "support_overlap_lt": 0.2,
    }
    assert report["risk_count"] == 1
    assert report["risk_fraction"] == 0.5
    assert report["examples"][0]["sample_id"] == "hotpotqa-risk"


def test_v3_split_manifest_uses_six_key_non_overlap_and_locked_counts() -> None:
    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))
    source_rows = {
        "gsm8k": [
            {
                "dataset": "gsm8k",
                "config": "main",
                "split": "test",
                "source_index": index,
                "sample_id": f"gsm8k-{index:05d}",
                "task_id": f"gsm8k-task-{index}",
                "question": f"What is {index} + 1?",
                "reference_answer": f"#### {index + 1}",
                "aliases": [],
                "task_type": "gsm8k",
            }
            for index in range(3)
        ],
        "hotpotqa": [
            {
                "dataset": "hotpot_qa",
                "config": "distractor",
                "split": "validation",
                "source_index": index,
                "sample_id": f"hotpotqa-{index:05d}",
                "task_id": f"hotpotqa-task-{index}",
                "question": f"Who is entity {index}?",
                "reference_answer": f"Entity {index}",
                "aliases": [f"Alias {index}"],
                "task_type": "hotpotqa",
            }
            for index in range(3)
        ],
    }
    overlap_sources = {
        "old": [
            {
                "sample_id": "gsm8k-00000",
                "task_id": "old",
                "question": "What is 0 + 1?",
                "reference_answer": "#### 1",
                "aliases": [],
            }
        ]
    }

    manifest, audit = build_v3_split_manifest(
        source_rows,
        config=config,
        split_name="smoke",
        sample_count_by_task={"gsm8k": 2, "hotpotqa": 2},
        overlap_sources=overlap_sources,
    )

    assert audit["status"] == "MANIFEST_OVERLAP_CLEAN"
    assert audit["split_name"] == "smoke"
    assert audit["manifest_rows"] == 4
    assert audit["overlap_summary"]["selected_overlaps_by_key"]["sample_id"] == 0
    assert "gsm8k-00000" not in {row["sample_id"] for row in manifest}
    assert {row["split_role"] for row in manifest} == {"smoke"}
    assert set(audit["required_non_overlap_keys"]) == {
        "sample_id",
        "task_id",
        "dataset_config_split_source_index",
        "normalized_question_hash",
        "reference_answer_hash",
        "non_empty_alias_hash",
    }
    assert all("non_empty_alias_hash" in row for row in manifest)


def test_v3_route_manifests_are_disjoint_across_splits() -> None:
    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))
    source_rows = {
        "gsm8k": [
            {
                "dataset": "gsm8k",
                "config": "main",
                "split": "train",
                "source_index": index,
                "sample_id": f"gsm8k-train-{index:05d}",
                "task_id": f"gsm8k-train-task-{index}",
                "question": f"What is {index} + 2?",
                "reference_answer": f"#### {index + 2}",
                "aliases": [],
                "task_type": "gsm8k",
            }
            for index in range(6)
        ],
        "hotpotqa": [
            {
                "dataset": "hotpot_qa",
                "config": "distractor",
                "split": "validation",
                "source_index": index,
                "sample_id": f"hotpotqa-v3-{index:05d}",
                "task_id": f"hotpotqa-v3-task-{index}",
                "question": f"Who is entity {index}?",
                "reference_answer": f"Entity {index}",
                "aliases": [f"Alias {index}"],
                "task_type": "hotpotqa",
            }
            for index in range(6)
        ],
    }

    manifests, audit = build_v3_route_manifests(
        source_rows,
        config=config,
        split_sample_counts={
            "smoke": {"gsm8k": 1, "hotpotqa": 1},
            "dev_calibration": {"gsm8k": 2, "hotpotqa": 2},
            "locked_validation": {"gsm8k": 3, "hotpotqa": 3},
        },
        overlap_sources={},
    )

    assert audit["status"] == "MANIFEST_OVERLAP_CLEAN"
    selected_ids_by_split = {
        split: {row["sample_id"] for row in rows} for split, rows in manifests.items()
    }
    assert selected_ids_by_split["smoke"].isdisjoint(selected_ids_by_split["dev_calibration"])
    assert selected_ids_by_split["dev_calibration"].isdisjoint(
        selected_ids_by_split["locked_validation"]
    )


def test_declared_gsm8k_source_requires_full_revision_and_stable_row_indices() -> None:
    assert len(DECLARED_GSM8K_REVISION) == 40
    assert validate_declared_revision(DECLARED_GSM8K_REVISION) == DECLARED_GSM8K_REVISION

    with pytest.raises(ValueError, match="40-character"):
        validate_declared_revision("e53f048")

    declared_rows = build_declared_gsm8k_rows(
        [
            {"question": "What is 1 + 1?", "answer": "#### 2"},
            {"question": "What is 2 + 2?", "answer": "#### 4"},
        ]
    )

    assert declared_rows[0]["dataset"] == "openai/gsm8k"
    assert declared_rows[0]["config"] == "main"
    assert declared_rows[0]["split"] == "train"
    assert declared_rows[0]["hf_row_index"] == 0
    assert declared_rows[0]["source_index"] == 0
    assert declared_rows[0]["sample_id"] == "gsm8k-train-00000"
    assert declared_rows[0]["task_id"] == "gsm8k-train-00000"
    assert declared_rows[0]["reference_answer"] == "#### 2"
    assert declared_rows[0]["aliases"] == []
    assert declared_rows[0]["task_type"] == "gsm8k"
    assert len(declared_rows[0]["source_row_hash"]) == 64
    assert declared_rows[0]["source_row_hash"] != declared_rows[1]["source_row_hash"]
    assert declared_rows[1]["source_index"] == 1


def test_declared_gsm8k_source_provenance_hashes_rows_and_previous_sources() -> None:
    declared_rows = build_declared_gsm8k_rows([{"question": "What is 3 + 3?", "answer": "#### 6"}])

    provenance = build_declared_source_provenance(
        rows=declared_rows,
        output_path=Path("data/real_task_v3/gsm8k_openai_main_train_declared.jsonl"),
        generated_file_hash=records_sha256(declared_rows),
        resolved_revision=DECLARED_GSM8K_REVISION,
        cache_path=Path("hf-cache/openai/gsm8k"),
        observed_previous_gsm8k_sources=[
            {
                "name": "real_task_pilot",
                "path": "outputs/real_task_pilot/sample_manifest.json",
                "splits": ["test"],
            }
        ],
        cache_hit=True,
        retry_attempts=0,
        download_timestamp=None,
    )

    assert provenance["dataset_id"] == "openai/gsm8k"
    assert provenance["full_revision"] == DECLARED_GSM8K_REVISION
    assert provenance["resolved_revision"] == DECLARED_GSM8K_REVISION
    assert provenance["row_order_policy"] == "source_index equals raw HF row index"
    assert provenance["row_count"] == 1
    assert provenance["aggregate_source_hash"] == records_sha256(declared_rows)
    assert provenance["generated_file_hash"] == records_sha256(declared_rows)
    assert len(provenance["conversion_script_hash"]) == 64
    assert provenance["observed_previous_gsm8k_sources"][0]["splits"] == ["test"]


def test_manifest_gate_links_declared_gsm8k_source_provenance(tmp_path: Path) -> None:
    extra_path = tmp_path / "gsm8k_openai_main_train_declared.jsonl"
    provenance_path = tmp_path / "gsm8k_openai_main_train_declared_provenance.json"
    hotpotqa_path, _ = _write_hotpotqa_source(tmp_path, 4)
    rows = build_declared_gsm8k_rows(
        [{"question": f"What is {index} + 1?", "answer": f"#### {index + 1}"} for index in range(4)]
    )
    write_records(rows, extra_path)
    provenance = build_declared_source_provenance(
        rows=rows,
        output_path=extra_path,
        generated_file_hash=file_sha256(extra_path),
        resolved_revision=DECLARED_GSM8K_REVISION,
        cache_path=Path("hf-cache/openai/gsm8k"),
        observed_previous_gsm8k_sources=[],
        cache_hit=False,
        retry_attempts=1,
        download_timestamp="2026-06-06T00:00:00+00:00",
    )
    provenance_path.write_text(json.dumps(provenance, sort_keys=True), encoding="utf-8")

    metadata = _load_gsm8k_extra_source_metadata(extra_path)
    assert metadata["provenance_path"] == str(provenance_path)
    assert metadata["generated_jsonl_sha256"] == file_sha256(extra_path)

    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))
    config = {
        **config,
        "experiment": {**config["experiment"], "output_dir": str(tmp_path / "out")},
        "splits": {
            **config["splits"],
            "smoke": {"sample_count_by_task": {"gsm8k": 1, "hotpotqa": 1}},
            "dev_calibration": {"sample_count_by_task": {"gsm8k": 1, "hotpotqa": 1}},
            "locked_validation": {"sample_count_by_task": {"gsm8k": 1, "hotpotqa": 1}},
        },
    }
    result = _write_manifest_generation_package(
        config,
        gsm8k_extra_source=extra_path,
        hotpotqa_extra_source=hotpotqa_path,
        exclusion_artifacts_dir=tmp_path / "empty_outputs",
        output_dir=tmp_path / "out",
        random_seed=123,
    )
    audit = json.loads(Path(result["audit_path"]).read_text(encoding="utf-8"))

    assert audit["gsm8k_extra_source_provenance_path"] == str(provenance_path)
    assert audit["gsm8k_extra_source_provenance_hash"] == file_sha256(provenance_path)
    assert audit["hotpotqa_extra_source_path"] == str(hotpotqa_path)
    assert audit["hotpotqa_extra_source_provenance_hash"] == file_sha256(
        hotpotqa_path.with_name(f"{hotpotqa_path.stem}_provenance.json")
    )
    assert result["status"] == "MANIFEST_OVERLAP_CLEAN"


def test_manifest_gate_rejects_missing_or_mismatched_gsm8k_source_provenance(
    tmp_path: Path,
) -> None:
    extra_path = tmp_path / "gsm8k_openai_main_train_declared.jsonl"
    write_records(
        build_declared_gsm8k_rows([{"question": "What is 5 + 5?", "answer": "#### 10"}]),
        extra_path,
    )

    with pytest.raises(RuntimeError, match="source_preparation_failure_audit"):
        _load_gsm8k_extra_source_metadata(extra_path)


def test_hotpotqa_source_preparation_cache_hit_writes_success_audit(tmp_path: Path) -> None:
    output_dir = tmp_path / "declared"

    result = prepare_declared_hotpotqa_source(
        output_dir=output_dir,
        declared_revision=DECLARED_HOTPOTQA_REVISION,
        cache_root=tmp_path / "hf-cache",
        allow_cache_reuse=True,
        dataset_loader=lambda **_: [
            {
                "id": "raw-hotpot-1",
                "question": "Who wrote Hamlet?",
                "answer": "William Shakespeare",
                "supporting_facts": [["Hamlet", 0]],
            }
        ],
        revision_resolver=lambda revision: revision,
        sleep=lambda _: None,
    )

    assert result["status"] == "DECLARED_HOTPOTQA_SOURCE_READY"
    assert result["row_count"] == 1
    rows = validate_declared_hotpotqa_jsonl_schema(Path(result["output_path"]))
    assert rows[0]["sample_id"] == "hotpotqa-train-00000"
    success = json.loads(Path(result["success_audit_path"]).read_text(encoding="utf-8"))
    assert success["ready_for_manifest"] is True
    assert success["current_status_remains"] == "PILOT_BLOCKED"


def test_hotpotqa_declared_schema_rejects_row_hash_mismatch(tmp_path: Path) -> None:
    path, _ = hotpotqa_declared_source_paths(tmp_path)
    rows = build_declared_hotpotqa_rows(
        [
            {
                "id": "raw-hotpot-1",
                "question": "Who wrote Hamlet?",
                "answer": "William Shakespeare",
                "supporting_facts": [["Hamlet", 0]],
            }
        ]
    )
    rows[0]["source_row_hash"] = "0" * 64
    write_records(rows, path)

    with pytest.raises(ValueError, match="source_row_hash"):
        validate_declared_hotpotqa_jsonl_schema(path)


def test_hotpotqa_prematerialized_hash_mismatch_cleans_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "declared"
    jsonl_path, provenance_path = hotpotqa_declared_source_paths(source_dir)
    rows = build_declared_hotpotqa_rows(
        [
            {
                "id": "raw-hotpot-1",
                "question": "Who wrote Hamlet?",
                "answer": "William Shakespeare",
                "supporting_facts": [["Hamlet", 0]],
            }
        ]
    )
    write_records(rows, jsonl_path)
    provenance = build_declared_hotpotqa_source_provenance(
        rows=rows,
        output_path=jsonl_path,
        generated_file_hash="0" * 64,
        resolved_revision=DECLARED_HOTPOTQA_REVISION,
        cache_path=None,
        observed_previous_hotpotqa_sources=[],
        cache_hit=False,
        retry_attempts=0,
        download_timestamp=None,
    )
    _write_json(provenance_path, provenance)

    with pytest.raises(HotpotQASourcePreparationBlocked, match="PREMATERIALIZED_VALIDATION_FAILED"):
        validate_hotpotqa_prematerialized_source(
            jsonl_path=jsonl_path,
            provenance_path=provenance_path,
            output_dir=output_dir,
            declared_revision=DECLARED_HOTPOTQA_REVISION,
        )

    declared_jsonl, declared_provenance = hotpotqa_declared_source_paths(output_dir)
    assert not declared_jsonl.exists()
    assert not declared_provenance.exists()


def test_real_task_v3_manifest_gate_clean_generation_writes_all_splits(tmp_path: Path) -> None:
    gsm8k_path, provenance_path, _ = _write_declared_gsm8k_pair(tmp_path, 2000)
    hotpotqa_path, _ = _write_hotpotqa_source(tmp_path, 2000)
    output_dir = tmp_path / "out"

    result = _run_manifest_gate(
        gsm8k_source=gsm8k_path,
        hotpotqa_source=hotpotqa_path,
        exclusion_dir=tmp_path / "empty_outputs",
        output_dir=output_dir,
    )

    assert result.returncode == 0, result.stderr
    assert "REAL_TASK_V3_MANIFEST_OVERLAP_CLEAN" in result.stdout
    audit = json.loads((output_dir / "manifest_overlap_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "MANIFEST_OVERLAP_CLEAN"
    assert audit["gsm8k_extra_source_provenance_path"] == str(provenance_path)
    assert audit["gsm8k_extra_source_provenance_hash"] == file_sha256(provenance_path)
    assert audit["hotpotqa_extra_source_path"] == str(hotpotqa_path)
    assert audit["hotpotqa_extra_source_provenance_hash"] == file_sha256(
        hotpotqa_path.with_name(f"{hotpotqa_path.stem}_provenance.json")
    )
    assert audit["split_counts"] == {
        "smoke": {"total": 200, "gsm8k": 100, "hotpotqa": 100},
        "dev": {"total": 1000, "gsm8k": 500, "hotpotqa": 500},
        "locked": {"total": 2000, "gsm8k": 1000, "hotpotqa": 1000},
    }
    assert len(_read_manifest_rows(output_dir / "smoke_manifest.jsonl")) == 200
    assert len(_read_manifest_rows(output_dir / "dev_calibration_manifest.jsonl")) == 1000
    assert len(_read_manifest_rows(output_dir / "locked_validation_manifest.jsonl")) == 2000


def test_real_task_v3_manifest_gate_warns_on_core_overlap_but_proceeds(tmp_path: Path) -> None:
    gsm8k_path, _, _ = _write_declared_gsm8k_pair(tmp_path, 2000)
    hotpotqa_path, hotpotqa_rows = _write_hotpotqa_source(tmp_path, 2000)
    exclusion_dir = tmp_path / "outputs"
    _write_json(exclusion_dir / "real_task_pilot" / "sample_manifest.json", [hotpotqa_rows[0]])
    output_dir = tmp_path / "out"

    result = _run_manifest_gate(
        gsm8k_source=gsm8k_path,
        hotpotqa_source=hotpotqa_path,
        exclusion_dir=exclusion_dir,
        output_dir=output_dir,
    )

    # Under core_and_per_source policy, the manifest generation no longer blocks
    # on overlap detection. It proceeds with eligible rows and logs a warning.
    assert result.returncode == 0


def test_real_task_v3_manifest_gate_blocks_insufficient_fresh_rows_without_partials(
    tmp_path: Path,
) -> None:
    gsm8k_path, _, _ = _write_declared_gsm8k_pair(tmp_path, 50)
    hotpotqa_path, _ = _write_hotpotqa_source(tmp_path, 2000)
    output_dir = tmp_path / "out"

    result = _run_manifest_gate(
        gsm8k_source=gsm8k_path,
        hotpotqa_source=hotpotqa_path,
        exclusion_dir=tmp_path / "empty_outputs",
        output_dir=output_dir,
    )

    assert result.returncode == 1
    assert "REAL_TASK_V3_MANIFEST_BLOCKED: insufficient_fresh_rows" in (
        result.stdout + result.stderr
    )
    audit = json.loads((output_dir / "manifest_overlap_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "BLOCKED_INSUFFICIENT_FRESH_ROWS"
    assert audit["post_dedup_counts"]["gsm8k"] == 50
    assert audit["preflight_passed"] is False
    assert not (output_dir / "smoke_manifest.jsonl").exists()
    assert not (output_dir / "dev_calibration_manifest.jsonl").exists()
    assert not (output_dir / "locked_validation_manifest.jsonl").exists()


def test_real_task_v3_manifest_gate_blocks_source_provenance_hash_mismatch(
    tmp_path: Path,
) -> None:
    gsm8k_path, provenance_path, _ = _write_declared_gsm8k_pair(tmp_path, 2000)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["generated_file_hash"] = "0" * 64
    _write_json(provenance_path, provenance)
    hotpotqa_path, _ = _write_hotpotqa_source(tmp_path, 2000)
    output_dir = tmp_path / "out"

    result = _run_manifest_gate(
        gsm8k_source=gsm8k_path,
        hotpotqa_source=hotpotqa_path,
        exclusion_dir=tmp_path / "empty_outputs",
        output_dir=output_dir,
    )

    assert result.returncode == 1
    assert "REAL_TASK_V3_MANIFEST_BLOCKED: source_provenance_invalid" in (
        result.stdout + result.stderr
    )
    audit = json.loads((output_dir / "manifest_overlap_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "BLOCKED_SOURCE_PROVENANCE_INVALID"
    assert not (output_dir / "smoke_manifest.jsonl").exists()


def test_real_task_v3_manifest_gate_rejects_legacy_hotpotqa_validation_source(
    tmp_path: Path,
) -> None:
    gsm8k_path, _, _ = _write_declared_gsm8k_pair(tmp_path, 2000)
    legacy_hotpotqa = tmp_path / "hotpotqa_validation.jsonl"
    write_records(
        [
            {
                "source_dataset": "hotpot_qa",
                "source_config": "distractor",
                "source_split": "validation",
                "source_index": 0,
                "task_id": "legacy-hotpotqa-0",
                "question": "Legacy validation question?",
                "reference_answer": "Legacy answer",
                "aliases": [],
                "task_type": "hotpotqa",
            }
        ],
        legacy_hotpotqa,
    )
    output_dir = tmp_path / "out"

    result = _run_manifest_gate(
        gsm8k_source=gsm8k_path,
        hotpotqa_source=legacy_hotpotqa,
        exclusion_dir=tmp_path / "empty_outputs",
        output_dir=output_dir,
    )

    assert result.returncode == 1
    assert "source_provenance_invalid" in (result.stdout + result.stderr)
    audit = json.loads((output_dir / "manifest_overlap_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "BLOCKED_SOURCE_PROVENANCE_INVALID"
    assert "declared HotpotQA train source" in audit["source_provenance_error"]


def test_real_task_v3_manifest_gate_enforces_split_disjointness_and_six_keys(
    tmp_path: Path,
) -> None:
    gsm8k_path, _, _ = _write_declared_gsm8k_pair(tmp_path, 2000)
    hotpotqa_path, _ = _write_hotpotqa_source(tmp_path, 2000)
    output_dir = tmp_path / "out"

    result = _run_manifest_gate(
        gsm8k_source=gsm8k_path,
        hotpotqa_source=hotpotqa_path,
        exclusion_dir=tmp_path / "empty_outputs",
        output_dir=output_dir,
    )

    assert result.returncode == 0, result.stderr
    split_paths = [
        output_dir / "smoke_manifest.jsonl",
        output_dir / "dev_calibration_manifest.jsonl",
        output_dir / "locked_validation_manifest.jsonl",
    ]
    rows_by_split = [_read_manifest_rows(path) for path in split_paths]
    seen_sample_ids: set[str] = set()
    seen_task_ids: set[str] = set()
    six_keys = {
        "sample_id",
        "task_id",
        "dataset_config_split_source_index",
        "normalized_question_hash",
        "reference_answer_hash",
        "non_empty_alias_hash",
    }
    for rows in rows_by_split:
        sample_ids = {str(row["sample_id"]) for row in rows}
        task_ids = {str(row["task_id"]) for row in rows}
        assert seen_sample_ids.isdisjoint(sample_ids)
        assert seen_task_ids.isdisjoint(task_ids)
        seen_sample_ids.update(sample_ids)
        seen_task_ids.update(task_ids)
        assert all(six_keys.issubset(row) for row in rows)
        assert all(row["split"] in {"smoke", "dev", "locked"} for row in rows)
    gsm8k_rows = [row for rows in rows_by_split for row in rows if row["task_type"] == "gsm8k"]
    assert all(row["non_empty_alias_hash"] == "__EMPTY_ALIAS_EXCLUDED__" for row in gsm8k_rows)


def test_real_task_v3_manifest_gate_requires_guarded_cli_flag(tmp_path: Path) -> None:
    gsm8k_path, _, _ = _write_declared_gsm8k_pair(tmp_path, 2000)
    hotpotqa_path, _ = _write_hotpotqa_source(tmp_path, 2000)
    command = [
        sys.executable,
        "scripts/generate_real_task_v3_manifest.py",
        "--task-scope",
        MANIFEST_SCOPE,
        "--gsm8k-extra-source",
        str(gsm8k_path),
        "--hotpotqa-extra-source",
        str(hotpotqa_path),
        "--exclusion-artifacts-dir",
        str(tmp_path / "empty_outputs"),
        "--output-dir",
        str(tmp_path / "out"),
    ]

    result = subprocess.run(
        command,
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "--allow-manifest-generation-only is required" in (result.stdout + result.stderr)


def test_source_preparation_cache_hit_writes_success_audit(tmp_path: Path) -> None:
    cache_root = tmp_path / "hf-cache"
    snapshot = cache_root / "datasets--openai--gsm8k" / "snapshots" / DECLARED_GSM8K_REVISION
    snapshot.mkdir(parents=True)
    output_dir = tmp_path / "declared"

    result = prepare_declared_gsm8k_source(
        output_dir=output_dir,
        declared_revision=DECLARED_GSM8K_REVISION,
        cache_root=cache_root,
        allow_cache_reuse=True,
        dataset_loader=lambda **_: [
            {"question": "What is 6 + 6?", "answer": "#### 12"},
        ],
        revision_resolver=lambda revision: revision,
        sleep=lambda _: None,
    )

    assert result["status"] == "DECLARED_GSM8K_SOURCE_READY"
    assert result["cache_hit"] is True
    assert Path(result["success_audit_path"]).exists()
    success = json.loads(Path(result["success_audit_path"]).read_text(encoding="utf-8"))
    assert success["ready_for_manifest"] is True
    assert success["cache_hit"] is True
    assert find_declared_revision_cache(cache_root, DECLARED_GSM8K_REVISION) == snapshot


def test_source_preparation_retry_exhaustion_freezes_failure_audit(tmp_path: Path) -> None:
    attempts = []

    def failing_loader(**_: object) -> list[dict[str, str]]:
        attempts.append("attempt")
        raise ConnectionError("network down")

    with pytest.raises(SourcePreparationBlocked) as excinfo:
        prepare_declared_gsm8k_source(
            output_dir=tmp_path / "declared",
            declared_revision=DECLARED_GSM8K_REVISION,
            cache_root=tmp_path / "empty-cache",
            allow_cache_reuse=False,
            dataset_loader=failing_loader,
            revision_resolver=lambda revision: revision,
            max_download_attempts=4,
            backoff_base_seconds=0,
            sleep=lambda _: None,
        )

    audit = excinfo.value.audit
    assert len(attempts) == 4
    assert audit["failure_mode"] == "NETWORK_RETRY_EXHAUSTED"
    assert audit["retry_attempts"] == 4
    assert audit["declared_revision"] == DECLARED_GSM8K_REVISION
    assert not (tmp_path / "declared" / "gsm8k_openai_main_train_declared.jsonl").exists()


def test_prematerialized_validation_accepts_valid_source_and_rejects_hash_mismatch(
    tmp_path: Path,
) -> None:
    pre_jsonl = tmp_path / "provided.jsonl"
    pre_provenance = tmp_path / "provided_provenance.json"
    output_dir = tmp_path / "declared"
    rows = build_declared_gsm8k_rows([{"question": "What is 7 + 7?", "answer": "#### 14"}])
    write_records(rows, pre_jsonl)
    provenance = build_declared_source_provenance(
        rows=rows,
        output_path=pre_jsonl,
        generated_file_hash=file_sha256(pre_jsonl),
        resolved_revision=DECLARED_GSM8K_REVISION,
        cache_path=None,
        observed_previous_gsm8k_sources=[],
        cache_hit=False,
        retry_attempts=0,
        download_timestamp=None,
    )
    pre_provenance.write_text(json.dumps(provenance, sort_keys=True), encoding="utf-8")

    result = validate_prematerialized_source(
        jsonl_path=pre_jsonl,
        provenance_path=pre_provenance,
        output_dir=output_dir,
        declared_revision=DECLARED_GSM8K_REVISION,
    )

    assert result["status"] == "DECLARED_GSM8K_SOURCE_READY"
    assert Path(result["output_path"]).exists()
    assert Path(result["provenance_path"]).exists()

    bad_provenance = {**provenance, "generated_file_hash": "0" * 64}
    pre_provenance.write_text(json.dumps(bad_provenance, sort_keys=True), encoding="utf-8")
    with pytest.raises(SourcePreparationBlocked) as excinfo:
        validate_prematerialized_source(
            jsonl_path=pre_jsonl,
            provenance_path=pre_provenance,
            output_dir=tmp_path / "bad",
            declared_revision=DECLARED_GSM8K_REVISION,
        )
    assert excinfo.value.audit["failure_mode"] == "PREMATERIALIZED_VALIDATION_FAILED"


def test_source_preparation_rejects_revision_mismatch_and_bad_schema(tmp_path: Path) -> None:
    different_revision = DECLARED_GSM8K_REVISION[:-1] + (
        "0" if DECLARED_GSM8K_REVISION[-1] != "0" else "1"
    )
    with pytest.raises(SourcePreparationBlocked) as excinfo:
        prepare_declared_gsm8k_source(
            output_dir=tmp_path / "declared",
            declared_revision=DECLARED_GSM8K_REVISION,
            cache_root=tmp_path / "empty-cache",
            allow_cache_reuse=False,
            dataset_loader=lambda **_: [{"question": "Q", "answer": "A"}],
            revision_resolver=lambda _: different_revision,
            max_download_attempts=1,
            backoff_base_seconds=0,
            sleep=lambda _: None,
        )
    assert excinfo.value.audit["failure_mode"] == "REVISION_MISMATCH"

    bad_jsonl = tmp_path / "bad.jsonl"
    write_records(
        [
            {
                "dataset": "openai/gsm8k",
                "config": "main",
                "split": "train",
                "source_index": 0,
                "sample_id": "wrong",
                "task_id": "wrong",
                "question": "Q",
                "reference_answer": "A",
                "aliases": [],
                "task_type": "gsm8k",
                "source_row_hash": "0" * 64,
            }
        ],
        bad_jsonl,
    )
    with pytest.raises(ValueError, match="hf_row_index"):
        validate_declared_jsonl_schema(bad_jsonl)


def test_source_preparation_backoff_schedule_matches_contract() -> None:
    assert [backoff_delay_seconds(index, 5) for index in range(1, 5)] == [0, 5, 15, 45]


def test_dense_target_reliability_gate_requires_variance_beyond_binary() -> None:
    rows = []
    for index in range(40):
        rows.append(
            {
                "sample_id": f"gsm8k-{index:05d}",
                "task_type": "gsm8k",
                "utility": (index % 20) / 20,
                "binary_correct": index % 2 == 0,
                "delta_u": 0.1 if index < 12 else 0.0,
            }
        )
        rows.append(
            {
                "sample_id": f"hotpotqa-{index:05d}",
                "task_type": "hotpotqa",
                "utility": (index % 25) / 25,
                "binary_correct": index % 3 == 0,
                "delta_u": 0.2 if index < 16 else 0.0,
            }
        )

    report = build_dense_target_reliability_report(rows)

    assert report["status"] == "V3_DENSE_TARGET_RELIABILITY_PASS"
    assert report["per_task"]["gsm8k"]["gate_pass"] is True
    assert report["per_task"]["hotpotqa"]["gate_pass"] is True
    assert report["per_task"]["gsm8k"]["nonzero_delta_fraction"] >= 0.25
    assert report["per_task"]["hotpotqa"]["nonzero_delta_fraction"] >= 0.35


def test_w_struct_feature_rows_reject_target_side_leakage() -> None:
    clean = [
        {
            "sample_id": "gsm8k-00001",
            "span_index": 0,
            "features": {
                "raw_local_utility": 0.4,
                "structural_necessity": 0.3,
                "raw_structural_interaction": 0.12,
                "redundancy": 0.2,
                "compensation": 0.1,
                "bottleneck_flag": 1,
                "span_type": "verification",
                "relative_position": 0.5,
                "span_length": 12,
                "task_type": "gsm8k",
                "question_difficulty_proxy": 0.4,
            },
            "source_fields_used": [
                "observable_trace",
                "reflection_spans",
                "structural_diagnostics",
                "redundancy_analysis",
            ],
        }
    ]
    leaked = [
        {
            **clean[0],
            "source_fields_used": [*clean[0]["source_fields_used"], "delta_u"],
        }
    ]

    assert validate_w_struct_feature_rows(clean)["status"] == "clean"
    assert validate_w_struct_feature_rows(leaked)["status"] == "target_leaking"


def test_w_struct_stability_gate_handles_sparse_structural_profile() -> None:
    report = build_w_struct_stability_report(
        folds=[
            {
                "raw_local_utility_direction": 1,
                "structural_profile_direction": 1,
                "structural_profile_ci95": [0.01, 0.05],
                "spearman_diff_over_raw": 0.04,
                "brier_improvement_over_base_rate": 0.02,
                "calibration_slope": 1.0,
            },
            {
                "raw_local_utility_direction": 1,
                "structural_profile_direction": 0,
                "structural_profile_ci95": [0.0, 0.04],
                "spearman_diff_over_raw": 0.03,
                "brier_improvement_over_base_rate": 0.01,
                "calibration_slope": 0.9,
            },
            {
                "raw_local_utility_direction": 1,
                "structural_profile_direction": 1,
                "structural_profile_ci95": [0.02, 0.06],
                "spearman_diff_over_raw": 0.05,
                "brier_improvement_over_base_rate": 0.03,
                "calibration_slope": 1.1,
            },
            {
                "raw_local_utility_direction": 1,
                "structural_profile_direction": 0,
                "structural_profile_ci95": [-0.01, 0.03],
                "spearman_diff_over_raw": 0.04,
                "brier_improvement_over_base_rate": 0.02,
                "calibration_slope": 1.2,
            },
            {
                "raw_local_utility_direction": 0,
                "structural_profile_direction": 1,
                "structural_profile_ci95": [-0.01, 0.02],
                "spearman_diff_over_raw": 0.04,
                "brier_improvement_over_base_rate": 0.02,
                "calibration_slope": 1.0,
            },
        ],
        zero_rate_by_task={"gsm8k": 0.7, "hotpotqa": 0.85},
    )

    assert report["gate_pass"] is True
    assert report["sparse_signal_warning"] is True
    assert report["checks"]["structural_profile_positive_ci_folds"] is True


def test_synthetic_real_profile_alignment_reports_sparse_warning() -> None:
    report = build_synthetic_real_profile_alignment_report(
        synthetic_profile={
            "structural_zero_rate": 0.6779,
            "bottleneck_ratio": 0.12,
            "redundancy_density": 0.31,
            "compensation": 0.18,
            "local_utility_alignment": 0.08,
        },
        real_task_profile={
            "structural_zero_rate": 0.82,
            "bottleneck_ratio": 0.09,
            "redundancy_density": 0.27,
            "compensation": 0.15,
            "local_utility_alignment": 0.05,
        },
    )

    assert report["sparse_signal_warning"] is True
    assert report["zero_rate"]["synthetic"] == 0.6779
    assert report["zero_rate"]["real_task"] == 0.82
    assert set(report["profile_comparisons"]) == {
        "zero_rate",
        "bottleneck_ratio",
        "redundancy_density",
        "compensation",
        "local_utility_alignment",
    }
    assert report["profile_comparisons"]["bottleneck_ratio"]["real_task"] == 0.09


def test_v3_decision_tree_separates_global_task_specific_and_downstream_claims() -> None:
    global_report = build_v3_decision_report(
        task_gate_pass={"gsm8k": True, "hotpotqa": True},
        pooled_gate_pass=True,
        paired_improvement_ci95=[0.01, 0.08],
        blockers=[],
        downstream_gate_pass=False,
    )
    task_specific = build_v3_decision_report(
        task_gate_pass={"gsm8k": True, "hotpotqa": False},
        pooled_gate_pass=True,
        paired_improvement_ci95=[0.01, 0.08],
        blockers=[],
        task_blockers={"hotpotqa": []},
        holm_corrected_task_gate_pass={"gsm8k": True, "hotpotqa": False},
        downstream_gate_pass=False,
    )
    task_specific_blocked = build_v3_decision_report(
        task_gate_pass={"gsm8k": True, "hotpotqa": False},
        pooled_gate_pass=True,
        paired_improvement_ci95=[0.01, 0.08],
        blockers=[],
        task_blockers={"hotpotqa": ["schema_transport"]},
        holm_corrected_task_gate_pass={"gsm8k": True, "hotpotqa": False},
        downstream_gate_pass=False,
    )
    blocked = build_v3_decision_report(
        task_gate_pass={"gsm8k": True, "hotpotqa": True},
        pooled_gate_pass=True,
        paired_improvement_ci95=[0.01, 0.08],
        blockers=["leakage"],
        downstream_gate_pass=True,
    )

    assert global_report["status"] == V3_GLOBAL_PASS
    assert global_report["diagnostic_validation_claim_allowed"] is True
    assert global_report["prm_filtering_improvement_claim_allowed"] is False
    assert task_specific["status"] == V3_TASK_SPECIFIC_ONLY
    assert task_specific["global_claim_allowed"] is False
    assert task_specific["downstream_gate_request_allowed"] is False
    assert task_specific_blocked["status"] == "REAL_TASK_V3_VALIDATION_FAIL"
    assert blocked["status"] == "REAL_TASK_V3_VALIDATION_FAIL"
    assert blocked["diagnostic_validation_claim_allowed"] is False


def test_circuit_breaker_uses_consecutive_and_rolling_error_limits() -> None:
    consecutive = build_circuit_breaker_report([{"error_class": "infra_error"} for _ in range(10)])
    rolling = build_circuit_breaker_report(
        [{"error_class": "infra_error"} for _ in range(11)]
        + [{"error_class": "success"} for _ in range(39)]
    )

    assert consecutive["hard_stop"] is True
    assert consecutive["reason"] == "consecutive_infra_errors"
    assert rolling["hard_stop"] is True
    assert rolling["reason"] == "rolling_infra_error_fraction"


def test_chat_completions_adapter_normalizes_fake_response() -> None:
    calls = []

    def fake_transport(endpoint, payload, headers, timeout):
        calls.append((endpoint, payload, headers, timeout))
        return {
            "id": "chatcmpl-test",
            "model": "deepseek-v4-flash",
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    adapter = ChatCompletionsAdapter(api_key="test-key", transport=fake_transport)
    result = adapter.create_trace(
        prompt="Return JSON",
        config={
            "model": {"temperature": 0, "max_output_tokens": 16},
            "api": {"request_timeout_seconds": 5},
        },
        model_name="deepseek-v4-flash",
    )

    assert calls[0][0] == DEFAULT_CHAT_COMPLETIONS_ENDPOINT
    assert calls[0][1]["response_format"] == {"type": "json_object"}
    assert calls[0][2]["Authorization"] == "Bearer test-key"
    assert result.output_text == '{"ok": true}'
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 5}
    assert result.response_id == "chatcmpl-test"
    assert result.request_metadata["endpoint"] == DEFAULT_CHAT_COMPLETIONS_ENDPOINT


def test_smoke_calibrated_cost_forecast_and_locked_checkpoint_freeze_on_cost_risk() -> None:
    forecast = build_smoke_calibrated_cost_forecast(
        smoke_attempts=[
            {"usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
            {"usage": {"prompt_tokens": 2000, "completion_tokens": 1000}},
            {"usage": {"prompt_tokens": 4000, "completion_tokens": 2000}},
        ],
        planned_request_counts={"locked_validation": 52000},
        route_cost_cap_usd=5000.0,
    )
    checkpoint = build_locked_cost_checkpoint(
        requests_completed=10000,
        cost_used_usd=1200.0,
        planned_locked_requests=52000,
        locked_stage_cost_cap_usd=2500.0,
    )

    assert forecast["token_quantiles"]["prompt_tokens"]["p95"] >= 2000
    assert checkpoint["status"] == "cost-exceeded partial locked"
    assert checkpoint["pass_claim_allowed"] is False


def test_real_task_v3_manifest_script_rejects_execution_scope_drift() -> None:
    config = load_pilot_config(Path("configs/real_task_v3_validation.yaml"))

    assert (
        _assert_current_task_boundary(config, task_scope=REAL_TASK_V3_PREREGISTRATION_ONLY) is None
    )

    bad = dict(config)
    bad["execution_boundary"] = {
        **config["execution_boundary"],
        "api_execution_allowed": True,
    }

    try:
        _assert_current_task_boundary(bad, task_scope=REAL_TASK_V3_PREREGISTRATION_ONLY)
    except RuntimeError as exc:
        assert "api_execution_allowed" in str(exc)
    else:
        raise AssertionError("expected execution boundary drift to be rejected")


def _v3_smoke_manifest_rows(per_task: int = 100) -> list[dict[str, Any]]:
    rows = []
    for task_type in ("gsm8k", "hotpotqa"):
        for index in range(per_task):
            rows.append(
                {
                    "sample_id": f"{task_type}-{index:05d}",
                    "task_id": f"{task_type}-task-{index:05d}",
                    "task_type": task_type,
                    "question": f"{task_type} question {index}",
                    "reference_answer": "#### 5" if task_type == "gsm8k" else "Entity",
                    "aliases": [] if task_type == "gsm8k" else ["Entity alias"],
                }
            )
    return rows


def _v3_trace_record(
    sample_id: str, *, span_count: int, task_type: str = "gsm8k"
) -> dict[str, Any]:
    trace_parts = ["Initial observable work without final answer."]
    for span_index in range(span_count):
        trace_parts.append(
            f'<reflection type="verification">Visible check {span_index}</reflection>'
        )
    trace_parts.append("Final Answer: 5")
    trace = "\n".join(trace_parts)
    return {
        "sample_id": sample_id,
        "task_id": sample_id,
        "task_type": task_type,
        "question": "What is 2 + 3?",
        "observable_trace": trace,
        "reflection_spans": extract_reflection_spans(trace),
        "final_answer": "5",
        "reference_answer": "#### 5",
        "aliases": [],
    }


def test_v3_smoke_rejects_underpowered_max_samples_without_diagnostic_flag() -> None:
    manifest = _v3_smoke_manifest_rows(per_task=100)

    with pytest.raises(RuntimeError, match="underpowered diagnostic"):
        v3_smoke_runner.select_smoke_manifest_rows(
            manifest,
            max_samples=50,
            allow_underpowered_diagnostic=False,
        )


def test_v3_smoke_underpowered_diagnostic_uses_stratified_round_robin_selection() -> None:
    manifest = _v3_smoke_manifest_rows(per_task=100)

    selected, selection_report = v3_smoke_runner.select_smoke_manifest_rows(
        manifest,
        max_samples=50,
        allow_underpowered_diagnostic=True,
    )

    assert len(selected) == 50
    assert selection_report["underpowered_diagnostic"] is True
    assert selection_report["selected_count_by_task"] == {"gsm8k": 25, "hotpotqa": 25}
    assert [row["task_type"] for row in selected[:4]] == [
        "gsm8k",
        "hotpotqa",
        "gsm8k",
        "hotpotqa",
    ]


def test_v3_prompt_requires_at_least_three_reflections_and_hotpotqa_examples() -> None:
    prompt = Path("prompts/real_task_reflection_generation.txt").read_text(encoding="utf-8")

    assert "at least 3 reflection blocks" in prompt
    assert "exactly 3" not in prompt.lower()
    assert "retrieval_verification" in prompt
    assert "reasoning_chain_check" in prompt
    assert "answer_consistency" in prompt


def test_v3_original_trace_requires_three_reflection_spans_before_replay() -> None:
    too_sparse = _v3_trace_record("gsm8k-00001", span_count=2)
    valid = _v3_trace_record("gsm8k-00002", span_count=3)

    assert v3_smoke_runner.original_trace_validation_errors(too_sparse) == [
        "reflection_spans: at least 3 reflection blocks required for V3 smoke"
    ]
    assert v3_smoke_runner.original_trace_validation_errors(valid) == []


def test_v3_prefix_builder_scores_first_three_spans_only_and_records_delete_contract() -> None:
    record = _v3_trace_record("gsm8k-00003", span_count=4)

    prefixes = v3_smoke_runner.build_v3_smoke_prefixes([record])

    assert [prefix["span_index"] for prefix in prefixes] == [0, 1, 2]
    assert all(prefix["intervention_type"] == "DELETE" for prefix in prefixes)
    assert all(
        prefix["intervention_implementation"] == "length_preserving_masked_delete"
        for prefix in prefixes
    )
    assert all("[REASONING_MASK]" in prefix["observable_prefix"] for prefix in prefixes)
    assert all("Visible check 3" not in prefix["observable_prefix"] for prefix in prefixes)


def test_v3_smoke_report_uses_delta_epsilon_and_requests_v3_1_replace_after_sparse_delete() -> None:
    records = [
        _v3_trace_record("gsm8k-00001", span_count=3, task_type="gsm8k"),
        _v3_trace_record("hotpotqa-00001", span_count=3, task_type="hotpotqa"),
    ]
    prefixes = v3_smoke_runner.build_v3_smoke_prefixes(records)
    delta_rows = [
        {"sample_id": "gsm8k-00001", "task_type": "gsm8k", "delta_u": 1e-19},
        {"sample_id": "hotpotqa-00001", "task_type": "hotpotqa", "delta_u": 0.0},
    ]

    report = v3_smoke_runner.build_smoke_report_for_test(
        original_records=[*_v3_smoke_manifest_rows(per_task=100)],
        original_attempts=[
            {"sample_id": row["sample_id"], "task_type": row["task_type"], "valid": True}
            for row in _v3_smoke_manifest_rows(per_task=100)
        ],
        replay_prefixes=prefixes * 100,
        replay_results=[{"status": "success"} for _ in range(600)],
        replay_attempts=[{"valid": True} for _ in range(600)],
        delta_rows=delta_rows,
        cost_usd=0.0,
        approved_budget_usd=50.0,
        selection_report={"underpowered_diagnostic": False},
    )

    assert report["nonzero_delta_gsm8k"] == 0
    assert report["next_allowed_step"] == "REQUEST_V3_1_REPLACE_PREREGISTRATION"
    assert report["intervention_type"] == "DELETE"
    assert report["v3_1_replace_preregistration"]["replace_evidence_mixed_with_v3_delete"] is False


def test_v3_delta_rows_do_not_execute_replace_intervention() -> None:
    original = _v3_trace_record("gsm8k-00004", span_count=3)
    replay = {
        "sample_id": "gsm8k-00004",
        "span_index": 0,
        "repeat_index": 0,
        "task_type": "gsm8k",
        "reference_answer": "#### 5",
        "aliases": [],
        "final_answer": "4",
        "status": "success",
    }

    rows = v3_smoke_runner.compute_v3_delta_rows_for_test([original], [replay])

    assert rows[0]["intervention_type"] == "DELETE"
    assert rows[0]["intervention_implementation"] == "length_preserving_masked_delete"
    assert "REPLACE" not in json.dumps(rows)


def test_v3_smoke_resume_guard_rejects_missing_or_mismatched_metadata(tmp_path: Path) -> None:
    metadata = {
        "prompt_sha256": "prompt-a",
        "manifest_sha256": "manifest-a",
        "intervention_contract": v3_smoke_runner.V3_INTERVENTION_CONTRACT,
    }
    (tmp_path / "smoke_original_traces.jsonl").write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="smoke_run_metadata.json"):
        v3_smoke_runner.assert_smoke_resume_allowed(tmp_path, metadata)

    (tmp_path / "smoke_run_metadata.json").write_text(
        json.dumps({**metadata, "prompt_sha256": "prompt-b"}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="does not match"):
        v3_smoke_runner.assert_smoke_resume_allowed(tmp_path, metadata)


def test_governance_diagnostic_report_contains_three_claim_safe_findings() -> None:
    report = build_governance_diagnostic_report(_sample_blocked_manifest_audit())

    assert report["status"] == "GOVERNANCE_DIAGNOSTIC_COMPLETE"
    assert report["blocked_stage"] == "MANIFEST_GATE"
    assert report["failure_mode"] == "BLOCKED_OVERLAP_DETECTED"
    findings = {finding["finding_id"]: finding for finding in report["diagnostic_findings"]}
    assert set(findings) == {"F1", "F2", "F3"}
    assert findings["F1"]["severity"] == "TOTAL_COLLAPSE"
    assert findings["F2"]["severity"] == "TOTAL_EXHAUSTION"
    assert findings["F3"]["severity"] == "COMBINATORIAL_OVERFLOW"
    assert report["claim_safe_boundary_evidence"] is True
    assert report["row_level_intersections_recoverable_from_audit"] is False


def test_governance_diagnostic_f1_records_empty_alias_collision_hash() -> None:
    report = build_governance_diagnostic_report(_sample_blocked_manifest_audit())
    f1 = {finding["finding_id"]: finding for finding in report["diagnostic_findings"]}["F1"]

    assert f1["collision_hash"] == EMPTY_STRING_HASH
    assert f1["hash_preimage"] == "SHA-256 of empty string"
    assert f1["affected_dataset"] == "gsm8k"


def test_governance_diagnostic_f3_exclusion_rate_math() -> None:
    audit = _sample_blocked_manifest_audit()
    report = build_governance_diagnostic_report(audit)
    f3 = {finding["finding_id"]: finding for finding in report["diagnostic_findings"]}["F3"]

    assert f3["total_candidates"] == 10
    assert f3["total_excluded"] == 10
    assert f3["exclusion_rate"] == pytest.approx(1.0)
    assert f3["per_key_marginal_contribution"]["non_empty_alias_hash"] == 10
    assert f3["per_key_marginal_contribution"]["reference_answer_hash"] == 3


def test_governance_diagnostic_outputs_final_status_audit(tmp_path: Path) -> None:
    audit_path = tmp_path / "manifest_overlap_audit.json"
    output_dir = tmp_path / "real_task_v3"
    _write_json(audit_path, _sample_blocked_manifest_audit())

    result = write_governance_diagnostic_outputs(
        audit_path=audit_path,
        output_dir=output_dir,
    )

    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    final_status = json.loads(Path(result["final_status_path"]).read_text(encoding="utf-8"))
    assert report["status"] == "GOVERNANCE_DIAGNOSTIC_COMPLETE"
    assert final_status["status"] == "REAL_TASK_V3_DATA_SCARCITY_BLOCKED"
    assert final_status["blocked_stage"] == "MANIFEST_GATE"
    assert final_status["failure_mode"] == "BLOCKED_OVERLAP_DETECTED"
    assert final_status["diagnostic_finding_ids"] == ["F1", "F2", "F3"]
    assert final_status["claim_registry_impact"].startswith("PILOT_BLOCKED remains")


def test_governance_diagnostic_plot_generation(tmp_path: Path) -> None:
    audit_path = tmp_path / "manifest_overlap_audit.json"
    output_path = tmp_path / "governance_diagnostic_upset.png"
    _write_json(audit_path, _sample_blocked_manifest_audit())

    result = build_governance_diagnostic_plot(
        audit_path=audit_path,
        output_path=output_path,
    )

    assert result["status"] == "GOVERNANCE_DIAGNOSTIC_PLOT_WRITTEN"
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_real_task_v3_claim_registry_final_status_section_is_claim_safe() -> None:
    text = Path("paper/claim_registry.md").read_text(encoding="utf-8")
    assert "## Real-Task v3/v3.1 Final Status (2026-06-08)" in text
    section = text.split("## Real-Task v3/v3.1 Final Status (2026-06-08)", maxsplit=1)[1]

    assert "`PILOT_BLOCKED`" in section
    assert "v3 and v3.1 are negative preliminary tests only" in section
    assert "threshold retuning" in section
    assert "downstream PRM/filtering gain claims" in section
    assert "REAL_TASK_V3_VALIDATION_PASS" not in section
    assert "PRM_FILTERING_IMPROVEMENT_PASS" not in section
