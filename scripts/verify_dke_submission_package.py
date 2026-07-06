from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


CURRENT_TITLE = (
    "Structurally-Calibrated Functional Attribution for Audit Prioritization "
    "in Knowledge-Intensive Reasoning"
)

REQUIRED_FILES = (
    "Highlights.docx",
    "cover_letter.docx",
    "manuscript.pdf",
    "supplementary.pdf",
    "latex_source.zip",
)

REQUIRED_ZIP_FILES = (
    "manuscript.tex",
    "supplementary.tex",
    "references.bib",
    "cas-sc.cls",
    "cas-common.sty",
    "cas-model2-names.bst",
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
    "*.synctex.gz",
    "_tmp_*",
)

AUXILIARY_ZIP_SUFFIXES = (
    ".aux",
    ".bbl",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".abs",
    ".synctex.gz",
)

FORBIDDEN_TRANSFER_SNIPPETS = {
    "Knowledge-Based Systems": "residual Knowledge-Based Systems venue wording remains",
    "for consideration as a regular article in Knowledge-Based Systems": (
        "old KBS journal submission wording remains"
    ),
    "Knowledge-Based Systems / Elsevier CAS manuscript package": (
        "old KBS manuscript package header remains"
    ),
    "Knowledge-Based Systems / Elsevier CAS supplementary package": (
        "old KBS supplementary package header remains"
    ),
    "Knowledge-Based Systems  \nElsevier": "old KBS cover-letter addressee remains",
    "Final KBS Package Manifest": "old KBS package manifest title remains",
    "KBS-facing": "residual KBS-facing wording remains",
    "KBS workflow": "residual KBS workflow wording remains",
    "KBS auditability": "residual KBS auditability wording remains",
    "KBS methodological analogy": "residual KBS methodological analogy remains",
    "KBS-style": "residual KBS-style wording remains",
    "production KBS": "residual production KBS wording remains",
    "live KBS": "residual live KBS wording remains",
    "Evidence Ladder": "Evidence Ladder should not appear in the DKE final package narrative",
    "Reviewer V2": "internal Reviewer V2 label remains",
    "reviewer_v2": "internal Reviewer V2 label remains",
    "outputs/kbs_": "old KBS path or output prefix remains",
    "outputs\\kbs_": "old KBS path or output prefix remains",
    "paper/kbs_submission": "old KBS path or output prefix remains",
    "paper\\kbs_submission": "old KBS path or output prefix remains",
}


@dataclass(frozen=True)
class VerificationReport:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("-\n", "")).strip()


def _contains_snippet(text: str, snippet: str) -> bool:
    return snippet in text or _normalize_for_match(snippet) in _normalize_for_match(text)


def _read_docx_text(path: Path, errors: list[str]) -> str:
    if not path.exists():
        return ""
    try:
        with zipfile.ZipFile(path) as zf:
            document_xml = zf.read("word/document.xml")
    except KeyError:
        errors.append(f"{path.name} is missing word/document.xml")
        return ""
    except zipfile.BadZipFile:
        errors.append(f"{path.name} is not a valid DOCX zip archive")
        return ""

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        errors.append(f"{path.name} has invalid document XML: {exc}")
        return ""

    paragraphs = []
    for para in root.iter():
        if not para.tag.endswith("}p"):
            continue
        text_nodes = [
            node.text
            for node in para.iter()
            if node.tag.endswith("}t") and node.text
        ]
        if text_nodes:
            paragraphs.append("".join(text_nodes))
    return "\n".join(paragraphs)


def _check_required_files(package_dir: Path, errors: list[str]) -> None:
    for rel_path in REQUIRED_FILES:
        path = package_dir / rel_path
        if not path.exists():
            errors.append(f"missing required package file: {rel_path}")
        elif path.stat().st_size == 0:
            errors.append(f"required package file is empty: {rel_path}")


def _check_top_level_boundary(package_dir: Path, errors: list[str]) -> None:
    allowed = set(REQUIRED_FILES)
    for path in sorted(p for p in package_dir.iterdir() if p.is_file()):
        if path.name not in allowed:
            errors.append(f"unexpected file in final upload boundary: {path.name}")


def _check_auxiliary_artifacts(package_dir: Path, errors: list[str]) -> None:
    for pattern in AUXILIARY_GLOBS:
        for path in sorted(package_dir.rglob(pattern)):
            if path.name not in REQUIRED_FILES:
                errors.append(f"local build artifact should not be in upload boundary: {path.name}")


