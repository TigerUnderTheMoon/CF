"""WebQSP trace-audit experiment for SC-FMA.

This package treats WebQSP as a source of executable reasoning traces, not as a
KGQA benchmark.  Trace generation is deterministic and rule-based; optional LLM
use is confined to replay verification.
"""

from __future__ import annotations

from fma.trace_audit.agreement import AgreementScorer
from fma.trace_audit.data import WebQSPLoader
from fma.trace_audit.decision import compare_datasets, final_dataset_decision
from fma.trace_audit.graph import VerificationGraphBuilder
from fma.trace_audit.metrics import build_experiment_report
from fma.trace_audit.preprocessing import WebQSPPreprocessor
from fma.trace_audit.replay import LLMReplayEngine, RuleReplayEngine
from fma.trace_audit.trace_generation import RuleTraceGenerator
from fma.trace_audit.validation import audit_traces, validate_trace

__all__ = [
    "AgreementScorer",
    "LLMReplayEngine",
    "RuleReplayEngine",
    "RuleTraceGenerator",
    "VerificationGraphBuilder",
    "WebQSPLoader",
    "WebQSPPreprocessor",
    "audit_traces",
    "build_experiment_report",
    "compare_datasets",
    "final_dataset_decision",
    "validate_trace",
]
