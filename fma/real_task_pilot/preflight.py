"""Preflight gates for schema, drift, and cost before full API runs."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .parsing import extract_reflection_spans, parse_json_object
from .schema import validate_trace_record


def token_diff_ratio(left: str, right: str) -> float:
    """Return a simple token-level edit-distance ratio."""

    left_tokens = left.split()
    right_tokens = right.split()
    denominator = max(1, max(len(left_tokens), len(right_tokens)))
    return _edit_distance(left_tokens, right_tokens) / denominator


def evaluate_preflight(
    raw_outputs: Sequence[Any],
    *,
    drift_outputs: Sequence[str] = (),
    config: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Evaluate preflight outputs without making API calls."""

    minimum_schema_rate = float(
        _nested(config, "generation", "minimum_schema_success_rate", default=0.95)
    )
    minimum_tag_rate = float(_nested(config, "generation", "minimum_tag_success_rate", default=0.95))
    max_drift = 0.05

    attempts = [_attempt_from_value(output) for output in raw_outputs]
    parsed = [attempt["parsed"] for attempt in attempts]
    json_success = [item is not None for item in parsed]
    schema_success = [
        item is not None and not validate_trace_record(item)
        for item in parsed
    ]
    tag_success = [
        item is not None
        and bool(extract_reflection_spans(str(item.get("observable_trace", ""))))
        for item in parsed
    ]

    drift_values = []
    for left_index in range(len(drift_outputs)):
        for right_index in range(left_index + 1, len(drift_outputs)):
            drift_values.append(token_diff_ratio(drift_outputs[left_index], drift_outputs[right_index]))
    max_observed_drift = max(drift_values) if drift_values else None

    usage_totals = _usage_totals(attempts)
    cost_report = _cost_report(usage_totals, len(raw_outputs), config or {})

    schema_rate = _mean_bool(schema_success)
    tag_rate = _mean_bool(tag_success)
    drift_pass = max_observed_drift is None or max_observed_drift < max_drift
    schema_gate = _mean_bool(json_success) >= minimum_schema_rate and schema_rate >= minimum_schema_rate
    tag_gate = tag_rate >= minimum_tag_rate

    return {
        "api_preflight_report": {
            "status": "pass" if schema_gate and tag_gate and drift_pass and cost_report["budget_gate_pass"] else "fail",
            "failure_codes": _failure_codes(
                schema_gate,
                tag_gate,
                drift_pass,
                cost_report["budget_gate_pass"],
            ),
            "records_evaluated": len(raw_outputs),
            "json_parse_success_rate": _mean_bool(json_success),
            "schema_success_rate": schema_rate,
            "tag_extraction_success_rate": tag_rate,
            "determinism_drift_max": max_observed_drift,
        },
        "schema_compliance_report": {
            "json_parse_success_rate": _mean_bool(json_success),
            "schema_success_rate": schema_rate,
            "tag_extraction_success_rate": tag_rate,
            "minimum_schema_success_rate": minimum_schema_rate,
            "minimum_tag_success_rate": minimum_tag_rate,
            "schema_gate_pass": schema_gate,
            "tag_gate_pass": tag_gate,
            "fallback_required": not (schema_gate and tag_gate),
        },
        "determinism_drift_report": {
            "calls": len(drift_outputs),
            "max_token_diff_ratio": max_observed_drift,
            "threshold": max_drift,
            "determinism_gate_pass": drift_pass,
            "paper_disclosure_required": not drift_pass,
        },
        "cost_and_rate_limit_report": cost_report,
    }