def _check_pdf_headers(package_dir: Path, errors: list[str]) -> None:
    for filename in ("manuscript.pdf", "supplementary.pdf"):
        path = package_dir / filename
        if not path.exists() or path.stat().st_size < 8:
            continue
        with path.open("rb") as fh:
            if fh.read(5) != b"%PDF-":
                errors.append(f"{filename} does not start with a PDF header")


def _read_source_zip(path: Path, errors: list[str]) -> tuple[set[str], dict[str, str]]:
    if not path.exists():
        return set(), {}
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            text_by_name = {
                name: zf.read(name).decode("utf-8", errors="ignore")
                for name in names
                if name.endswith((".tex", ".bib", ".cls", ".sty", ".bst"))
            }
            return names, text_by_name
    except zipfile.BadZipFile:
        errors.append("latex_source.zip is not a valid zip archive")
        return set(), {}


def _check_source_zip(package_dir: Path, errors: list[str]) -> dict[str, str]:
    names, text_by_name = _read_source_zip(package_dir / "latex_source.zip", errors)
    if not names:
        return {}
    for required in REQUIRED_ZIP_FILES:
        if required not in names:
            errors.append(f"latex_source.zip missing required source file: {required}")
    if not any(name.startswith("figures/") and not name.endswith("/") for name in names):
        errors.append("latex_source.zip missing required artwork directory: figures/")
    for name in sorted(names):
        if Path(name).name.startswith("_tmp_") or name.endswith(AUXILIARY_ZIP_SUFFIXES):
            errors.append(f"latex_source.zip contains build artifact: {name}")

    manuscript = text_by_name.get("manuscript.tex", "")
    supplementary = text_by_name.get("supplementary.tex", "")
    if CURRENT_TITLE not in manuscript:
        errors.append("manuscript.tex missing current title")
    for snippet in (
        "Data & Knowledge Engineering / Elsevier CAS manuscript package",
        "knowledge engineering",
        "knowledge representation",
        "knowledge maintenance",
        "knowledge graphs",
        "PRM800K Representation Behavior Study",
        "Scope and Limitations",
    ):
        if snippet not in manuscript:
            errors.append(f"manuscript.tex missing DKE transfer snippet: {snippet}")
    if "Data & Knowledge Engineering / Elsevier CAS supplementary package" not in supplementary:
        errors.append("supplementary.tex missing DKE supplementary package header")
    _check_includegraphics_paths_in_zip(names, manuscript, "manuscript.tex", errors)
    _check_includegraphics_paths_in_zip(names, supplementary, "supplementary.tex", errors)
    return text_by_name


def _check_includegraphics_paths_in_zip(
    names: set[str],
    latex_text: str,
    source_name: str,
    errors: list[str],
) -> None:
    for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{(?P<path>[^{}]+)\}", latex_text):
        raw_path = match.group("path")
        candidates = {raw_path}
        if not Path(raw_path).suffix:
            candidates.update({f"{raw_path}.png", f"{raw_path}.pdf", f"{raw_path}.jpg"})
        if not any(candidate in names for candidate in candidates):
            errors.append(f"{source_name} includes missing artwork in latex_source.zip: {raw_path}")


def _check_docx_text(package_dir: Path, errors: list[str]) -> dict[str, str]:
    cover = _read_docx_text(package_dir / "cover_letter.docx", errors)
    highlights = _read_docx_text(package_dir / "Highlights.docx", errors)
    text_by_name = {
        "cover_letter.docx": cover,
        "Highlights.docx": highlights,
    }
    for snippet in (
        "Data & Knowledge Engineering",
        CURRENT_TITLE,
        "knowledge representation and transformation layer",
        "structured audit records",
        "fixed-budget knowledge audit",
        "knowledge lifecycle",
        "knowledge maintenance",
        "knowledge curation",
        "graph-aware",
    ):
        if snippet not in cover:
            errors.append(f"cover_letter.docx missing required text: {snippet}")
    for snippet in (
        "Highlights",
        CURRENT_TITLE,
        "structured audit records",
        "Graph-aware representation fields",
        "fixed-budget knowledge maintenance, curation, and reuse",
    ):
        if snippet not in highlights:
            errors.append(f"Highlights.docx missing required text: {snippet}")
    return text_by_name


def _check_forbidden_text(text_by_name: dict[str, str], errors: list[str]) -> None:
    for filename, text in text_by_name.items():
        if filename == "references.bib":
            continue
        for snippet, message in FORBIDDEN_TRANSFER_SNIPPETS.items():
            if _contains_snippet(text, snippet):
                errors.append(f"{message}: {filename}")


