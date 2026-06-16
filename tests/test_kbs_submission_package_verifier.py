from __future__ import annotations

import zipfile
from pathlib import Path


TITLE = (
    "Structurally-Calibrated Functional Attribution: A Methodology for "
    "Process Supervision Weighting in Reflective Reasoning"
)

DATA_AVAILABILITY = (
    "PRM800K is publicly available from its original source. Derived locked-split reports, "
    "audit-prioritization artifacts, and reproduction scripts will be made available by the "
    "authors on request."
)


def _write_docx(path: Path, text: str | None = None) -> None:
    text = text or "\n".join(
        [
            TITLE,
            "Knowledge-Based Systems",
            "Haoran Ma",
            "Ningning Wang",
        ]
    )
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
</w:document>
"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        zf.writestr("word/document.xml", document_xml)


def _write_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\n% minimal test fixture\n%%EOF\n")


def _write_source_zip(
    path: Path,
    *,
    manuscript_tex: str | None = None,
    supplementary_tex: str | None = None,
) -> None:
    manuscript_tex = manuscript_tex or "\n".join(
        [
            rf"\title[mode=title]{{{TITLE}}}",
            r"\author[1]{Haoran Ma}",
            r"\author[1,2]{Ningning Wang}",
            "mahaoran0000@foamail.com",
            "wangningning@bistu.edu.cn",
            "National Social Science Fund of China Project (24BSH018)",
            "Beijing Natural Science Foundation Project (L252145)",
            r"\section*{Declaration of Competing Interest}",
            "The authors declared that they have no conflicts of interest to this work.",
            r"\section*{Data Availability}",
            DATA_AVAILABILITY,
            r"\section*{CRediT authorship contribution statement}",
            "Haoran Ma: Conceptualization. Ningning Wang: Supervision.",
            r"\includegraphics{figures/fig_sensitivity.png}",
        ]
    )
    supplementary_tex = supplementary_tex or "\n".join(
        [
            rf"\title[mode=title]{{Supplementary Material for {TITLE}}}",
            "Haoran Ma and Ningning Wang",
            r"\includegraphics{figures/fig_scaling.png}",
        ]
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manuscript.tex", manuscript_tex)
        zf.writestr("supplementary.tex", supplementary_tex)
        zf.writestr("references.bib", "@article{x,title={x}}\n")
        zf.writestr("cas-sc.cls", "class fixture\n")
        zf.writestr("cas-common.sty", "style fixture\n")
        zf.writestr("cas-model2-names.bst", "bst fixture\n")
        zf.writestr("figures/fig_sensitivity.png", b"png")
        zf.writestr("figures/fig_scaling.png", b"png")


def _write_final_package(package_dir: Path) -> None:
    package_dir.mkdir(parents=True, exist_ok=True)
    _write_docx(package_dir / "cover_letter.docx")
    _write_docx(
        package_dir / "Highlights.docx",
        "\n".join(
            [
                "Highlights",
                TITLE,
                "SC-FMA calibrates interventional utility into supervision weights.",
            ]
        ),
    )
    _write_pdf(package_dir / "manuscript.pdf")
    _write_docx(
        package_dir / "supplementary.docx",
        f"Supplementary Material\n{TITLE}\nHaoran Ma\nNingning Wang",
    )
    _write_source_zip(package_dir / "latex_source.zip")


def _pdf_text_by_name() -> dict[str, str]:
    manuscript_text = "\n".join(
        [
            TITLE,
            "Declaration of Competing Interest",
            "Data Availability",
            "CRediT authorship contribution statement",
            "Haoran Ma",
            "Ningning Wang",
            "mahaoran0000@foamail.com",
            "wangningning@bistu.edu.cn",
            "National Social Science Fund of China Project (24BSH018)",
            DATA_AVAILABILITY,
        ]
    )
    return {
        "manuscript.pdf": manuscript_text,
    }


def test_kbs_verifier_passes_final_submission_boundary(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    report = check_package(
        package_dir,
        require_author_metadata=True,
        require_pdf_text=True,
        pdf_text_by_name=_pdf_text_by_name(),
    )

    assert report.ok, report.errors
    assert report.warnings == []


def test_kbs_verifier_requires_final_upload_files(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    package_dir.mkdir()
    (package_dir / "main.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")

    report = check_package(package_dir)

    assert not report.ok
    assert any("missing required package file: cover_letter.docx" in error for error in report.errors)
    assert any("missing required package file: Highlights.docx" in error for error in report.errors)
    assert any("missing required package file: manuscript.pdf" in error for error in report.errors)
    assert any("missing required package file: supplementary.docx" in error for error in report.errors)
    assert any("missing required package file: latex_source.zip" in error for error in report.errors)
    assert any("unexpected file in final upload boundary: main.pdf" in error for error in report.errors)


def test_kbs_verifier_blocks_author_placeholders_in_source_zip(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_source_zip(
        package_dir / "latex_source.zip",
        manuscript_tex="Anonymous Author(s)\nAnonymous Institution\n",
    )

    report = check_package(package_dir, require_author_metadata=True)

    assert not report.ok
    assert any("author metadata placeholders remain" in error for error in report.errors)


def test_kbs_verifier_checks_source_zip_manifest(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    with zipfile.ZipFile(package_dir / "latex_source.zip", "w") as zf:
        zf.writestr("manuscript.tex", TITLE)

    report = check_package(package_dir)

    assert not report.ok
    assert any("latex_source.zip missing required source file: supplementary.tex" in error for error in report.errors)
    assert any("latex_source.zip missing required artwork directory: figures/" in error for error in report.errors)


def test_kbs_verifier_blocks_stale_rendered_pdf_text(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    report = check_package(
        package_dir,
        require_pdf_text=True,
        pdf_text_by_name={
            "manuscript.pdf": "Functional Metacognitive Attribution: A Diagnostic and Design Framework",
        },
    )

    assert not report.ok
    assert any("rendered manuscript.pdf text does not contain current title" in error for error in report.errors)


def test_kbs_verifier_blocks_legacy_split_pdfs(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_pdf(package_dir / "Highlights.pdf")
    _write_pdf(package_dir / "supplementary.pdf")

    report = check_package(package_dir)

    assert not report.ok
    assert any("unexpected file in final upload boundary: Highlights.pdf" in error for error in report.errors)
    assert any("unexpected file in final upload boundary: supplementary.pdf" in error for error in report.errors)
