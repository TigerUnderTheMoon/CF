from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fma.pilot.audit import AuditLogger, FailureAudit


RECOGNIZED_FAILURE_SECTIONS = {
    "Status Boundary",
    "Full Artifact Summary",
    "Quality Gate Failures",
    "Direct Pass-Gate Causes",
    "Route Decision",
    "Claim Boundary",
}
RECOGNIZED_ABANDONMENT_SECTIONS = {
    "Decision",
    "Evidence",
    "Basis",
    "Claim Boundary",
}


def migrate_markdown_audits(
    *,
    input_dir: Path = Path("outputs"),
    output_dir: Path = Path("outputs"),
    report_path: Path | None = None,
) -> dict[str, Any]:
    logger = AuditLogger(output_dir=output_dir)
    files = _find_audit_files(input_dir)
    results: list[dict[str, Any]] = []
    failed_files = 0

    for path in files:
        try:
            parsed = parse_markdown_audit(path, input_dir=input_dir)
            logger.log_failure(parsed["audit"])
            results.append({k: v for k, v in parsed.items() if k != "audit"})
        except Exception as exc:  # pragma: no cover - exercised by real migration runs.
            failed_files += 1
            results.append(
                {
                    "path": str(path),
                    "parsed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "unparsed_sections": [],
                }
            )

    report = {
        "input_dir": str(input_dir),
        "output_db": str(output_dir / "audit.db"),
        "output_jsonl": str(output_dir / "audit.jsonl"),
        "parsed_files": len(files) - failed_files,
        "failed_files": failed_files,
        "files": results,
    }
    destination = report_path or output_dir / "audit_migration_report.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_migration_report(report), encoding="utf-8")
    return report


