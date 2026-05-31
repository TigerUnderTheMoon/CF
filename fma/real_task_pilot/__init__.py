"""Real-task pilot utilities for reviewer-safe FMA validation."""

from .baselines import (
    FORBIDDEN_BASELINE_SOURCE_FIELDS,
    build_baseline_leakage_audit,
    score_independent_baselines,
)
from .config import load_pilot_config
from .generation import generate_trace_with_fallback, normalize_trace_record
from .metrics import exact_match, normalized_token_f1, score_answer
from .parsing import extract_reflection_spans, parse_json_object
from .preflight import evaluate_preflight
from .readiness import build_readiness_audit
from .replay import build_replay_prefix, compute_delta_u
from .schema import REAL_TASK_TRACE_SCHEMA, structured_output_text_format, validate_trace_record

__all__ = [
    "FORBIDDEN_BASELINE_SOURCE_FIELDS",
    "REAL_TASK_TRACE_SCHEMA",
    "build_baseline_leakage_audit",
    "build_readiness_audit",
    "build_replay_prefix",
    "compute_delta_u",
    "evaluate_preflight",
    "exact_match",
    "extract_reflection_spans",
    "load_pilot_config",
    "generate_trace_with_fallback",
    "normalized_token_f1",
    "normalize_trace_record",
    "parse_json_object",
    "score_answer",
    "score_independent_baselines",
    "structured_output_text_format",
    "validate_trace_record",
]
