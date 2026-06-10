"""Run the strict s_FMA_v2.1 full stochastic engineering retry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.real_task_pilot.archive_paths import v2_1_failed_provenance_root
from fma.real_task_pilot.config import load_pilot_config
from fma.real_task_pilot.fresh_preflight import (
    attempt_payloads_from_results,
    select_preflight_records,
)
from fma.real_task_pilot.fresh_smoke_v2_1 import (
    aggregate_v2_1_delta_u_by_span,
    build_v2_1_stochastic_smoke_prefixes,
)
from fma.real_task_pilot.generation import load_prompt_template
from fma.real_task_pilot.replay import missing_replay_jobs
from scripts.run_s_fma_v2_1_fresh_holdout_preflight import (
    SingleRequestOpenAITraceAdapter,
    generate_trace_once,
)
from scripts.run_s_fma_v2_1_full_stochastic_validation import (
    V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL,
    V2_1_FULL_STOCHASTIC_PASS,
    V2_1_FULL_STOCHASTIC_VALIDATION_ONLY,
    V2_1FullStochasticError,
    _estimate_cost_usd,
    _load_records_if_exists,
    _load_required_json,
    _load_required_records,
    _prompt_version,
    _replay_attempt_payload,
    _usage_totals,
    _write_json,
    _write_records_checkpoint,
    build_v2_1_full_generation_config,
    build_v2_1_full_rank_signal_report,
    build_v2_1_full_stochastic_report,
    validate_v2_1_full_stochastic_readiness,
    v2_1_full_stochastic_paths,
)


RETRYABLE_TRANSPORT_ERROR_PREFIXES = (
    "api_error:APITimeoutError:",
    "api_error:APIConnectionError:",
)
V2_1_FULL_STOCHASTIC_ENGINEERING_RETRY_ONLY = (
    "V2_1_FULL_STOCHASTIC_ENGINEERING_RETRY_ONLY"
)
MAX_TRANSPORT_RETRY_ATTEMPTS_PER_KEY = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded v2.1 full stochastic engineering retry only."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs") / "s_fma_v2_1_fresh_holdout.yaml",
    )
    parser.add_argument(
        "--allow-full-stochastic-engineering-retry-only",
        action="store_true",
        help="Required explicit guard for the strict v2.1 engineering retry.",
    )
    parser.add_argument(
        "--approved-budget-usd",
        type=float,
        required=True,
        help="Hard cumulative source+retry budget ceiling for this rescue route.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.allow_full_stochastic_engineering_retry_only:
        raise V2_1FullStochasticError(
            "v2.1 full engineering retry requires "
            "--allow-full-stochastic-engineering-retry-only."
        )

    config = load_pilot_config(args.config)
    output_root = Path(
        config.get("experiment", {}).get(
            "output_dir", "outputs/s_fma_v2_1_fresh_holdout"
        )
    )
    output_root = v2_1_failed_provenance_root(output_root)
    source_full_paths = v2_1_full_stochastic_paths(output_root)
    retry_paths = v2_1_full_engineering_retry_paths(output_root)
    paths = {
        "manifest": output_root / "fresh_manifest.json",
        "overlap": output_root / "manifest_overlap_audit.json",
        "contract": output_root / "v2_1_contract_audit.json",
        "pilot_report": output_root / "v2_1_pilot_stochastic_report.json",
        "approval": output_root / "v2_1_full_stochastic_validation_approval_request.json",
        "readiness": Path("outputs") / "real_task_pilot" / "readiness_audit.json",
        **{f"source_{key}": value for key, value in source_full_paths.items()},
        **retry_paths,
    }

    manifest = _load_required_records(paths["manifest"])
    overlap_audit = _load_required_json(paths["overlap"])
    contract_audit = _load_required_json(paths["contract"])
    pilot_report = _load_required_json(paths["pilot_report"])
    approval_request = _load_required_json(paths["approval"])
    current_readiness = _load_required_json(paths["readiness"])
    prompt_file = Path(
        config.get("span_diversity_policy", {}).get(
            "prompt_file", "prompts/s_fma_v2_1_reflection_generation.txt"
        )
    )
    current_prompt_version = _prompt_version(prompt_file)

    readiness = validate_v2_1_full_stochastic_readiness(
        config=config,
        manifest=manifest,
        overlap_audit=overlap_audit,
        contract_audit=contract_audit,
        pilot_report=pilot_report,
        approval_request=approval_request,
        current_readiness=current_readiness,
        allow_full_stochastic_validation_only=True,
        approved_budget_usd=args.approved_budget_usd,
        current_prompt_version=current_prompt_version,
    )
    if readiness["scope"] != V2_1_FULL_STOCHASTIC_VALIDATION_ONLY:
        raise V2_1FullStochasticError("source readiness must remain strict v2.1 full validation.")

    selected = select_preflight_records(
        manifest,
        samples_per_task=200,
        task_order=["gsm8k", "hotpotqa"],
    )
    selected_by_id = {str(row.get("sample_id") or ""): row for row in selected}
    live_config = build_v2_1_full_generation_config(config, readiness=readiness)
    generation_prompt = load_prompt_template(live_config["generation"]["prompt_file"])
    replay_prompt = load_prompt_template(
        live_config.get("stochastic_smoke", {}).get(
            "replay_prompt_file", "prompts/real_task_replay.txt"
        )
    )
    adapter = SingleRequestOpenAITraceAdapter()

    source_original_attempts = _load_required_records(paths["source_original_attempts"])
    source_replay_attempts = _load_required_records(paths["source_replay_attempts"])
    source_replay_results = _load_required_records(paths["source_replay_results"])
    source_report = _load_required_json(paths["source_report"])
    source_rank_signal = _load_required_json(paths["source_rank_signal"])
    source_cost_report = _load_required_json(paths["source_cost"])
    retry_original_attempts = _load_records_if_exists(paths["retry_original_attempts"])
    retry_replay_attempts = _load_records_if_exists(paths["retry_replay_attempts"])

    retry_original_attempts = _retry_original_transport_failures(
        source_original_attempts=source_original_attempts,
        retry_original_attempts=retry_original_attempts,
        selected_by_id=selected_by_id,
        adapter=adapter,
        config=live_config,
        prompt_template=generation_prompt,
        paths=paths,
        approved_budget_usd=float(readiness["approved_budget_usd"]),
        source_attempts=[*source_original_attempts, *source_replay_attempts],
        retry_replay_attempts=retry_replay_attempts,
    )
    original_effective = apply_successful_transport_retries(
        source_original_attempts,
        retry_original_attempts,
        retry_scope=V2_1_FULL_STOCHASTIC_ENGINEERING_RETRY_ONLY,
    )
    effective_original_attempts = original_effective["effective_attempts"]
    effective_original_records = [
        dict(attempt["record"])
        for attempt in effective_original_attempts
        if attempt.get("record") is not None
    ]
    _write_records_checkpoint(effective_original_attempts, paths["effective_original_attempts"])
    _write_records_checkpoint(effective_original_records, paths["effective_original_traces"])

    prefixes = build_v2_1_stochastic_smoke_prefixes(
        effective_original_records,
        config=live_config,
        mask_token=str(
            live_config.get("stochastic_smoke", {}).get(
                "mask_token", "[REASONING_MASK]"
            )
        ),
    )
    _write_records_checkpoint(prefixes, paths["effective_prefixes"])

    retry_replay_attempts = _retry_replay_transport_failures(
        prefixes=prefixes,
        source_replay_results=source_replay_results,
        retry_replay_attempts=retry_replay_attempts,
        adapter=adapter,
        config=live_config,
        prompt_template=replay_prompt,
        paths=paths,
        approved_budget_usd=float(readiness["approved_budget_usd"]),
        source_attempts=[*source_original_attempts, *source_replay_attempts],
        retry_original_attempts=retry_original_attempts,
        repeats=int(readiness["stochastic_repeats_per_span"]),
    )
    retry_replay_results = _successful_replay_results_from_attempts(retry_replay_attempts)
    effective_replay_results = [*source_replay_results, *retry_replay_results]
    replay_effective = apply_successful_transport_retries(
        source_replay_attempts,
        retry_replay_attempts,
        retry_scope=V2_1_FULL_STOCHASTIC_ENGINEERING_RETRY_ONLY,
    )
    effective_replay_attempts = [
        *replay_effective["effective_attempts"],
        *collapse_new_replay_attempts_for_effective_report(
            source_replay_attempts,
            retry_replay_attempts,
        ),
    ]
    effective_replay_results = _successful_replay_results_from_attempts(
        effective_replay_attempts
    )
    replay_plan = build_effective_replay_job_plan(
        prefixes,
        effective_replay_results,
        repeats=int(readiness["stochastic_repeats_per_span"]),
    )
    delta_rows = aggregate_v2_1_delta_u_by_span(
        effective_original_records,
        effective_replay_results,
    )
    _write_records_checkpoint(effective_replay_attempts, paths["effective_replay_attempts"])
    _write_records_checkpoint(effective_replay_results, paths["effective_replay_results"])
    _write_records_checkpoint(delta_rows, paths["effective_delta_u"])

    rank_signal = build_v2_1_full_rank_signal_report(
        delta_rows,
        resamples=int(
            config.get("nondeterministic_protocol", {})
            .get("bootstrap", {})
            .get("resamples", 10000)
        ),
        confidence_level=float(
            config.get("nondeterministic_protocol", {})
            .get("bootstrap", {})
            .get("confidence_level", 0.95)
        ),
        seed=int(
            config.get("nondeterministic_protocol", {})
            .get("bootstrap", {})
            .get("random_seed", 20260530)
        )
        + 4100,
    )
    effective_cost = _estimate_cost_usd(
        live_config,
        [*effective_original_attempts, *effective_replay_attempts],
    )
    source_attempts = [*source_original_attempts, *source_replay_attempts]
    retry_attempts = [*retry_original_attempts, *retry_replay_attempts]
    source_cost = _estimate_cost_usd(live_config, source_attempts)
    incremental_retry_cost = _estimate_cost_usd(live_config, retry_attempts)
    cumulative_route_cost = _estimate_cost_usd(live_config, [*source_attempts, *retry_attempts])
    report = build_v2_1_full_stochastic_report(
        original_records=effective_original_records,
        original_attempts=effective_original_attempts,
        replay_results=effective_replay_results,
        replay_attempts=effective_replay_attempts,
        delta_rows=delta_rows,
        rank_signal=rank_signal,
        readiness=readiness,
        cost_used_usd=effective_cost,
        expected_replay_jobs=int(replay_plan["expected_replay_jobs"]),
    )
    retry_nonretryable = [
        *partition_retryable_transport_attempts(source_original_attempts)["nonretryable"],
        *partition_retryable_transport_attempts(source_replay_attempts)["nonretryable"],
    ]
    unresolved_retryable = [
        *original_effective["unresolved_retryable_attempts"],
        *replay_effective["unresolved_retryable_attempts"],
    ]
    retry_replaced_attempts = [
        *original_effective["retry_replaced_attempts"],
        *replay_effective["retry_replaced_attempts"],
    ]
    retry_abandon_reason = retry_abandon_reason_from_report(
        report,
        unresolved_retryable_attempts=unresolved_retryable,
    )
    report.update(
        {
            "scope": V2_1_FULL_STOCHASTIC_ENGINEERING_RETRY_ONLY,
            "source_full_validation_scope": V2_1_FULL_STOCHASTIC_VALIDATION_ONLY,
            "source_full_validation_status": source_report.get("status"),
            "source_rank_signal": source_rank_signal,
            "source_api_attempts": len(source_attempts),
            "incremental_retry_api_calls": len(retry_attempts),
            "cumulative_route_api_calls": len(source_attempts) + len(retry_attempts),
            "effective_report_api_attempts": len(effective_original_attempts)
            + len(effective_replay_attempts),
            "source_cost_usd": source_cost,
            "source_cost_report_cost_usd": source_cost_report.get("cost_used_usd"),
            "incremental_retry_cost_usd": incremental_retry_cost,
            "cumulative_route_cost_usd": cumulative_route_cost,
            "retry_replaced_attempts": retry_replaced_attempts,
            "retry_nonretryable_attempts": retry_nonretryable,
            "retry_unresolved_retryable_attempts": unresolved_retryable,
            "retry_abandon_reason": retry_abandon_reason,
            "api_execution_performed": bool(retry_attempts),
            "source_failed_artifact_rewritten": False,
        }
    )
    audit = build_engineering_retry_audit(
        report=report,
        source_report=source_report,
        retry_abandon_reason=retry_abandon_reason,
        retry_replaced_attempts=retry_replaced_attempts,
        retry_nonretryable_attempts=retry_nonretryable,
        unresolved_retryable_attempts=unresolved_retryable,
    )

    _write_json(paths["rank_signal"], rank_signal)
    _write_json(paths["report"], report)
    _write_json(paths["audit"], audit)
    _write_json(
        paths["cost"],
        {
            "scope": V2_1_FULL_STOCHASTIC_ENGINEERING_RETRY_ONLY,
            "approved_budget_usd": float(readiness["approved_budget_usd"]),
            "source_api_attempts": len(source_attempts),
            "incremental_retry_api_calls": len(retry_attempts),
            "cumulative_route_api_calls": len(source_attempts) + len(retry_attempts),
            "effective_report_api_attempts": len(effective_original_attempts)
            + len(effective_replay_attempts),
            "source_cost_usd": source_cost,
            "incremental_retry_cost_usd": incremental_retry_cost,
            "cumulative_route_cost_usd": cumulative_route_cost,
            "effective_report_cost_usd": effective_cost,
            "budget_gate_pass": cumulative_route_cost
            <= float(readiness["approved_budget_usd"]),
            "usage_totals": _usage_totals([*source_attempts, *retry_attempts]),
        },
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "failure_codes": report["failure_codes"],
                "retry_abandon_reason": report["retry_abandon_reason"],
                "source_api_attempts": report["source_api_attempts"],
                "incremental_retry_api_calls": report["incremental_retry_api_calls"],
                "cumulative_route_api_calls": report["cumulative_route_api_calls"],
                "effective_report_api_attempts": report["effective_report_api_attempts"],
                "cumulative_route_cost_usd": report["cumulative_route_cost_usd"],
                "nonzero_delta_u_by_task": report["nonzero_delta_u_by_task"],
                "TASK_SPECIFIC_pass": report["TASK_SPECIFIC_pass"],
                "GLOBAL_pass": report["GLOBAL_pass"],
                "current_status_remains": report["current_status_remains"],
            },
            sort_keys=True,
        )
    )


def v2_1_full_engineering_retry_paths(output_root: Path) -> dict[str, Path]:
    output_root = v2_1_failed_provenance_root(output_root)
    return {
        "retry_original_attempts": output_root
        / "v2_1_full_stochastic_engineering_retry_original_attempts.jsonl",
        "retry_replay_attempts": output_root
        / "v2_1_full_stochastic_engineering_retry_replay_attempts.jsonl",
        "effective_original_attempts": output_root
        / "v2_1_full_stochastic_engineering_retry_effective_original_attempts.jsonl",
        "effective_original_traces": output_root
        / "v2_1_full_stochastic_engineering_retry_effective_original_traces.jsonl",
        "effective_prefixes": output_root
        / "v2_1_full_stochastic_engineering_retry_replay_prefixes.jsonl",
        "effective_replay_attempts": output_root
        / "v2_1_full_stochastic_engineering_retry_effective_replay_attempts.jsonl",
        "effective_replay_results": output_root
        / "v2_1_full_stochastic_engineering_retry_effective_replay_results.jsonl",
        "effective_delta_u": output_root
        / "v2_1_full_stochastic_engineering_retry_delta_u.jsonl",
        "rank_signal": output_root
        / "v2_1_full_stochastic_engineering_retry_rank_signal_report.json",
        "report": output_root / "v2_1_full_stochastic_engineering_retry_report.json",
        "audit": output_root / "v2_1_full_stochastic_engineering_retry_audit.json",
        "cost": output_root
        / "logs"
        / "v2_1_full_stochastic_engineering_retry_cost_report.json",
    }


def _retry_original_transport_failures(
    *,
    source_original_attempts: Sequence[Mapping[str, Any]],
    retry_original_attempts: list[dict[str, Any]],
    selected_by_id: Mapping[str, Mapping[str, Any]],
    adapter: SingleRequestOpenAITraceAdapter,
    config: Mapping[str, Any],
    prompt_template: str,
    paths: Mapping[str, Path],
    approved_budget_usd: float,
    source_attempts: Sequence[Mapping[str, Any]],
    retry_replay_attempts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    retry_attempts = list(retry_original_attempts)
    while True:
        effective = apply_successful_transport_retries(
            source_original_attempts,
            retry_attempts,
            retry_scope=V2_1_FULL_STOCHASTIC_ENGINEERING_RETRY_ONLY,
        )
        unresolved = list(effective["unresolved_retryable_attempts"])
        if not unresolved:
            return retry_attempts
        attempted_this_round = False
        for unresolved_attempt in unresolved:
            key = tuple(unresolved_attempt["attempt_key"])
            if _retry_count_for_key(retry_attempts, key) >= MAX_TRANSPORT_RETRY_ATTEMPTS_PER_KEY:
                continue
            if not _budget_available(
                config=config,
                source_attempts=source_attempts,
                retry_original_attempts=retry_attempts,
                retry_replay_attempts=retry_replay_attempts,
                approved_budget_usd=approved_budget_usd,
            ):
                return retry_attempts
            sample_id = str(key[1])
            sample = selected_by_id.get(sample_id)
            if sample is None:
                raise V2_1FullStochasticError(
                    f"retry source sample {sample_id!r} is not in the approved full selection."
                )
            result = generate_trace_once(
                sample,
                adapter=adapter,
                config=config,
                prompt_template=prompt_template,
            )
            attempt = attempt_payloads_from_results(
                [result],
                role="full_original_engineering_retry",
                samples=[sample],
            )[0]
            retry_attempts.append(attempt)
            _write_records_checkpoint(retry_attempts, paths["retry_original_attempts"])
            attempted_this_round = True
        if not attempted_this_round:
            return retry_attempts


def _retry_replay_transport_failures(
    *,
    prefixes: Sequence[Mapping[str, Any]],
    source_replay_results: Sequence[Mapping[str, Any]],
    retry_replay_attempts: list[dict[str, Any]],
    adapter: SingleRequestOpenAITraceAdapter,
    config: Mapping[str, Any],
    prompt_template: str,
    paths: Mapping[str, Path],
    approved_budget_usd: float,
    source_attempts: Sequence[Mapping[str, Any]],
    retry_original_attempts: Sequence[Mapping[str, Any]],
    repeats: int,
) -> list[dict[str, Any]]:
    retry_attempts = list(retry_replay_attempts)
    while True:
        retry_replay_results = _successful_replay_results_from_attempts(retry_attempts)
        effective_replay_results = [*source_replay_results, *retry_replay_results]
        plan = build_effective_replay_job_plan(
            prefixes,
            effective_replay_results,
            repeats=repeats,
        )
        jobs = list(plan["missing_jobs"])
        if not jobs:
            return retry_attempts
        attempted_this_round = False
        for job in jobs:
            key = _attempt_key(job)
            if _retry_count_for_key(retry_attempts, key) >= MAX_TRANSPORT_RETRY_ATTEMPTS_PER_KEY:
                continue
            if not _budget_available(
                config=config,
                source_attempts=source_attempts,
                retry_original_attempts=retry_original_attempts,
                retry_replay_attempts=retry_attempts,
                approved_budget_usd=approved_budget_usd,
            ):
                return retry_attempts
            result = generate_trace_once(
                job,
                adapter=adapter,
                config=config,
                prompt_template=prompt_template,
            )
            attempt = _replay_attempt_payload(job, result)
            attempt["attempt_role"] = "full_replay_engineering_retry"
            retry_attempts.append(attempt)
            _write_records_checkpoint(retry_attempts, paths["retry_replay_attempts"])
            attempted_this_round = True
        if not attempted_this_round:
            return retry_attempts


def is_retryable_transport_attempt(attempt: Mapping[str, Any]) -> bool:
    """Return true only for failed API timeout/connection attempts."""

    if attempt.get("record") is not None:
        return False
    validation_errors = attempt.get("validation_errors") or []
    return any(
        str(error).startswith(RETRYABLE_TRANSPORT_ERROR_PREFIXES)
        for error in validation_errors
    )


def partition_retryable_transport_attempts(
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Split failed attempts into retryable transport and nonretryable failures."""

    retryable: list[dict[str, Any]] = []
    nonretryable: list[dict[str, Any]] = []
    for attempt in attempts:
        if is_retryable_transport_attempt(attempt):
            retryable.append(dict(attempt))
        elif attempt.get("record") is None and attempt.get("validation_errors"):
            nonretryable.append(dict(attempt))
    return {"retryable": retryable, "nonretryable": nonretryable}


