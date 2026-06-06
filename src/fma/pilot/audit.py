from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AuditStatus = Literal["PASS", "FAIL", "WARN"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=_utc_now)
    route_id: str
    stage: str
    status: AuditStatus
    event_type: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class FailureAudit(AuditEvent):
    status: Literal["FAIL"] = "FAIL"
    failure_codes: list[str] = Field(default_factory=list)
    abandonment_reason: str | None = None
    cost_usd: float = 0.0


class AuditLogger:
    """Persist structured audit events to SQLite and JSONL."""

    def __init__(
        self,
        output_dir: str | Path = Path("outputs"),
        *,
        db_path: str | Path | None = None,
        jsonl_path: str | Path | None = None,
    ) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
            self.output_dir = self.db_path.parent
        else:
            self.output_dir = Path(output_dir)
            self.db_path = self.output_dir / "audit.db"
        self.jsonl_path = Path(jsonl_path) if jsonl_path is not None else self.output_dir / "audit.jsonl"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def log_event(self, event: AuditEvent) -> int:
        with self._connect() as conn:
            event_id = self._insert_event(conn, event)
        self._append_jsonl(event)
        return event_id

    def log_failure(self, failure: FailureAudit) -> int:
        with self._connect() as conn:
            event_id = self._insert_event(conn, failure)
            conn.execute(
                """
                INSERT INTO failure_audits (
                    event_id,
                    failure_codes_json,
                    abandonment_reason,
                    cost_usd
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    event_id,
                    _json_dumps(failure.failure_codes),
                    failure.abandonment_reason,
                    float(failure.cost_usd),
                ),
            )
            if failure.abandonment_reason or failure.event_type == "abandonment":
                conn.execute(
                    """
                    INSERT INTO route_decisions (
                        timestamp,
                        route_id,
                        decision,
                        reason,
                        source_event_id,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _format_timestamp(failure.timestamp),
                        failure.route_id,
                        "ABANDONED",
                        failure.abandonment_reason,
                        event_id,
                        _json_dumps(failure.metadata),
                    ),
                )
        self._append_jsonl(failure)
        return event_id

    def log_abandonment(self, failure: FailureAudit) -> int:
        payload = failure.model_copy(update={"event_type": "abandonment"})
        return self.log_failure(payload)

    def get_route_summary(self, route_id: str) -> dict[str, Any]:
        events = self.list_events(route_id=route_id)
        status_counts = Counter(str(event["status"]) for event in events)
        failures = [event for event in events if event.get("failure_codes") is not None]
        costs = [float(event.get("cost_usd") or 0.0) for event in failures]
        code_counts: Counter[str] = Counter()
        for event in failures:
            code_counts.update(str(code) for code in event.get("failure_codes") or [])

        latest_event = events[-1] if events else None
        latest_decision = self._latest_decision(route_id)
        total_events = len(events)
        fail_count = int(status_counts.get("FAIL", 0))

        return {
            "route_id": route_id,
            "total_events": total_events,
            "status_counts": dict(sorted(status_counts.items())),
            "failure_count": len(failures),
            "failure_rate": (fail_count / total_events) if total_events else 0.0,
            "total_cost_usd": sum(costs),
            "average_cost_usd": (sum(costs) / len(costs)) if costs else 0.0,
            "most_common_failure_codes": [
                {"failure_code": code, "count": count}
                for code, count in code_counts.most_common()
            ],
            "latest_event": latest_event,
            "latest_decision": latest_decision,
        }

    def list_events(
        self,
        *,
        status: str | None = None,
        route_id: str | None = None,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []
        if status:
            filters.append("e.status = ?")
            params.append(status)
        if route_id:
            filters.append("e.route_id = ?")
            params.append(route_id)

        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        query = f"""
            SELECT
                e.id,
                e.timestamp,
                e.route_id,
                e.stage,
                e.status,
                e.event_type,
                e.message,
                e.metadata_json,
                f.failure_codes_json,
                f.abandonment_reason,
                f.cost_usd
            FROM events e
            LEFT JOIN failure_audits f ON f.event_id = e.id
            {where}
            ORDER BY e.timestamp ASC, e.id ASC
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def iter_route_summaries(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            route_rows = conn.execute(
                "SELECT DISTINCT route_id FROM events ORDER BY route_id ASC"
            ).fetchall()
        return [self.get_route_summary(str(row[0])) for row in route_rows]

    def render_markdown_report(self, route_id: str) -> str:
        summary = self.get_route_summary(route_id)
        latest_event = summary.get("latest_event") or {}
        latest_decision = summary.get("latest_decision")
        lines = [
            f"# Audit Report: {route_id}",
            "",
            "## Summary",
            "",
            f"- Total events: `{summary['total_events']}`",
            f"- Current status: `{latest_event.get('status', 'UNKNOWN')}`",
            f"- Failure rate: `{summary['failure_rate']:.3f}`",
            f"- Average failure cost USD: `{summary['average_cost_usd']:.6f}`",
            "",
            "## Status Counts",
            "",
            "| Status | Count |",
            "|---|---:|",
        ]
        for status, count in summary["status_counts"].items():
            lines.append(f"| `{status}` | {count} |")

        lines.extend(["", "## Failure Codes", "", "| Failure code | Count |", "|---|---:|"])
        for item in summary["most_common_failure_codes"]:
            lines.append(f"| `{item['failure_code']}` | {item['count']} |")
        if not summary["most_common_failure_codes"]:
            lines.append("| None | 0 |")

        failure_events = [
            event for event in self.list_events(route_id=route_id) if event["status"] == "FAIL"
        ]
        lines.extend(["", "## Failure Events", "", "| Time | Stage | Message | Cost USD |", "|---|---|---|---:|"])
        for event in failure_events:
            lines.append(
                f"| `{event['timestamp']}` | `{event['stage']}` | "
                f"{event['message']} | {float(event.get('cost_usd') or 0.0):.6f} |"
            )
        if not failure_events:
            lines.append("| None | None | None | 0.000000 |")

        lines.extend(["", "## Route Decision", ""])
        if latest_decision:
            lines.extend(
                [
                    f"- Decision: `{latest_decision['decision']}`",
                    f"- Reason: `{latest_decision.get('reason') or ''}`",
                    f"- Timestamp: `{latest_decision['timestamp']}`",
                ]
            )
        else:
            lines.append("- Decision: `NONE_RECORDED`")

        return "\n".join(lines) + "\n"

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PASS', 'FAIL', 'WARN')),
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS failure_audits (
                    event_id INTEGER PRIMARY KEY,
                    failure_codes_json TEXT NOT NULL,
                    abandonment_reason TEXT,
                    cost_usd REAL NOT NULL DEFAULT 0.0,
                    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS route_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    source_event_id INTEGER,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(source_event_id) REFERENCES events(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_route_status
                    ON events(route_id, status);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                    ON events(timestamp, id);
                CREATE INDEX IF NOT EXISTS idx_route_decisions_route_timestamp
                    ON route_decisions(route_id, timestamp, id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _insert_event(self, conn: sqlite3.Connection, event: AuditEvent) -> int:
        cursor = conn.execute(
            """
            INSERT INTO events (
                timestamp,
                route_id,
                stage,
                status,
                event_type,
                message,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _format_timestamp(event.timestamp),
                event.route_id,
                event.stage,
                event.status,
                event.event_type,
                event.message,
                _json_dumps(event.metadata),
            ),
        )
        return int(cursor.lastrowid)

    def _append_jsonl(self, event: AuditEvent) -> None:
        payload = _event_to_json_payload(event)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(_json_dumps(payload) + "\n")

    def _row_to_event(self, row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
        (
            event_id,
            timestamp,
            route_id,
            stage,
            status,
            event_type,
            message,
            metadata_json,
            failure_codes_json,
            abandonment_reason,
            cost_usd,
        ) = row
        event: dict[str, Any] = {
            "id": event_id,
            "timestamp": timestamp,
            "route_id": route_id,
            "stage": stage,
            "status": status,
            "event_type": event_type,
            "message": message,
            "metadata": json.loads(metadata_json or "{}"),
        }
        if failure_codes_json is not None:
            event.update(
                {
                    "failure_codes": json.loads(failure_codes_json),
                    "abandonment_reason": abandonment_reason,
                    "cost_usd": float(cost_usd or 0.0),
                }
            )
        return event

    def _latest_decision(self, route_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, timestamp, route_id, decision, reason, source_event_id, metadata_json
                FROM route_decisions
                WHERE route_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (route_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "timestamp": row[1],
            "route_id": row[2],
            "decision": row[3],
            "reason": row[4],
            "source_event_id": row[5],
            "metadata": json.loads(row[6] or "{}"),
        }


def _event_to_json_payload(event: AuditEvent) -> dict[str, Any]:
    payload = event.model_dump(mode="python")
    payload["timestamp"] = _format_timestamp(event.timestamp)
    return payload


def format_event_list(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No audit events found.\n"
    lines = [
        "timestamp\troute_id\tstage\tstatus\tevent_type\tmessage\tfailure_codes\tcost_usd"
    ]
    for event in events:
        failure_codes = ";".join(str(code) for code in event.get("failure_codes") or [])
        cost = event.get("cost_usd")
        lines.append(
            "\t".join(
                [
                    str(event["timestamp"]),
                    str(event["route_id"]),
                    str(event["stage"]),
                    str(event["status"]),
                    str(event["event_type"]),
                    str(event["message"]),
                    failure_codes,
                    "" if cost is None else f"{float(cost):.6f}",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def format_route_stats(summaries: list[dict[str, Any]]) -> str:
    if not summaries:
        return "No audit events found.\n"
    lines = [
        "route_id\ttotal_events\tfailure_rate\taverage_cost_usd\tmost_common_failure_code"
    ]
    for summary in summaries:
        common = summary["most_common_failure_codes"]
        common_code = common[0]["failure_code"] if common else ""
        lines.append(
            "\t".join(
                [
                    str(summary["route_id"]),
                    str(summary["total_events"]),
                    f"{float(summary['failure_rate']):.6f}",
                    f"{float(summary['average_cost_usd']):.6f}",
                    common_code,
                ]
            )
        )
    return "\n".join(lines) + "\n"
