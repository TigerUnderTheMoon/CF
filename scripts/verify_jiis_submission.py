"""Verify the local JIIS submission workspace."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

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
        "sn-mathphys-num.bst",
    }
    existing = {path.name for path in package.iterdir()} if package.exists() else set()
    missing = sorted(required_package - existing)
    if missing:
        errors.append(f"submission_package missing {missing}")
    build_artifacts = [
        path.name for path in package.iterdir()
        if path.is_file() and any(path.name.endswith(suffix) for suffix in BUILD_SUFFIXES)
    ] if package.exists() else []
    if build_artifacts:
        errors.append(f"submission_package contains build artifacts {build_artifacts}")

    result = {
        "workspace": str(ws),
        "abstract_words": abs_count,
        "keyword_count": kw_count,
        "manuscript_pages": pages,
        "package_files": sorted(existing),
        "errors": errors,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
