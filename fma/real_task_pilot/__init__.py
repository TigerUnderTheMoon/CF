"""Real-task pilot utilities for reviewer-safe FMA validation."""

from .baselines import (
    FORBIDDEN_BASELINE_SOURCE_FIELDS,
    build_baseline_leakage_audit,
    score_independent_baselines,
)
from .config import load_pilot_config
from .coverage import audit_key_coverage, expected_span_keys
from .generation import generate_trace_with_fallback, normalize_trace_record
from .metrics import exact_match, normalized_token_f1, score_answer
from .parsing import extract_reflection_spans, parse_json_object
from .preflight import evaluate_preflight
from .readiness import build_readiness_audit
from .replay import aggregate_delta_u_by_span, build_replay_prefix, compute_delta_u, missing_replay_jobs
from .schema import REAL_TASK_TRACE_SCHEMA, structured_output_text_format, validate_trace_record
from .signal import build_rank_signal_report

__all__ = [
    "FORBIDDEN_BASELINE_SOURCE_FIELDS",
    "REAL_TASK_TRACE_SCHEMA",
    "aggregate_delta_u_by_span",
    "audit_key_coverage",
    "build_baseline_leakage_audit",
    "build_rank_signal_report",
    "build_readiness_audit",
    "build_replay_prefix",
    "compute_delta_u",
    "evaluate_preflight",
    "exact_match",
    "expected_span_keys",
    "extract_reflection_spans",
    "load_pilot_config",
    "generate_trace_with_fallback",
    "missing_replay_jobs",
    "normalized_token_f1",
    "normalize_trace_record",
    "parse_json_object",
    "score_answer",
    "score_independent_baselines",
    "structured_output_text_format",
    "validate_trace_record",
]
