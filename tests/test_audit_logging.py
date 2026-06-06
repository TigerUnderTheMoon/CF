from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def test_log_failure_writes_sqlite_and_jsonl(tmp_path: Path) -> None:
    from fma.pilot.audit import AuditLogger, FailureAudit

    output_dir = tmp_path / "outputs"
    logger = AuditLogger(output_dir=output_dir)
    event = FailureAudit(
        timestamp=datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc),
        route_id="v2.1",
        stage="full_validation",
        status="FAIL",
        event_type="failure",
        message="Full stochastic validation failed preregistered gates.",
        metadata={"GLOBAL_pass": False},
        failure_codes=[
            "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS",
            "V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL",
        ],
        cost_usd=65.689985,
    )

    event_id = logger.log_failure(event)

    with sqlite3.connect(output_dir / "audit.db") as conn:
        event_row = conn.execute(
            "SELECT route_id, stage, status, event_type, message, metadata_json "
            "FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        failure_row = conn.execute(
            "SELECT failure_codes_json, abandonment_reason, cost_usd "
            "FROM failure_audits WHERE event_id = ?",
            (event_id,),
        ).fetchone()

    assert event_row[:5] == (
        "v2.1",
        "full_validation",
        "FAIL",
        "failure",
        "Full stochastic validation failed preregistered gates.",
    )
    assert json.loads(event_row[5]) == {"GLOBAL_pass": False}
    assert json.loads(failure_row[0]) == [
        "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS",
        "V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL",
    ]
    assert failure_row[1] is None
    assert failure_row[2] == 65.689985

    jsonl_records = [
        json.loads(line)
        for line in (output_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert jsonl_records == [
        {
            "timestamp": "2026-06-06T12:00:00Z",
            "route_id": "v2.1",
            "stage": "full_validation",
            "status": "FAIL",
            "event_type": "failure",
            "message": "Full stochastic validation failed preregistered gates.",
            "metadata": {"GLOBAL_pass": False},
            "failure_codes": [
                "V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS",
                "V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL",
            ],
            "abandonment_reason": None,
            "cost_usd": 65.689985,
        }
    ]


def test_route_summary_aggregates_failure_codes_and_cost(tmp_path: Path) -> None:
    from fma.pilot.audit import AuditEvent, AuditLogger, FailureAudit

    logger = AuditLogger(output_dir=tmp_path / "outputs")
    logger.log_event(
        AuditEvent(
            timestamp=datetime(2026, 6, 6, 10, 0, tzinfo=timezone.utc),
            route_id="v2.1",
            stage="pilot",
            status="PASS",
            event_type="gate",
            message="Pilot gate passed.",
            metadata={},
        )
    )
    logger.log_failure(
        FailureAudit(
            timestamp=datetime(2026, 6, 6, 11, 0, tzinfo=timezone.utc),
            route_id="v2.1",
            stage="full_validation",
            status="FAIL",
            event_type="failure",
            message="Full validation failed.",
            metadata={},
            failure_codes=["SCHEMA_FAIL", "SPARSE_SIGNAL"],
            cost_usd=10.0,
        )
    )
    logger.log_failure(
        FailureAudit(
            timestamp=datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc),
            route_id="v2.1",
            stage="retry",
            status="FAIL",
            event_type="abandonment",
            message="Strict route abandoned.",
            metadata={},
            failure_codes=["SCHEMA_FAIL"],
            abandonment_reason="transport_unresolved",
            cost_usd=14.0,
        )
    )

    summary = logger.get_route_summary("v2.1")

    assert summary["route_id"] == "v2.1"
    assert summary["total_events"] == 3
    assert summary["status_counts"] == {"FAIL": 2, "PASS": 1}
    assert summary["failure_rate"] == 2 / 3
    assert summary["average_cost_usd"] == 12.0
    assert summary["most_common_failure_codes"][0] == {"failure_code": "SCHEMA_FAIL", "count": 2}
    assert summary["latest_event"]["event_type"] == "abandonment"
    assert summary["latest_decision"]["decision"] == "ABANDONED"


def test_audit_cli_lists_reports_and_stats(tmp_path: Path, capsys) -> None:
    from fma.cli import main
    from fma.pilot.audit import FailureAudit

    output_dir = tmp_path / "outputs"
    from fma.pilot.audit import AuditLogger

    logger = AuditLogger(output_dir=output_dir)
    logger.log_failure(
        FailureAudit(
            timestamp=datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc),
            route_id="v2.1",
            stage="full_validation",
            status="FAIL",
            event_type="failure",
            message="Full validation failed.",
            metadata={"GLOBAL_pass": False},
            failure_codes=["SCHEMA_FAIL"],
            cost_usd=65.0,
        )
    )

    main(["audit", "list", "--status", "FAIL", "--route", "v2.1", "--db", str(output_dir / "audit.db")])
    listed = capsys.readouterr().out
    assert "v2.1" in listed
    assert "SCHEMA_FAIL" in listed

    main(["audit", "report", "--route", "v2.1", "--format", "markdown", "--db", str(output_dir / "audit.db")])
    report = capsys.readouterr().out
    assert "# Audit Report: v2.1" in report
    assert "Current status" in report
    assert "SCHEMA_FAIL" in report

    main(["audit", "stats", "--db", str(output_dir / "audit.db")])
    stats = capsys.readouterr().out
    assert "failure_rate" in stats
    assert "v2.1" in stats