def apply_successful_transport_retries(
    source_attempts: Sequence[Mapping[str, Any]],
    retry_attempts: Sequence[Mapping[str, Any]],
    *,
    retry_scope: str,
) -> dict[str, Any]:
    """Replace retryable failed attempts with successful retry attempts."""

    successful_retry_by_key = {
        _attempt_key(attempt): dict(attempt)
        for attempt in retry_attempts
        if attempt.get("record") is not None and not attempt.get("validation_errors")
    }
    effective_attempts: list[dict[str, Any]] = []
    replaced_attempts: list[dict[str, Any]] = []
    unresolved_retryable_attempts: list[dict[str, Any]] = []

    for index, source in enumerate(source_attempts):
        source_payload = dict(source)
        source_key = _attempt_key(source_payload)
        replacement = successful_retry_by_key.get(source_key)
        if is_retryable_transport_attempt(source_payload) and replacement is not None:
            replacement["retry_provenance"] = {
                "retry_scope": retry_scope,
                "source_attempt_index": index,
                "source_attempt_role": source_payload.get("attempt_role"),
                "source_validation_errors": list(
                    source_payload.get("validation_errors") or []
                ),
            }
            effective_attempts.append(replacement)
            replaced_attempts.append(
                {
                    "attempt_key": list(source_key),
                    "source_attempt_index": index,
                    "source_attempt_role": source_payload.get("attempt_role"),
                    "retry_attempt_role": replacement.get("attempt_role"),
                    "source_validation_errors": list(
                        source_payload.get("validation_errors") or []
                    ),
                }
            )
        else:
            effective_attempts.append(source_payload)
            if is_retryable_transport_attempt(source_payload):
                unresolved_retryable_attempts.append(
                    {
                        "attempt_key": list(source_key),
                        "source_attempt_index": index,
                        "source_attempt_role": source_payload.get("attempt_role"),
                        "source_validation_errors": list(
                            source_payload.get("validation_errors") or []
                        ),
                    }
                )

    return {
        "effective_attempts": effective_attempts,
        "retry_replaced_attempts": replaced_attempts,
        "unresolved_retryable_attempts": unresolved_retryable_attempts,
    }


