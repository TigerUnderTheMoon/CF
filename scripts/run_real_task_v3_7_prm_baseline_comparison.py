"""v3.7 offline PRM800K contamination audit for frozen PRM baseline comparison.

This route does not run PRM inference and does not validate PRM training,
GSM8K/HotpotQA replay, or causal claims.  It materializes a bidirectional
training-overlap audit for future frozen PRM baseline comparisons.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "real_task_v3_7_prm_baseline_comparison.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "real_task_v3_7_prm_baseline_comparison"

OVERLAP_OR_UNKNOWN_VALUES = {
    "known_yes",
    "unknown",
    "known_yes_or_unclear_by_public_sources",
    "unknown_by_public_sources",
}
SOURCE_BACKED_EVIDENCE_TYPES = {"model_card", "paper", "official_repo", "dataset_card"}
PRIMARY_EVIDENCE_STRENGTHS = {"primary"}
CSV_COLUMNS = [
    "artifact_name",
    "artifact_type",
    "hf_or_repo_id",
    "uses_prm800k",
    "usage_mode",
    "source_url",
    "evidence_strength",
    "notes",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--stage",
        choices=["fixture_smoke", "contamination_audit", "decision", "all"],
        default="all",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config(args.config)
    output_dir = args.output_dir or PROJECT_ROOT / config["outputs"]["root"]
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.stage == "fixture_smoke":
        audit = run_contamination_audit(config, output_dir)
        print(json.dumps({"status": audit["status"], "output_dir": str(output_dir)}, sort_keys=True))
        return

    audit: dict[str, Any] | None = None
    if args.stage in {"contamination_audit", "all"}:
        audit = run_contamination_audit(config, output_dir)
    if args.stage in {"decision", "all"}:
        if audit is None:
            audit_path = output_dir / config["outputs"]["training_overlap_audit"]
            audit = read_json(audit_path)
        decision = run_decision(config, output_dir, audit)
        print(
            json.dumps(
                {
                    "status": decision["status"],
                    "claim_boundary": decision["claim_boundary"],
                    "decision_report": str(output_dir / config["outputs"]["decision_report"]),
                },
                sort_keys=True,
            )
        )


def load_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Config is not a mapping: {path}")
    return value


def run_contamination_audit(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    started = time.time()
    audit = build_training_overlap_audit(config)
    audit["elapsed_seconds"] = round(time.time() - started, 3)
    write_json(output_dir / config["outputs"]["training_overlap_audit"], audit)
    write_reverse_usage_csv(
        output_dir / config["outputs"]["reverse_usage_scan_csv"],
        audit["reverse_prm800k_usage_scan"],
    )
    return audit


def run_decision(
    config: Mapping[str, Any],
    output_dir: Path,
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    decision = build_decision_report(config, audit)
    write_json(output_dir / config["outputs"]["decision_report"], decision)
    write_summary(output_dir / config["outputs"]["summary"], decision, audit)
    return decision


def build_training_overlap_audit(config: Mapping[str, Any]) -> dict[str, Any]:
    target = config["data"]["target_dataset"]
    provenance = config["data"]["target_dataset_provenance"]
    candidates = list(config.get("candidate_prm_models", []))
    reverse_scan = list(config.get("reverse_prm800k_usage_scan", []))
    if not reverse_scan:
        raise ValueError("training_overlap_audit requires reverse_prm800k_usage_scan")
    if not candidates:
        raise ValueError("training_overlap_audit requires candidate_prm_models")

    validate_source_backing(candidates, row_name_key="model_name")
    validate_source_backing(reverse_scan, row_name_key="public_model_or_dataset")

    candidate_risky = risky_usage_values(candidates)
    reverse_risky = risky_usage_values(reverse_scan)
    overlap_or_unknown = bool(candidate_risky or reverse_risky)
    claim_policy = config["claim_policy"]
    if overlap_or_unknown and claim_policy.get("external_generalization_claim_allowed") is True:
        raise ValueError("overlap or unknown overlap blocks external generalization claims")

    decision = {
        "external_generalization_claim_allowed": bool(
            claim_policy.get("external_generalization_claim_allowed", False)
        )
        and not overlap_or_unknown,
        "in_distribution_prm_baseline_context_allowed": bool(
            claim_policy.get("in_distribution_prm_baseline_context_allowed", True)
        )
        or overlap_or_unknown,
        "overlap_or_unknown_detected": overlap_or_unknown,
        "blocking_usage_values": sorted(candidate_risky | reverse_risky),
    }
    if overlap_or_unknown:
        decision["external_generalization_claim_allowed"] = False
        decision["in_distribution_prm_baseline_context_allowed"] = True

    return {
        "status": "pass_with_in_distribution_limitation" if overlap_or_unknown else "pass",
        "route_id": config["route"]["id"],
        "target_dataset": target,
        "target_dataset_provenance": provenance,
        "oracle_label_policy": config["data"]["oracle_label_policy"],
        "candidate_prm_models": candidates,
        "reverse_prm800k_usage_scan": reverse_scan,
        "secondary_context_sources": list(config.get("secondary_context_sources", [])),
        "decision": decision,
        "claim_boundary": "in_distribution_prm_baseline_context_only",
        "api_calls": 0,
        "estimated_api_cost_usd": 0.0,
    }


def validate_source_backing(rows: Sequence[Mapping[str, Any]], *, row_name_key: str) -> None:
    for row in rows:
        name = str(row.get(row_name_key, "<unknown>"))
        usage = str(row.get("uses_prm800k", ""))
        evidence_type = str(row.get("evidence_type", ""))
        evidence_strength = str(row.get("evidence_strength", ""))
        source_url = str(row.get("source_url", "")).strip()

        if usage == "known_no":
            if not source_url or evidence_strength not in PRIMARY_EVIDENCE_STRENGTHS:
                raise ValueError(f"known_no PRM800K usage requires primary-source URL: {name}")
        if evidence_strength == "secondary_context":
            continue
        if evidence_type not in SOURCE_BACKED_EVIDENCE_TYPES:
            raise ValueError(f"Unsupported evidence_type for {name}: {evidence_type}")
        if not source_url:
            raise ValueError(f"Missing source_url for {name}")


def risky_usage_values(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(row.get("uses_prm800k", ""))
        for row in rows
        if str(row.get("uses_prm800k", "")) in OVERLAP_OR_UNKNOWN_VALUES
    }


def build_decision_report(config: Mapping[str, Any], audit: Mapping[str, Any]) -> dict[str, Any]:
    audit_decision = audit["decision"]
    external_allowed = bool(audit_decision["external_generalization_claim_allowed"])
    in_distribution_allowed = bool(audit_decision["in_distribution_prm_baseline_context_allowed"])
    return {
        "status": "pass_with_in_distribution_limitation" if in_distribution_allowed else "fail",
        "route_id": config["route"]["id"],
        "source_route_id": config["source_route"]["id"],
        "training_overlap_audit_status": audit["status"],
        "claim_permissions": {
            "M_STEP_RANKING": False,
            "M_BASELINE_COMPARISON": False,
            "M_BASELINE_COMPARISON_CONTEXT_ONLY": in_distribution_allowed,
            "in_distribution_prm_baseline_context_allowed": in_distribution_allowed,
            "external_generalization_claim_allowed": external_allowed,
            "F_REAL_TASK_SC_FMA": False,
            "F_PRM_TRAINING": False,
            "deterministic_replay_claim": False,
            "causal_identification_claim": False,
        },
        "required_claim_text": config["claim_policy"]["required_claim_text"],
        "forbidden_claims": config["claim_policy"]["forbidden_claims"],
        "next_allowed_step": (
            "REPORT_IN_DISTRIBUTION_PRM_BASELINE_CONTEXT_ONLY"
            if in_distribution_allowed
            else "FREEZE_V3_7_AUDIT_AS_FAILED_AND_DO_NOT_UPDATE_BASELINE_CLAIM"
        ),
        "claim_boundary": "in_distribution_prm_baseline_context_only",
        "api_calls": 0,
        "estimated_api_cost_usd": 0.0,
    }


def write_reverse_usage_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "artifact_name": row.get("public_model_or_dataset", ""),
                    "artifact_type": row.get("artifact_type", ""),
                    "hf_or_repo_id": row.get("hf_or_repo_id", ""),
                    "uses_prm800k": row.get("uses_prm800k", ""),
                    "usage_mode": row.get("usage_mode", ""),
                    "source_url": row.get("source_url", ""),
                    "evidence_strength": row.get("evidence_strength", ""),
                    "notes": row.get("notes", ""),
                }
            )


def write_summary(path: Path, decision: Mapping[str, Any], audit: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# real_task_v3_7_prm_baseline_comparison Summary",
        "",
        f"- Status: `{decision['status']}`",
        f"- Route: `{decision['route_id']}`",
        f"- Target dataset: `{audit['target_dataset']}`",
        f"- Claim boundary: `{decision['claim_boundary']}`",
        "- API calls: `0`",
        "- Estimated API cost USD: `0.0`",
        "",
        "Required claim text:",
        "",
        f"> {decision['required_claim_text']}",
        "",
        "Forbidden claim upgrades remain disabled for PRM training, GSM8K/HotpotQA replay, "
        "external PRM generalization, and causal identification.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
