"""Guarded real_task_v3 stochastic smoke runner with v3 utility scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.generation import (
    build_generation_prompt,
    load_prompt_template,
    normalize_trace_record,
)
from fma.real_task_pilot.parsing import parse_json_object
from fma.real_task_pilot.replay import (
    build_replay_prefix,
    missing_replay_jobs,
)
from fma.real_task_pilot.validation_v3 import (
    score_gsm8k_v3_utility,
    score_hotpotqa_v3_utility,
)
from fma.pilot.api_client import OpenAIClient, APIResponse


import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


# Thread-local client storage for parallel workers
_thread_local = threading.local()


def _get_thread_client(config: Mapping[str, Any], approved_budget_usd: float) -> OpenAIClient:
    """Return a thread-local OpenAIClient to avoid shared-state races."""
    if not hasattr(_thread_local, "client"):
        _thread_local.client = _build_client(config, approved_budget_usd=approved_budget_usd)
    return _thread_local.client


# Lock for thread-safe incremental file writes
_file_write_lock = threading.Lock()


def _locked_write_records(records: Sequence[Mapping[str, Any]], path: Path) -> None:
    with _file_write_lock:
        write_records(records, path)


REAL_TASK_V3_1_SMOKE_ONLY = "REAL_TASK_V3_1_SMOKE_ONLY"
V3_SMOKE_PASS = "V3_1_SMOKE_PASS"
V3_SMOKE_PASS_WITH_DISCLOSURES = "V3_1_SMOKE_PASS_WITH_DISCLOSURES"
V3_SMOKE_FAIL_INSUFFICIENT_TRACES = "V3_1_SMOKE_FAIL_INSUFFICIENT_TRACES"
V3_SMOKE_FAIL_INSUFFICIENT_SPANS = "V3_1_SMOKE_FAIL_INSUFFICIENT_SPANS"
V3_SMOKE_FAIL_SPARSE_SIGNAL_GSM8K = "V3_1_SMOKE_FAIL_SPARSE_SIGNAL_GSM8K"
V3_SMOKE_FAIL_SPARSE_SIGNAL_HOTPOTQA = "V3_1_SMOKE_FAIL_SPARSE_SIGNAL_HOTPOTQA"
V3_SMOKE_FAIL_COST = "V3_1_SMOKE_FAIL_COST"
V3_SMOKE_FAIL_GENERATION = "V3_1_SMOKE_FAIL_GENERATION"
V3_SMOKE_FAIL_REPLAY = "V3_1_SMOKE_FAIL_REPLAY"
V3_DELTA_EPSILON = 1e-12
V3_MIN_REFLECTION_SPANS = 3
V3_MAX_SCORED_SPANS_PER_TRACE = 3
V3_TASK_ORDER = ("gsm8k", "hotpotqa")
V3_INTERVENTION_CONTRACT = {
    "intervention_type": "REPLACE",
    "intervention_implementation": "reasoning_mask_replacement",
    "mask_token": "[REASONING_MASK]",
    "replace_intervention_in_current_v3": True,
}
V3_1_REPLACE_PREREGISTRATION = {
    "fallback_route": "v3.1_REPLACE",
    "trigger": "full_v3_delete_smoke_sparse_delta_u",
    "requires_separate_preregistration": True,
    "requires_separate_manifest_metadata_and_artifacts": True,
    "delete_smoke_data_allowed_use": "failure_provenance_only",
    "replace_evidence_mixed_with_v3_delete": False,
}


V3_SMOKE_GATES = {
    "valid_trace_min_per_task": 95,
    "eligible_span_min_pooled": 150,
    "nonzero_delta_gsm8k_min": 25,
    "nonzero_delta_hotpotqa_min": 35,
    "transport_success_rate_min": 0.95,
    "replay_repeats_per_span": 3,
    "smoke_api_calls_max": 6500,
    "smoke_cost_usd_max": 50,
}

DEFAULT_CONFIG = Path("configs") / "real_task_v3_validation.yaml"
DEFAULT_MANIFEST = Path("outputs") / "real_task_v3" / "smoke_manifest.jsonl"
DEFAULT_PROMPT = Path("prompts") / "real_task_reflection_generation.txt"
SMOKE_METADATA_NAME = "smoke_run_metadata.json"
SMOKE_ARTIFACT_NAMES = (
    "smoke_original_traces.jsonl",
    "smoke_original_attempts.jsonl",
    "smoke_replay_prefixes.jsonl",
    "smoke_replay_results.jsonl",
    "smoke_replay_attempts.jsonl",
    "smoke_delta_u.jsonl",
    "smoke_report.json",
)


@dataclass
class ChatGenerationResult:
    record: dict[str, Any] | None
    raw_output: str
    model_name: str
    system_fingerprint: str | None
    usage: dict[str, Any]
    validation_errors: list[str]
    cost_usd: float
    cached: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real_task_v3 stochastic smoke.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--approved-budget-usd", type=float, default=50)
    parser.add_argument("--allow-api", action="store_true")
    parser.add_argument("--task-scope")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--allow-underpowered-diagnostic", action="store_true")
    parser.add_argument("--random-seed", type=int, default=20260606)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.allow_api:
        raise RuntimeError("v3 smoke requires --allow-api to prevent accidental API spend.")
    if args.task_scope != REAL_TASK_V3_1_SMOKE_ONLY:
        raise RuntimeError(f"--task-scope must equal {REAL_TASK_V3_1_SMOKE_ONLY}")

    config = _load_config(args.config)
    output_dir = Path(args.output_dir or config.get("experiment", {}).get("output_dir", "outputs/real_task_v3_1"))
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_records(args.manifest)
    manifest, selection_report = select_smoke_manifest_rows(
        manifest,
        max_samples=args.max_samples,
        allow_underpowered_diagnostic=args.allow_underpowered_diagnostic,
    )
    prompt_template = load_prompt_template(args.prompt)
    run_metadata = build_smoke_run_metadata(
        manifest=manifest,
        prompt_template=prompt_template,
        selection_report=selection_report,
    )
    assert_smoke_resume_allowed(output_dir, run_metadata)
    _write_json(output_dir / SMOKE_METADATA_NAME, run_metadata)

    print(f"v3 smoke: {len(manifest)} manifest rows, budget=${args.approved_budget_usd}")

    client = _build_client(config, approved_budget_usd=args.approved_budget_usd)

    original_records, original_attempts, generation_cost = _stage_generate_chat(
        manifest=manifest,
        client=client,
        config=config,
        prompt_template=prompt_template,
        output_dir=output_dir,
        approved_budget_usd=args.approved_budget_usd,
    )

    replay_prefixes = _stage_build_prefixes(original_records)
    write_records(replay_prefixes, output_dir / "smoke_replay_prefixes.jsonl")
    print(f"  built {len(replay_prefixes)} replay prefixes")

    replay_results, replay_attempts, replay_cost = _stage_replay_chat(
        prefixes=replay_prefixes,
        client=client,
        config=config,
        prompt_template=prompt_template,
        output_dir=output_dir,
        repeats=V3_SMOKE_GATES["replay_repeats_per_span"],
        approved_budget_usd=args.approved_budget_usd,
    )
    total_cost = generation_cost + replay_cost

    delta_rows = _stage_delta_u(
        original_records=original_records,
        replay_results=replay_results,
        output_dir=output_dir,
    )

    report = _build_smoke_report(
        original_records=original_records,
        original_attempts=original_attempts,
        replay_prefixes=replay_prefixes,
        replay_results=replay_results,
        replay_attempts=replay_attempts,
        delta_rows=delta_rows,
        cost_usd=total_cost,
        approved_budget_usd=args.approved_budget_usd,
        selection_report=selection_report,
    )
    _write_json(output_dir / "smoke_report.json", report)

    _write_cost_report(
        log_dir / "smoke_cost_report.json",
        total_cost=total_cost,
        original_cost=generation_cost,
        replay_cost=replay_cost,
        approved_budget_usd=args.approved_budget_usd,
    )

    print(f"\nv3 smoke complete: {report['status']}")
    print(f"  traces: {report['valid_trace_count']} valid of {report['manifest_row_count']}")
    print(f"  spans: {report['eligible_span_count']}")
    print(f"  nonzero delta: GSM8K={report['nonzero_delta_gsm8k']}, HotpotQA={report['nonzero_delta_hotpotqa']}")
    print(f"  cost: ${total_cost:.4f} / ${args.approved_budget_usd}")
    print(f"  total API calls: {report['total_api_calls']}")
    print(f"  next step: {report['next_allowed_step']}")

    if report["status"] in {V3_SMOKE_PASS, V3_SMOKE_PASS_WITH_DISCLOSURES}:
        print("V3_SMOKE_PASS")
    else:
        print(f"V3_SMOKE_FAIL: {report['status']}")
        raise SystemExit(1)


def select_smoke_manifest_rows(
    manifest: Sequence[Mapping[str, Any]],
    *,
    max_samples: int | None,
    allow_underpowered_diagnostic: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select a task-balanced smoke manifest before any API call."""

    if max_samples is not None and max_samples <= 0:
        raise RuntimeError("--max-samples must be positive when provided.")
    by_task = _rows_by_task(manifest)
    available_by_task = {task: len(by_task.get(task, [])) for task in V3_TASK_ORDER}
    gate_min = int(V3_SMOKE_GATES["valid_trace_min_per_task"])

    if max_samples is None:
        target_by_task = dict(available_by_task)
    else:
        target_by_task = _balanced_target_counts(
            max_samples,
            available_by_task=available_by_task,
        )

    underpowered = any(target_by_task.get(task, 0) < gate_min for task in V3_TASK_ORDER)
    if underpowered and not allow_underpowered_diagnostic:
        raise RuntimeError(
            "--max-samples creates an underpowered diagnostic; pass "
            "--allow-underpowered-diagnostic or run at least 95 rows per task."
        )

    selected_by_task = {
        task: [dict(row) for row in by_task.get(task, [])[: target_by_task.get(task, 0)]]
        for task in V3_TASK_ORDER
    }
    selected = _round_robin_task_rows(selected_by_task)
    selected_by_task_counts = Counter(str(row.get("task_type") or "") for row in selected)
    return selected, {
        "selection_policy": "task_stratified_round_robin",
        "underpowered_diagnostic": bool(underpowered),
        "max_samples": max_samples,
        "available_count_by_task": available_by_task,
        "selected_count_by_task": {
            task: int(selected_by_task_counts.get(task, 0)) for task in V3_TASK_ORDER
        },
        "valid_trace_min_per_task": gate_min,
    }