def test_migration_parses_failure_and_abandonment_markdown(tmp_path: Path) -> None:
    from scripts.migrate_markdown_audits import migrate_markdown_audits

    audit_dir = tmp_path / "outputs" / "s_fma_v2_1_fresh_holdout"
    audit_dir.mkdir(parents=True)
    (audit_dir / "v2_1_full_validation_failure_audit.md").write_text(
        "\n".join(
            [
                "# v2.1 Full Stochastic Validation Failure Audit",
                "",
                "Date: 2026-06-05",
                "",
                "## Full Artifact Summary",
                "",
                "| Field | Value |",
                "|---|---:|",
                "| Full status | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS` |",
                "| Failure codes | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`; `V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL` |",
                "| Cost in source artifact | USD `65.689985` of approved USD `150.0` |",
                "",
                "## Manual Note",
                "",
                "This paragraph is intentionally not part of the structured parser.",
            ]
        ),
        encoding="utf-8",
    )
    (audit_dir / "v2_1_full_validation_abandonment_audit.md").write_text(
        "\n".join(
            [
                "# v2.1 Full Validation Abandonment Audit",
                "",
                "Date: 2026-06-06",
                "",
                "## Decision",
                "",
                "Strict `s_FMA_v2.1` full validation is abandoned as non-viable under the current contract.",
                "",
                "## Evidence",
                "",
                "| Field | Value |",
                "|---|---:|",
                "| Source full status | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS` |",
                "| Engineering retry failure codes | `V2_1_FULL_STOCHASTIC_FAIL_SCHEMA_OR_TAGS`; `V2_1_FULL_STOCHASTIC_FAIL_SPARSE_SIGNAL` |",
                "| Cumulative route cost | USD `65.806855` |",
            ]
        ),
        encoding="utf-8",
    )

    report = migrate_markdown_audits(
        input_dir=tmp_path / "outputs",
        output_dir=tmp_path / "outputs",
        report_path=tmp_path / "outputs" / "audit_migration_report.md",
    )

    assert report["parsed_files"] == 2
    assert report["failed_files"] == 0
    assert report["files"][0]["route_id"] == "v2.1"
    assert "Manual Note" in report["files"][0]["unparsed_sections"]
    assert (tmp_path / "outputs" / "audit.db").exists()


def test_ci_check_warns_without_failing_when_latest_route_fail_rate_is_high(
    tmp_path: Path,
) -> None:
    from fma.pilot.audit import AuditEvent, AuditLogger, FailureAudit
    from scripts.check_audit_fail_rate import check_audit_fail_rate

    output_dir = tmp_path / "outputs"
    logger = AuditLogger(output_dir=output_dir)
    logger.log_event(
        AuditEvent(
            timestamp=datetime(2026, 6, 6, 10, 0, tzinfo=timezone.utc),
            route_id="v2.1",
            stage="pilot",
            status="PASS",
            event_type="gate",
            message="Pilot gate passed.",
            metadata={},
        )
    )
    for hour in (11, 12):
        logger.log_failure(
            FailureAudit(
                timestamp=datetime(2026, 6, 6, hour, 0, tzinfo=timezone.utc),
                route_id="v2.1",
                stage="full_validation",
                status="FAIL",
                event_type="failure",
                message="Full validation failed.",
                metadata={},
                failure_codes=["SCHEMA_FAIL"],
                cost_usd=1.0,
            )
        )

    result = check_audit_fail_rate(output_dir / "audit.db", threshold=0.5)

    assert result.exit_code == 0
    assert result.warning_needed is True
    assert result.latest_route_id == "v2.1"
    assert result.failure_rate == 2 / 3
