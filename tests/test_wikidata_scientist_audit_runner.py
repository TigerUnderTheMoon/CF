from __future__ import annotations

import json
from pathlib import Path

from fma.eval.wikidata_scientist_audit_runner import run_wikidata_scientist_audit


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _binding(subject: str, predicate: str, obj: str) -> dict[str, dict[str, str]]:
    return {
        "subject": {"type": "uri", "value": f"http://www.wikidata.org/entity/{subject}"},
        "predicate": {
            "type": "uri",
            "value": f"http://www.wikidata.org/prop/direct/{predicate}",
        },
        "object": {"type": "uri", "value": f"http://www.wikidata.org/entity/{obj}"},
    }


def _fixture_response() -> dict[str, object]:
    bindings = []
    for index in range(4):
        scientist = f"Q{index + 1}"
        bindings.extend(
            [
                _binding(scientist, "P106", "Q169470"),
                _binding(scientist, "P108", f"Q{100 + index}"),
                _binding(f"Q{100 + index}", "P17", f"Q{200 + index}"),
                _binding(f"Q{200 + index}", "P30", f"Q{300 + index}"),
            ]
        )
    return {"results": {"bindings": bindings}}


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


def test_runner_writes_reproducible_audit_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "audit"
    histories = {
        "Q1": [
            {
                "revid": 11,
                "parentid": 10,
                "timestamp": "2025-01-02T00:00:00Z",
                "comment": "[[Property:P108]]",
            }
        ],
        "Q2": [
            {
                "revid": 21,
                "parentid": 20,
                "timestamp": "2025-02-02T00:00:00Z",
                "comment": "[[Property:P166]]",
            }
        ],
        "Q3": [],
        "Q4": [],
    }
    revisions = {
        ("Q1", 10): _entity_payload("Q1", "P108", ["Q100"]),
        ("Q1", 11): _entity_payload("Q1", "P108", ["Q101"]),
        ("Q2", 20): _entity_payload("Q2", "P166", []),
        ("Q2", 21): _entity_payload("Q2", "P166", ["Q200"]),
    }
    config = {
        "experiment": {"name": "fixture_wikidata_audit", "seed": 5, "seeds": [5, 7]},
        "output_dir": output_dir,
        "extraction": {
            "endpoint": "https://query.wikidata.org/sparql",
            "scientist_limits": [4],
            "min_nodes": 12,
            "max_nodes": 20,
            "min_edges": 12,
            "max_edges": 30,
            "cache_path": output_dir / "data" / "wdqs_cache.json",
            "timeout_seconds": 1,
        },
        "audit": {"primary_budget_fraction": 0.25, "motif_count": 1},
        "anchor_confirmation": {
            "budget_fraction": 0.05,
            "clusters_per_discipline": 2,
            "require_complete_clusters": False,
        },
        "noise": {"rates": [0.0, 0.10]},
        "budget": {"fractions": [0.10, 0.25]},
        "statistics": {"bootstrap_rounds": 20},
        "efficiency": {"sizes": [8, 12], "repeats": 1, "warmups": 0},
        "case_studies": {"max_entities": 4},
        "countries_report_path": PROJECT_ROOT
        / "paper"
        / "JIIS_submission"
        / "reports"
        / "jiis_audit_case"
        / "jiis_audit_case_report.json",
        "substrate_provenance": {
            "version": "fixture_corrected_multidisciplinary_v2",
            "same_as_v1": False,
            "supersedes_cache_sha256": "fixture-v1-hash",
            "correction_reason": "fixture physical-only rejection",
        },
    }

    report = run_wikidata_scientist_audit(
        config,
        fetch_json=lambda *_args: _fixture_response(),
        revision_history_loader=lambda qid: histories[qid],
        revision_entity_loader=lambda qid, revision_id: revisions[(qid, revision_id)],
    )

    required = [
        "configs/config.yaml",
        "logs/run.log",
        "data/triples.jsonl",
        "data/triples.csv",
        "data/raw_graph.graphml",
        "data/audit_overlay.graphml",
        "traces/motif_manifest.json",
        "metrics/graph_statistics.json",
        "metrics/controlled_audit_roles.json",
        "metrics/impact_coverage.json",
        "metrics/noise_deletion.json",
        "metrics/noise_insertion.json",
        "metrics/budget_sensitivity.json",
        "metrics/efficiency.json",
        "metrics/anchor_cluster_confirmation.json",
        "metrics/anchor_cluster_confirmation_summary.csv",
        "cases/revision_cases.json",
        "summary.json",
        "summary.csv",
        "report.md",
    ]
    figures = [
        "overall_workflow.png",
        "core_structure.png",
        "impact_coverage_comparison.png",
        "noise_deletion.png",
        "noise_insertion.png",
        "budget_sensitivity.png",
        "efficiency_scaling.png",
        "anchor_cluster_confirmation.png",
        "budget_structural_protection.png",
        "noise_deletion_structural_protection.png",
        "noise_insertion_structural_protection.png",
    ]
    assert all((output_dir / relative).is_file() for relative in required)
    assert all((output_dir / "figures" / name).stat().st_size > 0 for name in figures)
    text = (output_dir / "report.md").read_text(encoding="utf-8")
    assert "Controlled Audit Role Evaluation" in text
    assert "Evaluation is performed against controlled audit motifs" in text
    assert "Role Recovery" not in text
    assert "Audit Role Agreement" not in text
    assert "Anchor-Cluster Confirmation" in text
    assert len(report["case_studies"]) == 2
    assert all(case["life_saving_first_selected"] for case in report["case_studies"])
    assert all(not case["flat_top_k_selected"] for case in report["case_studies"])
    assert all(
        case["life_saving_first_protected_at_risk_records"] == 3
        for case in report["case_studies"]
    )
    assert all(case["flat_top_k_protected_at_risk_records"] == 0 for case in report["case_studies"])
    assert report["validated_production_workflow"] is False
    assert report["source"]["substrate_provenance"]["same_as_v1"] is False
    assert report["anchor_cluster_confirmation"]["statistical_unit"] == "anchor_cluster"
    assert report["anchor_cluster_confirmation"]["budget_fraction"] == 0.05
    wikidata_rows = [
        row for row in report["summary_rows"] if row["dataset"] == "Wikidata scientist KG"
    ]
    assert all("cliffs_delta_lsf_minus_method" in row for row in wikidata_rows)
    assert all("cliffs_delta_vs_lsf" not in row for row in wikidata_rows)
    assert json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))["rows"]
