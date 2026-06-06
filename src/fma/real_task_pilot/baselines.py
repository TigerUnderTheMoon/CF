"""Independent scorer baselines and leakage audit for the real-task pilot."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .parsing import extract_reflection_spans, proxy_token_count


FORBIDDEN_BASELINE_SOURCE_FIELDS = {
    "correctness",
    "original_score",
    "intervened_score",
    "delta_u",
    "necessity",
    "structural_necessity",
    "attribution_score",
    "replay_outcome",
}

QUESTION_DIFFICULTY_FIELDS = {
    "question_length",
    "number_count",
    "entity_count",
    "supporting_fact_count",
}

TAXONOMY_PRIOR = {
    "verification": 0.70,
    "self-evaluation": 0.65,
    "error_diagnosis": 0.60,
    "plan_revision": 0.55,
    "planning": 0.55,
    "strategy_critique": 0.50,
    "uncertainty_monitoring": 0.45,
    "self-reflection": 0.40,
    "other": 0.35,
}


def question_difficulty_proxy(record: Mapping[str, Any]) -> dict[str, Any]:
    question = str(record.get("question") or "")
    metadata = record.get("metadata", {}) if isinstance(record.get("metadata"), Mapping) else {}
    supporting_facts = record.get("supporting_facts", metadata.get("supporting_facts", []))
    if isinstance(supporting_facts, int):
        supporting_count = supporting_facts
    elif isinstance(supporting_facts, Sequence) and not isinstance(supporting_facts, str):
        supporting_count = len(supporting_facts)
    else:
        supporting_count = 0
    features = {
        "question_length": len(question.split()),
        "number_count": len(re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", question)),
        "entity_count": len(re.findall(r"\b[A-Z][a-zA-Z0-9_-]+\b", question)),
        "supporting_fact_count": supporting_count,
    }
    score = min(
        1.0,
        0.01 * features["question_length"]
        + 0.08 * features["number_count"]
        + 0.03 * features["entity_count"]
        + 0.05 * features["supporting_fact_count"],
    )
    return {
        "score": float(score),
        "features": features,
        "source_fields_used": sorted(QUESTION_DIFFICULTY_FIELDS),
    }


def score_independent_baselines(records: Sequence[Mapping[str, Any]], *, seed: int = 20260530) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        trace = str(record.get("observable_trace") or record.get("reasoning_trace") or "")
        spans = record.get("reflection_spans") or extract_reflection_spans(trace)
        trajectory_tokens = max(1, proxy_token_count(trace))
        difficulty = question_difficulty_proxy(record)
        for span_index, span in enumerate(spans):
            span_length = max(0, int(span.get("end_token", 0)) - int(span.get("start_token", 0)))
            relative_position = int(span.get("start_token", 0)) / trajectory_tokens
            operation_type = str(span.get("operation_type") or span.get("reflection_type") or "other")
            rows.append(
                {
                    "sample_id": record.get("sample_id"),
                    "task_type": record.get("task_type"),
                    "span_index": span_index,
                    "scores": {
                        "random": _stable_float(f"{seed}:{record.get('sample_id')}:{span_index}"),
                        "span_length": min(1.0, span_length / trajectory_tokens),
                        "relative_position": min(1.0, max(0.0, relative_position)),
                        "taxonomy_prior": TAXONOMY_PRIOR.get(operation_type, TAXONOMY_PRIOR["other"]),
                        "uniform_reflection_weight": 1.0,
                        "question_difficulty_proxy": difficulty["score"],
                    },
                    "source_fields_used": sorted(
                        {
                            "sample_id",
                            "task_type",
                            "observable_trace",
                            "reflection_spans",
                            *difficulty["source_fields_used"],
                        }
                    ),
                    "forbidden_fields_used": [],
                }
            )
    return rows


def build_baseline_leakage_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    checks = []
    leaked = False
    for row in rows:
        used = set(row.get("source_fields_used", []))
        forbidden = sorted(used.intersection(FORBIDDEN_BASELINE_SOURCE_FIELDS))
        leaked = leaked or bool(forbidden)
        checks.append(
            {
                "sample_id": row.get("sample_id"),
                "span_index": row.get("span_index"),
                "forbidden_fields_used": forbidden,
                "target_leakage_status": "target_leaking" if forbidden else "clean",
            }
        )
    return {
        "baseline_family": "independent_scorer_baselines",
        "target_leakage_detected": leaked,
        "target_leakage_status": "target_leaking" if leaked else "clean",
        "forbidden_source_fields": sorted(FORBIDDEN_BASELINE_SOURCE_FIELDS),
        "checks": checks,
    }


def _stable_float(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(16**16 - 1)
