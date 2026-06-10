"""Generate conservative governance diagnostics from the frozen v3 manifest audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_AUDIT_PATH = Path("outputs") / "real_task_v3" / "manifest_overlap_audit.json"
DEFAULT_OUTPUT_DIR = Path("outputs") / "real_task_v3"
EMPTY_STRING_SHA256 = hashlib.sha256(b"").hexdigest()
SIX_KEYS = (
    "sample_id",
    "task_id",
    "dataset_config_split_source_index",
    "normalized_question_hash",
    "reference_answer_hash",
    "non_empty_alias_hash",
)
DECLARED_GSM8K_TRAIN_ROWS = 7473


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate real_task_v3 governance diagnostic artifacts."
    )
    parser.add_argument("--audit-path", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = write_governance_diagnostic_outputs(
        audit_path=args.audit_path,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, sort_keys=True))


def write_governance_diagnostic_outputs(
    *,
    audit_path: Path = DEFAULT_AUDIT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, str]:
    audit = _read_json(audit_path)
    report = build_governance_diagnostic_report(audit)
    final_status = build_final_status_audit(audit, report)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "governance_diagnostic_report.json"
    final_status_path = output_dir / "real_task_v3_final_status.json"
    _write_json(report_path, report)
    _write_json(final_status_path, final_status)
    return {
        "status": "GOVERNANCE_DIAGNOSTIC_COMPLETE",
        "report_path": str(report_path),
        "final_status_path": str(final_status_path),
    }


def build_governance_diagnostic_report(audit: Mapping[str, Any]) -> dict[str, Any]:
    total_excluded = int(audit.get("total_excluded_rows", 0) or 0)
    post_dedup = _mapping(audit.get("post_dedup_counts"))
    total_candidates = total_excluded + sum(int(value or 0) for value in post_dedup.values())
    per_key = per_key_marginal_contribution(audit)
    detected_hotpot_sources = _detected_hotpotqa_consumption_sources(audit)

    return {
        "status": "GOVERNANCE_DIAGNOSTIC_COMPLETE",
        "blocked_stage": "MANIFEST_GATE",
        "failure_mode": str(audit.get("status") or ""),
        "diagnostic_findings": [
            {
                "finding_id": "F1",
                "title": "Empty-Alias Hash Collision",
                "description": "non_empty_alias_hash key produces identical SHA-256 for rows when aliases=[]",
                "affected_dataset": "gsm8k",
                "affected_rows": DECLARED_GSM8K_TRAIN_ROWS,
                "observed_audit_key_count": int(per_key.get("non_empty_alias_hash", 0)),
                "collision_hash": EMPTY_STRING_SHA256,
                "hash_preimage": "SHA-256 of empty string",
                "severity": "TOTAL_COLLAPSE",
                "implication": (
                    "Deduplication key design must be dataset-aware; universal schemas "
                    "assume structural homogeneity that does not hold"
                ),
            },
            {
                "finding_id": "F2",
                "title": "Split Consumption Under Revision Locking",
                "description": "HotpotQA validation split is already represented in prior artifacts",
                "affected_dataset": "hotpotqa",
                "consumed_split": "distractor:validation",
                "overlap_sources": detected_hotpot_sources,
                "severity": "TOTAL_EXHAUSTION",
                "implication": (
                    "Fresh-source declarations must include split-level consumption audit, "
                    "not just dataset-level provenance"
                ),
            },
            {
                "finding_id": "F3",
                "title": "Cumulative Exclusion Under OR-Logic",
                "description": "Six-key OR-composition approaches total exclusion faster than intuition suggests",
                "total_candidates": total_candidates,
                "total_excluded": total_excluded,
                "exclusion_rate": _safe_ratio(total_excluded, total_candidates),
                "per_key_marginal_contribution": per_key,
                "marginal_contribution_mode": "max_count_across_exclusion_sources_from_frozen_audit",
                "severity": "COMBINATORIAL_OVERFLOW",
                "implication": (
                    "Deduplication logic should report per-key marginal contribution, "
                    "not just aggregate overlap"
                ),
            },
        ],
        "finding_overlap_analysis": {
            "mode": "audit_limited",
            "row_level_intersections_recoverable": False,
            "F1_F2_overlap": (
                "Exact row-level overlap is not recoverable from the frozen manifest audit; "
                "the audit stores aggregate per-source counts and bounded examples."
            ),
            "F1_F3_overlap": "F1 is a dominant contributor to F3 under the audit count summary.",
            "F2_F3_overlap": "F2 contributes to F3 through repeated HotpotQA validation split key matches.",
        },
        "recommendations_for_future_work": [
            "Dataset-aware deduplication key schemas",
            "Split-level consumption tracking in provenance",
            "Marginal contribution reporting for multi-key exclusion",
        ],
        "claim_safe_boundary_evidence": True,
        "row_level_intersections_recoverable_from_audit": False,
        "timestamp": _now_iso(),
    }


def build_final_status_audit(
    audit: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    post_dedup = _mapping(audit.get("post_dedup_counts"))
    return {
        "status": "REAL_TASK_V3_DATA_SCARCITY_BLOCKED",
        "blocked_stage": "MANIFEST_GATE",
        "failure_mode": str(audit.get("status") or ""),
        "root_cause": "strict_six_key_deduplication_exhausts_all_available_data",
        "contributing_factors": [
            "GSM8K non_empty_alias_hash design flaw: empty aliases produce identical hash for all rows",
            "HotpotQA validation split fully consumed by prior v2/v2.1/v2.2 artifacts",
            "Six-key OR logic: any single key match triggers exclusion, cumulative effect is total",
        ],
        "diagnostic_finding_ids": [
            finding["finding_id"]
            for finding in report.get("diagnostic_findings", [])
            if isinstance(finding, Mapping)
        ],
        "gsm8k_post_dedup": int(post_dedup.get("gsm8k", 0) or 0),
        "hotpotqa_post_dedup": int(post_dedup.get("hotpotqa", 0) or 0),
        "total_excluded_rows": int(audit.get("total_excluded_rows", 0) or 0),
        "historical_consumption": {
            "pilot": "detected_hotpotqa_validation_plus_alias_collision",
            "v2": "detected_hotpotqa_validation_plus_alias_collision",
            "v2.1": "detected_hotpotqa_validation_plus_gsm8k_train_alias_collision",
            "v2.2": "detected_hotpotqa_validation_plus_gsm8k_train_alias_collision",
        },
        "claim_registry_impact": "PILOT_BLOCKED remains; no real-task validation data generated",
        "paper_boundary_evidence": (
            "real-task data scarcity under strict deduplication and source-verification requirements"
        ),
        "methodological_contribution": (
            "governance diagnostics reveal hidden data-availability ceiling in reproducibility frameworks"
        ),
        "timestamp": _now_iso(),
    }


def per_key_marginal_contribution(audit: Mapping[str, Any]) -> dict[str, int]:
    overlap_counts = _mapping(audit.get("overlap_counts"))
    result: dict[str, int] = {}
    for key in SIX_KEYS:
        result[key] = max(
            (
                int(_mapping(source_counts).get(key, 0) or 0)
                for source_counts in overlap_counts.values()
            ),
            default=0,
        )
    return result


def per_key_source_count_sum(audit: Mapping[str, Any]) -> dict[str, int]:
    overlap_counts = _mapping(audit.get("overlap_counts"))
    return {
        key: sum(
            int(_mapping(source_counts).get(key, 0) or 0)
            for source_counts in overlap_counts.values()
        )
        for key in SIX_KEYS
    }


def _detected_hotpotqa_consumption_sources(audit: Mapping[str, Any]) -> list[str]:
    overlap_counts = _mapping(audit.get("overlap_counts"))
    sources = []
    for source, counts in overlap_counts.items():
        mapped = _mapping(counts)
        if any(
            int(mapped.get(key, 0) or 0) > 0
            for key in (
                "sample_id",
                "task_id",
                "dataset_config_split_source_index",
                "normalized_question_hash",
            )
        ):
            sources.append(str(source))
    return sources


def _safe_ratio(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    main()
