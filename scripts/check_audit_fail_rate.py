from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuditCheckResult:
    exit_code: int
    warning_needed: bool
    latest_route_id: str | None
    failure_rate: float
    message: str


def check_audit_fail_rate(db_path: Path = Path("outputs") / "audit.db", *, threshold: float = 0.5) -> AuditCheckResult:
    if not db_path.exists():
        return AuditCheckResult(
            exit_code=0,
            warning_needed=False,
            latest_route_id=None,
            failure_rate=0.0,
            message=f"audit db not found: {db_path}",
        )

    with sqlite3.connect(db_path) as conn:
        latest = conn.execute(
            """
            SELECT route_id
            FROM events
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if latest is None:
            return AuditCheckResult(
                exit_code=0,
                warning_needed=False,
                latest_route_id=None,
                failure_rate=0.0,
                message="audit db has no events",
            )
        route_id = str(latest[0])
        total, fails = conn.execute(
            """
            SELECT COUNT(*), SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END)
            FROM events
            WHERE route_id = ?
            """,
            (route_id,),
        ).fetchone()

    failure_rate = (float(fails or 0) / float(total or 1)) if total else 0.0
    warning_needed = failure_rate > threshold
    message = (
        f"latest route {route_id} FAIL rate {failure_rate:.3f} "
        f"threshold {threshold:.3f}"
    )
    return AuditCheckResult(
        exit_code=0,
        warning_needed=warning_needed,
        latest_route_id=route_id,
        failure_rate=failure_rate,
        message=message,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warn when latest audit route has high FAIL rate.")
    parser.add_argument("--db", type=Path, default=Path("outputs") / "audit.db")
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = check_audit_fail_rate(args.db, threshold=args.threshold)
    prefix = "::warning::" if result.warning_needed else ""
    print(f"{prefix}{result.message}")
    raise SystemExit(result.exit_code)


if __name__ == "__main__":
    main()
