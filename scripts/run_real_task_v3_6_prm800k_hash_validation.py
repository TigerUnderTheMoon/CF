"""Hash-stratified v3.6 PRM800K real-data validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_real_task_v3_5_prm800k_validation import (  # noqa: E402
    SOURCE_KIND,
    build_decision_report,
    build_samples,
    compute_stability,
    count_steps,
    evaluate_locked_samples,
    fit_w_struct_model,
    leakage_audit,
    load_config,
    locked_gates,
    read_json,
    run_fixture_smoke,
    sample_manifest_rows,
    selected_rows_hash,
    stream_prm800k_rows,
    write_json,
    write_jsonl,
)

DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "real_task_v3_6_prm800k_hash_validation.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "real_task_v3_6_prm800k_hash"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=["fixture_smoke", "all", "decision"], default="all")
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.stage == "fixture_smoke":
        output_dir = args.output_dir or DEFAULT_OUTPUT_ROOT
        report = run_fixture_smoke(output_dir)
        print(json.dumps({"status": report["status"], "output_dir": str(output_dir)}, sort_keys=True))
        return

    config = load_config(args.config)
    output_dir = args.output_dir or PROJECT_ROOT / config["outputs"]["root"]
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.stage == "all":
        decision = run_all(config, output_dir)
    else:
        decision = run_decision(config, output_dir)
    print(
        json.dumps(
            {
                "status": decision["status"],
                "next_allowed_step": decision["next_allowed_step"],
                "decision_report": str(output_dir / config["outputs"]["decision_report"]),
            },
            sort_keys=True,
        )
    )


def run_all(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    started = time.time()
    source = config["data"]["source"]
    pool = config["data"]["pool"]
    rows = stream_prm800k_rows(
        source["url"],
        start_row=int(pool["start_row"]),
        row_count=int(pool["row_count"]),
    )
    samples = build_samples(rows, split_name="pool", row_start=int(pool["start_row"]))
    dev_samples, locked_samples = split_samples(samples, config["data"]["split_strategy"])
    write_split_artifacts(config, output_dir, rows, samples, dev_samples, locked_samples, started)

    dev_report = run_dev_from_samples(config, output_dir, dev_samples, rows)
    locked_report = run_locked_from_samples(config, output_dir, locked_samples, rows)
    decision = route_decision_report(
        build_decision_report(dev_report=dev_report, locked_report=locked_report),
        route_id=str(config["route"]["id"]),
    )
    decision["config"] = {
        "data": config["data"],
        "validation_gates": config["validation_gates"],
        "claim_policy": config["claim_policy"],
    }
    write_json(output_dir / config["outputs"]["decision_report"], decision)
    return decision


def run_dev_from_samples(
    config: Mapping[str, Any],
    output_dir: Path,
    dev_samples: Sequence[Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    gates = config["validation_gates"]["dev"]
    model = fit_w_struct_model(dev_samples, ridge_lambda=float(config["model"]["ridge_lambda"]))
    stability = compute_stability(dev_samples, ridge_lambda=float(config["model"]["ridge_lambda"]))
    leak = leakage_audit()
    report = {
        "status": "pass",
        "route_id": config["route"]["id"],
        "source_kind": SOURCE_KIND,
        "n_source_rows": len(rows),
        "n_samples": len(dev_samples),
        "n_steps": count_steps(dev_samples),
        "selected_rows_sha256": selected_rows_hash(rows),
        "leakage_audit": leak,
        "stability": stability,
        "gates": {
            "dev_min_samples": {
                "threshold": int(gates["min_samples"]),
                "observed": len(dev_samples),
                "pass": len(dev_samples) >= int(gates["min_samples"]),
            },
            "dev_min_steps": {
                "threshold": int(gates["min_steps"]),
                "observed": count_steps(dev_samples),
                "pass": count_steps(dev_samples) >= int(gates["min_steps"]),
            },
            "leakage_audit": {"pass": leak["pass"]},
            "stability": {"pass": stability["pass"]},
        },
        "claim_boundary": "dev_calibration_only",
    }
    report["status"] = "pass" if all(gate["pass"] for gate in report["gates"].values()) else "fail"
    write_json(output_dir / config["outputs"]["dev_model"], model)
    write_json(output_dir / config["outputs"]["dev_report"], report)
    write_jsonl(output_dir / "dev_sample_manifest.jsonl", sample_manifest_rows(dev_samples))
    return report


def run_locked_from_samples(
    config: Mapping[str, Any],
    output_dir: Path,
    locked_samples: Sequence[Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    model = read_json(output_dir / config["outputs"]["dev_model"])
    metrics = evaluate_locked_samples(
        locked_samples,
        model,
        bootstrap_samples=int(config["validation_gates"]["locked"]["bootstrap_samples"]),
    )
    gates = locked_gates(metrics, config["validation_gates"]["locked"])
    report = {
        "status": "pass" if all(gate["pass"] for gate in gates.values()) else "fail",
        "route_id": config["route"]["id"],
        "source_kind": SOURCE_KIND,
        "n_source_rows": len(rows),
        "n_samples": len(locked_samples),
        "n_steps": count_steps(locked_samples),
        "selected_rows_sha256": selected_rows_hash(rows),
        "metrics": metrics,
        "gates": gates,
        "claim_boundary": "locked_real_prm800k_hash_step_label_validation",
        "api_calls": 0,
        "estimated_api_cost_usd": 0.0,
    }
    write_json(output_dir / config["outputs"]["locked_report"], report)
    write_jsonl(output_dir / "locked_sample_manifest.jsonl", sample_manifest_rows(locked_samples))
    return report


def run_decision(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    dev_report = read_json(output_dir / config["outputs"]["dev_report"])
    locked_report = read_json(output_dir / config["outputs"]["locked_report"])
    decision = route_decision_report(
        build_decision_report(dev_report=dev_report, locked_report=locked_report),
        route_id=str(config["route"]["id"]),
    )
    write_json(output_dir / config["outputs"]["decision_report"], decision)
    return decision


def write_split_artifacts(
    config: Mapping[str, Any],
    output_dir: Path,
    rows: Sequence[Mapping[str, Any]],
    samples: Sequence[Any],
    dev_samples: Sequence[Any],
    locked_samples: Sequence[Any],
    started: float,
) -> None:
    report = {
        "status": "pass",
        "route_id": config["route"]["id"],
        "source_kind": SOURCE_KIND,
        "n_source_rows": len(rows),
        "n_eligible_samples": len(samples),
        "n_eligible_steps": count_steps(samples),
        "n_dev_samples": len(dev_samples),
        "n_dev_steps": count_steps(dev_samples),
        "n_locked_samples": len(locked_samples),
        "n_locked_steps": count_steps(locked_samples),
        "selected_rows_sha256": selected_rows_hash(rows),
        "split_strategy": config["data"]["split_strategy"],
        "elapsed_seconds": round(time.time() - started, 3),
        "api_calls": 0,
        "estimated_api_cost_usd": 0.0,
    }
    write_json(output_dir / config["outputs"]["split_report"], report)


def split_samples(samples: Sequence[Any], split_config: Mapping[str, Any]) -> tuple[list[Any], list[Any]]:
    salt = str(split_config["salt"])
    dev_upper = int(split_config["dev_mod_upper_exclusive"])
    dev: list[Any] = []
    locked: list[Any] = []
    for sample in samples:
        target = assign_split(sample.sample_id, salt=salt, dev_mod_upper_exclusive=dev_upper)
        if target == "dev":
            dev.append(sample)
        else:
            locked.append(sample)
    return dev, locked


def assign_split(sample_id: str, *, salt: str, dev_mod_upper_exclusive: int) -> str:
    digest = hashlib.sha256(f"{sample_id}|{salt}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return "dev" if bucket < dev_mod_upper_exclusive else "locked"


def route_decision_report(decision: Mapping[str, Any], *, route_id: str) -> dict[str, Any]:
    routed = dict(decision)
    routed["route_id"] = route_id
    if routed.get("status") == "pass":
        routed["next_allowed_step"] = "UPDATE_STEP_RANKING_CLAIM_WITH_V3_6_ARTIFACT"
    return routed


if __name__ == "__main__":
    main()
