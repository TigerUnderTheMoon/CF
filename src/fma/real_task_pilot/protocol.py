"""Protocol revision artifacts for non-deterministic API pilots."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping


BLOCKED_STATUS = "BLOCKED_BY_API_DETERMINISM"
REVISED_STATUS = "NONDETERMINISTIC_PROTOCOL_PREREGISTERED"


def build_api_determinism_blocker(
    *,
    api_preflight_report: Mapping[str, Any],
    seed_transport_report: Mapping[str, Any],
    seed_model_probe: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize why the original deterministic route cannot launch."""

    probe_models = seed_model_probe.get("models", [])
    passing_models = list(seed_model_probe.get("passing_models") or [])
    return {
        "status": BLOCKED_STATUS,
        "blocked_route": "deterministic_seed_controlled_api_pilot",
        "created_at": date.today().isoformat(),
        "evidence": {
            "api_preflight_status": api_preflight_report.get("status"),
            "api_preflight_failure_codes": list(api_preflight_report.get("failure_codes") or []),
            "seed_requested": bool(seed_transport_report.get("seed_requested")),
            "seed_sent_rate": float(seed_transport_report.get("seed_sent_rate") or 0.0),
            "passing_seed_probe_models": passing_models,
            "model_probe_summary": [
                {
                    "model_name": item.get("model_name"),
                    "valid_records": item.get("valid_records"),
                    "attempts": item.get("attempts"),
                    "seed_sent_rate": item.get("seed_sent_rate"),
                    "max_token_diff_ratio": item.get("max_token_diff_ratio"),
                    "drift_gate_pass": item.get("drift_gate_pass"),
                }
                for item in probe_models
            ],
        },
        "decision": {
            "run_400_deterministic_pilot": False,
            "reason": "No probed model both accepted seed control and passed the drift gate.",
            "allowed_next_protocol": "nondeterministic_repeated_estimation",
        },
    }


def build_nondeterministic_protocol(
    *,
    config: Mapping[str, Any],
    blocker: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the preregistered replacement gate for API non-determinism."""

    protocol = config.get("nondeterministic_protocol", {})
    repeats = protocol.get("repeats", {})
    bootstrap = protocol.get("bootstrap", {})
    gates = protocol.get("gates", {})
    return {
        "status": REVISED_STATUS,
        "created_at": date.today().isoformat(),
        "supersedes_route": blocker.get("blocked_route", "deterministic_seed_controlled_api_pilot"),
        "scope": "real_task_pilot_under_api_nondeterminism",
        "disclosure": {
            "required": bool(protocol.get("disclosure_required", True)),
            "text": (
                "OpenAI API seed transport was not available in preflight; repeated "
                "sampling and bootstrap confidence intervals replace deterministic replay claims."
            ),
        },
        "run_policy": {
            "allow_400_trace_generation": bool(protocol.get("allow_400_trace_generation", True)),
            "allow_top_tier_scale_up": False,
            "claim_level": "pilot_only_until_repeated_replay_ci_passes",
            "forbidden_claims": [
                "deterministic replay effect",
                "globally identifiable causal effect",
                "single-run intervention estimate",
            ],
        },
        "repeats": {
            "original_generation_per_sample": int(repeats.get("original_generation_per_sample", 1)),
            "replay_per_span": int(repeats.get("replay_per_span", 3)),
            "key_sample_replay_per_span": int(repeats.get("key_sample_replay_per_span", 5)),
        },
        "bootstrap": {
            "resamples": int(bootstrap.get("resamples", 10000)),
            "confidence_level": float(bootstrap.get("confidence_level", 0.95)),
            "unit": str(bootstrap.get("unit", "sample_id")),
            "random_seed": int(bootstrap.get("random_seed", 20260530)),
        },
        "gates": {
            "minimum_schema_success_rate": float(gates.get("minimum_schema_success_rate", 0.95)),
            "minimum_tag_success_rate": float(gates.get("minimum_tag_success_rate", 0.95)),
            "maximum_projected_cost_usd": config.get("experiment", {}).get("user_approved_budget_usd"),
            "minimum_valid_traces": int(gates.get("minimum_valid_traces", 300)),
            "minimum_span_validity_rate": float(gates.get("minimum_span_validity_rate", 0.90)),
            "minimum_replay_success_rate": float(gates.get("minimum_replay_success_rate", 0.85)),
            "effect_gate": str(gates.get("effect_gate", "bootstrap_ci_lower_gt_zero_by_task_or_pooled_with_task_pass")),
        },
        "required_artifacts": [
            "api_determinism_blocker.json",
            "nondeterministic_protocol.json",
            "sample_manifest.json",
            "pilot_traces.jsonl",
            "repeated_replay_results.jsonl",
            "bootstrap_ci_report.json",
            "readiness_audit.json",
        ],
    }


def protocol_allows_generation(protocol: Mapping[str, Any]) -> bool:
    return (
        protocol.get("status") == REVISED_STATUS
        and bool(protocol.get("run_policy", {}).get("allow_400_trace_generation"))
    )
