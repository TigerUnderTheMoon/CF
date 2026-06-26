"""Validation and data-audit checks for WebQSP trace audit."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from collections import defaultdict
from typing import Any

from fma.trace_audit.schema import EDGE_CATEGORIES, STEP_TYPES


def validate_trace(trace: Mapping[str, Any]) -> None:
    for key in ("trace_id", "sample_id", "steps", "final_answer", "local_kg", "generation_policy"):
        if key not in trace:
            raise ValueError(f"trace missing {key}.")
    steps = trace["steps"]
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)):
        raise ValueError("steps must be a list.")
    observed = [str(step.get("step_type")) for step in steps if isinstance(step, Mapping)]
    if observed != list(STEP_TYPES):
        raise ValueError(f"trace step types must be {list(STEP_TYPES)}.")
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            raise ValueError(f"step {index} must be an object.")
        for key in (
            "step_id",
            "step_index",
            "step_type",
            "operation",
            "input_entities",
            "output_entities",
            "state_before_hash",
            "state_after_hash",
            "leakage_safe_text",
        ):
            if key not in step:
                raise ValueError(f"step {index} missing {key}.")
        if "shortest_path" in str(step.get("operation", "")):
            raise ValueError("shortest-path trace generation is forbidden.")


def audit_traces(
    traces: Sequence[Mapping[str, Any]],
    replay_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    duplicate_hashes: set[str] = set()
    duplicate_count = 0
    missing_entity_count = 0
    disconnected_count = 0
    leakage_count = 0
    invalid_count = 0

    for trace in traces:
        try:
            validate_trace(trace)
        except ValueError:
            invalid_count += 1
            continue
        trace_hash = _trace_hash(trace)
        if trace_hash in duplicate_hashes:
            duplicate_count += 1
        duplicate_hashes.add(trace_hash)
        missing_entity_count += _missing_entities(trace)
        if not _is_connected_to_answer(trace):
            disconnected_count += 1
        if _has_answer_leakage(trace):
            leakage_count += 1

    replay_failures = 0
    replay_total = 0
    replay_by_step_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "success": 0, "failure": 0}
    )
    for row in replay_rows or []:
        step_type = str(row.get("step_type") or "unknown")
        status = str(row.get("status") or "")
        replay_total += 1
        replay_by_step_type[step_type]["total"] += 1
        if status in {"success", "cached"}:
            replay_by_step_type[step_type]["success"] += 1
        else:
            replay_failures += 1
            replay_by_step_type[step_type]["failure"] += 1

    replay_failure_rate_by_step_type = {
        step_type: (
            counts["failure"] / counts["total"] if counts["total"] else 0.0
        )
        for step_type, counts in sorted(replay_by_step_type.items())
    }

    return {
        "route_id": "webqsp_trace_audit_v1",
        "trace_count": len(traces),
        "invalid_trace_count": invalid_count,
        "missing_entity_count": missing_entity_count,
        "disconnected_subgraph_count": disconnected_count,
        "duplicate_trace_count": duplicate_count,
        "answer_leakage_count": leakage_count,
        "replay_failure_count": replay_failures,
        "replay_result_count": replay_total,
        "replay_failure_rate": (
            replay_failures / replay_total if replay_total else 0.0
        ),
        "replay_failure_rate_by_step_type": replay_failure_rate_by_step_type,
        "replay_coverage_by_step_type": {
            step_type: {
                "total": counts["total"],
                "success": counts["success"],
                "failure": counts["failure"],
            }
            for step_type, counts in sorted(replay_by_step_type.items())
        },
        "replay_failure_policy": "descriptive_only_no_fixed_hard_threshold",
        "edge_categories": list(EDGE_CATEGORIES),
        "passed": (
            invalid_count == 0
            and missing_entity_count == 0
            and disconnected_count == 0
            and leakage_count == 0
        ),
    }


def _known_entities(trace: Mapping[str, Any]) -> set[str]:
    known: set[str] = set()
    for triple in trace.get("local_kg", {}).get("triples", []):
        if isinstance(triple, Mapping):
            known.add(str(triple.get("subject")))
            known.add(str(triple.get("object")))
    for candidate in trace.get("local_kg", {}).get("candidate_entities", []):
        if isinstance(candidate, Mapping):
            known.add(str(candidate.get("id")))
    for answer in trace.get("final_answer", []):
        if isinstance(answer, Mapping):
            known.add(str(answer.get("id")))
    for step in trace.get("steps", []):
        if not isinstance(step, Mapping):
            continue
        if step.get("step_type") in {"entity_linking", "candidate_generation"}:
            for key in ("input_entities", "output_entities", "candidate_entities"):
                for entity_id in step.get(key, []):
                    known.add(str(entity_id))
    known.discard("")
    return known


def _missing_entities(trace: Mapping[str, Any]) -> int:
    known = _known_entities(trace)
    missing = set()
    for step in trace["steps"]:
        for key in ("input_entities", "output_entities", "candidate_entities"):
            for entity_id in step.get(key, []):
                value = str(entity_id)
                if value and value not in known:
                    missing.add(value)
    return len(missing)


def _is_connected_to_answer(trace: Mapping[str, Any]) -> bool:
    triples = [
        (str(t.get("subject")), str(t.get("object")))
        for t in trace.get("local_kg", {}).get("triples", [])
        if isinstance(t, Mapping)
    ]
    if not triples:
        return False
    starts = set(trace["steps"][0].get("output_entities", []))
    answers = {str(answer.get("id")) for answer in trace.get("final_answer", []) if isinstance(answer, Mapping)}
    reachable = set(starts)
    changed = True
    while changed:
        changed = False
        for subject, obj in triples:
            if subject in reachable and obj not in reachable:
                reachable.add(obj)
                changed = True
    return bool(reachable & answers)


def _has_answer_leakage(trace: Mapping[str, Any]) -> bool:
    needles = []
    for answer in trace.get("final_answer", []):
        if isinstance(answer, Mapping):
            needles.extend([str(answer.get("id", "")), str(answer.get("name", ""))])
    needles = [needle for needle in needles if needle]
    for step in trace.get("steps", []):
        text = str(step.get("leakage_safe_text", ""))
        if any(_contains_answer_mention(text, needle) for needle in needles):
            return True
    return False


def _contains_answer_mention(text: str, answer: str) -> bool:
    escaped = re.escape(answer)
    if not escaped:
        return False
    pattern = rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _trace_hash(trace: Mapping[str, Any]) -> str:
    payload = {
        "question": trace.get("question"),
        "steps": [
            {
                "step_type": step.get("step_type"),
                "operation": step.get("operation"),
                "relations": step.get("relations"),
                "output_entities": step.get("output_entities"),
                "leakage_safe_text": step.get("leakage_safe_text"),
            }
            for step in trace.get("steps", [])
            if isinstance(step, Mapping)
        ],
        "final_answer": trace.get("final_answer"),
        "local_kg": trace.get("local_kg"),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")).hexdigest()