def build_effective_replay_job_plan(
    prefixes: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
    *,
    repeats: int,
) -> dict[str, Any]:
    """Return the full replay job plan after applying effective retry rows."""

    return {
        "expected_replay_jobs": len(prefixes) * repeats,
        "missing_jobs": missing_replay_jobs(prefixes, replay_results, repeats=repeats),
    }


def retry_abandon_reason_from_report(
    report: Mapping[str, Any],
    *,
    unresolved_retryable_attempts: Sequence[Mapping[str, Any]],
) -> str | None:
    if report.get("status") == V2_1_FULL_STOCHASTIC_PASS:
        return None
    nonzero_by_task = dict(report.get("nonzero_delta_u_by_task") or {})
    failure_codes = set(report.get("failure_codes") or [])
    if (
        V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL in failure_codes
        and int(nonzero_by_task.get("gsm8k", 0) or 0) < 20
    ):
        if unresolved_retryable_attempts:
            return (
                "transport_unresolved_and_gsm8k_sparse_signal_below_"
                "preregistered_threshold"
            )
        return "gsm8k_sparse_signal_below_preregistered_threshold"
    if unresolved_retryable_attempts:
        return "retryable_transport_failures_unresolved_under_budget_or_retry_cap"
    if failure_codes:
        return "strict_v2_1_gate_failed_without_allowed_retry_path"
    return None


