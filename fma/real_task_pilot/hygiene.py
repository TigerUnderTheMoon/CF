"""Narrative hygiene audit for allowed manuscript and docs paths."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


FORBIDDEN_PATTERNS = {
    "true causal effect": re.compile(r"\btrue causal effect\b", re.IGNORECASE),
    "average treatment effect": re.compile(r"\baverage treatment effect\b", re.IGNORECASE),
    "globally identifiable causal quantity": re.compile(
        r"\bglobally identifiable causal quantity\b", re.IGNORECASE
    ),
    "global confirmation": re.compile(r"\bglobal confirmation\b", re.IGNORECASE),
    "causal discovery framework": re.compile(r"\bcausal discovery framework\b", re.IGNORECASE),
    "full causal identification": re.compile(r"\bfull causal identification\b", re.IGNORECASE),
    "causal attribution of reflective cognition": re.compile(
        r"\bcausal attribution of reflective cognition\b", re.IGNORECASE
    ),
    "direct causal contrast": re.compile(r"\bdirect causal contrast\b", re.IGNORECASE),
    "causally improve": re.compile(r"\bcausally improve\b", re.IGNORECASE),
    "causal utility": re.compile(r"\bcausal utility\b", re.IGNORECASE),
}


def candidate_files(root: str | Path = ".") -> list[Path]:
    repo = Path(root)
    paths = [repo / "README.md", repo / "PLANS.md"]
    for folder in ("docs", "paper"):
        paths.extend(sorted((repo / folder).glob("*.md")))
    return [path for path in paths if path.exists()]


def scan_hygiene(paths: Iterable[Path]) -> dict[str, object]:
    findings = []
    placeholders = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in FORBIDDEN_PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        {
                            "path": str(path),
                            "line": line_number,
                            "pattern": label,
                            "text": line.strip(),
                        }
                    )
            if "PLACEHOLDER" in line or "TODO: manual bibliography completion" in line:
                placeholders.append(
                    {
                        "path": str(path),
                        "line": line_number,
                        "text": line.strip(),
                    }
                )
    return {
        "hygiene_clean": not findings and not placeholders,
        "forbidden_findings": findings,
        "citation_placeholders_retained": placeholders,
        "scanned_files": [str(path) for path in paths],
    }


def render_hygiene_markdown(report: dict[str, object]) -> str:
    findings = report.get("forbidden_findings", [])
    placeholders = report.get("citation_placeholders_retained", [])
    lines = [
        "# Real-Task Pilot Hygiene Audit",
        "",
        f"hygiene_clean: {str(report.get('hygiene_clean')).lower()}",
        f"scanned_files: {len(report.get('scanned_files', []))}",
        "",
        "## Forbidden Findings",
    ]
    if findings:
        for item in findings:
            lines.append(
                "- {path}:{line} [{pattern}] {text}".format(**item)
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Retained Citation Placeholders"])
    if placeholders:
        for item in placeholders:
            lines.append("- {path}:{line} {text}".format(**item))
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)
