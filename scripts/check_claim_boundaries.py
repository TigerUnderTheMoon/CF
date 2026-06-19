"""Scan active paper and project sources for claim-boundary regressions."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ACTIVE_KBS_DOIS = (
    "10.1016/j.knosys.2025.113503",
    "10.1016/j.knosys.2025.113648",
    "10.1016/j.knosys.2024.112410",
)

FORBIDDEN_PATTERNS = (
    "true causal effect",
    "average treatment effect",
    "external generalization",
    "PRM training improvement",
    "deployed KBS validation",
    "all interventions are structure-preserving",
    "per-step counterfactual outcome differences",
)

NEGATION_MARKERS = (
    "not ",
    "no ",
    "without ",
    "does not ",
    "do not ",
    "cannot ",
    "must not ",
    "unvalidated",
    "future ",
    "blocked",
    "forbidden",
    "requires",
    "remain",
    "remains",
)

ACTIVE_EXTENSIONS = {".md", ".tex", ".yml", ".yaml"}
ACTIVE_ROOT_FILES = {"README.md", "AGENTS.md", "dvc.yaml", "dvc.lock"}
EXCLUDED_PREFIXES = (
    ".git/",
    ".pytest_cache/",
    "docs/legacy/",
    "docs/superpowers/",
)
SUPERSEDED_PAPER_MARKDOWN = {
    "paper/introduction.md",
    "paper/manuscript.md",
    "paper/related_work.md",
}


@dataclass(frozen=True)
class ClaimFinding:
    path: str
    line: int
    pattern: str
    text: str


def strip_fenced_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def scan_text(path: str, text: str) -> list[ClaimFinding]:
    scanned = strip_fenced_code(text) if path.replace("\\", "/").endswith("AGENTS.md") else text
    findings: list[ClaimFinding] = []
    lines = scanned.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if "[XX]" in line:
            findings.append(ClaimFinding(path, line_number, "[XX]", line.strip()))
        lower_line = line.lower()
        lower_context = " ".join(lines[max(0, line_number - 4) : line_number]).lower()
        for pattern in FORBIDDEN_PATTERNS:
            pattern_lower = pattern.lower()
            if pattern_lower not in lower_line:
                continue
            if _is_boundary_language(lower_context, pattern_lower):
                continue
            findings.append(ClaimFinding(path, line_number, pattern, line.strip()))
    return findings


def iter_active_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in SUPERSEDED_PAPER_MARKDOWN:
            continue
        if any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            continue
        if ".git/" in rel or rel.startswith(".git/"):
            continue
        if rel in ACTIVE_ROOT_FILES or path.suffix in ACTIVE_EXTENSIONS:
            yield path


def scan_active_files(root: Path) -> list[ClaimFinding]:
    findings: list[ClaimFinding] = []
    for path in iter_active_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(path.relative_to(root).as_posix(), text))
    return findings


def check_doi_links(dois: Sequence[str] = ACTIVE_KBS_DOIS) -> list[str]:
    failures: list[str] = []
    for doi in dois:
        request = urllib.request.Request(
            f"https://doi.org/{doi}",
            method="HEAD",
            headers={"User-Agent": "fma-claim-boundary-check/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status < 200 or response.status >= 400:
                    failures.append(f"{doi}: HTTP {response.status}")
        except Exception as exc:  # pragma: no cover - network-dependent CI guard
            failures.append(f"{doi}: {exc}")
    return failures


def _is_boundary_language(line: str, pattern: str) -> bool:
    index = line.find(pattern)
    if index < 0:
        return False
    window = line[max(0, index - 80) : min(len(line), index + len(pattern) + 80)]
    return any(marker in window for marker in NEGATION_MARKERS)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--active-only", action="store_true", help="Scan active project sources.")
    parser.add_argument("--check-dois", action="store_true", help="Check configured DOI links.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    findings = scan_active_files(args.root) if args.active_only else []
    doi_failures = check_doi_links() if args.check_dois else []

    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.pattern}: {finding.text}")
    for failure in doi_failures:
        print(f"DOI check failed: {failure}")

    return 1 if findings or doi_failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
