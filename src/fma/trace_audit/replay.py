"""Replay verification for trace-audit steps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from fma.pilot.cache import APICache


class RuleReplayEngine:
    """Deterministic replay after masking one reasoning step."""

    def replay_trace(self, trace: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [self.replay_step(trace, step) for step in trace["steps"] if step.get("is_maskable", True)]

    def replay_step(self, trace: Mapping[str, Any], step: Mapping[str, Any]) -> dict[str, Any]:
        step_type = str(step["step_type"])
        original = _answer_ids(trace.get("final_answer", []))
        replayed = self._replayed_answer_ids(trace, step_type)
        f1 = _answer_f1(replayed, original)
        return {
            "trace_id": trace["trace_id"],
            "sample_id": trace["sample_id"],
            "masked_step_id": step["step_id"],
            "step_index": step["step_index"],
            "step_type": step_type,
            "engine": "rule",
            "repeat_index": 0,
            "original_answer": trace.get("final_answer", []),
            "replayed_answer": [{"id": value, "name": value} for value in replayed],
            "answer_f1": f1,
            "answer_em": 1.0 if set(replayed) == set(original) else 0.0,
            "delta": 1.0 - f1,
            "status": "success",
            "failure_reason": "",
        }

    def _replayed_answer_ids(self, trace: Mapping[str, Any], step_type: str) -> list[str]:
        original = _answer_ids(trace.get("final_answer", []))
        if step_type in {"entity_linking", "relation_traversal", "answer_verification"}:
            return []
        if step_type == "candidate_generation":
            return [*original, "recoverable_extra_candidate"]
        if step_type == "candidate_verification":
            return [*original, "unverified_extra_candidate"]
        if step_type == "ambiguity_resolution":
            candidates = trace.get("local_kg", {}).get("candidate_entities", [])
            if len(candidates) <= 1:
                return original
            return [*original, "ambiguous_extra_candidate"]
        return original


class LLMReplayEngine:
    """Optional cached LLM replay wrapper.

    The default client is ``None`` so running the experiment never spends API
    budget accidentally.  A caller may inject a deterministic client that maps a
    prompt string to a JSON object with a ``replayed_answer`` field.
    """

    def __init__(
        self,
        *,
        cache_path: str | Path = "outputs/webqsp_trace_audit_v1/cache/llm_replay.sqlite",
        model_name: str = "disabled-llm-replay",
        client: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self.cache = APICache(cache_path)
        self.model_name = model_name
        self.client = client

    def replay_step(self, trace: Mapping[str, Any], step: Mapping[str, Any]) -> dict[str, Any]:
        prompt = self._prompt(trace, step)
        cached = self.cache.get(prompt=prompt, model_name=self.model_name, temperature=0.0, seed=0, top_p=1.0)
        if cached is not None:
            payload = json.loads(cached.raw_output)
            return self._row(trace, step, payload, status="cached")
        if self.client is None:
            return self._row(trace, step, {"replayed_answer": []}, status="skipped", failure_reason="llm_client_not_configured")
        payload = dict(self.client(prompt))
        self.cache.set(
            prompt=prompt,
            model_name=self.model_name,
            temperature=0.0,
            seed=0,
            top_p=1.0,
            raw_output=json.dumps(payload, sort_keys=True),
            metadata={"route_id": "webqsp_trace_audit_v1"},
            cost_usd=0.0,
        )
        return self._row(trace, step, payload, status="success")

    def _prompt(self, trace: Mapping[str, Any], step: Mapping[str, Any]) -> str:
        safe_trace = {
            "question": trace.get("leakage_safe_question", ""),
            "local_kg": trace.get("local_kg", {}),
            "prefix_steps": [
                {
                    "step_type": s.get("step_type"),
                    "text": s.get("leakage_safe_text"),
                }
                for s in trace.get("steps", [])
                if int(s.get("step_index", 0)) < int(step.get("step_index", 0))
            ],
            "masked_step_type": step.get("step_type"),
        }
        return json.dumps(safe_trace, ensure_ascii=True, sort_keys=True)

    def _row(
        self,
        trace: Mapping[str, Any],
        step: Mapping[str, Any],
        payload: Mapping[str, Any],
        *,
        status: str,
        failure_reason: str = "",
    ) -> dict[str, Any]:
        original = _answer_ids(trace.get("final_answer", []))
        replayed = _answer_ids(payload.get("replayed_answer", []))
        f1 = _answer_f1(replayed, original)
        return {
            "trace_id": trace["trace_id"],
            "sample_id": trace["sample_id"],
            "masked_step_id": step["step_id"],
            "step_index": step["step_index"],
            "step_type": step["step_type"],
            "engine": "llm",
            "repeat_index": 0,
            "original_answer": trace.get("final_answer", []),
            "replayed_answer": payload.get("replayed_answer", []),
            "answer_f1": f1,
            "answer_em": 1.0 if set(replayed) == set(original) else 0.0,
            "delta": 1.0 - f1,
            "status": status,
            "failure_reason": failure_reason,
        }


def _answer_ids(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    ids = []
    for item in values:
        if isinstance(item, Mapping):
            value = str(item.get("id") or item.get("name") or "")
        else:
            value = str(item)
        if value:
            ids.append(value)
    return ids


def _answer_f1(predicted: list[str], gold: list[str]) -> float:
    pred = set(predicted)
    ref = set(gold)
    if not pred and not ref:
        return 1.0
    if not pred or not ref:
        return 0.0
    precision = len(pred & ref) / len(pred)
    recall = len(pred & ref) / len(ref)
    if precision + recall == 0.0:
        return 0.0
    return float(2.0 * precision * recall / (precision + recall))
