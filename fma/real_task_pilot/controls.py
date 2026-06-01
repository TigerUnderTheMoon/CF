"""Trajectory-control definitions and reports for separate reporting."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .metrics import score_answer
from .parsing import extract_final_answer, extract_reflection_spans, parse_json_object


TRAJECTORY_CONTROLS = {
    "no_reflection": {
        "definition": "Answer directly without visible reflection tags.",
        "mix_with_span_attribution": False,
    },
    "tagged_reflection": {
        "definition": "Use one or more visible <reflection> tags in a single-pass solution.",
        "mix_with_span_attribution": False,
    },
    "self_refine_style": {
        "definition": "Visible draft, feedback, and revision for the same question.",
        "mix_with_span_attribution": False,
    },
    "reflexion_style": {
        "definition": "Visible verbal reflection after failure or uncertainty, then retry.",
        "mix_with_span_attribution": False,
    },
}

CONTROL_INSTRUCTIONS = {
    "no_reflection": (
        "Answer directly without any <reflection> tags. Keep the trace concise and visible."
    ),
    "tagged_reflection": (
        "Use one or more visible <reflection type=\"verification\">...</reflection> tags in a single-pass solution."
    ),
    "self_refine_style": (
        "Write a visible draft, a <reflection type=\"self-evaluation\">...</reflection> feedback step, and a revised answer."
    ),
    "reflexion_style": (
        "Write a visible initial attempt, a <reflection type=\"error_diagnosis\">...</reflection> retry rationale, and a final answer."
    ),
}


def control_report_skeleton() -> dict[str, dict[str, object]]:
    return build_control_report([], expected_per_variant=0)


def build_control_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_per_variant: int,
) -> dict[str, dict[str, object]]:
    """Aggregate trajectory-level controls without mixing them into span attribution."""

    report: dict[str, dict[str, object]] = {}
    for name, definition in TRAJECTORY_CONTROLS.items():
        variant_rows = [row for row in rows if row.get("variant") == name]
        successful_rows = [
            row
            for row in variant_rows
            if row.get("status") == "success" and bool(row.get("valid", True))
        ]
        attempted_count = len(variant_rows)
        successful_count = len(successful_rows)
        expected_count = max(0, expected_per_variant)
        status = _control_status(
            expected_count=expected_count,
            attempted_count=attempted_count,
            successful_count=successful_count,
        )
        report[name] = {
            **definition,
            "status": status,
            "expected_count": expected_count,
            "attempted_count": attempted_count,
            "successful_count": successful_count,
            "failed_count": max(0, attempted_count - successful_count),
            "failure_reasons": _failure_reasons(
                variant_rows,
                expected_count=expected_count,
                attempted_count=attempted_count,
            ),
            "metrics": {
                "accuracy": _mean_bool(row.get("correctness") for row in successful_rows),
                "tokens": _sum_usage(variant_rows, "total_tokens"),
                "validity": (successful_count / expected_count) if expected_count else None,
                "reflection_count": _mean_number(row.get("reflection_count") for row in successful_rows),
                "cost": _sum_optional_number(row.get("cost_usd") for row in variant_rows),
            },
        }
    return report


def build_control_jobs(
    records: Sequence[Mapping[str, Any]],
    *,
    variants: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    variant_names = list(variants or TRAJECTORY_CONTROLS)
    jobs = []
    for record in records:
        for variant in variant_names:
            jobs.append(
                {
                    "variant": variant,
                    "sample_id": record.get("sample_id"),
                    "task_id": record.get("task_id"),
                    "task_type": record.get("task_type"),
                    "question": record.get("question"),
                    "reference_answer": record.get("reference_answer"),
                    "aliases": list(record.get("aliases") or []),
                }
            )
    return jobs


def missing_control_jobs(
    records: Sequence[Mapping[str, Any]],
    existing_rows: Sequence[Mapping[str, Any]],
    *,
    variants: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    completed = {
        _control_key(row)
        for row in existing_rows
        if row.get("status") == "success" and row.get("sample_id") and row.get("variant")
    }
    return [
        job
        for job in build_control_jobs(records, variants=variants)
        if _control_key(job) not in completed
    ]


def build_control_prompt(job: Mapping[str, Any]) -> str:
    variant = str(job.get("variant") or "")
    instruction = CONTROL_INSTRUCTIONS.get(variant, CONTROL_INSTRUCTIONS["tagged_reflection"])
    return (
        "You are generating an observable benchmark solution trace for a trajectory-control comparison.\n\n"
        "Return exactly one JSON object with these keys: observable_trace and final_answer.\n"
        "The trace must be visible text, not hidden reasoning.\n\n"
        f"Control variant: {variant}\n"
        f"Variant instruction: {instruction}\n\n"
        f"Task type: {job.get('task_type')}\n"
        "Question:\n"
        f"{job.get('question')}\n"
    )


def control_row_from_response(
    job: Mapping[str, Any],
    response: Any,
    *,
    structured_output_mode: str,
    validation_errors: Sequence[str] = (),
) -> dict[str, Any]:
    raw_output = str(getattr(response, "output_text", ""))
    parsed = parse_json_object(raw_output)
    errors = list(validation_errors)
    trace = ""
    final_answer = ""
    if parsed is None:
        errors.append("<root>: response is not a JSON object")
    else:
        trace = str(parsed.get("observable_trace") or "")
        final_answer = str(parsed.get("final_answer") or extract_final_answer(trace))
        if not trace:
            errors.append("observable_trace: missing")
        if final_answer == "":
            errors.append("final_answer: missing")
    spans = extract_reflection_spans(trace)
    variant = str(job.get("variant") or "")
    if variant == "no_reflection" and spans:
        errors.append("unexpected_reflection_tags")
    if variant != "no_reflection" and not spans:
        errors.append("missing_reflection_tags")
    score = score_answer(
        str(job.get("task_type") or ""),
        final_answer,
        str(job.get("reference_answer") or ""),
        job.get("aliases") or [],
    )
    return {
        "sample_id": job.get("sample_id"),
        "task_id": job.get("task_id"),
        "task_type": job.get("task_type"),
        "variant": variant,
        "status": "failed" if errors else "success",
        "valid": not errors,
        "validation_errors": errors,
        "observable_trace": trace,
        "final_answer": final_answer,
        "reference_answer": job.get("reference_answer"),
        "correctness": bool(score["exact_match"]),
        "score": score["score"],
        "normalized_token_f1": score["normalized_token_f1"],
        "reflection_count": len(spans),
        "usage": dict(getattr(response, "usage", {}) or {}),
        "model_name": getattr(response, "model_name", None),
        "system_fingerprint": getattr(response, "system_fingerprint", None),
        "structured_output_mode": structured_output_mode,
    }


def _control_status(
    *,
    expected_count: int,
    attempted_count: int,
    successful_count: int,
) -> str:
    if attempted_count == 0:
        return "skeleton_unmeasured"
    if expected_count > 0 and successful_count >= expected_count:
        return "measured"
    return "partial"


def _failure_reasons(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_count: int,
    attempted_count: int,
) -> list[str]:
    reasons = []
    for row in rows:
        for error in row.get("validation_errors") or []:
            reason = str(error)
            if reason and reason not in reasons:
                reasons.append(reason)
        if row.get("error"):
            reason = str(row["error"])
            if reason and reason not in reasons:
                reasons.append(reason)
    if expected_count and attempted_count < expected_count and "missing_control_jobs" not in reasons:
        reasons.append("missing_control_jobs")
    return reasons


def _mean_bool(values: Sequence[Any]) -> float | None:
    items = [bool(value) for value in values]
    if not items:
        return None
    return sum(1 for item in items if item) / len(items)


def _mean_number(values: Sequence[Any]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def _sum_usage(rows: Sequence[Mapping[str, Any]], key: str) -> int | None:
    values = []
    for row in rows:
        usage = row.get("usage")
        if isinstance(usage, Mapping) and usage.get(key) is not None:
            values.append(int(usage[key]))
    if not values:
        return None
    return sum(values)


def _sum_optional_number(values: Sequence[Any]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return sum(numbers)


def _control_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("sample_id") or ""), str(row.get("variant") or "")
