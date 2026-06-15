from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


CURRENT_TITLE = (
    "Structurally-Calibrated Functional Attribution: A Methodology for "
    "Process Supervision Weighting in Reflective Reasoning"
)

REQUIRED_FILES = (
    "main.pdf",
    "main.tex",
    "references.bib",
    "cas-sc.cls",
    "cas-common.sty",
    "cas-model2-names.bst",
    "cover_letter.md",
    "format_checklist.md",
    "final_submission_manifest.md",
    "submission_author_metadata_template.md",
    "supplementary_materials.md",
    "supplementary/supplementary_manifest.md",
    "supplementary/Supplementary_Figure_S1_governance_diagnostic_upset.png",
    "supplementary/Supplementary_Data_S1_governance_diagnostic_report.json",
)

AUXILIARY_GLOBS = (
    "*.aux",
    "*.bbl",
    "*.blg",
    "*.fdb_latexmk",
    "*.fls",
    "*.log",
    "*.out",
    "*.abs",
    "test_title.*",
)

REQUIRED_MAIN_TEX_SNIPPETS = (
    r"\begin{abstract}",
    r"\begin{highlights}",
    r"\section*{Declaration of competing interest}",
    r"\section*{Declaration of generative AI and AI-assisted technologies in the writing process}",
    r"\section*{Data and code availability}",
    r"\section*{CRediT authorship contribution statement}",
)

REQUIRED_PDF_TEXT_SNIPPETS = (
    CURRENT_TITLE,
    "Highlights",
    "Declaration of competing interest",
    "Declaration of generative AI",
    "Data and code availability",
    "CRediT authorship contribution statement",
)

FORBIDDEN_SNIPPETS = {
    "Functional Metacognitive Attribution: A Diagnostic and Design Framework": (
        "old cover-letter title remains"
    ),
    "anonymous reviewers for their constructive feedback": (
        "pre-review anonymous reviewer acknowledgment remains"
    ),
    "true causal effect": "forbidden causal-effect wording remains",
    "average treatment effect": "forbidden ATE wording remains",
    "globally identifiable causal": "forbidden global-causal-identification wording remains",
}

AUTHOR_PLACEHOLDERS = (
    "Anonymous Author(s)",
    "Anonymous Institution",
)


@dataclass(frozen=True)
class VerificationReport:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_text(path: Path, errors: list[str]) -> str:
    if not path.exists():
        errors.append(f"missing required text file: {path}")
        return ""
    return path.read_text(encoding="utf-8")


def _extract_title(main_tex: str, errors: list[str]) -> str:
    match = re.search(r"\\title\[mode=title\]\{(?P<title>[^{}]+)\}", main_tex)
    if match is None:
        errors.append("main.tex is missing \\title[mode=title]{...}")
        return ""
    return match.group("title").strip()


def _check_required_files(package_dir: Path, errors: list[str]) -> None:
    for rel_path in REQUIRED_FILES:
        path = package_dir / rel_path
        if not path.exists():
            errors.append(f"missing required package file: {rel_path}")


def _check_auxiliary_artifacts(package_dir: Path, errors: list[str]) -> None:
    for pattern in AUXILIARY_GLOBS:
        for path in sorted(package_dir.glob(pattern)):
            errors.append(f"local build artifact should not be in upload boundary: {path.name}")
    if (package_dir / "build_tmp").exists():
        errors.append("temporary build directory should not be in upload boundary: build_tmp")


def _check_title_consistency(main_tex: str, cover_letter: str, errors: list[str]) -> None:
    title = _extract_title(main_tex, errors)
    if not title:
        return
    if title != CURRENT_TITLE:
        errors.append(f"main.tex title drifted from current KBS title: {title}")
    if CURRENT_TITLE not in cover_letter:
        errors.append("cover letter does not contain current title")
    if title not in cover_letter:
        errors.append("cover letter title does not match main.tex title")


def _check_required_sections(main_tex: str, errors: list[str]) -> None:
    for snippet in REQUIRED_MAIN_TEX_SNIPPETS:
        if snippet not in main_tex:
            errors.append(f"main.tex missing required section/snippet: {snippet}")


def _check_forbidden_text(text_by_name: dict[str, str], errors: list[str]) -> None:
    for filename, text in text_by_name.items():
        for snippet, message in FORBIDDEN_SNIPPETS.items():
            if snippet in text:
                errors.append(f"{message}: {filename}")