def parse_markdown_audit(path: Path, *, input_dir: Path = Path("outputs")) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    title = _first_match(r"^#\s+(.+?)\s*$", text, flags=re.MULTILINE) or path.stem
    event_type = "abandonment" if "abandonment" in path.name.lower() else "failure"
    route_id = _infer_route_id(f"{path} {title}")
    stage = _infer_stage(path)
    timestamp = _parse_date(_first_match(r"^Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, flags=re.MULTILINE))
    source_status = _extract_status_code(text)
    failure_codes = _extract_failure_codes(text)
    if not failure_codes and source_status and ("FAIL" in source_status or "BLOCKED" in source_status):
        failure_codes = [source_status]
    cost_usd = _extract_cost_usd(text)
    abandonment_reason = _extract_abandonment_reason(text) if event_type == "abandonment" else None
    unparsed_sections = _unparsed_sections(text, event_type)

    metadata = {
        "source_path": _safe_relative_path(path, input_dir),
        "source_status": source_status,
        "parsed_title": title,
        "unparsed_sections": unparsed_sections,
        "migration_parser": "regex_v1",
    }
    message = title
    if source_status:
        message = f"{title}: {source_status}"

    audit = FailureAudit(
        timestamp=timestamp,
        route_id=route_id,
        stage=stage,
        status="FAIL",
        event_type=event_type,
        message=message,
        metadata=metadata,
        failure_codes=failure_codes,
        abandonment_reason=abandonment_reason,
        cost_usd=cost_usd,
    )
    return {
        "path": str(path),
        "parsed": True,
        "route_id": route_id,
        "stage": stage,
        "event_type": event_type,
        "failure_codes": failure_codes,
        "cost_usd": cost_usd,
        "abandonment_reason": abandonment_reason,
        "unparsed_sections": unparsed_sections,
        "audit": audit,
    }


def render_migration_report(report: dict[str, Any]) -> str:
    lines = [
        "# Audit Migration Report",
        "",
        f"- Input directory: `{report['input_dir']}`",
        f"- Output DB: `{report['output_db']}`",
        f"- Output JSONL: `{report['output_jsonl']}`",
        f"- Parsed files: `{report['parsed_files']}`",
        f"- Failed files: `{report['failed_files']}`",
        "",
        "## Files",
        "",
        "| File | Route | Type | Parsed | Unparsed sections |",
        "|---|---|---|---|---|",
    ]
    for item in report["files"]:
        unparsed = "; ".join(item.get("unparsed_sections") or [])
        lines.append(
            "| {path} | `{route}` | `{event_type}` | `{parsed}` | {unparsed} |".format(
                path=item.get("path", ""),
                route=item.get("route_id", ""),
                event_type=item.get("event_type", ""),
                parsed=item.get("parsed", False),
                unparsed=unparsed or "None",
            )
        )
    return "\n".join(lines) + "\n"


def _find_audit_files(input_dir: Path) -> list[Path]:
    files = {
        *input_dir.rglob("*failure_audit.md"),
        *input_dir.rglob("*abandonment_audit.md"),
    }
    return sorted(files, key=lambda path: ("abandonment" in path.name.lower(), str(path)))


def _extract_status_code(text: str) -> str | None:
    patterns = [
        r"\|\s*(?:Full status|Source full status|Engineering retry status|Status)\s*\|\s*`([^`]+)`\s*\|",
        r"\b(V[0-9_]+[A-Z0-9_]*FAIL[A-Z0-9_]*)\b",
        r"\b([A-Z0-9_]*BLOCKED[A-Z0-9_]*)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _extract_failure_codes(text: str) -> list[str]:
    row_match = re.search(
        r"\|\s*(?:Failure codes|Engineering retry failure codes)\s*\|\s*(.+?)\s*\|",
        text,
    )
    if row_match:
        return re.findall(r"`([^`]+)`", row_match.group(1))
    return sorted(set(re.findall(r"\b[A-Z0-9_]*FAIL[A-Z0-9_]*\b", text)))


def _extract_cost_usd(text: str) -> float:
    matches = re.findall(r"USD\s*`?([0-9]+(?:\.[0-9]+)?)`?", text)
    return float(matches[0]) if matches else 0.0


def _extract_abandonment_reason(text: str) -> str | None:
    decision = _section_text(text, "Decision")
    if decision:
        first_line = next((line.strip() for line in decision.splitlines() if line.strip()), "")
        if first_line:
            return re.sub(r"`", "", first_line)
    match = re.search(r"\babandon(?:ed|ment)\b(.+?)(?:\.|\n)", text, flags=re.IGNORECASE)
    if match:
        return match.group(0).strip().replace("`", "")
    return None


def _unparsed_sections(text: str, event_type: str) -> list[str]:
    recognized = (
        RECOGNIZED_ABANDONMENT_SECTIONS if event_type == "abandonment" else RECOGNIZED_FAILURE_SECTIONS
    )
    sections = re.findall(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE)
    return [section for section in sections if section not in recognized]


def _section_text(text: str, section: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(section)}\s*$(.*?)(?=^##\s+|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _infer_route_id(value: str) -> str:
    lowered = value.lower()
    if re.search(r"v2[._-]?1", lowered):
        return "v2.1"
    if re.search(r"v2[._-]?2", lowered):
        return "v2.2"
    if re.search(r"v2(?![._-]?[0-9])", lowered):
        return "v2"
    if "real_task_pilot" in lowered:
        return "real_task_pilot"
    return "unknown"


def _infer_stage(path: Path) -> str:
    name = path.name.lower()
    for stage in (
        "api_preflight",
        "full_validation",
        "stochastic_smoke",
        "pilot_transport",
        "primary_signal",
        "manifest_overlap",
        "contract",
        "hygiene",
    ):
        if stage in name:
            return stage
    return re.sub(r"_(?:failure|abandonment)_audit$", "", path.stem.lower())


def _parse_date(value: str | None) -> datetime:
    if value:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _first_match(pattern: str, text: str, *, flags: int = 0) -> str | None:
    match = re.search(pattern, text, flags=flags)
    return match.group(1) if match else None


def _safe_relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate markdown audit files into audit.db.")
    parser.add_argument("--input-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--report", type=Path, default=Path("outputs") / "audit_migration_report.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = migrate_markdown_audits(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        report_path=args.report,
    )
    print(render_migration_report(report), end="")


if __name__ == "__main__":
    main()
