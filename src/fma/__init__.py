"""Functional Metacognitive Attribution research package."""

from fma.utils.logging_config import configure_logging, get_logger

configure_logging()

from fma.attribution import AttributionResult
from fma.diagnostics import DiagnosticResult
from fma.graph import (
    GraphIntervention,
    GraphInterventionBatch,
    GraphInterventionReport,
    ParallelGraphInterventionEngine,
    ReflectionEdge,
    ReflectionGraph,
    ReflectionNode,
    RemovalMode,
    run_structural_diagnostics,
)
from fma.pilot import (
    APIResponse,
    AuditEvent,
    AuditLogger,
    BaseAPIClient,
    FailureAudit,
    OpenAIClient,
    VLLMClient,
)
from fma.utils import (
    BenchmarkResult,
    CleanupReport,
    FMAConfig,
    benchmark,
    cleanup_outputs,
    load_config,
    validate_config,
)

__version__ = "0.1.0"

__all__ = [
    "APIResponse",
    "AttributionResult",
    "AuditEvent",
    "AuditLogger",
    "BaseAPIClient",
    "BenchmarkResult",
    "CleanupReport",
    "DiagnosticResult",
    "FMAConfig",
    "FailureAudit",
    "GraphIntervention",
    "GraphInterventionBatch",
    "GraphInterventionReport",
    "OpenAIClient",
    "ParallelGraphInterventionEngine",
    "ReflectionEdge",
    "ReflectionGraph",
    "ReflectionNode",
    "RemovalMode",
    "VLLMClient",
    "benchmark",
    "cleanup_outputs",
    "configure_logging",
    "get_logger",
    "load_config",
    "run_structural_diagnostics",
    "validate_config",
    "__version__",
]
