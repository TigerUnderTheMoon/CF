"""Step Importance Ranking — downstream task for SC-FMA validation.

Ranks reasoning steps by predicted importance and evaluates against
ground-truth step-level labels from PRM800K, ProcessBench, and GSM8K CoT.

Provides:
  - Multi-method comparison (SC-FMA variants vs 6 baseline families)
  - Rank correlation metrics (Spearman, Kendall, NDCG)
  - Statistical significance testing
  - Stratified analysis by taxonomy and position
"""

from .comparison import (
    BaselineMethod,
    ComparisonEntry,
    ImportanceRanker,
    RankingComparisonReport,
    compare_methods,
    list_methods,
    rank_steps_by_method,
)
from .metrics import (
    compute_ndcg,
    compute_ranking_metrics,
    compute_topk_overlap,
)
from .significance import (
    bootstrap_ci,
    friedman_test,
    wilcoxon_pairs,
)

__all__ = [
    "BaselineMethod",
    "ComparisonEntry",
    "ImportanceRanker",
    "RankingComparisonReport",
    "bootstrap_ci",
    "compare_methods",
    "compute_ndcg",
    "compute_ranking_metrics",
    "compute_topk_overlap",
    "friedman_test",
    "list_methods",
    "rank_steps_by_method",
    "wilcoxon_pairs",
]
