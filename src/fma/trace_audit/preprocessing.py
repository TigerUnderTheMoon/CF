"""Preprocess WebQSP records into local KG audit samples."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


class WebQSPPreprocessor:
    """Build leakage-safe trace-audit samples from WebQSP parses."""

    def build_sample(
        self,
        record: Mapping[str, Any],
        *,
        source_split: str,
        audit_split: str | None = None,
    ) -> dict[str, Any]:
        parse = _first_parse(record)
        sample_id = str(record.get("QuestionId") or record.get("id") or _stable_hash(record))
        question = str(record.get("ProcessedQuestion") or record.get("RawQuestion") or record.get("Question") or "")
        sparql = str(parse.get("Sparql") or parse.get("sparql") or "")
        topic_id = str(parse.get("TopicEntityMid") or parse.get("topic_entity_mid") or "")
        topic_name = str(parse.get("TopicEntityName") or parse.get("topic_entity_name") or topic_id)
        relations = _relations(parse, sparql)
        answers = _answers(parse)
        triples = _triples_from_parse(topic_id, relations, answers, sparql)
        entities = [{"id": topic_id, "name": topic_name, "source": "topic_entity"}] if topic_id else []
        candidate_entities = _candidate_entities(answers)

        sample = {
            "sample_id": sample_id,
            "dataset": "webqsp",
            "source_split": source_split,
            "audit_split": audit_split or _hash_split(sample_id),
            "question": question,
            "leakage_safe_question": _remove_answer_mentions(question, answers),
            "sparql": sparql,
            "entities": entities,
            "relations": [{"id": rel, "label": rel} for rel in relations],
            "answers": answers,
            "local_kg": {
                "triples": triples,
                "candidate_entities": candidate_entities,
            },
            "parse_status": "full" if topic_id and relations and answers else "partial",
            "source_hash": _stable_hash(record),
            "provenance": {
                "source_dataset": "webqsp",
                "semantic_parser_used": False,
                "kgqa_model_used": False,
                "trace_audit_only": True,
            },
        }
        sample["local_kg"]["subgraph_hash"] = _stable_hash(sample["local_kg"])
        return sample


def _first_parse(record: Mapping[str, Any]) -> Mapping[str, Any]:
    parses = record.get("Parses") or record.get("parses") or []
    if isinstance(parses, list) and parses:
        first = parses[0]
        if isinstance(first, Mapping):
            return first
    return {}


def _answers(parse: Mapping[str, Any]) -> list[dict[str, str]]:
    raw = parse.get("Answers") or parse.get("answers") or []
    answers = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            answer_id = str(item.get("AnswerArgument") or item.get("answer_argument") or item.get("id") or "")
            name = str(item.get("EntityName") or item.get("entity_name") or item.get("name") or answer_id)
            if answer_id:
                answers.append({"id": answer_id, "name": name})
    return answers


def _relations(parse: Mapping[str, Any], sparql: str) -> list[str]:
    chain = parse.get("InferentialChain") or parse.get("inferential_chain") or []
    if isinstance(chain, list):
        values = [str(item) for item in chain if str(item)]
        if values:
            return list(dict.fromkeys(values))
    values = []
    for _subject, relation, _object in _sparql_triples(sparql):
        values.append(relation)
    return list(dict.fromkeys(values))


def _triples_from_parse(
    topic_id: str,
    relations: list[str],
    answers: list[dict[str, str]],
    sparql: str,
) -> list[dict[str, str]]:
    chain = _executable_chain(topic_id, relations, answers)
    parsed = _sparql_triples(sparql)
    if parsed and _parsed_connects_topic_to_answer(parsed, topic_id, answers):
        triples = []
        answer_id = answers[0]["id"] if answers else ""
        for subject, relation, obj in parsed:
            triples.append(
                {
                    "subject": subject or topic_id,
                    "relation": relation,
                    "object": answer_id if obj.startswith("?") and answer_id else obj,
                }
            )
        return triples

    if chain:
        return chain
    return []


def _executable_chain(
    topic_id: str,
    relations: list[str],
    answers: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not topic_id or not relations or not answers:
        return []
    triples = []
    current = topic_id
    for index, relation in enumerate(relations):
        target = answers[0]["id"] if index == len(relations) - 1 else f"{topic_id}.bridge.{index}"
        triples.append({"subject": current, "relation": relation, "object": target})
        current = target
    return triples


def _parsed_connects_topic_to_answer(
    triples: list[tuple[str, str, str]],
    topic_id: str,
    answers: list[dict[str, str]],
) -> bool:
    answer_ids = {str(answer.get("id")) for answer in answers if answer.get("id")}
    if not topic_id or not answer_ids:
        return False
    reachable = {topic_id}
    changed = True
    while changed:
        changed = False
        for subject, _relation, obj in triples:
            if subject in reachable and obj not in reachable:
                reachable.add(obj)
                changed = True
            if subject in reachable and obj.startswith("?") and answer_ids - reachable:
                reachable.update(answer_ids)
                changed = True
    return bool(reachable & answer_ids)


def _sparql_triples(sparql: str) -> list[tuple[str, str, str]]:
    pattern = re.compile(r"(?:ns:)?([A-Za-z0-9_.:-]+|\?[A-Za-z0-9_]+)\s+(?:ns:)?([A-Za-z0-9_.:-]+)\s+(?:ns:)?([A-Za-z0-9_.:-]+|\?[A-Za-z0-9_]+)\s*\.")
    triples = []
    for match in pattern.finditer(sparql):
        subject, relation, obj = match.groups()
        triples.append((subject, relation, obj))
    return triples


def _candidate_entities(answers: list[dict[str, str]]) -> list[dict[str, Any]]:
    candidates = [dict(answer, source="answer_candidate", is_gold=False) for answer in answers]
    if answers:
        candidates.append(
            {
                "id": f"{answers[0]['id']}.distractor",
                "name": "distractor candidate",
                "source": "deterministic_distractor",
                "is_gold": False,
            }
        )
    return candidates


def _remove_answer_mentions(question: str, answers: list[dict[str, str]]) -> str:
    safe = question
    for answer in answers:
        for value in (answer.get("id", ""), answer.get("name", "")):
            if value:
                safe = safe.replace(value, "[ANSWER]")
    return safe


def _hash_split(sample_id: str, *, dev_percent: int = 30) -> str:
    digest = hashlib.sha256(f"webqsp-trace-audit:{sample_id}".encode("utf-8")).hexdigest()
    return "dev" if int(digest[:8], 16) % 100 < dev_percent else "locked"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