def build_smoke_run_metadata(
    *,
    manifest: Sequence[Mapping[str, Any]],
    prompt_template: str,
    selection_report: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "artifact": "v3_smoke_run_metadata",
        "scope": REAL_TASK_V3_1_SMOKE_ONLY,
        "prompt_sha256": _sha256_text(prompt_template),
        "manifest_sha256": _records_sha256(manifest),
        "manifest_row_count": len(manifest),
        "manifest_count_by_task": dict(selection_report.get("selected_count_by_task") or {}),
        "selection_report": dict(selection_report),
        "span_policy": {
            "minimum_reflection_spans_per_original": V3_MIN_REFLECTION_SPANS,
            "scored_spans_per_trace_max": V3_MAX_SCORED_SPANS_PER_TRACE,
            "span_selection": "first_three_by_observable_order",
        },
        "intervention_contract": dict(V3_INTERVENTION_CONTRACT),
        "gates": dict(V3_SMOKE_GATES),
        "delta_epsilon": V3_DELTA_EPSILON,
        "current_status_remains": "PILOT_BLOCKED",
    }


def assert_smoke_resume_allowed(output_dir: Path, expected_metadata: Mapping[str, Any]) -> None:
    """Reject mixed check-point resumes unless metadata exactly matches."""

    metadata_path = output_dir / SMOKE_METADATA_NAME
    existing_artifacts = [
        name for name in SMOKE_ARTIFACT_NAMES if (output_dir / name).exists()
    ]
    if existing_artifacts and not metadata_path.exists():
        raise RuntimeError(
            f"Existing smoke artifacts require {SMOKE_METADATA_NAME}; use a new --output-dir."
        )
    if not metadata_path.exists():
        return
    try:
        observed = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{SMOKE_METADATA_NAME} is not valid JSON.") from exc
    if observed != dict(expected_metadata):
        raise RuntimeError(
            f"{SMOKE_METADATA_NAME} does not match the requested smoke run; use a new --output-dir."
        )


