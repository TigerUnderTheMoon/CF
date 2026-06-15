from __future__ import annotations

from pathlib import Path


TITLE = (
    "Structurally-Calibrated Functional Attribution: A Methodology for "
    "Process Supervision Weighting in Reflective Reasoning"
)


def _write_minimal_package(
    package_dir: Path,
    *,
    title: str = TITLE,
    cover_title: str | None = None,
    author_text: str = "Anonymous Author(s)",
    affiliation_text: str = "Anonymous Institution",
    acknowledgement_text: str = "The authors have no acknowledgments to report for the initial submission.",
) -> None:
    cover_title = cover_title or title
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "supplementary").mkdir()

    (package_dir / "main.tex").write_text(
        "\n".join(
            [
                rf"\title[mode=title]{{{title}}}",
                rf"\author[1]{{{author_text}}}",
                rf"\affiliation[1]{{organization={{{affiliation_text}}}}}",
                r"\begin{abstract}",
                "Abstract text.",
                r"\end{abstract}",
                r"\begin{highlights}",
                r"\item SC-FMA calibrates interventional utility into supervision weights.",
                r"\end{highlights}",
                r"\section*{Acknowledgments}",
                acknowledgement_text,
                r"\section*{Declaration of competing interest}",
                "The authors declare no known competing financial interests.",
                r"\section*{Declaration of generative AI and AI-assisted technologies in the writing process}",
                "The authors used OpenAI Codex for language editing.",
                r"\section*{Data and code availability}",
                "Data and code are available in the anonymous submission package.",
                r"\section*{CRediT authorship contribution statement}",
                "Author roles are stated here.",
            ]
        ),
        encoding="utf-8",
    )
    (package_dir / "cover_letter.md").write_text(
        "\n".join(
            [
                "# Cover Letter",
                "",
                f'**Subject**: Submission of Regular Article: "{cover_title}"',
                "",
                "Dear Editor,",
                "",
                f'Please consider the manuscript "{cover_title}" as a Regular Article for Knowledge-Based Systems.',
            ]
        ),
        encoding="utf-8",
    )
    for filename in (
        "main.pdf",
        "references.bib",
        "cas-sc.cls",
        "cas-common.sty",
        "cas-model2-names.bst",
        "format_checklist.md",
        "final_submission_manifest.md",
        "submission_author_metadata_template.md",
        "supplementary_materials.md",
    ):
        (package_dir / filename).write_text("placeholder\n", encoding="utf-8")
    (package_dir / "supplementary" / "supplementary_manifest.md").write_text(
        "manifest\n", encoding="utf-8"
    )
    (package_dir / "supplementary" / "Supplementary_Data_S1_governance_diagnostic_report.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (package_dir / "supplementary" / "Supplementary_Figure_S1_governance_diagnostic_upset.png").write_bytes(
        b"png"
    )


def test_kbs_verifier_passes_package_controlled_checks_without_author_gate(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "kbs_submission"
    _write_minimal_package(package_dir)

    report = check_package(package_dir, require_author_metadata=False)

    assert report.ok, report.errors
    assert report.warnings == ["author metadata placeholders remain"]


def test_kbs_verifier_blocks_direct_upload_when_author_metadata_is_required(
    tmp_path: Path,
) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "kbs_submission"
    _write_minimal_package(package_dir)

    report = check_package(package_dir, require_author_metadata=True)

    assert not report.ok
    assert any("author metadata placeholders remain" in error for error in report.errors)


def test_kbs_verifier_catches_title_drift_and_pre_review_acknowledgment(
    tmp_path: Path,
) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "kbs_submission"
    _write_minimal_package(
        package_dir,
        cover_title="Functional Metacognitive Attribution: A Diagnostic and Design Framework",
        acknowledgement_text="The authors acknowledge the anonymous reviewers for their constructive feedback.",
    )

    report = check_package(package_dir, require_author_metadata=False)

    assert not report.ok
    assert any("cover letter does not contain current title" in error for error in report.errors)
    assert any("pre-review anonymous reviewer acknowledgment" in error for error in report.errors)


def test_kbs_verifier_passes_rendered_pdf_text_gate(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "kbs_submission"
    _write_minimal_package(package_dir)
    pdf_text = "\n".join(
        [
            TITLE,
            "Highlights",
            "Declaration of competing interest",
            "Declaration of generative AI",
            "Data and code availability",
            "CRediT authorship contribution statement",
        ]
    )

    report = check_package(package_dir, require_pdf_text=True, pdf_text=pdf_text)

    assert report.ok, report.errors


def test_kbs_verifier_blocks_stale_rendered_pdf_text(tmp_path: Path) -> None:
    from scripts.verify_kbs_submission_package import check_package

    package_dir = tmp_path / "kbs_submission"
    _write_minimal_package(package_dir)
    pdf_text = "\n".join(
        [
            "Functional Metacognitive Attribution: A Diagnostic and Design Framework",
            "Highlights",
            "Declaration of competing interest",
            "Declaration of generative AI",
            "Data and code availability",
            "CRediT authorship contribution statement",
        ]
    )

    report = check_package(package_dir, require_pdf_text=True, pdf_text=pdf_text)

    assert not report.ok
    assert any("rendered PDF text does not contain current title" in error for error in report.errors)
