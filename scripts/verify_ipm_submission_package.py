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

DATA_AVAILABILITY = (
    "PRM800K is publicly available from its original source. Derived locked-split reports, "
    "audit-prioritization artifacts, and reproduction scripts will be made available by the "
    "authors on request."
)

REQUIRED_FILES = (
    "Highlights.docx",
    "cover_letter.docx",
    "manuscript.pdf",
    "supplementary.docx",
    "latex_source.zip",
)

# Optional files allowed in the upload boundary for double-blind review
# and graphical abstract requirements.
OPTIONAL_FILES = (
    "manuscript_anonymous.pdf",
    "graphical_abstract.png",
    "graphical_abstract.pdf",
    "graphical_abstract.tiff",
    "graphical_abstract.tif",
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
    "test_title.*",
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

AUTHOR_PLACEHOLDERS = (
    "Anonymous Author(s)",
    "Anonymous Institution",
    "anonymous submission package",
)

COVER_LETTER_VENUE = "Information Processing & Management"

# Patterns that must NOT appear in cover_letter.docx / Highlights.docx /
# supplementary.docx rendered text. ``Knowledge-Based Systems`` is the prior
# venue label and must not leak into the IPM upload. The bare token ``KBS`` is
# also blocked as a system-type label, but the machine-readable claim-boundary
# marker ``validated_kbs_workflow`` is exempt because it is a venue-neutral
# claim-governance key, not venue wording.
FORBIDDEN_VENUE_PATTERNS = (
    "Knowledge-Based Systems",
    re.compile(r"\bKBS\b"),
)


def _has_forbidden_venue_wording(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in FORBIDDEN_VENUE_PATTERNS:
        if isinstance(pattern, str):
            if pattern in text:
                hits.append(pattern)
        else:
            seen: set[str] = set()
            for match in pattern.findall(text):
                if match and match not in seen:
                    seen.add(match)
                    hits.append(match)
    return hits

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

REQUIRED_MANUSCRIPT_SNIPPETS = (
    CURRENT_TITLE,
)

# For double-blind review, the LaTeX source in the zip MUST be anonymized.
# These snippets must NOT appear in the zip's manuscript.tex.
FORBIDDEN_MANUSCRIPT_SNIPPETS = (
    "Haoran Ma",
    "Ningning Wang",
    "mahaoran0000@foxmail.com",
    "wangningning@bistu.edu.cn",
    "Beijing Information Science and Technology University",
    "ESG Intelligent Application Innovation Research Center",
    "National Social Science Fund of China Project (24BSH018)",
    "Beijing Natural Science Foundation Project (L252145)",
    r"\section*{Acknowledgments}",
    r"\section*{Funding}",
    r"\section*{Declaration of Competing Interest}",
    r"\section*{Declaration of generative AI",
    r"\section*{Data Availability}",
    r"\section*{CRediT authorship contribution statement}",
)

REQUIRED_DOCX_TEXT_SNIPPETS = {
    "Highlights.docx": (
        "Highlights",
        CURRENT_TITLE,
        "SC-FMA calibrates utility or proxy fidelity into auditable step weights.",
        "PRM800K stratified readout supports audit prioritization moderately.",
    ),
    "supplementary.docx": (
        "Supplementary Material",
        CURRENT_TITLE,
        "Haoran Ma",
        "Ningning Wang",
    ),
}

REQUIRED_PDF_TEXT_SNIPPETS = {
    "manuscript.pdf": (
        CURRENT_TITLE,
        "Declaration of Competing Interest",
        "Data Availability",
        "CRediT authorship contribution statement",
        "Haoran Ma",
        "Ningning Wang",
        "National Social Science Fund of China Project (24BSH018)",
        DATA_AVAILABILITY,
    ),
}

FORBIDDEN_PDF_SNIPPETS = {
    "manuscript.pdf": ("Highlights",),
}


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
    return path.read_text(encoding="utf-8", errors="ignore")


def _check_required_files(package_dir: Path, errors: list[str]) -> None:
    for rel_path in REQUIRED_FILES:
        path = package_dir / rel_path
        if not path.exists():
            errors.append(f"missing required package file: {rel_path}")
        elif path.stat().st_size == 0:
            errors.append(f"required package file is empty: {rel_path}")


def _check_top_level_boundary(package_dir: Path, errors: list[str]) -> None:
    allowed = set(REQUIRED_FILES) | set(OPTIONAL_FILES)
    for path in sorted(p for p in package_dir.iterdir() if p.is_file()):
        if path.name not in allowed:
            errors.append(f"unexpected file in final upload boundary: {path.name}")


def _check_auxiliary_artifacts(package_dir: Path, errors: list[str]) -> None:
    for pattern in AUXILIARY_GLOBS:
        for path in sorted(package_dir.rglob(pattern)):
            if path.name not in REQUIRED_FILES:
                errors.append(f"local build artifact should not be in upload boundary: {path.name}")
    for dirname in ("build", "build_tmp", "build_manuscript", "build_supplementary"):
        if (package_dir / dirname).exists():
            errors.append(f"temporary build directory should not be in upload boundary: {dirname}")


def _check_pdf_headers(package_dir: Path, errors: list[str]) -> None:
    for filename in ("manuscript.pdf",):
        path = package_dir / filename
        if not path.exists():
            continue
        if path.stat().st_size < 8:
            errors.append(f"{filename} is too small to be a valid PDF")
            continue
        with path.open("rb") as fh:
            if fh.read(5) != b"%PDF-":
                errors.append(f"{filename} does not start with a PDF header")


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


def _check_cover_letter(package_dir: Path, errors: list[str]) -> None:
    cover_text = _read_docx_text(package_dir / "cover_letter.docx", errors)
    if not cover_text:
        return
    for snippet in (CURRENT_TITLE, COVER_LETTER_VENUE, "Haoran Ma", "Ningning Wang"):
        if snippet not in cover_text:
            errors.append(f"cover_letter.docx missing required text: {snippet}")
    venue_hits = _has_forbidden_venue_wording(cover_text)
    for hit in venue_hits:
        errors.append(f"cover_letter.docx contains residual KBS venue wording: {hit}")
    _check_forbidden_text({"cover_letter.docx": cover_text}, errors)


def _check_docx_text(package_dir: Path, errors: list[str]) -> dict[str, str]:
    text_by_name: dict[str, str] = {}
    for filename, snippets in REQUIRED_DOCX_TEXT_SNIPPETS.items():
        docx_text = _read_docx_text(package_dir / filename, errors)
        if not docx_text:
            continue
        text_by_name[filename] = docx_text
        for snippet in snippets:
            if not _contains_snippet(docx_text, snippet):
                errors.append(f"{filename} missing required text: {snippet}")
        venue_hits = _has_forbidden_venue_wording(docx_text)
        for hit in venue_hits:
            errors.append(f"{filename} contains residual KBS venue wording: {hit}")
    _check_forbidden_text(text_by_name, errors)
    return text_by_name


def _read_source_zip(path: Path, errors: list[str]) -> tuple[set[str], dict[str, str]]:
    if not path.exists():
        return set(), {}
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            text_by_name: dict[str, str] = {}
            for name in names:
                if name.endswith((".tex", ".bib", ".md", ".cls", ".sty", ".bst")):
                    text_by_name[name] = zf.read(name).decode("utf-8", errors="ignore")
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
    for snippet in REQUIRED_MANUSCRIPT_SNIPPETS:
        if snippet not in manuscript:
            errors.append(f"manuscript.tex missing required snippet: {snippet}")
    if CURRENT_TITLE not in supplementary:
        errors.append("supplementary.tex missing current title")

    # Double-blind: the zip's manuscript.tex MUST NOT contain author
    # identifying information or title-page sections.
    for snippet in FORBIDDEN_MANUSCRIPT_SNIPPETS:
        if snippet in manuscript:
            errors.append(
                f"manuscript.tex contains forbidden author-identifying snippet for "
                f"double-blind review: {snippet}"
            )
    for snippet in FORBIDDEN_MANUSCRIPT_SNIPPETS:
        if snippet in supplementary:
            errors.append(
                f"supplementary.tex contains forbidden author-identifying snippet for "
                f"double-blind review: {snippet}"
            )

    _check_includegraphics_paths_in_zip(names, manuscript, "manuscript.tex", errors)
    _check_includegraphics_paths_in_zip(names, supplementary, "supplementary.tex", errors)
    _check_forbidden_text(text_by_name, errors)
    for name, text in text_by_name.items():
        # ``.bib`` entries may legitimately cite works published in the
        # journal ``Knowledge-Based Systems``; exempt bibliographic files
        # from the venue-wording residual check.
        if name.endswith(".bib"):
            continue
        venue_hits = _has_forbidden_venue_wording(text)
        for hit in venue_hits:
            errors.append(f"{name} contains residual KBS venue wording: {hit}")
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


def _check_forbidden_text(text_by_name: dict[str, str], errors: list[str]) -> None:
    for filename, text in text_by_name.items():
        for snippet, message in FORBIDDEN_SNIPPETS.items():
            if _contains_snippet(text, snippet):
                errors.append(f"{message}: {filename}")


def _normalize_for_match(text: str) -> str:
    text = text.replace("-\n", "")
    return re.sub(r"\s+", " ", text).strip()


def _contains_snippet(text: str, snippet: str) -> bool:
    return snippet in text or _normalize_for_match(snippet) in _normalize_for_match(text)


def _check_author_metadata(
    text_by_name: dict[str, str],
    *,
    require_author_metadata: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    # Zip source files are expected to be anonymized for double-blind review;
    # exclude them from the placeholder check. Only check non-zip artifacts
    # (manuscript.pdf text, docx files, cover letter) for author metadata.
    zip_source_extensions = (".tex", ".cls", ".sty", ".bst", ".bib")
    placeholders: list[str] = []
    for name, text in text_by_name.items():
        if name.endswith(zip_source_extensions):
            continue
        placeholders.extend(
            placeholder for placeholder in AUTHOR_PLACEHOLDERS if placeholder in text
        )
    placeholders = sorted(set(placeholders))
    if not placeholders:
        return

    message = f"author metadata placeholders remain: {', '.join(placeholders)}"
    if require_author_metadata:
        errors.append(message)
    else:
        warnings.append(message)


def _extract_pdf_text(package_dir: Path, filename: str, errors: list[str]) -> str:
    pdf_path = package_dir / filename
    try:
        result = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
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
        detail = (result.stderr or result.stdout).strip()
        errors.append(f"pdftotext failed for {filename}: {detail}")
        return ""

    return result.stdout


def _check_pdf_text(
    package_dir: Path,
    errors: list[str],
    *,
    pdf_text_by_name: dict[str, str] | None,
) -> None:
    for filename, snippets in REQUIRED_PDF_TEXT_SNIPPETS.items():
        pdf_text = (
            pdf_text_by_name[filename]
            if pdf_text_by_name is not None and filename in pdf_text_by_name
            else _extract_pdf_text(package_dir, filename, errors)
        )
        if not pdf_text:
            continue
        if not _contains_snippet(pdf_text, CURRENT_TITLE):
            errors.append(f"rendered {filename} text does not contain current title")
        for snippet in snippets[1:]:
            if not _contains_snippet(pdf_text, snippet):
                errors.append(f"rendered {filename} text missing required snippet: {snippet}")
        for snippet in FORBIDDEN_PDF_SNIPPETS.get(filename, ()):
            if _contains_snippet(pdf_text, snippet):
                errors.append(f"rendered {filename} text contains forbidden snippet: {snippet}")
        _check_forbidden_text({f"rendered {filename}": pdf_text}, errors)


def _extract_pdf_page_count(package_dir: Path, filename: str, errors: list[str]) -> int | None:
    pdf_path = package_dir / filename
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            cwd=package_dir,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        errors.append("pdfinfo is required for rendered PDF page-count verification")
        return None

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        errors.append(f"pdfinfo failed for {filename}: {detail}")
        return None

    match = re.search(r"^Pages:\s*(\d+)\s*$", result.stdout or "", flags=re.MULTILINE)
    if match is None:
        errors.append(f"pdfinfo output for {filename} did not include a Pages field")
        return None
    return int(match.group(1))


def _check_pdf_page_count(
    package_dir: Path,
    errors: list[str],
    *,
    expected_manuscript_pages: int | None,
    min_manuscript_pages: int | None,
    max_manuscript_pages: int | None,
    pdf_page_count_by_name: dict[str, int] | None,
) -> None:
    if (
        expected_manuscript_pages is None
        and min_manuscript_pages is None
        and max_manuscript_pages is None
    ):
        return

    filename = "manuscript.pdf"
    observed = (
        pdf_page_count_by_name[filename]
        if pdf_page_count_by_name is not None and filename in pdf_page_count_by_name
        else _extract_pdf_page_count(package_dir, filename, errors)
    )
    if observed is None:
        return
    if expected_manuscript_pages is not None and observed != expected_manuscript_pages:
        errors.append(
            f"rendered {filename} page count {observed} does not match expected "
            f"{expected_manuscript_pages}"
        )
    if min_manuscript_pages is not None and observed < min_manuscript_pages:
        errors.append(
            f"rendered {filename} page count {observed} is below minimum "
            f"{min_manuscript_pages}"
        )
    if max_manuscript_pages is not None and observed > max_manuscript_pages:
        errors.append(
            f"rendered {filename} page count {observed} exceeds maximum "
            f"{max_manuscript_pages}"
        )


def check_package(
    package_dir: Path,
    *,
    require_author_metadata: bool = False,
    require_pdf_text: bool = False,
    pdf_text: str | None = None,
    pdf_text_by_name: dict[str, str] | None = None,
    expected_manuscript_pages: int | None = None,
    min_manuscript_pages: int | None = None,
    max_manuscript_pages: int | None = None,
    pdf_page_count_by_name: dict[str, int] | None = None,
) -> VerificationReport:
    errors: list[str] = []
    warnings: list[str] = []
    package_dir = package_dir.resolve()

    if not package_dir.exists():
        return VerificationReport(errors=[f"missing package directory: {package_dir}"], warnings=[])

    if pdf_text is not None and pdf_text_by_name is None:
        pdf_text_by_name = {"manuscript.pdf": pdf_text}

    _check_required_files(package_dir, errors)
    _check_top_level_boundary(package_dir, errors)
    _check_auxiliary_artifacts(package_dir, errors)
    _check_pdf_headers(package_dir, errors)
    _check_cover_letter(package_dir, errors)
    package_docx_text = _check_docx_text(package_dir, errors)
    source_text_by_name = _check_source_zip(package_dir, errors)
    cover_text = _read_docx_text(package_dir / "cover_letter.docx", errors)
    all_text = dict(source_text_by_name)
    all_text.update(package_docx_text)
    if cover_text:
        all_text["cover_letter.docx"] = cover_text
    _check_author_metadata(
        all_text,
        require_author_metadata=require_author_metadata,
        errors=errors,
        warnings=warnings,
    )
    if require_pdf_text:
        _check_pdf_text(package_dir, errors, pdf_text_by_name=pdf_text_by_name)
    _check_pdf_page_count(
        package_dir,
        errors,
        expected_manuscript_pages=expected_manuscript_pages,
        min_manuscript_pages=min_manuscript_pages,
        max_manuscript_pages=max_manuscript_pages,
        pdf_page_count_by_name=pdf_page_count_by_name,
    )

    return VerificationReport(errors=errors, warnings=warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the final Information Processing & Management submission upload boundary."
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=Path("paper") / "ipm_submission" / "final_package",
        help="Path to the final IPM submission package directory.",
    )
    parser.add_argument(
        "--require-author-metadata",
        action="store_true",
        help="Fail if anonymous author/affiliation placeholders remain.",
    )
    parser.add_argument(
        "--require-pdf-text",
        action="store_true",
        help="Fail if rendered PDF text does not contain the current title and required statements.",
    )
    parser.add_argument(
        "--expected-manuscript-pages",
        type=int,
        default=None,
        help="Fail if rendered manuscript.pdf does not have this page count.",
    )
    parser.add_argument(
        "--max-manuscript-pages",
        type=int,
        default=None,
        help="Fail if rendered manuscript.pdf exceeds this page count.",
    )
    parser.add_argument(
        "--min-manuscript-pages",
        type=int,
        default=None,
        help="Fail if rendered manuscript.pdf is below this page count.",
    )
    args = parser.parse_args(argv)

    report = check_package(
        args.package_dir,
        require_author_metadata=args.require_author_metadata,
        require_pdf_text=args.require_pdf_text,
        expected_manuscript_pages=args.expected_manuscript_pages,
        min_manuscript_pages=args.min_manuscript_pages,
        max_manuscript_pages=args.max_manuscript_pages,
    )
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)

    if report.ok:
        print("IPM final submission package check passed")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
