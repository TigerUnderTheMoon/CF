from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from scripts.build_jiis_submission_package import (
    build_reproducibility_archive,
    referenced_figure_names,
    stage_submission_package,
    verify_archive_checksums,
)


def test_referenced_figures_require_bare_names_and_preserve_order() -> None:
    tex = """
    \\graphicspath{{./}{figures/}}
    \\includegraphics{first.png}
    \\includegraphics[width=0.5\\linewidth]{second.png}
    \\includegraphics{first.png}
    """

    assert referenced_figure_names(tex) == ["first.png", "second.png"]


def test_builder_never_reads_superseded_information_sciences_source() -> None:
    builder = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "build_jiis_submission_package.py"
    ).read_text(encoding="utf-8")

    assert "information_sciences_submission" not in builder


def test_stage_submission_package_is_flat_and_contains_only_referenced_figures(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    build = tmp_path / "build"
    package = tmp_path / "submission_package"
    figures = source / "figures"
    figures.mkdir(parents=True)
    build.mkdir()
    manuscript = """\\documentclass{sn-jnl}
\\usepackage{graphicx}
\\graphicspath{{./}{figures/}}
\\begin{document}\\includegraphics{used.png}\\end{document}
"""
    supplementary = """\\documentclass{sn-jnl}
\\begin{document}Supplement\\end{document}
"""
    (source / "manuscript.tex").write_text(manuscript, encoding="utf-8")
    (source / "supplementary.tex").write_text(supplementary, encoding="utf-8")
    (source / "references.bib").write_text("@misc{x,title={X}}\n", encoding="utf-8")
    (source / "sn-jnl.cls").write_text("class", encoding="utf-8")
    (source / "sn-basic.bst").write_text("bst", encoding="utf-8")
    (figures / "used.png").write_bytes(b"used")
    (figures / "unused.png").write_bytes(b"unused")
    (build / "manuscript.pdf").write_bytes(b"main-pdf")
    (build / "supplementary.pdf").write_bytes(b"supp-pdf")

    staged = stage_submission_package(source, build, package)

    assert set(staged) == {
        "manuscript.tex",
        "supplementary.tex",
        "references.bib",
        "sn-jnl.cls",
        "sn-basic.bst",
        "manuscript.pdf",
        "supplementary.pdf",
        "used.png",
    }
    assert not any(path.is_dir() for path in package.iterdir())
    assert not (package / "unused.png").exists()


def test_reproducibility_archive_is_deterministic_and_checksum_verified(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha\n", encoding="utf-8")
    second.write_text("beta\n", encoding="utf-8")
    archive = tmp_path / "reproduction.zip"
    files = {"z/second.txt": second, "a/first.txt": first}

    build_reproducibility_archive(files, archive, readme="offline\n")
    digest_before = hashlib.sha256(archive.read_bytes()).hexdigest()
    build_reproducibility_archive(files, archive, readme="offline\n")
    digest_after = hashlib.sha256(archive.read_bytes()).hexdigest()

    assert digest_after == digest_before
    assert verify_archive_checksums(archive) == []
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.namelist() == sorted(bundle.namelist())
        assert all(not name.endswith("/") for name in bundle.namelist())
        assert bundle.read("README.md") == b"offline\n"