def build_engineering_retry_audit(
    *,
    report: Mapping[str, Any],
    source_report: Mapping[str, Any],
    retry_abandon_reason: str | None,
    retry_replaced_attempts: Sequence[Mapping[str, Any]],
    retry_nonretryable_attempts: Sequence[Mapping[str, Any]],
    unresolved_retryable_attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "artifact": "v2_1_full_stochastic_engineering_retry_audit",
        "scope": V2_1_FULL_STOCHASTIC_ENGINEERING_RETRY_ONLY,
        "source_scope": V2_1_FULL_STOCHASTIC_VALIDATION_ONLY,
        "source_status": source_report.get("status"),
        "retry_status": report.get("status"),
        "retry_failure_codes": list(report.get("failure_codes") or []),
        "retry_abandon_reason": retry_abandon_reason,
        "source_failed_artifact_rewritten": False,
        "retry_replaced_attempt_count": len(retry_replaced_attempts),
        "retry_replaced_attempts": [dict(row) for row in retry_replaced_attempts],
        "retry_nonretryable_attempt_count": len(retry_nonretryable_attempts),
        "retry_nonretryable_attempts": [
            _attempt_summary(row) for row in retry_nonretryable_attempts
        ],
        "unresolved_retryable_attempt_count": len(unresolved_retryable_attempts),
        "unresolved_retryable_attempts": [
            dict(row) for row in unresolved_retryable_attempts
        ],
        "quality_rates": {
            "json_parse_success_rate": report.get("json_parse_success_rate"),
            "schema_success_rate": report.get("schema_success_rate"),
            "tag_extraction_success_rate": report.get("tag_extraction_success_rate"),
            "final_answer_parse_success_rate": report.get(
                "final_answer_parse_success_rate"
            ),
        },
        "nonzero_delta_u_by_task": dict(report.get("nonzero_delta_u_by_task") or {}),
        "TASK_SPECIFIC_pass": report.get("TASK_SPECIFIC_pass"),
        "GLOBAL_pass": report.get("GLOBAL_pass"),
        "current_status_remains": report.get("current_status_remains"),
        "claim_boundaries": {
            "deterministic_replay_claim_allowed": False,
            "submission_ready_claim_allowed": False,
            "top_tier_ready_claim_allowed": False,
            "prm_filtering_execution_allowed": False,
            "gate_relaxation_performed": False,
        },
    }