def original_trace_validation_errors(record: Mapping[str, Any]) -> list[str]:
    spans = record.get("reflection_spans")
    span_count = len(spans) if isinstance(spans, list) else 0
    if span_count < V3_MIN_REFLECTION_SPANS:
        return ["reflection_spans: at least 3 reflection blocks required for V3 smoke"]
    return []


def build_v3_smoke_prefixes(
    original_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    prefixes: list[dict[str, Any]] = []
    for record in original_records:
        if original_trace_validation_errors(record):
            continue
        spans = sorted(
            list(record.get("reflection_spans") or []),
            key=lambda span: int(span.get("start_char", span.get("span_index", 0)) or 0),
        )
        for span in spans[:V3_MAX_SCORED_SPANS_PER_TRACE]:
            try:
                prefix = build_replay_prefix(
                    record,
                    span_index=int(span.get("span_index", 0) or 0),
                )
            except Exception:
                continue
            prefix["intervention_type"] = V3_INTERVENTION_CONTRACT["intervention_type"]
            prefix["intervention_implementation"] = V3_INTERVENTION_CONTRACT[
                "intervention_implementation"
            ]
            prefix["replace_intervention_in_current_v3"] = True
            prefixes.append(prefix)
    return prefixes


def build_smoke_report_for_test(**kwargs: Any) -> dict[str, Any]:
    return _build_smoke_report(**kwargs)


def compute_v3_delta_rows_for_test(
    original_records: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return _compute_v3_delta_rows(
        original_records=original_records,
        replay_results=replay_results,
    )


def _rows_by_task(manifest: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    by_task: dict[str, list[Mapping[str, Any]]] = {task: [] for task in V3_TASK_ORDER}
    for row in manifest:
        task_type = str(row.get("task_type") or "")
        if task_type in by_task:
            by_task[task_type].append(row)
    return by_task


def _balanced_target_counts(
    max_samples: int,
    *,
    available_by_task: Mapping[str, int],
) -> dict[str, int]:
    task_count = len(V3_TASK_ORDER)
    base = max_samples // task_count
    remainder = max_samples % task_count
    targets: dict[str, int] = {}
    for index, task in enumerate(V3_TASK_ORDER):
        requested = base + (1 if index < remainder else 0)
        available = int(available_by_task.get(task, 0))
        if requested > available:
            raise RuntimeError(f"requested {requested} {task} rows but only {available} are available.")
        targets[task] = requested
    return targets


def _round_robin_task_rows(rows_by_task: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    max_len = max((len(rows_by_task.get(task, [])) for task in V3_TASK_ORDER), default=0)
    for index in range(max_len):
        for task in V3_TASK_ORDER:
            rows = rows_by_task.get(task, [])
            if index < len(rows):
                selected.append(dict(rows[index]))
    return selected


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _records_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    hasher = hashlib.sha256()
    for record in records:
        hasher.update(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        hasher.update(b"\n")
    return hasher.hexdigest()


def _call_chat(
    client: OpenAIClient,
    prompt: str,
    model_name: str,
    *,
    config: Mapping[str, Any],
    json_mode: bool = False,
) -> ChatGenerationResult:
    """Call Chat Completions API and parse JSON result."""

    model_config = config.get("model", {})
    experiment = config.get("experiment", {})
    temperature = float(model_config.get("temperature", 0.0))
    top_p = float(model_config.get("top_p", 1.0))
    max_tokens = int(model_config.get("max_output_tokens", 2048))
    seed = int(experiment.get("seed", 20260606))

    request_overrides: dict[str, Any] = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "seed": seed,
        "extra_body": {"enable_thinking": False},
    }
    if json_mode:
        request_overrides["response_format"] = {"type": "json_object"}

    response = client.chat_complete(
        prompt=prompt,
        model_name=model_name,
        temperature=temperature,
        top_p=top_p,
        seed=seed,
        max_output_tokens=max_tokens,
        request_overrides=request_overrides,
    )

    raw_text = response.raw_output
    fingerprint = response.metadata.get("system_fingerprint")
    usage = dict(response.usage)

    parsed = parse_json_object(raw_text)
    errors: list[str] = []

    if parsed is None:
        errors.append("<root>: response is not a JSON object")
        return ChatGenerationResult(
            record=None,
            raw_output=raw_text,
            model_name=response.model_name,
            system_fingerprint=fingerprint,
            usage=usage,
            validation_errors=errors,
            cost_usd=response.cost_usd,
            cached=response.cached,
        )

    trace = str(parsed.get("observable_trace") or parsed.get("visible_solution_trace") or "")
    final_answer = str(parsed.get("final_answer") or "")
    record = {
        "sample_id": "",
        "task_id": "",
        "task_type": "",
        "question": "",
        "observable_trace": trace,
        "reflection_spans": [],
        "final_answer": final_answer,
        "reference_answer": "",
        "aliases": [],
        "correctness": False,
        "model_name": response.model_name,
        "generation_config": {
            "model": model_name,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "seed": seed,
            "json_mode": json_mode,
        },
        "system_fingerprint": fingerprint,
        "usage": usage,
    }
    return ChatGenerationResult(
        record=record,
        raw_output=raw_text,
        model_name=response.model_name,
        system_fingerprint=fingerprint,
        usage=usage,
        validation_errors=[],
        cost_usd=response.cost_usd,
        cached=response.cached,
    )


def _stage_generate_chat(
    *,
    manifest: Sequence[Mapping[str, Any]],
    client: OpenAIClient,
    config: Mapping[str, Any],
    prompt_template: str,
    output_dir: Path,
    approved_budget_usd: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Generate original traces via Chat Completions API (parallel)."""

    traces_path = output_dir / "smoke_original_traces.jsonl"
    attempts_path = output_dir / "smoke_original_attempts.jsonl"

    existing_traces = _load_if_exists(traces_path)
    existing_attempts = _load_if_exists(attempts_path)
    existing_ids = {str(r.get("sample_id") or "") for r in existing_traces}

    model_config = config.get("model", {})
    model_name = str(model_config.get("primary") or "deepseek-v4-flash")

    attempts: list[dict[str, Any]] = list(existing_attempts)
    new_traces: list[dict[str, Any]] = []
    attempts_lock = threading.Lock()
    traces_lock = threading.Lock()

    samples_to_process = [
        s for s in manifest if str(s.get("sample_id") or "") not in existing_ids
    ]

    if not samples_to_process:
        all_traces = list(existing_traces)
        cost_usd = sum(a.get("cost_usd", 0.0) or 0.0 for a in attempts)
        print(f"  generation: {len(all_traces)} valid traces (all cached), ${cost_usd:.4f}")
        return all_traces, attempts, cost_usd

    def _process_one(sample: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        sample_id = str(sample.get("sample_id") or "")
        prompt = build_generation_prompt(prompt_template, sample)
        thread_client = _get_thread_client(config, approved_budget_usd)

        result = _call_chat(thread_client, prompt, model_name, config=config, json_mode=False)
        if result.record is None:
            result = _call_chat(thread_client, prompt, model_name, config=config, json_mode=True)

        record_errors: list[str] = []
        valid_record: dict[str, Any] | None = None
        if result.record is not None:
            record = result.record
            record["sample_id"] = sample_id
            record["task_id"] = str(sample.get("task_id") or sample_id)
            record["task_type"] = str(sample.get("task_type") or "")
            record["question"] = str(sample.get("question") or "")
            record["reference_answer"] = str(sample.get("reference_answer") or "")
            record["aliases"] = list(sample.get("aliases") or [])

            from fma.real_task_pilot.parsing import extract_reflection_spans, extract_final_answer
            trace = record["observable_trace"]
            record["reflection_spans"] = extract_reflection_spans(trace)
            if not record["final_answer"]:
                record["final_answer"] = extract_final_answer(trace) or ""

            record_errors = original_trace_validation_errors(record)
            if not record_errors:
                valid_record = record

        attempt = {
            "sample_id": sample_id,
            "task_type": sample.get("task_type"),
            "valid": valid_record is not None,
            "model_name": result.model_name,
            "system_fingerprint": result.system_fingerprint,
            "validation_errors": [*result.validation_errors, *record_errors],
            "cost_usd": result.cost_usd,
            "cached": result.cached,
            "usage": result.usage,
        }
        return valid_record, attempt

    max_workers = int(config.get("experiment", {}).get("max_workers", 10))
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sample = {executor.submit(_process_one, s): s for s in samples_to_process}
        for future in as_completed(future_to_sample):
            valid_record, attempt = future.result()
            with attempts_lock:
                attempts.append(attempt)
            if valid_record is not None:
                with traces_lock:
                    new_traces.append(valid_record)
            completed += 1
            progress = len(existing_traces) + len(new_traces)
            sample_id = str(future_to_sample[future].get("sample_id") or "")
            print(f"  [{progress}/{len(manifest)}] {sample_id} {'OK' if valid_record else 'FAIL'}")

            if completed % 10 == 0:
                all_traces = list(existing_traces) + new_traces
                _locked_write_records(all_traces, traces_path)
                _locked_write_records(attempts, attempts_path)

    all_traces = list(existing_traces) + new_traces
    _locked_write_records(all_traces, traces_path)
    _locked_write_records(attempts, attempts_path)

    cost_usd = sum(a.get("cost_usd", 0.0) or 0.0 for a in attempts)
    print(f"  generation: {len(all_traces)} valid traces, ${cost_usd:.4f}")
    return all_traces, attempts, cost_usd


def _stage_build_prefixes(
    original_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build one replay prefix per span from original records."""

    return build_v3_smoke_prefixes(original_records)


def _stage_replay_chat(
    *,
    prefixes: Sequence[Mapping[str, Any]],
    client: OpenAIClient,
    config: Mapping[str, Any],
    prompt_template: str,
    output_dir: Path,
    repeats: int,
    approved_budget_usd: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Run intervention replay via Chat Completions API (parallel)."""

    results_path = output_dir / "smoke_replay_results.jsonl"
    attempts_path = output_dir / "smoke_replay_attempts.jsonl"

    existing_results = _load_if_exists(results_path)
    existing_attempts = _load_if_exists(attempts_path)

    jobs = missing_replay_jobs(prefixes, existing_results, repeats=repeats)
    if not jobs:
        print(f"  replay: {len(existing_results)} results already complete (no new jobs)")
        return existing_results, existing_attempts, 0.0

    model_config = config.get("model", {})
    model_name = str(model_config.get("primary") or "deepseek-v4-flash")
    replay_prompt = _replay_prompt_template(prompt_template)

    attempts: list[dict[str, Any]] = list(existing_attempts)
    new_results: list[dict[str, Any]] = []
    attempts_lock = threading.Lock()
    results_lock = threading.Lock()

    def _process_one(job: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        sample_id = str(job.get("sample_id") or "")
        span_index = int(job.get("span_index", 0))
        repeat_index = int(job.get("repeat_index", 0))

        sample = {
            "sample_id": sample_id,
            "task_id": job.get("task_id", ""),
            "task_type": job.get("task_type", ""),
            "question": job.get("question", ""),
            "reference_answer": job.get("reference_answer", ""),
            "aliases": job.get("aliases", []),
            "observable_prefix": job.get("observable_prefix", ""),
        }
        prompt = build_generation_prompt(replay_prompt, sample)
        thread_client = _get_thread_client(config, approved_budget_usd)

        result = _call_chat(thread_client, prompt, model_name, config=config, json_mode=False)
        if result.record is None:
            result = _call_chat(thread_client, prompt, model_name, config=config, json_mode=True)

        intervened = dict(result.record or {})
        intervened["sample_id"] = sample_id
        intervened["span_index"] = span_index
        intervened["repeat_index"] = repeat_index
        intervened["intervention_type"] = job.get("intervention_type", "REPLACE")
        intervened["intervention_implementation"] = job.get(
            "intervention_implementation",
            "length_preserving_masked_delete",
        )

        valid_result: dict[str, Any] | None = None
        if result.record is not None:
            from fma.real_task_pilot.parsing import extract_reflection_spans, extract_final_answer
            trace = intervened["observable_trace"]
            intervened["reflection_spans"] = extract_reflection_spans(trace)
            if not intervened.get("final_answer"):
                intervened["final_answer"] = extract_final_answer(trace) or ""
            intervened["status"] = "success"
            intervened["task_type"] = job.get("task_type", "")
            intervened["reference_answer"] = job.get("reference_answer", "")
            intervened["aliases"] = list(job.get("aliases") or [])
            valid_result = intervened

        attempt = {
            "sample_id": sample_id,
            "span_index": span_index,
            "repeat_index": repeat_index,
            "intervention_type": job.get("intervention_type", "REPLACE"),
            "intervention_implementation": job.get(
                "intervention_implementation",
                "length_preserving_masked_delete",
            ),
            "valid": result.record is not None,
            "model_name": result.model_name,
            "system_fingerprint": result.system_fingerprint,
            "cost_usd": result.cost_usd,
            "cached": result.cached,
            "usage": result.usage,
        }
        return valid_result, attempt

    max_workers = int(config.get("experiment", {}).get("max_workers", 10))
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {executor.submit(_process_one, j): j for j in jobs}
        for future in as_completed(future_to_job):
            valid_result, attempt = future.result()
            with attempts_lock:
                attempts.append(attempt)
            if valid_result is not None:
                with results_lock:
                    new_results.append(valid_result)
            completed += 1
            progress = len(existing_results) + len(new_results)
            total = len(existing_results) + len(jobs)
            job = future_to_job[future]
            sample_id = str(job.get("sample_id") or "")
            span_index = int(job.get("span_index", 0))
            repeat_index = int(job.get("repeat_index", 0))
            print(f"  replay [{progress}/{total}] {sample_id} span={span_index} r={repeat_index} {'OK' if valid_result else 'FAIL'}")

            if completed % 10 == 0:
                all_results = list(existing_results) + new_results
                _locked_write_records(all_results, results_path)
                _locked_write_records(attempts, attempts_path)

    all_results = list(existing_results) + new_results
    _locked_write_records(all_results, results_path)
    _locked_write_records(attempts, attempts_path)

    cost_usd = sum(a.get("cost_usd", 0.0) or 0.0 for a in attempts)
    print(f"  replay: {len(all_results)} results, ${cost_usd:.4f}")
    return all_results, attempts, cost_usd


def _replay_prompt_template(original_template: str) -> str:
    """Adapt the generation prompt for REPLACE replay with observable_prefix."""
    return (
        "You are continuing a partially-written solution trace for a benchmark item. "
        "Return JSON with exactly these keys: observable_trace and final_answer. "
        "Continue the trace from where it left off. Some reflection blocks in the "
        "partial trace have been replaced with [REASONING_MASK] — you must continue "
        "reasoning without the information those blocks would have provided.\n\n"
        "Task type: {task_type}\n"
        "Question:\n{question}\n\n"
        "Partial trace so far:\n{observable_prefix}\n\n"
        "Continue from here. Include any remaining reflection blocks if needed. "
        "End with Final Answer: <answer>"
    )


def _stage_delta_u(
    *,
    original_records: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
    output_dir: Path,
) -> list[dict[str, Any]]:
    """Compute v3 dense Delta-U for each span."""

    delta_rows = _compute_v3_delta_rows(
        original_records=original_records,
        replay_results=replay_results,
    )
    write_records(delta_rows, output_dir / "smoke_delta_u.jsonl")
    return delta_rows


def _compute_v3_delta_rows(
    *,
    original_records: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    original_by_id = {str(r.get("sample_id")): r for r in original_records}
    grouped: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for r in replay_results:
        sid = str(r.get("sample_id") or "")
        si = int(r.get("span_index", 0) or 0)
        grouped[(sid, si)].append(r)

    delta_rows = []
    for (sample_id, span_index), repeats in sorted(grouped.items()):
        original = original_by_id.get(sample_id)
        if original is None:
            continue
        task_type = str(original.get("task_type") or "")
        reference = str(original.get("reference_answer") or "")
        aliases = list(original.get("aliases") or [])
        original_final = str(original.get("final_answer") or "")

        original_score = _score_v3(task_type, original_final, reference, aliases)
        intervened_scores = [
            _score_v3(task_type, str(r.get("final_answer") or ""), reference, aliases)
            for r in repeats
        ]
        intervened_mean = sum(intervened_scores) / len(intervened_scores) if intervened_scores else 0.0

        delta_rows.append({
            "sample_id": sample_id,
            "task_type": task_type,
            "span_index": span_index,
            "repeat_count": len(repeats),
            "original_utility": original_score,
            "intervened_mean_utility": intervened_mean,
            "delta_u": original_score - intervened_mean,
            "metric": "dense_real_task_delta_u_v3",
            "intervention_type": "REPLACE",
            "intervention_implementation": "length_preserving_masked_delete",
        })

    return delta_rows


def _score_v3(
    task_type: str,
    prediction: str,
    reference: str,
    aliases: list[str],
) -> float:
    if task_type == "gsm8k":
        result = score_gsm8k_v3_utility(
            predictions=[prediction],
            reference_answer=reference,
        )
    else:
        result = score_hotpotqa_v3_utility(
            prediction=prediction,
            reference_answer=reference,
            aliases=aliases,
        )
    return float(result.get("utility", 0.0) or 0.0)


def _build_smoke_report(
    *,
    original_records: Sequence[Mapping[str, Any]],
    original_attempts: Sequence[Mapping[str, Any]],
    replay_prefixes: Sequence[Mapping[str, Any]],
    replay_results: Sequence[Mapping[str, Any]],
    replay_attempts: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
    cost_usd: float,
    approved_budget_usd: float,
    selection_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate smoke results against v3 thresholds."""

    active_selection_report = dict(selection_report or {"underpowered_diagnostic": False})
    gsm8k_traces = [r for r in original_records if r.get("task_type") == "gsm8k"]
    hotpotqa_traces = [r for r in original_records if r.get("task_type") == "hotpotqa"]
    valid_gsm8k = len(gsm8k_traces)
    valid_hotpotqa = len(hotpotqa_traces)
    eligible_spans = len(replay_prefixes)
    generated_span_count = sum(
        len(record.get("reflection_spans") or [])
        for record in original_records
    )
    total_api_calls = len(original_attempts) + len(replay_attempts)

    gsm8k_nonzero = [
        d for d in delta_rows
        if d.get("task_type") == "gsm8k"
        and abs(float(d.get("delta_u", 0.0) or 0.0)) > V3_DELTA_EPSILON
    ]
    hotpotqa_nonzero = [
        d for d in delta_rows
        if d.get("task_type") == "hotpotqa"
        and abs(float(d.get("delta_u", 0.0) or 0.0)) > V3_DELTA_EPSILON
    ]

    non_cached_attempts = [a for a in original_attempts + replay_attempts if not a.get("cached", False)]
    transport_failures = sum(
        1 for a in non_cached_attempts if not a.get("valid", True)
    )
    transport_rate = (
        1.0 - transport_failures / max(1, len(non_cached_attempts))
        if len(non_cached_attempts) > 0
        else 1.0
    )

    checks = {
        "gsm8k_trace_count": valid_gsm8k >= V3_SMOKE_GATES["valid_trace_min_per_task"],
        "hotpotqa_trace_count": valid_hotpotqa >= V3_SMOKE_GATES["valid_trace_min_per_task"],
        "eligible_span_count": eligible_spans >= V3_SMOKE_GATES["eligible_span_min_pooled"],
        "nonzero_delta_gsm8k": len(gsm8k_nonzero) >= V3_SMOKE_GATES["nonzero_delta_gsm8k_min"],
        "nonzero_delta_hotpotqa": len(hotpotqa_nonzero) >= V3_SMOKE_GATES["nonzero_delta_hotpotqa_min"],
        "transport_success_rate": transport_rate >= V3_SMOKE_GATES["transport_success_rate_min"],
        "cost_within_budget": cost_usd <= approved_budget_usd,
        "api_calls_within_cap": total_api_calls <= V3_SMOKE_GATES["smoke_api_calls_max"],
    }

    if not checks["cost_within_budget"]:
        status = V3_SMOKE_FAIL_COST
        next_step = "STOP_AND_FIX_SMOKE_COST"
    elif not checks["gsm8k_trace_count"] or not checks["hotpotqa_trace_count"]:
        status = V3_SMOKE_FAIL_INSUFFICIENT_TRACES
        next_step = (
            "RERUN_FULL_V3_DELETE_SMOKE"
            if active_selection_report.get("underpowered_diagnostic") is True
            else "FIX_GENERATION_PIPELINE"
        )
    elif not checks["eligible_span_count"]:
        status = V3_SMOKE_FAIL_INSUFFICIENT_SPANS
        next_step = "FIX_REFLECTION_EXTRACTION"
    elif not checks["nonzero_delta_gsm8k"]:
        status = V3_SMOKE_FAIL_SPARSE_SIGNAL_GSM8K
        next_step = "REQUEST_V3_1_REPLACE_PREREGISTRATION"
    elif not checks["nonzero_delta_hotpotqa"]:
        status = V3_SMOKE_FAIL_SPARSE_SIGNAL_HOTPOTQA
        next_step = "REQUEST_V3_1_REPLACE_PREREGISTRATION"
    elif not checks["transport_success_rate"]:
        status = V3_SMOKE_FAIL_GENERATION
        next_step = "FIX_TRANSPORT_ISSUES"
    else:
        status = V3_SMOKE_PASS
        next_step = "REQUEST_DEV_CALIBRATION_BUDGET"

    return {
        "artifact": "v3_smoke_report",
        "scope": REAL_TASK_V3_1_SMOKE_ONLY,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "manifest_row_count": len(original_attempts),
        "valid_trace_count": len(original_records),
        "gsm8k_trace_count": valid_gsm8k,
        "hotpotqa_trace_count": valid_hotpotqa,
        "generated_span_count": generated_span_count,
        "eligible_span_count": eligible_spans,
        "scored_span_count": eligible_spans,
        "replay_result_count": len(replay_results),
        "delta_row_count": len(delta_rows),
        "nonzero_delta_gsm8k": len(gsm8k_nonzero),
        "nonzero_delta_hotpotqa": len(hotpotqa_nonzero),
        "delta_epsilon": V3_DELTA_EPSILON,
        "total_api_calls": total_api_calls,
        "transport_failure_count": transport_failures,
        "transport_success_rate": transport_rate,
        "cost_used_usd": cost_usd,
        "approved_budget_usd": approved_budget_usd,
        "underpowered_diagnostic": bool(active_selection_report.get("underpowered_diagnostic")),
        "selection_report": active_selection_report,
        "intervention_type": "REPLACE",
        "intervention_implementation": "length_preserving_masked_delete",
        "v3_1_replace_preregistration": dict(V3_1_REPLACE_PREREGISTRATION),
        "gates": V3_SMOKE_GATES,
        "checks": checks,
        "next_allowed_step": next_step,
        "current_status_remains": "PILOT_BLOCKED",
        "api_allowed_after_smoke": status == V3_SMOKE_PASS
        and active_selection_report.get("underpowered_diagnostic") is not True,
        "claim_upgrade_allowed": False,
        "validation_claim_allowed": False,
        "prm_filtering_claim_allowed": False,
    }


def _build_client(
    config: Mapping[str, Any],
    *,
    approved_budget_usd: float,
) -> OpenAIClient:
    """Build OpenAIClient pointing at the configured Chat Completions endpoint."""

    import os

    api_config = config.get("api", {})
    model_config = config.get("model", {})
    raw_endpoint = str(api_config.get("chat_completions_endpoint") or "")
    primary_model = str(model_config.get("primary") or "deepseek-v4-flash")
    api_key_env = str(api_config.get("api_key_env") or "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"API key env variable {api_key_env!r} is not set.")

    base_url = raw_endpoint.rstrip("/")
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]

    client = OpenAIClient(
        model_name=primary_model,
        api_key=api_key,
        base_url=base_url if base_url else None,
        endpoint="chat_completions",
        cache_enabled=False,
    )
    if hasattr(client, "cost_tracker") and client.cost_tracker is not None:
        client.cost_tracker.cost_ceiling_usd = approved_budget_usd
    return client


def _write_cost_report(
    path: Path,
    *,
    total_cost: float,
    original_cost: float,
    replay_cost: float,
    approved_budget_usd: float,
) -> None:
    _write_json(
        path,
        {
            "artifact": "v3_smoke_cost_report",
            "total_cost_usd": total_cost,
            "original_generation_cost_usd": original_cost,
            "replay_cost_usd": replay_cost,
            "approved_budget_usd": approved_budget_usd,
            "within_budget": total_cost <= approved_budget_usd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def _load_config(path: Path) -> dict[str, Any]:
    import yaml
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    payload["_config_path"] = str(path)
    return payload


def _load_if_exists(path: Path) -> list[dict[str, Any]]:
    if path.exists():
        return load_records(path)
    return []


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
