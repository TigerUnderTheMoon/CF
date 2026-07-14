from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "scar_audit_record.schema.json"


def _valid_record() -> dict[str, object]:
    return {
        "schema_version": "scar-1.0",
        "artifact_id": "Q42",
        "graph_snapshot": {
            "snapshot_id": "fixture-overlay",
            "sha256": "a" * 64,
        },
        "auditable": True,
        "is_bottleneck": False,
        "is_redundant": True,
        "redundancy_group_id": "rg_0001",
        "downstream_impact_count": 4,
        "sink_drop_count": 0,
        "at_risk_terminal_ids": [],
        "raw_risk_score": 0.5,
        "extractor_metadata": {
            "extractor": "structural-audit-v1",
            "protocol_version": "fair-v1",
            "candidate_rule": "layer > 0 and downstream_impact_count > 0",
            "source_unit_id": "fixture",
            "replicate_id": "7",
            "candidate_id_sha256": "b" * 64,
        },
    }


def test_scar_schema_accepts_complete_record_and_rejects_missing_contract_field() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(_valid_record(), schema)

    incomplete = _valid_record()
    del incomplete["sink_drop_count"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(incomplete, schema)


def test_scar_schema_rejects_unknown_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    record = _valid_record()
    record["legacy_scu_score"] = 0.7

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)