def _cost_report(
    usage_totals: Mapping[str, int],
    observed_requests: int,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    experiment = config.get("experiment", {}) if isinstance(config, Mapping) else {}
    max_requests = int(experiment.get("max_api_requests_pilot") or 0)
    budget = experiment.get("user_approved_budget_usd")
    planned_requests = max_requests or _planned_request_count(config)
    multiplier = planned_requests / max(1, observed_requests)
    projected_tokens = {
        key: int(math.ceil(value * multiplier))
        for key, value in usage_totals.items()
    }
    price = config.get("pricing", {}) if isinstance(config, Mapping) else {}
    projected_cost = _projected_cost(projected_tokens, price)
    budget_gate = budget is not None and (
        projected_cost is None or float(projected_cost) <= float(budget)
    )
    return {
        "observed_requests": observed_requests,
        "projected_requests": planned_requests,
        "usage_totals": dict(usage_totals),
        "projected_tokens": projected_tokens,
        "projected_cost_usd": projected_cost,
        "user_approved_budget_usd": budget,
        "budget_gate_pass": budget_gate,
        "retry_count": 0,
        "failure_reasons": [],
    }


def _planned_request_count(config: Mapping[str, Any]) -> int:
    experiment = config.get("experiment", {}) if isinstance(config, Mapping) else {}
    pilot_requests = int(experiment.get("pilot_generation_requests") or 0)
    data_tasks = _nested(config, "data", "tasks", default={})
    data_total = (
        sum(int(task.get("count", 0)) for task in data_tasks.values())
        if isinstance(data_tasks, Mapping)
        else 0
    )
    total = pilot_requests or data_total or 400
    if "replay" not in config and "trajectory_controls" not in config:
        return total
    replay_max = int(_nested(config, "replay", "max_spans_per_trace", default=3))
    replay_repeats = int(
        _nested(
            config,
            "nondeterministic_protocol",
            "repeats",
            "replay_per_span",
            default=1,
        )
    )
    control_count = len(_nested(config, "trajectory_controls", "variants", default=[]))
    return total + total * replay_max * replay_repeats + total * control_count


def _projected_cost(projected_tokens: Mapping[str, int], price: Mapping[str, Any]) -> float | None:
    input_rate = price.get("input_per_million_usd")
    output_rate = price.get("output_per_million_usd")
    if input_rate is None or output_rate is None:
        return None
    return float(
        (projected_tokens.get("input_tokens", 0) / 1_000_000) * float(input_rate)
        + (projected_tokens.get("output_tokens", 0) / 1_000_000) * float(output_rate)
    )


def _usage_totals(attempts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for attempt in attempts:
        usage = attempt.get("usage", {})
        for key in totals:
            totals[key] += int(usage.get(key, 0) or 0)
    return totals


def _failure_codes(schema_gate: bool, tag_gate: bool, drift_pass: bool, cost_pass: bool) -> list[str]:
    codes = []
    if not schema_gate:
        codes.append("PREFLIGHT_FAIL_SCHEMA")
    if not tag_gate:
        codes.append("PREFLIGHT_FAIL_TAG")
    if not drift_pass:
        codes.append("PREFLIGHT_FAIL_DRIFT")
    if not cost_pass:
        codes.append("PREFLIGHT_FAIL_COST")
    return codes


def _attempt_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping) and value.get("preflight_attempt") is True:
        record = value.get("record")
        raw_output = record if record is not None else value.get("raw_output")
        parsed = parse_json_object(raw_output)
        usage = value.get("usage") or (parsed.get("usage", {}) if isinstance(parsed, Mapping) else {})
        return {"parsed": parsed, "usage": usage}
    parsed = parse_json_object(value)
    usage = parsed.get("usage", {}) if isinstance(parsed, Mapping) else {}
    return {"parsed": parsed, "usage": usage}


def _mean_bool(values: Sequence[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


def _nested(config: Mapping[str, Any] | None, *keys: str, default: Any) -> Any:
    value: Any = config or {}
    for key in keys:
        if not isinstance(value, Mapping) or key not in value:
            return default
        value = value[key]
    return value


def _edit_distance(left: Sequence[str], right: Sequence[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, left_token in enumerate(left, start=1):
        current = [i]
        for j, right_token in enumerate(right, start=1):
            cost = 0 if left_token == right_token else 1
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + cost,
                )
            )
        previous = current
    return previous[-1]
