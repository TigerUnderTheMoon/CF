"""Run the approved s_FMA_v2 20-row stochastic smoke only."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_preflight import (
    FreshPreflightError,
    attempt_payloads_from_results,
    select_preflight_records,
)
from fma.real_task_pilot.fresh_smoke import (
    build_stochastic_smoke_prefixes,
    build_stochastic_smoke_report,
    validate_stochastic_smoke_readiness,
)
from fma.real_task_pilot.generation import (
    GeneratedTraceResult,
    generate_trace_with_fallback,
    load_prompt_template,
)
from fma.real_task_pilot.openai_client import OpenAIResponsesAdapter
from fma.real_task_pilot.replay import aggregate_delta_u_by_span, missing_replay_jobs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded STOCHASTIC_SMOKE_ONLY for the s_FMA_v2 fresh holdout."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-stochastic-smoke-only",
        action="store_true",
        help="Required explicit guard for the approved 20-row stochastic smoke.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="User-approved smoke budget ceiling. Must not exceed the approval request ceiling.",
    )
    parser.add_argument(
        "--finalize-existing-checkpoints",
        action="store_true",
        help="Write smoke report from existing checkpoints only. Performs no API calls.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    output_root = Path(
        config.get("fresh_holdout", {}).get("output_root", "outputs/s_fma_v2_fresh_holdout")
    )
    manifest_path = Path(
        config.get("fresh_holdout", {}).get("manifest_path", output_root / "fresh_manifest.json")
    )
    overlap_audit_path = output_root / "manifest_overlap_audit.json"
    preflight_report_path = output_root / "api_preflight_report.json"
    smoke_config = config.get("stochastic_smoke", {})
    approval_path = Path(
        smoke_config.get(
            "approval_request_json",
            output_root / "stochastic_smoke_approval_request.json",
        )
    )

    manifest = _load_required_records(manifest_path)
    overlap_audit = _load_required_json(overlap_audit_path)
    preflight_report = _load_required_json(preflight_report_path)
    approval_request = _load_required_json(approval_path)
    readiness = validate_stochastic_smoke_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=overlap_audit,
        preflight_report=preflight_report,
        approval_request=approval_request,
        allow_stochastic_smoke_only=args.allow_stochastic_smoke_only,
        approved_budget_usd=args.approved_budget_usd,
    )

    selected = select_preflight_records(
        manifest,
        samples_per_task=int(config.get("api_preflight", {}).get("samples_per_task", 10)),
        task_order=list(config.get("fresh_holdout", {}).get("tasks", {}).keys()),
    )
    if len(selected) != int(readiness["sample_count"]):
        raise FreshPreflightError("balanced smoke selection did not match the approved sample count.")

    paths = {
        "original_traces": output_root / "stochastic_smoke_original_traces.jsonl",
        "original_attempts": output_root / "stochastic_smoke_original_attempts.jsonl",
        "prefixes": output_root / "stochastic_smoke_replay_prefixes.jsonl",
        "replay_attempts": output_root / "stochastic_smoke_replay_attempts.jsonl",
        "replay_results": output_root / "stochastic_smoke_replay_results.jsonl",
        "delta_u": output_root / "stochastic_smoke_delta_u.jsonl",
        "report": output_root / "stochastic_smoke_report.json",
        "cost": output_root / "logs" / "stochastic_smoke_cost_report.json",
    }

    if args.finalize_existing_checkpoints:
        report = finalize_existing_stochastic_smoke_checkpoints(
            paths,
            config=config,
            readiness=readiness,
            approval_path=approval_path,
            manifest_path=manifest_path,
            preflight_report_path=preflight_report_path,
            expected_replay_jobs=int(smoke_config.get("expected_spans", 20))
            * int(smoke_config.get("replay_repeats_per_span", 3)),
        )
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "sample_count": report["sample_count"],
                    "successful_replay_count": report["successful_replay_count"],
                    "cost_used_usd": report["cost_used_usd"],
                    "next_allowed_step": report["next_allowed_step"],
                },
                sort_keys=True,
            )
        )
        return

    adapter = OpenAIResponsesAdapter()
    generation_prompt = load_prompt_template(config["generation"]["prompt_file"])
    replay_prompt = load_prompt_template(
        smoke_config.get("replay_prompt_file", "prompts/real_task_replay.txt")
    )

    original_results: list[GeneratedTraceResult] = []
    for sample in selected:
        original_results.append(
            generate_trace_with_fallback(
                sample,
                adapter=adapter,
                config=config,
                prompt_template=generation_prompt,
            )
        )
        _write_original_checkpoint(paths, original_results, selected[: len(original_results)])

    original_records = [result.record for result in original_results if result.record is not None]
    original_attempts = attempt_payloads_from_results(
        original_results,
        role="smoke_original",
        samples=selected,
    )
    early_report = finalize_incomplete_original_generation(
        paths,
        original_records=original_records,
        original_attempts=original_attempts,
        config=config,
        readiness=readiness,
        approval_path=approval_path,
        manifest_path=manifest_path,
        preflight_report_path=preflight_report_path,
        expected_replay_jobs=int(smoke_config.get("expected_spans", 20))
        * int(smoke_config.get("replay_repeats_per_span", 3)),
    )
    if early_report is not None:
        print(
            json.dumps(
                {
                    "status": early_report["status"],
                    "sample_count": early_report["sample_count"],
                    "successful_replay_count": early_report["successful_replay_count"],
                    "cost_used_usd": early_report["cost_used_usd"],
                    "next_allowed_step": early_report["next_allowed_step"],
                },
                sort_keys=True,
            )
        )
        return

    prefixes = build_stochastic_smoke_prefixes(
        original_records,
        mask_token=str(smoke_config.get("mask_token", "[REASONING_MASK]")),
    )
    write_records(prefixes, paths["prefixes"])

    repeats = int(smoke_config.get("replay_repeats_per_span", 3))
    jobs = missing_replay_jobs(prefixes, [], repeats=repeats)
    max_jobs = int(readiness["max_api_requests"]) - len(original_results)
    if len(jobs) > max_jobs:
        raise FreshPreflightError("smoke replay jobs exceed the approved 80-request scope.")

    replay_attempts: list[dict[str, Any]] = []
    replay_results: list[dict[str, Any]] = []
    for job in jobs:
        result = generate_trace_with_fallback(
            job,
            adapter=adapter,
            config=config,
            prompt_template=replay_prompt,
        )
        attempt = _replay_attempt_payload(job, result)
        replay_attempts.append(attempt)
        if result.record is not None:
            replay_results.append(_replay_result_payload(job, result))
        _write_replay_checkpoint(paths, replay_attempts, replay_results)

    delta_rows = aggregate_delta_u_by_span(original_records, replay_results)
    write_records(delta_rows, paths["delta_u"])

    all_attempts = [*original_attempts, *replay_attempts]
    cost_used = _estimate_cost_usd(config, all_attempts)
    report = build_stochastic_smoke_report(
        original_records=original_records,
        replay_results=replay_results,
        replay_attempts=replay_attempts,
        delta_rows=delta_rows,
        approved_budget_usd=float(readiness["approved_budget_usd"]),
        cost_used_usd=cost_used,
        expected_original_records=int(readiness["sample_count"]),
        expected_replay_jobs=int(smoke_config.get("expected_spans", 20))
        * int(smoke_config.get("replay_repeats_per_span", 3)),
    )
    report["approval_source"] = str(approval_path)
    report["manifest_source"] = str(manifest_path)
    report["preflight_report_source"] = str(preflight_report_path)
    report["api_attempts"] = len(all_attempts)
    _write_json(paths["report"], report)
    _write_json(
        paths["cost"],
        {
            "cost_used_usd": cost_used,
            "approved_budget_usd": float(readiness["approved_budget_usd"]),
            "api_attempts": len(all_attempts),
            "usage_totals": _usage_totals(all_attempts),
        },
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "sample_count": report["sample_count"],
                "successful_replay_count": report["successful_replay_count"],
                "cost_used_usd": report["cost_used_usd"],
                "next_allowed_step": report["next_allowed_step"],
            },
            sort_keys=True,
        )
    )


def finalize_incomplete_original_generation(
    paths: Mapping[str, Path],
    *,
    original_records: list[dict[str, Any]],
    original_attempts: list[dict[str, Any]],
    config: Mapping[str, Any],
    readiness: Mapping[str, Any],
    approval_path: Path,
    manifest_path: Path,
    preflight_report_path: Path,
    expected_replay_jobs: int,
) -> dict[str, Any] | None:
    """Write a generation-failure smoke report before replay starts, if needed."""

    expected_originals = int(readiness["sample_count"])
    if len(original_records) == expected_originals:
        return None

    delta_rows: list[dict[str, Any]] = []
    write_records(delta_rows, paths["delta_u"])
    cost_used = _estimate_cost_usd(config, original_attempts)
    report = build_stochastic_smoke_report(
        original_records=original_records,
        replay_results=[],
        replay_attempts=[],
        delta_rows=delta_rows,
        approved_budget_usd=float(readiness["approved_budget_usd"]),
        cost_used_usd=cost_used,
        expected_original_records=expected_originals,
        expected_replay_jobs=expected_replay_jobs,
    )
    invalid_originals = [
        attempt for attempt in original_attempts if attempt.get("record") is None
    ]
    report.update(
        {
            "approval_source": str(approval_path),
            "manifest_source": str(manifest_path),
            "preflight_report_source": str(preflight_report_path),
            "api_attempts": len(original_attempts),
            "original_attempt_count": len(original_attempts),
            "invalid_original_attempt_count": len(invalid_originals),
            "original_validation_error_counts": _validation_error_counts(invalid_originals),
            "partial_replay_attempt_count": 0,
            "partial_replay_result_count": 0,
            "api_execution_performed_by_finalize": False,
            "generation_gate_stopped_before_replay": True,
            "finalize_mode": "live_generation_gate",
            "interruption_disclosure": (
                "Original smoke generation did not produce the approved number of valid "
                "records. The runner stopped before replay and did not upgrade claims."
            ),
        }
    )
    _write_json(paths["report"], report)
    _write_json(
        paths["cost"],
        {
            "cost_used_usd": cost_used,
            "approved_budget_usd": float(readiness["approved_budget_usd"]),
            "api_attempts": len(original_attempts),
            "usage_totals": _usage_totals(original_attempts),
            "finalize_mode": "live_generation_gate",
            "api_execution_performed_by_finalize": False,
        },
    )
    return report


def finalize_existing_stochastic_smoke_checkpoints(
    paths: Mapping[str, Path],
    *,
    config: Mapping[str, Any],
    readiness: Mapping[str, Any],
    approval_path: Path,
    manifest_path: Path,
    preflight_report_path: Path,
    expected_replay_jobs: int,
) -> dict[str, Any]:
    """Finalize an interrupted smoke run from checkpoint files without API calls."""

    original_records = _load_optional_records(paths["original_traces"])
    original_attempts = _load_optional_records(paths["original_attempts"])
    replay_attempts = _load_optional_records(paths["replay_attempts"])
    replay_results = _load_optional_records(paths["replay_results"])
    original_generation_complete = len(original_records) == int(readiness["sample_count"])
    delta_rows = (
        aggregate_delta_u_by_span(original_records, replay_results)
        if original_generation_complete
        else []
    )
    write_records(delta_rows, paths["delta_u"])

    all_attempts = [*original_attempts, *replay_attempts]
    cost_used = _estimate_cost_usd(config, all_attempts)
    report = build_stochastic_smoke_report(
        original_records=original_records,
        replay_results=replay_results,
        replay_attempts=replay_attempts,
        delta_rows=delta_rows,
        approved_budget_usd=float(readiness["approved_budget_usd"]),
        cost_used_usd=cost_used,
        expected_original_records=int(readiness["sample_count"]),
        expected_replay_jobs=expected_replay_jobs,
    )
    invalid_originals = [
        attempt for attempt in original_attempts if attempt.get("record") is None
    ]
    report.update(
        {
            "approval_source": str(approval_path),
            "manifest_source": str(manifest_path),
            "preflight_report_source": str(preflight_report_path),
            "api_attempts": len(all_attempts),
            "original_attempt_count": len(original_attempts),
            "invalid_original_attempt_count": len(invalid_originals),
            "original_validation_error_counts": _validation_error_counts(invalid_originals),
            "partial_replay_attempt_count": len(replay_attempts),
            "partial_replay_result_count": len(replay_results),
            "partial_replay_validation_evidence_allowed": original_generation_complete,
            "api_execution_performed_by_finalize": False,
            "finalize_mode": "existing_checkpoints_only",
            "interruption_disclosure": (
                "Smoke runner was finalized from checkpoint artifacts. "
                "Finalize performed no API calls and does not upgrade claims."
            ),
        }
    )
    _write_json(paths["report"], report)
    _write_json(
        paths["cost"],
        {
            "cost_used_usd": cost_used,
            "approved_budget_usd": float(readiness["approved_budget_usd"]),
            "api_attempts": len(all_attempts),
            "usage_totals": _usage_totals(all_attempts),
            "finalize_mode": "existing_checkpoints_only",
            "api_execution_performed_by_finalize": False,
        },
    )
    return report


def _write_original_checkpoint(
    paths: dict[str, Path],
    original_results: list[GeneratedTraceResult],
    samples: list[Mapping[str, Any]],
) -> None:
    write_records(
        [result.record for result in original_results if result.record is not None],
        paths["original_traces"],
    )
    write_records(
        attempt_payloads_from_results(
            original_results,
            role="smoke_original",
            samples=samples,
        ),
        paths["original_attempts"],
    )


def _write_replay_checkpoint(
    paths: dict[str, Path],
    replay_attempts: list[dict[str, Any]],
    replay_results: list[dict[str, Any]],
) -> None:
    write_records(replay_attempts, paths["replay_attempts"])
    write_records(replay_results, paths["replay_results"])


def _load_optional_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_records(path)


def _validation_error_counts(attempts: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for attempt in attempts:
        errors = attempt.get("validation_errors") or []
        if not errors:
            counts["<missing validation_errors>"] += 1
            continue
        for error in errors:
            counts[str(error)] += 1
    return dict(counts)


def _replay_attempt_payload(
    job: Mapping[str, Any],
    result: GeneratedTraceResult,
) -> dict[str, Any]:
    generation_config = result.record.get("generation_config", {}) if result.record else {}
    return {
        "attempt_role": "smoke_replay",
        "sample_id": job.get("sample_id"),
        "task_type": job.get("task_type"),
        "span_index": int(job.get("span_index", 0) or 0),
        "repeat_index": int(job.get("repeat_index", 0) or 0),
        "status": "success" if result.record is not None else "failed",
        "record": result.record,
        "raw_output": result.raw_output,
        "usage": result.usage,
        "model_name": result.model_name,
        "system_fingerprint": result.system_fingerprint,
        "response_id": result.response_id or generation_config.get("response_id"),
        "validation_errors": list(result.validation_errors),
    }


def _replay_result_payload(
    job: Mapping[str, Any],
    result: GeneratedTraceResult,
) -> dict[str, Any]:
    record = dict(result.record or {})
    record.update(
        {
            "sample_id": job.get("sample_id"),
            "task_type": job.get("task_type"),
            "span_index": int(job.get("span_index", 0) or 0),
            "repeat_index": int(job.get("repeat_index", 0) or 0),
            "status": "success",
            "intervention_type": job.get("intervention_type", "api_length_preserving_masked_prefix"),
            "target_span": job.get("target_span"),
        }
    )
    return record


def _estimate_cost_usd(config: Mapping[str, Any], attempts: list[Mapping[str, Any]]) -> float:
    usage = _usage_totals(attempts)
    pricing = config.get("pricing", {})
    input_price = float(pricing.get("input_per_million_usd", 0.0))
    output_price = float(pricing.get("output_per_million_usd", 0.0))
    return round(
        usage["input_tokens"] / 1_000_000 * input_price
        + usage["output_tokens"] / 1_000_000 * output_price,
        6,
    )


def _usage_totals(attempts: list[Mapping[str, Any]]) -> dict[str, int]:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    for attempt in attempts:
        usage = attempt.get("usage") or {}
        input_tokens += int(usage.get("input_tokens", 0) or 0)
        output_tokens += int(usage.get("output_tokens", 0) or 0)
        total_tokens += int(usage.get("total_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _load_required_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FreshPreflightError(f"required records file does not exist: {path}")
    return load_records(path)


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FreshPreflightError(f"required JSON does not exist: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FreshPreflightError(f"{path} must contain a JSON object.")
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