def _check_author_metadata(
    main_tex: str,
    *,
    require_author_metadata: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    placeholders = [placeholder for placeholder in AUTHOR_PLACEHOLDERS if placeholder in main_tex]
    if not placeholders:
        return

    message = "author metadata placeholders remain"
    if require_author_metadata:
        errors.append(f"{message}: {', '.join(placeholders)}")
    else:
        warnings.append(message)


def _check_includegraphics_paths(package_dir: Path, main_tex: str, errors: list[str]) -> None:
    for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{(?P<path>[^{}]+)\}", main_tex):
        raw_path = match.group("path")
        candidate = package_dir / raw_path
        if not candidate.exists():
            errors.append(f"main.tex includes missing artwork: {raw_path}")


def _extract_pdf_text(package_dir: Path, errors: list[str]) -> str:
    pdf_path = package_dir / "main.pdf"
    text_path = package_dir / ".kbs_submission_pdf_text_check.txt"
    try:
        result = subprocess.run(
            ["pdftotext", str(pdf_path), str(text_path)],
            cwd=package_dir,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        errors.append("pdftotext is required for rendered PDF text verification")
        return ""

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        errors.append(f"pdftotext failed for rendered PDF text verification: {detail}")
        return ""

    try:
        return text_path.read_text(encoding="utf-8", errors="ignore")
    finally:
        if text_path.exists():
            text_path.unlink()


def _check_pdf_text(pdf_text: str, errors: list[str]) -> None:
    if CURRENT_TITLE not in pdf_text:
        errors.append("rendered PDF text does not contain current title")
    for snippet in REQUIRED_PDF_TEXT_SNIPPETS[1:]:
        if snippet not in pdf_text:
            errors.append(f"rendered PDF text missing required snippet: {snippet}")
    for snippet, message in FORBIDDEN_SNIPPETS.items():
        if snippet in pdf_text:
            errors.append(f"{message}: rendered PDF")


def check_package(
    package_dir: Path,
    *,
    require_author_metadata: bool = False,
    require_pdf_text: bool = False,
    pdf_text: str | None = None,
) -> VerificationReport:
    errors: list[str] = []
    warnings: list[str] = []
    package_dir = package_dir.resolve()

    if not package_dir.exists():
        return VerificationReport(errors=[f"missing package directory: {package_dir}"], warnings=[])

    _check_required_files(package_dir, errors)
    _check_auxiliary_artifacts(package_dir, errors)

    main_tex = _read_text(package_dir / "main.tex", errors)
    cover_letter = _read_text(package_dir / "cover_letter.md", errors)
    supplementary = _read_text(package_dir / "supplementary_materials.md", errors)
    supplementary_manifest = _read_text(
        package_dir / "supplementary" / "supplementary_manifest.md", errors
    )

    _check_title_consistency(main_tex, cover_letter, errors)
    _check_required_sections(main_tex, errors)
    _check_forbidden_text(
        {
            "main.tex": main_tex,
            "cover_letter.md": cover_letter,
            "supplementary_materials.md": supplementary,
            "supplementary/supplementary_manifest.md": supplementary_manifest,
        },
        errors,
    )
    _check_author_metadata(
        main_tex,
        require_author_metadata=require_author_metadata,
        errors=errors,
        warnings=warnings,
    )
    _check_includegraphics_paths(package_dir, main_tex, errors)
    if require_pdf_text:
        rendered_text = pdf_text if pdf_text is not None else _extract_pdf_text(package_dir, errors)
        if rendered_text:
            _check_pdf_text(rendered_text, errors)

    return VerificationReport(errors=errors, warnings=warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the local Knowledge-Based Systems submission package boundary."
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=Path("paper") / "kbs_submission",
        help="Path to the KBS submission package directory.",
    )
    parser.add_argument(
        "--require-author-metadata",
        action="store_true",
        help="Fail if anonymous author/affiliation placeholders remain.",
    )
    parser.add_argument(
        "--require-pdf-text",
        action="store_true",
        help="Fail if rendered main.pdf text does not contain the current title and required statements.",
    )
    args = parser.parse_args(argv)

    report = check_package(
        args.package_dir,
        require_author_metadata=args.require_author_metadata,
        require_pdf_text=args.require_pdf_text,
    )
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)

    if report.ok:
        print("KBS submission package check passed")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
