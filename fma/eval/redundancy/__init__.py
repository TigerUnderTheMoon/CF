"""Phase 7 redundancy and compensation analysis helpers."""

from fma.eval.redundancy.bottleneck import compute_bottlenecks
from fma.eval.redundancy.compensation import (
    AffectedNodeDelta,
    CompensationRecord,
    InterventionDelta,
    compute_compensation_records,
    reconstruct_intervention_deltas,
    stratify_compensation,
    summarize_compensation,
)
from fma.eval.redundancy.distributedness import (
    distributedness_index,
    gini_coefficient,
    summarize_distributedness,
)
from fma.eval.redundancy.overlap import (
    MODE_ORDER,
    NodeProfile,
    cosine_similarity,
    hybrid_similarity,
    jaccard_overlap,
    overall_necessity,
    profiles_from_graphs,
)
from fma.eval.redundancy.redundancy_density import compute_redundancy
from fma.eval.redundancy.rerouting import (
    ReroutingRecord,
    compute_rerouting_records,
    summarize_rerouting,
)
from fma.eval.redundancy.resilience import (
    is_monotonic_degradation,
    resilience_curve,
    summarize_resilience,
    topology_resilience,
)

__all__ = [
    "AffectedNodeDelta",
    "CompensationRecord",
    "InterventionDelta",
    "MODE_ORDER",
    "NodeProfile",
    "ReroutingRecord",
    "compute_bottlenecks",
    "compute_compensation_records",
    "compute_redundancy",
    "compute_rerouting_records",
    "cosine_similarity",
    "distributedness_index",
    "gini_coefficient",
    "hybrid_similarity",
    "is_monotonic_degradation",
    "jaccard_overlap",
    "overall_necessity",
    "profiles_from_graphs",
    "reconstruct_intervention_deltas",
    "resilience_curve",
    "stratify_compensation",
    "summarize_compensation",
    "summarize_distributedness",
    "summarize_rerouting",
    "summarize_resilience",
    "topology_resilience",
]
