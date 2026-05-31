"""Thin runner for the real-task FMA pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.real_task_pilot.baselines import build_baseline_leakage_audit, score_independent_baselines
from fma.real_task_pilot.config import load_pilot_config, output_dir
from fma.real_task_pilot.controls import control_report_skeleton
from fma.real_task_pilot.hygiene import candidate_files, render_hygiene_markdown, scan_hygiene
from fma.real_task_pilot.generation import (
    GeneratedTraceResult,
    build_generation_summary,
    generate_trace_with_fallback,
    load_prompt_template,
)
from fma.real_task_pilot.openai_client import OpenAIResponsesAdapter
from fma.real_task_pilot.preflight import evaluate_preflight
from fma.real_task_pilot.protocol import (
    build_api_determinism_blocker,
    build_nondeterministic_protocol,
    protocol_allows_generation,
)
from fma.real_task_pilot.readiness import build_readiness_audit
from fma.real_task_pilot.replay import build_replay_prefix, compute_delta_u
from fma.real_task_pilot.sampling import (
    build_sample_manifest,
    normalize_real_task_source_row,
    validate_manifest_for_live_api,
    write_manifest,
)


STAGES = (
    "hygiene",
    "export-data",
    "manifest",
    "seed-probe",
    "protocol-revision",
    "api-preflight",
    "api-pilot",
    "preflight-eval",
    "replay-prefixes",
    "delta-u",
    "baselines",
    "controls",
    "readiness",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run guarded real-task pilot utilities.")
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs") / "real_task_pilot.yaml")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--intervened-input", type=Path, default=None)
    parser.add_argument("--gsm8k-input", type=Path, default=None)
    parser.add_argument("--hotpotqa-input", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--allow-api", action="store_true", help="Reserved guard for future live API calls.")
    parser.add_argument("--tests-passed", action="store_true", help="Mark the local test suite as passed for readiness audit.")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    config = load_pilot_config(args.config)
    root = args.output_dir or output_dir(config)
    root.mkdir(parents=True, exist_ok=True)

    if args.stage == "hygiene":
        report = scan_hygiene(candidate_files(PROJECT_ROOT))
        (root / "hygiene_audit.md").write_text(render_hygiene_markdown(report), encoding="utf-8")
        write_json(root / "hygiene_audit.json", report)
        print(f"Wrote hygiene audit to {root / 'hygiene_audit.md'}")
        return

    if args.stage == "export-data":
        paths = export_real_task_data(config)
        print(
            "Wrote real-task source exports: "
            + ", ".join(f"{task}={path}" for task, path in sorted(paths.items()))
        )
        return

    if args.stage == "manifest":
        if args.gsm8k_input is None or args.hotpotqa_input is None:
            raise ValueError("--gsm8k-input and --hotpotqa-input are required for stage 'manifest'.")
        gsm8k_rows = load_records(args.gsm8k_input)
        hotpotqa_rows = load_records(args.hotpotqa_input)
        max_per_task = int(config.get("experiment", {}).get("max_samples_per_task", 200))
        manifest = build_sample_manifest(
            gsm8k_rows,
            hotpotqa_rows,
            seed=int(config["experiment"]["seed"]),
            max_per_task=max_per_task,
        )
        path = Path(config["experiment"].get("sample_manifest", root / "sample_manifest.json"))
        write_manifest(manifest, path)
        print(f"Wrote {len(manifest)} manifest rows to {path}")
        return

    if args.input is None:
        raise ValueError(f"--input is required for stage {args.stage!r}.")

    records = load_records(args.input)
    if args.stage in {"seed-probe", "api-preflight", "api-pilot"}:
        _assert_live_manifest(records, source_path=args.input)

    if args.stage == "seed-probe":
        if not args.allow_api:
            raise RuntimeError("stage 'seed-probe' requires --allow-api to prevent accidental API spend.")
        adapter = OpenAIResponsesAdapter()
        prompt_template = load_prompt_template(config["generation"]["prompt_file"])
        report = run_seed_model_probe(
            records[0],
            adapter=adapter,
            config=config,
            prompt_template=prompt_template,
        )
        write_json(root / "seed_model_probe.json", report)
        print(f"Wrote seed/model compatibility probe to {root / 'seed_model_probe.json'}")
        return

    if args.stage == "protocol-revision":
        preflight_report = _read_json(root / "api_preflight_report.json", default={})
        seed_transport_report = _read_json(root / "seed_transport_report.json", default={})
        seed_model_probe = _read_json(root / "seed_model_probe.json", default={})
        blocker = build_api_determinism_blocker(
            api_preflight_report=preflight_report,
            seed_transport_report=seed_transport_report,
            seed_model_probe=seed_model_probe,
        )
        protocol = build_nondeterministic_protocol(config=config, blocker=blocker)
        write_json(root / "api_determinism_blocker.json", blocker)
        write_json(root / "nondeterministic_protocol.json", protocol)
        (root / "nondeterministic_protocol.md").write_text(
            render_nondeterministic_protocol_markdown(blocker, protocol),
            encoding="utf-8",
        )
        print(f"Wrote protocol revision artifacts to {root}")
        return

    if args.stage == "api-preflight":
        if not args.allow_api:
            raise RuntimeError("stage 'api-preflight' requires --allow-api to prevent accidental API spend.")
        adapter = OpenAIResponsesAdapter()
        prompt_template = load_prompt_template(config["generation"]["prompt_file"])
        preflight_n = int(config.get("experiment", {}).get("preflight_samples", 20))
        if preflight_n != 20:
            raise RuntimeError("stage 'api-preflight' is fixed to exactly 20 attempts for this pilot.")
        if len(records) < preflight_n:
            raise RuntimeError(f"stage 'api-preflight' requires at least {preflight_n} manifest rows.")
        results = []
        for sample in records[:preflight_n]:
            results.append(generate_trace_with_fallback(
                sample,
                adapter=adapter,
                config=config,
                prompt_template=prompt_template,
            ))
            _write_generation_checkpoint(root, "preflight", results)
        seed_report = _seed_transport_report(results)
        drift_results = []
        if seed_report["seed_sent_rate"] > 0.0:
            for _index in range(3):
                if not records:
                    break
                drift_results.append(generate_trace_with_fallback(
                    records[0],
                    adapter=adapter,
                    config=config,
                    prompt_template=prompt_template,
                ))
        valid_records = [result.record for result in results if result.record is not None]
        drift_outputs = [
            str(result.record.get("observable_trace"))
            if result.record is not None
            else result.raw_output
            for result in drift_results
        ]
        write_records(valid_records, root / "preflight_traces.jsonl")
        write_json(root / "generation_fallback_report.json", build_generation_summary(results))
        write_json(
            root / "determinism_drift_samples.json",
            [
                {
                    "model_name": result.model_name,
                    "structured_output_mode": result.structured_output_mode,
                    "system_fingerprint": result.system_fingerprint,
                    "valid": result.record is not None,
                }
                for result in drift_results
            ],
        )
        write_json(root / "seed_transport_report.json", seed_report)
        report = evaluate_preflight(
            _preflight_attempt_payloads(results),
            drift_outputs=drift_outputs,
            config=config,
        )
        if seed_report["seed_requested"] and seed_report["seed_sent_rate"] == 0.0:
            _force_preflight_failure(
                report,
                code="PREFLIGHT_FAIL_DRIFT",
                reason="seed transport was rejected by the API, so deterministic drift cannot be verified",
            )
        for name, payload in report.items():
            write_json(root / f"{name}.json", payload)
        print(f"Wrote {len(valid_records)} live preflight traces and reports to {root}")
        return

    if args.stage == "api-pilot":
        if not args.allow_api:
            raise RuntimeError("stage 'api-pilot' requires --allow-api to prevent accidental API spend.")
        preflight_report = _read_json(root / "api_preflight_report.json", default={})
        protocol = _read_json(root / "nondeterministic_protocol.json", default={})
        if preflight_report.get("status") != "pass" and not protocol_allows_generation(protocol):
            raise RuntimeError(
                "stage 'api-pilot' requires either a passing api_preflight_report.json or a preregistered nondeterministic protocol before launching 400 calls."
            )
        adapter = OpenAIResponsesAdapter()
        prompt_template = load_prompt_template(config["generation"]["prompt_file"])
        pilot_n = int(config.get("experiment", {}).get("pilot_generation_requests", 400))
        if len(records) < pilot_n:
            raise RuntimeError(f"stage 'api-pilot' requires at least {pilot_n} manifest rows.")
        existing_attempts = _load_existing_records(root / "pilot_attempts.jsonl")
        valid_records = _load_existing_records(root / "pilot_traces.jsonl")
        existing_summary = _read_json(root / "pilot_generation_fallback_report.json", default={})
        if len(existing_attempts) > pilot_n:
            raise RuntimeError(
                f"existing pilot_attempts.jsonl has {len(existing_attempts)} rows, "
                f"which exceeds target {pilot_n}."
            )
        results: list[GeneratedTraceResult] = []
        for index, sample in enumerate(records[len(existing_attempts):pilot_n], start=len(existing_attempts) + 1):
            write_json(
                root / "pilot_progress.json",
                {
                    "status": "running",
                    "current_index": index,
                    "completed_attempts": len(existing_attempts) + len(results),
                    "target_attempts": pilot_n,
                    "current_sample_id": sample.get("sample_id"),
                },
            )
            result = generate_trace_with_fallback(
                sample,
                adapter=adapter,
                config=config,
                prompt_template=prompt_template,
            )
            results.append(result)
            if result.record is not None:
                valid_records.append(result.record)
            attempts = existing_attempts + _preflight_attempt_payloads(results)
            _write_pilot_checkpoint(
                root,
                attempts=attempts,
                valid_records=valid_records,
                summary=_merge_generation_summary(
                    existing_summary,
                    new_results=results,
                    attempts=attempts,
                    valid_records=valid_records,
                ),
            )
        attempts = existing_attempts + _preflight_attempt_payloads(results)
        _write_pilot_checkpoint(
            root,
            attempts=attempts,
            valid_records=valid_records,
            summary=_merge_generation_summary(
                existing_summary,
                new_results=results,
                attempts=attempts,
                valid_records=valid_records,
            ),
        )
        write_json(
            root / "pilot_progress.json",
            {
                "status": "complete",
                "completed_attempts": len(attempts),
                "valid_records": len(valid_records),
                "target_attempts": pilot_n,
            },
        )
        print(f"Wrote {len(valid_records)} live pilot traces to {root / 'pilot_traces.jsonl'}")
        return

    if args.stage == "preflight-eval":
        report = evaluate_preflight(records, config=config)
        for name, payload in report.items():
            write_json(root / f"{name}.json", payload)
        print(f"Wrote preflight reports to {root}")
        return

    if args.stage == "replay-prefixes":
        prefixes = []
        max_spans = int(config.get("replay", {}).get("max_spans_per_trace", 3))
        mask_token = str(config.get("replay", {}).get("mask_token", "[REASONING_MASK]"))
        for record in records:
            span_count = len(record.get("reflection_spans") or [])
            for span_index in range(min(span_count, max_spans)):
                prefixes.append(
                    build_replay_prefix(record, span_index=span_index, mask_token=mask_token)
                )
        write_records(prefixes, root / "replay_prefixes.jsonl")
        print(f"Wrote {len(prefixes)} replay prefixes to {root / 'replay_prefixes.jsonl'}")
        return

    if args.stage == "delta-u":
        if args.intervened_input is None:
            raise ValueError("--intervened-input is required for stage 'delta-u'.")
        intervened_records = load_records(args.intervened_input)
        original_by_id = {str(record.get("sample_id")): record for record in records}
        deltas = []
        for intervened in intervened_records:
            sample_id = str(intervened.get("sample_id"))
            if sample_id not in original_by_id:
                continue
            delta = compute_delta_u(original_by_id[sample_id], intervened)
            if "span_index" in intervened:
                delta["span_index"] = intervened["span_index"]
            deltas.append(delta)
        write_records(deltas, root / "real_task_delta_u.jsonl")
        print(f"Wrote {len(deltas)} Delta U rows to {root / 'real_task_delta_u.jsonl'}")
        return

    if args.stage == "baselines":
        rows = score_independent_baselines(records, seed=int(config["experiment"]["seed"]))
        audit = build_baseline_leakage_audit(rows)
        write_records(rows, root / "independent_baseline_scores.jsonl")
        write_json(root / "baseline_leakage_audit.json", audit)
        print(f"Wrote {len(rows)} baseline scores to {root}")
        return

    if args.stage == "controls":
        write_json(root / "trajectory_controls_report.json", control_report_skeleton())
        print(f"Wrote trajectory control skeleton to {root / 'trajectory_controls_report.json'}")
        return

    if args.stage == "readiness":
        preflight_report = _read_json(root / "api_preflight_report.json", default={"status": "missing", "failure_codes": ["PREFLIGHT_FAIL_MODEL"]})
        hygiene_report = _read_json(root / "hygiene_audit.json", default={"hygiene_clean": False})
        baseline_audit = _read_json(root / "baseline_leakage_audit.json", default={"target_leakage_status": "missing"})
        cost_report = _read_json(root / "cost_and_rate_limit_report.json", default={})
        signal_report = _read_json(root / "rank_signal_report.json", default={})
        valid_trace_count = len(records)
        span_validity_rate = _span_validity_rate(records)
        replay_success_rate = _replay_success_rate(root)
        audit = build_readiness_audit(
            preflight_report=preflight_report,
            valid_trace_count=valid_trace_count,
            span_validity_rate=span_validity_rate,
            replay_success_rate=replay_success_rate,
            baseline_leakage_clean=baseline_audit.get("target_leakage_status") == "clean",
            cost_report_complete=bool(cost_report.get("projected_requests")),
            tests_passed=args.tests_passed,
            hygiene_clean=bool(hygiene_report.get("hygiene_clean")),
            signal_report=signal_report,
        )
        write_json(root / "readiness_audit.json", audit)
        print(f"Wrote readiness audit to {root / 'readiness_audit.json'}; status={audit['status']}")
        return


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def export_real_task_data(config: dict[str, Any]) -> dict[str, Path]:
    """Export normalized real benchmark rows for the pilot manifest."""

    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("datasets is required for stage 'export-data'.") from exc

    tasks = config.get("data", {}).get("tasks", {})
    export_dir = Path(config.get("data", {}).get("export_dir", Path("data") / "real_task_pilot"))
    export_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for task_type, task_config in tasks.items():
        dataset_name = str(task_config["dataset"])
        dataset_config = str(task_config.get("config") or "")
        split = str(task_config["split"])
        dataset = load_dataset(dataset_name, dataset_config, split=split)
        rows = [
            normalize_real_task_source_row(
                row,
                task_type=task_type,
                source_dataset=dataset_name,
                source_config=dataset_config,
                source_split=split,
                source_index=index,
            )
            for index, row in enumerate(dataset)
        ]
        output_path = export_dir / f"{task_type}_{split}.jsonl"
        write_records(rows, output_path)
        outputs[task_type] = output_path
    return outputs


def run_seed_model_probe(
    sample: dict[str, Any],
    *,
    adapter: OpenAIResponsesAdapter,
    config: dict[str, Any],
    prompt_template: str,
) -> dict[str, Any]:
    models = list(
        config.get("seed_probe", {}).get(
            "models",
            ["gpt-5.5", "gpt-5.4", "gpt-5.1", "gpt-4o-2024-08-06"],
        )
    )
    repeats = int(config.get("seed_probe", {}).get("repeats", 3))
    model_reports = []
    for model_name in models:
        model_config = _single_model_config(config, model_name)
        results = [
            generate_trace_with_fallback(
                sample,
                adapter=adapter,
                config=model_config,
                prompt_template=prompt_template,
            )
            for _index in range(repeats)
        ]
        outputs = [
            str(result.record.get("observable_trace"))
            if result.record is not None
            else result.raw_output
            for result in results
        ]
        drift_values = []
        for left_index in range(len(outputs)):
            for right_index in range(left_index + 1, len(outputs)):
                from fma.real_task_pilot.preflight import token_diff_ratio

                drift_values.append(token_diff_ratio(outputs[left_index], outputs[right_index]))
        metadata = [
            result.record.get("generation_config", {}).get("api_request_metadata", {})
            for result in results
            if result.record is not None
        ]
        seed_sent_count = sum(1 for item in metadata if item.get("seed_sent"))
        valid_count = sum(1 for result in results if result.record is not None)
        max_drift = max(drift_values) if drift_values else None
        drift_gate_pass = (
            valid_count == repeats
            and max_drift is not None
            and max_drift < 0.05
        )
        model_reports.append(
            {
                "model_name": model_name,
                "attempts": repeats,
                "valid_records": valid_count,
                "seed_sent_count": seed_sent_count,
                "seed_sent_rate": seed_sent_count / repeats if repeats else 0.0,
                "system_fingerprints": sorted(
                    {
                        str(result.system_fingerprint)
                        for result in results
                        if result.system_fingerprint is not None
                    }
                ),
                "max_token_diff_ratio": max_drift,
                "drift_gate_pass": drift_gate_pass,
                "retry_labels": sorted(
                    {str(item.get("retry_label")) for item in metadata if item.get("retry_label")}
                ),
                "sample_retry_errors": [
                    error
                    for item in metadata[:1]
                    for error in item.get("retry_errors", [])
                ],
                "fallback_events": [
                    event
                    for result in results
                    for event in result.fallback_events
                    if event.get("status") != "selected"
                ],
            }
        )
    passing_models = [
        item["model_name"]
        for item in model_reports
        if item["valid_records"] == repeats
        and item["seed_sent_rate"] == 1.0
        and item["drift_gate_pass"]
    ]
    return {
        "sample_id": sample.get("sample_id"),
        "task_type": sample.get("task_type"),
        "repeats": repeats,
        "models": model_reports,
        "passing_models": passing_models,
        "recommended_model": passing_models[0] if passing_models else None,
        "status": "pass" if passing_models else "fail",
    }


def _single_model_config(config: dict[str, Any], model_name: str) -> dict[str, Any]:
    cloned = json.loads(json.dumps(config, default=str))
    cloned.setdefault("model", {})
    cloned["model"]["primary"] = model_name
    cloned["model"]["fallback_order"] = [model_name]
    return cloned


def render_nondeterministic_protocol_markdown(
    blocker: dict[str, Any],
    protocol: dict[str, Any],
) -> str:
    gates = protocol["gates"]
    repeats = protocol["repeats"]
    bootstrap = protocol["bootstrap"]
    return "\n".join(
        [
            "# Non-Deterministic API Pilot Protocol",
            "",
            f"Status: `{protocol['status']}`",
            "",
            "## Blocked Original Route",
            "",
            f"- Blocked route: `{blocker['blocked_route']}`",
            f"- Decision: `{blocker['status']}`",
            f"- Reason: {blocker['decision']['reason']}",
            "",
            "## Replacement Protocol",
            "",
            f"- Disclosure required: `{protocol['disclosure']['required']}`",
            f"- Claim level: `{protocol['run_policy']['claim_level']}`",
            f"- Original generations per sample: `{repeats['original_generation_per_sample']}`",
            f"- Replay repeats per span: `{repeats['replay_per_span']}`",
            f"- Key-sample replay repeats per span: `{repeats['key_sample_replay_per_span']}`",
            f"- Bootstrap resamples: `{bootstrap['resamples']}`",
            f"- Bootstrap confidence level: `{bootstrap['confidence_level']}`",
            "",
            "## Gates",
            "",
            f"- Minimum schema success rate: `{gates['minimum_schema_success_rate']}`",
            f"- Minimum tag success rate: `{gates['minimum_tag_success_rate']}`",
            f"- Minimum valid traces: `{gates['minimum_valid_traces']}`",
            f"- Minimum span validity rate: `{gates['minimum_span_validity_rate']}`",
            f"- Minimum replay success rate: `{gates['minimum_replay_success_rate']}`",
            f"- Effect gate: `{gates['effect_gate']}`",
            "",
            "## Required Disclosure",
            "",
            protocol["disclosure"]["text"],
            "",
        ]
    )


def _assert_live_manifest(records: list[dict[str, Any]], *, source_path: Path) -> None:
    errors = validate_manifest_for_live_api(records, source_path=source_path)
    if errors:
        raise RuntimeError("live API input rejected: " + "; ".join(errors))


def _preflight_attempt_payloads(results: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "preflight_attempt": True,
            "record": result.record,
            "raw_output": result.raw_output,
            "usage": result.usage,
            "model_name": result.model_name,
            "system_fingerprint": result.system_fingerprint,
            "validation_errors": list(result.validation_errors),
        }
        for result in results
    ]


def _write_generation_checkpoint(root: Path, prefix: str, results: list[Any]) -> None:
    valid_records = [result.record for result in results if result.record is not None]
    write_records(valid_records, root / f"{prefix}_traces.jsonl")
    write_records(_preflight_attempt_payloads(results), root / f"{prefix}_attempts.jsonl")
    write_json(root / f"{prefix}_generation_fallback_report.json", build_generation_summary(results))


def _load_existing_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_records(path)


def _write_pilot_checkpoint(
    root: Path,
    *,
    attempts: list[dict[str, Any]],
    valid_records: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    write_records(valid_records, root / "pilot_traces.jsonl")
    write_records(attempts, root / "pilot_attempts.jsonl")
    write_json(root / "pilot_generation_fallback_report.json", summary)


def _merge_generation_summary(
    existing_summary: dict[str, Any],
    *,
    new_results: list[GeneratedTraceResult],
    attempts: list[dict[str, Any]],
    valid_records: list[dict[str, Any]],
) -> dict[str, Any]:
    new_summary = build_generation_summary(new_results)
    lower_confidence = sum(
        1
        for record in valid_records
        if record.get("generation_config", {}).get("structured_output_mode") == "json_object"
    )
    return {
        "records_requested": len(attempts),
        "valid_records": len(valid_records),
        "invalid_records": len(attempts) - len(valid_records),
        "valid_rate": len(valid_records) / len(attempts) if attempts else 0.0,
        "lower_confidence_records": lower_confidence,
        "fallback_events": list(existing_summary.get("fallback_events", []))
        + list(new_summary.get("fallback_events", [])),
    }


def _seed_transport_report(results: list[Any]) -> dict[str, Any]:
    metadata = [
        result.record.get("generation_config", {}).get("api_request_metadata", {})
        for result in results
        if result.record is not None
    ]
    requested = [bool(item.get("seed_requested")) for item in metadata]
    sent = [bool(item.get("seed_sent")) for item in metadata]
    return {
        "records_evaluated": len(metadata),
        "seed_requested": any(requested),
        "seed_sent_count": sum(1 for value in sent if value),
        "seed_sent_rate": (sum(1 for value in sent if value) / len(sent)) if sent else 0.0,
        "retry_labels": sorted({str(item.get("retry_label")) for item in metadata if item.get("retry_label")}),
        "sample_retry_errors": [
            error
            for item in metadata[:3]
            for error in item.get("retry_errors", [])
        ],
    }


def _force_preflight_failure(report: dict[str, dict[str, Any]], *, code: str, reason: str) -> None:
    preflight = report["api_preflight_report"]
    codes = set(preflight.get("failure_codes", []))
    codes.add(code)
    preflight["failure_codes"] = sorted(codes)
    preflight["status"] = "fail"
    drift = report["determinism_drift_report"]
    drift["determinism_gate_pass"] = False
    drift["paper_disclosure_required"] = True
    drift["failure_reason"] = reason


def _span_validity_rate(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.0
    valid = sum(1 for record in records if record.get("reflection_spans"))
    return valid / len(records)


def _replay_success_rate(root: Path) -> float:
    replay_path = root / "real_task_replay_results.jsonl"
    delta_path = root / "real_task_delta_u.jsonl"
    if replay_path.exists():
        rows = load_records(replay_path)
        if not rows:
            return 0.0
        successes = sum(1 for row in rows if row.get("status") in {"success", "replayed"})
        return successes / len(rows)
    if not delta_path.exists():
        return 0.0
    rows = load_records(delta_path)
    if not rows:
        return 0.0
    return 1.0


if __name__ == "__main__":
    main()