def _extract_pdf_text(package_dir: Path, filename: str, errors: list[str]) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", str(package_dir / filename), "-"],
            cwd=package_dir,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        errors.append("pdftotext is required for rendered PDF text verification")
        return ""
    if result.returncode != 0:
        errors.append(f"pdftotext failed for {filename}: {(result.stderr or result.stdout).strip()}")
        return ""
    return result.stdout


def _check_pdf_text(
    package_dir: Path,
    errors: list[str],
    *,
    pdf_text_by_name: dict[str, str] | None,
) -> None:
    pdf_text = (
        pdf_text_by_name["manuscript.pdf"]
        if pdf_text_by_name is not None and "manuscript.pdf" in pdf_text_by_name
        else _extract_pdf_text(package_dir, "manuscript.pdf", errors)
    )
    if pdf_text and not _contains_snippet(pdf_text, CURRENT_TITLE):
        errors.append("rendered manuscript.pdf text does not contain current title")


def _extract_pdf_page_count(package_dir: Path, filename: str, errors: list[str]) -> int | None:
    try:
        result = subprocess.run(
            ["pdfinfo", str(package_dir / filename)],
            cwd=package_dir,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        errors.append("pdfinfo is required for page-count verification")
        return None
    if result.returncode != 0:
        errors.append(f"pdfinfo failed for {filename}: {(result.stderr or result.stdout).strip()}")
        return None
    match = re.search(r"^Pages:\s*(\d+)\s*$", result.stdout or "", flags=re.MULTILINE)
    if not match:
        errors.append(f"pdfinfo failed for {filename}: no Pages field")
        return None
    return int(match.group(1))


def _check_pdf_page_count(
    package_dir: Path,
    errors: list[str],
    *,
    min_manuscript_pages: int | None,
    max_manuscript_pages: int | None,
    pdf_page_count_by_name: dict[str, int] | None,
) -> None:
    if min_manuscript_pages is None and max_manuscript_pages is None:
        return
    observed = (
        pdf_page_count_by_name["manuscript.pdf"]
        if pdf_page_count_by_name is not None and "manuscript.pdf" in pdf_page_count_by_name
        else _extract_pdf_page_count(package_dir, "manuscript.pdf", errors)
    )
    if observed is None:
        return
    if min_manuscript_pages is not None and observed < min_manuscript_pages:
        errors.append(
            f"rendered manuscript.pdf page count {observed} is below minimum {min_manuscript_pages}"
        )
    if max_manuscript_pages is not None and observed > max_manuscript_pages:
        errors.append(
            f"rendered manuscript.pdf page count {observed} exceeds maximum {max_manuscript_pages}"
        )


def check_package(
    package_dir: Path,
    *,
    require_pdf_text: bool = False,
    pdf_text_by_name: dict[str, str] | None = None,
    min_manuscript_pages: int | None = None,
    max_manuscript_pages: int | None = None,
    pdf_page_count_by_name: dict[str, int] | None = None,
) -> VerificationReport:
    errors: list[str] = []
    warnings: list[str] = []
    package_dir = package_dir.resolve()
    if not package_dir.exists():
        return VerificationReport(errors=[f"missing package directory: {package_dir}"], warnings=[])

    _check_required_files(package_dir, errors)
    _check_top_level_boundary(package_dir, errors)
    _check_auxiliary_artifacts(package_dir, errors)
    _check_pdf_headers(package_dir, errors)
    docx_text = _check_docx_text(package_dir, errors)
    source_text = _check_source_zip(package_dir, errors)
    all_text = dict(source_text)
    all_text.update(docx_text)
    _check_forbidden_text(all_text, errors)
    if require_pdf_text:
        _check_pdf_text(package_dir, errors, pdf_text_by_name=pdf_text_by_name)
    _check_pdf_page_count(
        package_dir,
        errors,
        min_manuscript_pages=min_manuscript_pages,
        max_manuscript_pages=max_manuscript_pages,
        pdf_page_count_by_name=pdf_page_count_by_name,
    )
    return VerificationReport(errors=errors, warnings=warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the final Data & Knowledge Engineering transfer package."
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=Path("paper") / "dke_submission" / "final_package",
    )
    parser.add_argument("--require-pdf-text", action="store_true")
    parser.add_argument("--min-manuscript-pages", type=int, default=None)
    parser.add_argument("--max-manuscript-pages", type=int, default=None)
    args = parser.parse_args(argv)

    report = check_package(
        args.package_dir,
        require_pdf_text=args.require_pdf_text,
        min_manuscript_pages=args.min_manuscript_pages,
        max_manuscript_pages=args.max_manuscript_pages,
    )
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    if report.ok:
        print("DKE final submission package check passed")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