def _successful_replay_results_from_attempts(
    attempts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for attempt in attempts:
        if attempt.get("record") is None or attempt.get("validation_errors"):
            continue
        record = dict(attempt.get("record") or {})
        record.update(
            {
                "sample_id": attempt.get("sample_id"),
                "task_id": attempt.get("task_id"),
                "task_type": attempt.get("task_type"),
                "span_index": int(attempt.get("span_index", 0) or 0),
                "repeat_index": int(attempt.get("repeat_index", 0) or 0),
                "status": "success",
                "intervention_type": attempt.get(
                    "intervention_type", "api_length_preserving_masked_prefix"
                ),
            }
        )
        results.append(record)
    return results


def collapse_new_replay_attempts_for_effective_report(
    source_replay_attempts: Sequence[Mapping[str, Any]],
    retry_replay_attempts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    source_keys = {_attempt_key(attempt) for attempt in source_replay_attempts}
    ordered_keys: list[tuple[Any, ...]] = []
    collapsed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for attempt in retry_replay_attempts:
        key = _attempt_key(attempt)
        if key in source_keys:
            continue
        attempt_payload = dict(attempt)
        if key not in collapsed:
            ordered_keys.append(key)
            collapsed[key] = attempt_payload
            continue
        existing = collapsed[key]
        if _attempt_success(attempt_payload) or not _attempt_success(existing):
            collapsed[key] = attempt_payload
    return [collapsed[key] for key in ordered_keys]


def _budget_available(
    *,
    config: Mapping[str, Any],
    source_attempts: Sequence[Mapping[str, Any]],
    retry_original_attempts: Sequence[Mapping[str, Any]],
    retry_replay_attempts: Sequence[Mapping[str, Any]],
    approved_budget_usd: float,
) -> bool:
    cost = _estimate_cost_usd(
        config,
        [*source_attempts, *retry_original_attempts, *retry_replay_attempts],
    )
    return cost < approved_budget_usd


def _retry_count_for_key(
    retry_attempts: Sequence[Mapping[str, Any]],
    key: tuple[Any, ...],
) -> int:
    return sum(1 for attempt in retry_attempts if _attempt_key(attempt) == key)


def _attempt_success(attempt: Mapping[str, Any]) -> bool:
    return attempt.get("record") is not None and not attempt.get("validation_errors")


def _attempt_summary(attempt: Mapping[str, Any]) -> dict[str, Any]:
    summary = {
        "attempt_role": attempt.get("attempt_role"),
        "sample_id": attempt.get("sample_id"),
        "task_id": attempt.get("task_id"),
        "task_type": attempt.get("task_type"),
        "validation_errors": list(attempt.get("validation_errors") or []),
    }
    if "span_index" in attempt:
        summary["span_index"] = int(attempt.get("span_index", 0) or 0)
    if "repeat_index" in attempt:
        summary["repeat_index"] = int(attempt.get("repeat_index", 0) or 0)
    return summary


def _attempt_key(attempt: Mapping[str, Any]) -> tuple[Any, ...]:
    sample_id = str(attempt.get("sample_id") or "")
    if "span_index" in attempt or "repeat_index" in attempt:
        return (
            "replay",
            sample_id,
            int(attempt.get("span_index", 0) or 0),
            int(attempt.get("repeat_index", 0) or 0),
        )
    return ("original", sample_id)


if __name__ == "__main__":
    main()
