"""Verified Wikidata revision-history cases for controlled maintenance reports."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
ENTITY_DATA_URL = (
    "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json?revision={revision_id}"
)


@dataclass(frozen=True)
class RevisionCase:
    case_type: str
    entity_id: str
    property_id: str
    revision_id: int
    parent_revision_id: int
    timestamp: str
    old_values: tuple[str, ...]
    new_values: tuple[str, ...]
    permalink: str


def diff_property_claims(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    qid: str,
    property_id: str,
) -> dict[str, Any]:
    old_values = _claim_values(before, qid, property_id)
    new_values = _claim_values(after, qid, property_id)
    return {
        "old_values": old_values,
        "new_values": new_values,
        "changed": old_values != new_values,
    }


def fetch_verified_revision_cases(
    scientist_ids: Sequence[str],
    *,
    fetch_history: Callable[[str], Sequence[Mapping[str, Any]]] | None = None,
    fetch_revision: Callable[[str, int], Mapping[str, Any]] | None = None,
    max_entities: int = 100,
) -> list[RevisionCase]:
    """Find one institution and one award update verified by entity JSON diffs."""
    history_loader = fetch_history or fetch_revision_history
    revision_loader = fetch_revision or fetch_entity_revision
    wanted = {
        "institution_change": ("P108", "P463"),
        "award_update": ("P166",),
    }
    found: dict[str, RevisionCase] = {}
    for qid in sorted(map(str, scientist_ids))[:max_entities]:
        for revision in history_loader(qid):
            revision_id = int(revision.get("revid", 0))
            parent_id = int(revision.get("parentid", 0))
            if revision_id <= 0 or parent_id <= 0:
                continue
            comment = str(revision.get("comment", ""))
            for case_type, properties in wanted.items():
                if case_type in found:
                    continue
                for property_id in properties:
                    if property_id not in comment:
                        continue
                    before = revision_loader(qid, parent_id)
                    after = revision_loader(qid, revision_id)
                    change = diff_property_claims(
                        before,
                        after,
                        qid=qid,
                        property_id=property_id,
                    )
                    if not change["changed"]:
                        continue
                    found[case_type] = RevisionCase(
                        case_type=case_type,
                        entity_id=qid,
                        property_id=property_id,
                        revision_id=revision_id,
                        parent_revision_id=parent_id,
                        timestamp=str(revision.get("timestamp", "")),
                        old_values=tuple(change["old_values"]),
                        new_values=tuple(change["new_values"]),
                        permalink=(
                            f"https://www.wikidata.org/w/index.php?title={qid}"
                            f"&oldid={revision_id}"
                        ),
                    )
                    break
            if len(found) == len(wanted):
                break
        if len(found) == len(wanted):
            break
    return [found[key] for key in ("institution_change", "award_update") if key in found]


def fetch_revision_history(qid: str) -> list[dict[str, Any]]:
    revisions: list[dict[str, Any]] = []
    continuation: dict[str, str] = {}
    while True:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "revisions",
            "titles": qid,
            "rvprop": "ids|timestamp|comment",
            "rvlimit": "max",
            **continuation,
        }
        payload = _get_json(f"{WIKIDATA_API}?{urlencode(params)}")
        pages = payload.get("query", {}).get("pages", [])
        if pages:
            revisions.extend(dict(row) for row in pages[0].get("revisions", []))
        next_page = payload.get("continue")
        if not next_page:
            break
        continuation = {str(key): str(value) for key, value in next_page.items()}
    return revisions


def fetch_entity_revision(qid: str, revision_id: int) -> dict[str, Any]:
    return _get_json(ENTITY_DATA_URL.format(qid=qid, revision_id=revision_id))


def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "FMA-Wikidata-Scientist-Audit/1.0"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60.0) as response:  # noqa: S310 - fixed Wikidata URLs
                return json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(0.5 * (2**attempt))
    raise RuntimeError("unreachable Wikidata request retry state")


def _claim_values(payload: Mapping[str, Any], qid: str, property_id: str) -> list[str]:
    claims = payload.get("entities", {}).get(qid, {}).get("claims", {}).get(property_id, [])
    values = []
    for claim in claims:
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, Mapping) and value.get("id"):
            values.append(str(value["id"]))
        elif value is not None:
            values.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return sorted(set(values))
