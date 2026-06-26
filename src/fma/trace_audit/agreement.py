"""Continuous agreement and importance scoring."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence


class AgreementScorer:
    """Combine rule and optional LLM replay into continuous targets."""

    def __init__(self, *, rule_weight: float = 0.7, llm_weight: float = 0.3) -> None:
        self.rule_weight = float(rule_weight)
        self.llm_weight = float(llm_weight)

    def score_trace(
        self,
        trace: Mapping[str, Any],
        replay_rows: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        by_step: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in replay_rows:
            by_step[str(row["masked_step_id"])].append(row)

        scored = []
        for step in trace["steps"]:
            rows = by_step.get(str(step["step_id"]), [])
            rule_values = [float(row.get("delta", 0.0)) for row in rows if row.get("engine") == "rule"]
            llm_values = [
                float(row.get("delta", 0.0))
                for row in rows
                if row.get("engine") == "llm" and row.get("status") in {"success", "cached"}
            ]
            rule_delta = _mean(rule_values)
            llm_delta = _mean(llm_values) if llm_values else rule_delta
            agreement = 1.0 - abs(rule_delta - llm_delta)
            importance = self.rule_weight * rule_delta + self.llm_weight * llm_delta
            scored.append(
                {
                    "trace_id": trace["trace_id"],
                    "sample_id": trace["sample_id"],
                    "step_id": step["step_id"],
                    "step_index": step["step_index"],
                    "step_type": step["step_type"],
                    "rule_delta": _clip(rule_delta),
                    "llm_delta": _clip(llm_delta),
                    "agreement_score": _clip(agreement),
                    "importance_target": _clip(importance),
                    "target_reliability": _clip(agreement),
                }
            )
        return scored


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
