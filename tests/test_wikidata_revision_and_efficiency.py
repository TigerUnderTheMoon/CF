from __future__ import annotations

import json
from urllib.error import URLError

import fma.eval.wikidata_revision_cases as revision_module
from fma.eval.wikidata_controlled_audit import run_efficiency_experiment
from fma.eval.wikidata_revision_cases import (
    diff_property_claims,
    fetch_verified_revision_cases,
)
from fma.graph.wikidata_scientist_kg import Triple, build_clean_digraph


def _entity_payload(qid: str, property_id: str, targets: list[str]) -> dict[str, object]:
    return {
        "entities": {
            qid: {
                "claims": {
                    property_id: [
                        {"mainsnak": {"datavalue": {"value": {"id": target}}}}
                        for target in targets
                    ]
                }
            }
        }
    }


def test_property_claim_diff_verifies_old_and_new_values() -> None:
    before = _entity_payload("Q1", "P108", ["Q2"])
    after = _entity_payload("Q1", "P108", ["Q3"])

    change = diff_property_claims(before, after, qid="Q1", property_id="P108")

    assert change == {"old_values": ["Q2"], "new_values": ["Q3"], "changed": True}


def test_revision_cases_require_verified_claim_changes() -> None:
    histories = {
        "Q1": [
            {
                "revid": 11,
                "parentid": 10,
                "timestamp": "2025-01-02T00:00:00Z",
                "comment": "/* wbsetclaim-update:2||1 */ [[Property:P108]]",
            }
        ],
        "Q2": [
            {
                "revid": 21,
                "parentid": 20,
                "timestamp": "2025-02-02T00:00:00Z",
                "comment": "/* wbsetclaim-create:1 */ [[Property:P166]]",
            }
        ],
    }
    payloads = {
        ("Q1", 10): _entity_payload("Q1", "P108", ["Q100"]),
        ("Q1", 11): _entity_payload("Q1", "P108", ["Q101"]),
        ("Q2", 20): _entity_payload("Q2", "P166", []),
        ("Q2", 21): _entity_payload("Q2", "P166", ["Q200"]),
    }

    cases = fetch_verified_revision_cases(
        ["Q1", "Q2"],
        fetch_history=lambda qid: histories[qid],
        fetch_revision=lambda qid, revision_id: payloads[(qid, revision_id)],
        max_entities=2,
    )

    assert [case.case_type for case in cases] == ["institution_change", "award_update"]
    assert cases[0].old_values == ("Q100",)
    assert cases[0].new_values == ("Q101",)
    assert cases[1].old_values == ()
    assert cases[1].new_values == ("Q200",)
    assert all("oldid=" in case.permalink for case in cases)


def test_efficiency_experiment_reports_stages_memory_and_complexity() -> None:
    triples = []
    scientists = set()
    for index in range(4):
        scientist = f"Q{index + 1}"
        scientists.add(scientist)
        triples.extend(
            [
                Triple(scientist, "P108", f"Q{100 + index}"),
                Triple(f"Q{100 + index}", "P17", f"Q{200 + index}"),
                Triple(f"Q{200 + index}", "P30", f"Q{300 + index}"),
            ]
        )
    graph = build_clean_digraph(triples)

    report = run_efficiency_experiment(
        graph,
        scientists,
        sizes=[8, 12],
        repeats=2,
        warmups=0,
        seed=13,
        motif_count=1,
    )

    assert len(report["rows"]) == 4
    assert {row["target_nodes"] for row in report["rows"]} == {8, 12}
    assert all(row["total_seconds"] > 0.0 for row in report["rows"])
    assert all(row["clustered_selection_seconds"] >= 0.0 for row in report["rows"])
    assert all(row["peak_python_mb"] >= 0.0 for row in report["rows"])
    assert set(report["complexity"]) == {
        "cleaning_and_layering",
        "bottleneck_definition",
        "bottleneck_implementation",
        "terminal_coverage_and_redundancy",
        "selection",
        "impact_coverage",
    }
    assert report["empirical_log_log_slope"] is not None


def test_revision_history_retries_transient_network_eof(monkeypatch) -> None:
    payload = {
        "query": {
            "pages": [
                {
                    "revisions": [
                        {"revid": 2, "parentid": 1, "timestamp": "2025-01-01", "comment": "P108"}
                    ]
                }
            ]
        }
    }
    attempts = 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    def flaky_urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise URLError("unexpected EOF")
        return Response()

    monkeypatch.setattr(revision_module, "urlopen", flaky_urlopen)

    rows = revision_module.fetch_revision_history("Q1")

    assert attempts == 2
    assert rows[0]["revid"] == 2
