from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape
from pathlib import Path


TITLE = (
    "Structurally-Calibrated Functional Attribution for Audit Prioritization "
    "in Knowledge-Intensive Reasoning"
)


def _write_docx(path: Path, text: str) -> None:
    text = escape(text)
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


def _write_source_zip(path: Path, manuscript_tex: str | None = None) -> None:
    manuscript_tex = manuscript_tex or "\n".join(
            [
                rf"\title[mode=title]{{{TITLE}}}",
                "Data & Knowledge Engineering / Elsevier CAS manuscript package.",
                "knowledge engineering \\sep knowledge representation \\sep knowledge maintenance \\sep knowledge graphs",
                "PRM800K Representation Behavior Study",
                "Scope and Limitations",
                r"\includegraphics{figures/fig_sensitivity.png}",
            ]
        )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manuscript.tex", manuscript_tex)
        zf.writestr("supplementary.tex", "Data & Knowledge Engineering / Elsevier CAS supplementary package.")
        zf.writestr("references.bib", "@article{x,title={x},journal={Knowledge-Based Systems}}\n")
        zf.writestr("cas-sc.cls", "class fixture\n")
        zf.writestr("cas-common.sty", "style fixture\n")
        zf.writestr("cas-model2-names.bst", "bst fixture\n")
        zf.writestr("figures/fig_sensitivity.png", b"png")


def _write_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\n% minimal test fixture\n%%EOF\n")


def _write_final_package(package_dir: Path) -> None:
    package_dir.mkdir(parents=True, exist_ok=True)
    _write_docx(
        package_dir / "cover_letter.docx",
        "\n".join(
            [
                "Cover Letter",
                "Data & Knowledge Engineering",
                TITLE,
                "knowledge representation and transformation layer",
                "structured audit records",
                "fixed-budget knowledge audit",
                "knowledge lifecycle",
                "knowledge maintenance",
                "knowledge curation",
                "graph-aware",
            ]
        ),
    )
    _write_docx(
        package_dir / "Highlights.docx",
        "\n".join(
            [
                "Highlights",
                TITLE,
                "SC-FMA represents intermediate reasoning and knowledge-process artifacts as structured audit records.",
                "Graph-aware representation fields expose dependency, redundancy, bottleneck, and maintenance-action roles.",
                "Audit-record construction supports fixed-budget knowledge maintenance, curation, and reuse.",
            ]
        ),
    )
    _write_pdf(package_dir / "supplementary.pdf")
    _write_pdf(package_dir / "manuscript.pdf")
    _write_source_zip(package_dir / "latex_source.zip")


def test_dke_verifier_accepts_dke_transfer_boundary(tmp_path: Path) -> None:
    from scripts.verify_dke_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    report = check_package(
        package_dir,
        require_pdf_text=True,
        pdf_text_by_name={"manuscript.pdf": TITLE},
        min_manuscript_pages=12,
        max_manuscript_pages=25,
        pdf_page_count_by_name={"manuscript.pdf": 21},
    )

    assert report.ok, report.errors


def test_dke_verifier_blocks_old_journal_submission_wording(tmp_path: Path) -> None:
    from scripts.verify_dke_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_docx(
        package_dir / "cover_letter.docx",
        f"{TITLE}\nfor consideration as a regular article in Knowledge-Based Systems",
    )

    report = check_package(package_dir)

    assert not report.ok
    assert any("old KBS journal submission wording remains" in error for error in report.errors)


def test_dke_verifier_blocks_kbs_facing_manuscript_wording(tmp_path: Path) -> None:
    from scripts.verify_dke_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_source_zip(
        package_dir / "latex_source.zip",
        "\n".join(
            [
                rf"\title[mode=title]{{{TITLE}}}",
                "Data & Knowledge Engineering / Elsevier CAS manuscript package.",
                "knowledge engineering \\sep knowledge representation \\sep knowledge maintenance \\sep knowledge graphs",
                "PRM800K Representation Behavior Study",
                "Scope and Limitations",
                "The current KBS-facing evidence is limited to audit prioritization.",
                r"\includegraphics{figures/fig_sensitivity.png}",
            ]
        ),
    )

    report = check_package(package_dir)

    assert not report.ok
    assert any("residual KBS-facing wording remains" in error for error in report.errors)


def test_dke_verifier_blocks_evidence_ladder_in_package_narrative(tmp_path: Path) -> None:
    from scripts.verify_dke_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_source_zip(
        package_dir / "latex_source.zip",
        "\n".join(
            [
                rf"\title[mode=title]{{{TITLE}}}",
                "Data & Knowledge Engineering / Elsevier CAS manuscript package.",
                "knowledge engineering \\sep knowledge representation \\sep knowledge maintenance \\sep knowledge graphs",
                "PRM800K Representation Behavior Study",
                "Scope and Limitations",
                "The evaluation is organized as an Evidence Ladder.",
                r"\includegraphics{figures/fig_sensitivity.png}",
            ]
        ),
    )

    report = check_package(package_dir)

    assert not report.ok
    assert any("Evidence Ladder should not appear" in error for error in report.errors)


def test_dke_verifier_blocks_internal_reviewer_v2_label(tmp_path: Path) -> None:
    from scripts.verify_dke_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_source_zip(
        package_dir / "latex_source.zip",
        "\n".join(
            [
                rf"\title[mode=title]{{{TITLE}}}",
                "Data & Knowledge Engineering / Elsevier CAS manuscript package.",
                "knowledge engineering \\sep knowledge representation \\sep knowledge maintenance \\sep knowledge graphs",
                "PRM800K Representation Behavior Study",
                "Scope and Limitations",
                "Reviewer V2 failure taxonomy distribution.",
                r"\includegraphics{figures/fig_sensitivity.png}",
            ]
        ),
    )

    report = check_package(package_dir)

    assert not report.ok
    assert any("internal Reviewer V2 label remains" in error for error in report.errors)


def test_dke_verifier_blocks_old_kbs_paths_in_source_zip(tmp_path: Path) -> None:
    from scripts.verify_dke_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_source_zip(
        package_dir / "latex_source.zip",
        "\n".join(
            [
                rf"\title[mode=title]{{{TITLE}}}",
                "Data & Knowledge Engineering / Elsevier CAS manuscript package.",
                "knowledge engineering \\sep knowledge representation \\sep knowledge maintenance \\sep knowledge graphs",
                "PRM800K Representation Behavior Study",
                "Scope and Limitations",
                "See outputs/kbs_audit_card_auto_validation_v1 and paper/kbs_submission/supplementary.",
                r"\includegraphics{figures/fig_sensitivity.png}",
            ]
        ),
    )

    report = check_package(package_dir)

    assert not report.ok
    assert any("old KBS path or output prefix remains" in error for error in report.errors)
