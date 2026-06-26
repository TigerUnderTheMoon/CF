"""Schema constants for the WebQSP trace-audit route."""

from __future__ import annotations

ROUTE_ID = "webqsp_trace_audit_v1"
CLAIM = "SC-FMA ranks functionally indispensable reasoning steps ahead of recoverable reasoning steps."

STEP_TYPES = (
    "entity_linking",
    "relation_traversal",
    "candidate_generation",
    "candidate_verification",
    "ambiguity_resolution",
    "answer_verification",
)

EDGE_CATEGORIES = ("Temporal", "Dependency", "Support")

FORBIDDEN_CLAIMS = (
    "KGQA benchmark result",
    "semantic parser improvement",
    "question-answering optimization",
    "deployed KBS validation",
    "causal effect",
)
