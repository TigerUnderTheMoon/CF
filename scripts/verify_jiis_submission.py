"""Verify the local JIIS submission workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

import jsonschema
from pypdf import PdfReader


BUILD_SUFFIXES = {
    ".aux", ".bbl", ".bcf", ".blg", ".fdb_latexmk", ".fls", ".log",
    ".out", ".run.xml", ".synctex.gz",
}

FORBIDDEN_POSITIVE = (
    "human validation",
    "human audit usefulness",
    "production knowledge-base validation",
    "production kg validation",
    "causal effect",
    "average treatment effect",
    "external deployment",
    "deployed workflow validation",
    "robust to arbitrary kg noise",
)

NEGATORS = ("not ", "no ", "does not ", "do not ", "future ", "without ", "rather than ", "not a ")


def referenced_figures(tex: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(
            r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", tex
        )
    ]


def archive_checksum_errors(path: Path) -> list[str]:
    if not path.is_file():
        return ["missing reproducibility archive"]
    errors: list[str] = []
    with zipfile.ZipFile(path) as bundle:
        names = bundle.namelist()
        if "SHA256SUMS.txt" not in names:
            return ["archive missing SHA256SUMS.txt"]
        expected = {}
        for line in bundle.read("SHA256SUMS.txt").decode("ascii").splitlines():
            digest, name = line.split("  ", 1)
            expected[name] = digest
        for name, digest in expected.items():
            if name not in names:
                errors.append(f"archive checksum target missing: {name}")
                continue
            observed = hashlib.sha256(bundle.read(name)).hexdigest()
            if observed != digest:
                errors.append(f"archive checksum mismatch: {name}")
        unchecked = sorted(set(names) - set(expected) - {"SHA256SUMS.txt"})
        if unchecked:
            errors.append(f"archive entries missing checksums: {unchecked}")
    return errors


def tex_reference_errors(tex: str) -> list[str]:
    labels = re.findall(r"\\label\{([^{}]+)\}", tex)
    duplicate_labels = sorted({label for label in labels if labels.count(label) > 1})
    references = re.findall(r"\\(?:ref|eqref|pageref|autoref)\{([^{}]+)\}", tex)
    undefined = sorted(set(references) - set(labels))
    errors = []
    if duplicate_labels:
        errors.append(f"duplicate labels: {duplicate_labels}")
    if undefined:
        errors.append(f"undefined references: {undefined}")
    return errors


def latex_log_errors(log_text: str, name: str) -> list[str]:
    checks = {
        "undefined references": r"undefined references|Reference `[^']+' on page .* undefined",
        "duplicate destinations": r"destination with the same identifier|duplicate ignored",
        "multiply defined labels": r"multiply defined",
        "overfull boxes": r"Overfull \\hbox|Overfull \\vbox",
    }
    return [
        f"{name}: {label}"
        for label, pattern in checks.items()
        if re.search(pattern, log_text, flags=re.I)
    ]


def abstract_words(tex: str) -> int:
    match = re.search(r"\\abstract\{(.+?)\}\s*\\keywords", tex, flags=re.S)
    if not match:
        return 0
    text = re.sub(r"\\[a-zA-Z]+(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", match.group(1))
    text = re.sub(r"[^A-Za-z0-9\- ]+", " ", text)
    return len([word for word in text.split() if word])


def keyword_count(tex: str) -> int:
    match = re.search(r"\\keywords\{(.+?)\}", tex, flags=re.S)
    if not match:
        return 0
    return len([item.strip() for item in match.group(1).replace(";", ",").split(",") if item.strip()])


def is_negated(text: str, pattern: str) -> bool:
    idx = text.lower().find(pattern)
    if idx < 0:
        return True
    window = text.lower()[max(0, idx - 120): idx + len(pattern) + 120]
    return any(marker in window for marker in NEGATORS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("paper/JIIS_submission"))
    parser.add_argument("--max-pages", type=int, default=25)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)

    ws = args.workspace.resolve()
    source = ws / "source"
    package = ws / "submission_package"
    main_tex = source / "manuscript.tex"
    supp_tex = source / "supplementary.tex"
    main_pdf = source / "manuscript.pdf"
    supp_pdf = source / "supplementary.pdf"
    schema_path = ws.parents[1] / "schemas" / "scar_audit_record.schema.json"
    errors: list[str] = []

    tex = main_tex.read_text(encoding="utf-8") if main_tex.exists() else ""
    abs_count = abstract_words(tex)
    kw_count = keyword_count(tex)
    if not 150 <= abs_count <= 250:
        errors.append(f"abstract_words={abs_count}, expected 150-250")
    if kw_count != 6:
        errors.append(f"keyword_count={kw_count}, expected 6")
    if r"\input{" in tex:
        errors.append("main manuscript uses \\input")
    if "Recall@25%" in tex:
        errors.append("Recall@25% appears as a main-result metric")
    for phrase in FORBIDDEN_POSITIVE:
        if phrase in tex.lower() and not is_negated(tex, phrase):
            errors.append(f"forbidden positive claim: {phrase}")

    pages = None
    if main_pdf.exists():
        pages = len(PdfReader(str(main_pdf)).pages)
        if pages > args.max_pages:
            errors.append(f"manuscript_pages={pages}, expected <= {args.max_pages}")
    else:
        errors.append("missing source/manuscript.pdf")
    if not supp_pdf.exists():
        errors.append("missing source/supplementary.pdf")
    for src in (main_tex, supp_tex):
        pdf = src.with_suffix(".pdf")
        if src.exists() and pdf.exists() and pdf.stat().st_mtime < src.stat().st_mtime:
            errors.append(f"{pdf.name} older than {src.name}")

    required_package = {
        "manuscript.pdf",
        "supplementary.pdf",
        "manuscript.tex",
        "supplementary.tex",
        "references.bib",
        "sn-jnl.cls",
        "sn-basic.bst",
    }
    package_entries = list(package.iterdir()) if package.exists() else []
    existing = {path.name for path in package_entries}
    missing = sorted(required_package - existing)
    if missing:
        errors.append(f"submission_package missing {missing}")
    build_artifacts = [
        path.name for path in package.iterdir()
        if path.is_file() and any(path.name.endswith(suffix) for suffix in BUILD_SUFFIXES)
    ] if package.exists() else []
    if build_artifacts:
        errors.append(f"submission_package contains build artifacts {build_artifacts}")
    package_directories = sorted(path.name for path in package_entries if path.is_dir())
    if package_directories:
        errors.append(f"submission_package contains directories {package_directories}")

    figure_names = []
    for source_tex in (main_tex, supp_tex):
        if not source_tex.is_file():
            continue
        source_text = source_tex.read_text(encoding="utf-8")
        if r"\graphicspath{{./}{figures/}}" not in source_text:
            errors.append(f"{source_tex.name} missing required graphicspath")
        errors.extend(f"{source_tex.name}: {error}" for error in tex_reference_errors(source_text))
        for name in referenced_figures(source_text):
            if Path(name).name != name:
                errors.append(f"figure reference is not a bare filename: {name}")
                continue
            if name not in figure_names:
                figure_names.append(name)
            if not (source / "figures" / name).is_file():
                errors.append(f"source figure missing: {name}")
            if not (package / name).is_file():
                errors.append(f"package figure missing: {name}")
    unreferenced_package_pngs = sorted(
        path.name
        for path in package_entries
        if path.is_file() and path.suffix.lower() == ".png" and path.name not in figure_names
    )
    if unreferenced_package_pngs:
        errors.append(f"submission_package contains unreferenced PNGs {unreferenced_package_pngs}")

    paired_names = ("manuscript.tex", "supplementary.tex", "references.bib", "manuscript.pdf", "supplementary.pdf")
    paired_hashes = {}
    for name in paired_names:
        source_path = source / name
        package_path = package / name
        if source_path.is_file() and package_path.is_file():
            source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            package_hash = hashlib.sha256(package_path.read_bytes()).hexdigest()
            paired_hashes[name] = {"source": source_hash, "package": package_hash}
            if source_hash != package_hash:
                errors.append(f"source/package hash mismatch: {name}")

    schema_valid = False
    if not schema_path.is_file():
        errors.append("missing schemas/scar_audit_record.schema.json")
    else:
        try:
            jsonschema.Draft202012Validator.check_schema(
                json.loads(schema_path.read_text(encoding="utf-8"))
            )
            schema_valid = True
        except (json.JSONDecodeError, jsonschema.SchemaError) as exc:
            errors.append(f"invalid SCAR schema: {exc}")

    archive_errors = archive_checksum_errors(package / "reproducibility_archive.zip")
    errors.extend(archive_errors)
    latex_warnings = []
    for name in ("manuscript", "supplementary"):
        log_path = ws / "build" / f"{name}.log"
        if not log_path.is_file():
            errors.append(f"missing build/{name}.log")
            continue
        latex_warnings.extend(
            latex_log_errors(log_path.read_text(encoding="utf-8", errors="replace"), log_path.name)
        )
    errors.extend(latex_warnings)
    for pdf_path in (main_pdf, supp_pdf):
        if pdf_path.is_file():
            pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
            if "???" in pdf_text:
                errors.append(f"{pdf_path.name} contains ???")

    result = {
        "workspace": str(ws),
        "abstract_words": abs_count,
        "keyword_count": kw_count,
        "manuscript_pages": pages,
        "package_files": sorted(existing),
        "package_directories": package_directories,
        "figure_references": figure_names,
        "paired_hashes": paired_hashes,
        "schema_valid": schema_valid,
        "archive_checksum_errors": archive_errors,
        "latex_warnings": latex_warnings,
        "errors": errors,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
