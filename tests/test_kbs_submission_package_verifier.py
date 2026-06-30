from __future__ import annotations

import zipfile
from pathlib import Path


TITLE = (
    "Structurally-Calibrated Functional Attribution for Audit Prioritization "
    "in Knowledge-Intensive Reasoning"
)

DATA_AVAILABILITY = (
    "PRM800K, MuSiQue, and WebQSP are publicly available from their original sources. "
    "Derived locked-split reports, audit-prioritization artifacts, trace-audit diagnostics, "
    "experiment configurations, and reproduction scripts will be deposited in an anonymous "
    "public repository for review and released with the final article."
)

DATA_AVAILABILITY_PDF = (
    "PRM800K, MuSiQue, and WebQSP are publicly available from their original sources."
)

REPRODUCIBILITY_CHECKLIST_SOURCE = (
    "Full commands, local raw-data expectations, output paths, and claim-boundary notes "
    "are documented in the supplementary reproducibility checklist."
)

AI_DISCLOSURE = (
    "During the preparation of this work, the authors used OpenAI GPT-5 "
    "to improve language clarity and assist with LaTeX formatting checks."
)

MUSIQUE_BOUNDARY = "kbs_style_audit_prioritization_evidence_only"
KBS_AUDIT_BOUNDARY = (
    "The current KBS-facing evidence is limited to audit prioritization "
    "and does not validate a deployed KBS workflow."
)
STRESS_TEST_SOURCE_SNIPPET = "SCU component contribution on a structural stress-test benchmark"
KG_STAGE_SOURCE_SNIPPET = r"\subsection{Countries-KG Typed-Edge Stage}"


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
            "mahaoran0000@foxmail.com",
            "wangningning@bistu.edu.cn",
            "National Social Science Fund of China Project (24BSH018)",
            "Beijing Natural Science Foundation Project (L252145)",
            r"\section*{Declaration of Competing Interest}",
            "The authors declare that they have no conflicts of interest related to this work.",
            AI_DISCLOSURE,
            r"\section*{Data Availability}",
            DATA_AVAILABILITY,
            REPRODUCIBILITY_CHECKLIST_SOURCE,
            KBS_AUDIT_BOUNDARY,
            r"\section*{CRediT authorship contribution statement}",
            "Haoran Ma: Conceptualization. Ningning Wang: Supervision.",
            r"\includegraphics{figures/fig_sensitivity.png}",
        ]
    )
    supplementary_tex = supplementary_tex or "\n".join(
        [
            rf"\title[mode=title]{{Supplementary Material for {TITLE}}}",
            "Haoran Ma and Ningning Wang",
            r"\subsection{MuSiQue KBS-style Knowledge-Audit Details}",
            MUSIQUE_BOUNDARY,
            STRESS_TEST_SOURCE_SNIPPET,
            KG_STAGE_SOURCE_SNIPPET,
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
                "SC-FMA calibrates utility into auditable verification-step weights.",
                "PRM800K readout gives preliminary audit-prioritization support.",
            ]
        ),
    )
    _write_pdf(package_dir / "manuscript.pdf")
    _write_docx(
        package_dir / "supplementary.docx",
        (
            f"Supplementary Material\n{TITLE}\nHaoran Ma\nNingning Wang\n"
            f"MuSiQue KBS-style Knowledge-Audit Details\n{MUSIQUE_BOUNDARY}\n"
            f"{STRESS_TEST_SOURCE_SNIPPET}\nCountries-KG typed-edge stage"
        ),
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
            "mahaoran0000@foxmail.com",
            "wangningning@bistu.edu.cn",
            "National Social Science Fund of China Project (24BSH018)",
            DATA_AVAILABILITY_PDF,
            AI_DISCLOSURE,
            KBS_AUDIT_BOUNDARY,
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
        expected_manuscript_pages=35,
        pdf_page_count_by_name={"manuscript.pdf": 35},
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


def test_kbs_verifier_blocks_manuscript_repair_regressions(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_source_zip(
        package_dir / "latex_source.zip",
        manuscript_tex="\n".join(
            [
                TITLE,
                "OpenAI Codex",
                "ORCID (s):",
                "validated_kbs_workflow=false",
                "F_PRM_TRAINING",
                "NOT claimed",
                "Fixed-budget audit-prioritization comparison on the locked PRM800K hash split",
                "tab:audit-demo-results",
                "[NAME OF TOOL / SERVICE TO BE CONFIRMED BY AUTHORS]",
            ]
        ),
    )

    report = check_package(package_dir)

    assert not report.ok
    assert any("obsolete generative-AI tool statement remains" in error for error in report.errors)
    assert any("empty ORCID field remains visible" in error for error in report.errors)
    assert any("visible code-style KBS boundary variable remains" in error for error in report.errors)
    assert any("visible code-style PRM-training boundary variable remains" in error for error in report.errors)
    assert any("defensive all-caps claim heading remains" in error for error in report.errors)
    assert any("duplicate fixed-budget audit table remains" in error for error in report.errors)
    assert any("duplicate fixed-budget audit table remains" in error for error in report.errors)
    assert any("unresolved generative-AI tool placeholder remains" in error for error in report.errors)


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


def test_kbs_verifier_blocks_unexpected_manuscript_page_count(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    report = check_package(
        package_dir,
        expected_manuscript_pages=35,
        pdf_page_count_by_name={"manuscript.pdf": 36},
    )

    assert not report.ok
    assert any(
        "rendered manuscript.pdf page count 36 does not match expected 35" in error
        for error in report.errors
    )


def test_kbs_verifier_allows_manuscript_page_count_within_minimum_and_maximum(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    report = check_package(
        package_dir,
        min_manuscript_pages=12,
        max_manuscript_pages=20,
        pdf_page_count_by_name={"manuscript.pdf": 19},
    )

    assert report.ok, report.errors


def test_kbs_verifier_blocks_manuscript_page_count_below_minimum(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    report = check_package(
        package_dir,
        min_manuscript_pages=12,
        max_manuscript_pages=20,
        pdf_page_count_by_name={"manuscript.pdf": 5},
    )

    assert not report.ok
    assert any(
        "rendered manuscript.pdf page count 5 is below minimum 12" in error
        for error in report.errors
    )


def test_kbs_verifier_blocks_manuscript_page_count_above_maximum(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    report = check_package(
        package_dir,
        max_manuscript_pages=20,
        pdf_page_count_by_name={"manuscript.pdf": 21},
    )

    assert not report.ok
    assert any(
        "rendered manuscript.pdf page count 21 exceeds maximum 20" in error
        for error in report.errors
    )


def test_kbs_verifier_reads_pdfinfo_with_utf8_replacement(tmp_path: Path, monkeypatch) -> None:
    from scripts import verify_kbs_submission_package
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    calls: list[dict[str, object]] = []

    class PdfInfoResult:
        returncode = 0
        stdout = "Title: contains replacement-safe metadata\nPages: 35\n"
        stderr = ""

    def fake_run(*_args, **kwargs):
        calls.append(kwargs)
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        return PdfInfoResult()

    monkeypatch.setattr(verify_kbs_submission_package.subprocess, "run", fake_run)

    report = check_package(package_dir, expected_manuscript_pages=35)

    assert report.ok, report.errors
    assert calls


def test_kbs_verifier_falls_back_when_pdfinfo_shim_fails(tmp_path: Path, monkeypatch) -> None:
    from scripts import verify_kbs_submission_package
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)

    class FailedPdfInfo:
        returncode = 1
        stdout = ""
        stderr = "The system cannot find the path specified."

    class GoodPdfInfo:
        returncode = 0
        stdout = "Pages: 35\n"
        stderr = ""

    def fake_candidates():
        return ["pdfinfo", r"D:\DevelopTools\texlive\2026\bin\windows\pdfinfo.exe"]

    def fake_run(args, **_kwargs):
        return FailedPdfInfo() if args[0] == "pdfinfo" else GoodPdfInfo()

    monkeypatch.setattr(verify_kbs_submission_package, "_pdfinfo_candidates", fake_candidates)
    monkeypatch.setattr(verify_kbs_submission_package.subprocess, "run", fake_run)

    report = check_package(package_dir, expected_manuscript_pages=35)

    assert report.ok, report.errors


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


def test_kbs_verifier_blocks_docx_table_conversion_markers(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "final_package"
    _write_final_package(package_dir)
    _write_docx(
        package_dir / "supplementary.docx",
        (
            f"Supplementary Material\n{TITLE}\nHaoran Ma\nNingning Wang\n"
            f"MuSiQue KBS-style Knowledge-Audit Details\n{MUSIQUE_BOUNDARY}\n"
            "Cross-correlation table [/TABLE]"
        ),
    )

    report = check_package(package_dir)

    assert not report.ok
    assert any("residual table-conversion marker remains" in error for error in report.errors)
