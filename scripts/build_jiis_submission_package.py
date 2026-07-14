"""Build the flat JIIS submission package and deterministic reproduction archive."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "paper" / "JIIS_submission"
BUILD_SUFFIXES = (
    ".aux",
    ".bbl",
    ".bcf",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".run.xml",
    ".synctex.gz",
)
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def referenced_figure_names(tex: str) -> list[str]:
    """Return unique bare image names in first-use order."""
    names: list[str] = []
    for match in re.finditer(
        r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", tex
    ):
        name = match.group(1).strip()
        path = PurePosixPath(name.replace("\\", "/"))
        if len(path.parts) != 1 or path.name != name:
            raise ValueError(f"figure reference must use a bare filename: {name}")
        if name not in names:
            names.append(name)
    return names


def compile_current_source(source: Path, build: Path) -> None:
    """Compile the current source files without importing any legacy manuscript."""
    build.mkdir(parents=True, exist_ok=True)
    for name in ("manuscript", "supplementary"):
        command = [
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-outdir={build}",
            f"{name}.tex",
        ]
        subprocess.run(command, cwd=source, check=True)  # noqa: S603


def stage_submission_package(
    source: Path,
    build: Path,
    package: Path,
) -> list[str]:
    """Create the minimal flat journal package from current source and PDFs."""
    if package.exists():
        for path in package.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    package.mkdir(parents=True, exist_ok=True)
    source_names = (
        "manuscript.tex",
        "supplementary.tex",
        "references.bib",
        "sn-jnl.cls",
        "sn-basic.bst",
    )
    for name in source_names:
        shutil.copy2(source / name, package / name)
    for name in ("manuscript.pdf", "supplementary.pdf"):
        compiled = build / name
        shutil.copy2(compiled, source / name)
        shutil.copy2(compiled, package / name)
    figure_names: list[str] = []
    for tex_name in ("manuscript.tex", "supplementary.tex"):
        for name in referenced_figure_names(
            (source / tex_name).read_text(encoding="utf-8")
        ):
            if name not in figure_names:
                figure_names.append(name)
    for name in figure_names:
        shutil.copy2(source / "figures" / name, package / name)
    staged = sorted(path.name for path in package.iterdir())
    if any(path.is_dir() for path in package.iterdir()):
        raise ValueError("submission package must not contain directories")
    if any(any(path.name.endswith(suffix) for suffix in BUILD_SUFFIXES) for path in package.iterdir()):
        raise ValueError("submission package contains LaTeX build artifacts")
    return staged


def build_reproducibility_archive(
    files: Mapping[str, Path | bytes],
    archive_path: Path,
    *,
    readme: str,
) -> None:
    """Write a byte-reproducible ZIP with sorted internal checksums."""
    payloads: dict[str, bytes] = {
        str(PurePosixPath(name)): (
            value if isinstance(value, bytes) else Path(value).read_bytes()
        )
        for name, value in files.items()
    }
    payloads["README.md"] = readme.encode("utf-8")
    checksums = "".join(
        f"{hashlib.sha256(payloads[name]).hexdigest()}  {name}\n"
        for name in sorted(payloads)
    )
    payloads["SHA256SUMS.txt"] = checksums.encode("ascii")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as bundle:
        for name in sorted(payloads):
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, payloads[name], compresslevel=9)


def verify_archive_checksums(archive_path: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(archive_path) as bundle:
        names = bundle.namelist()
        if names != sorted(names):
            errors.append("archive entries are not sorted")
        if any(name.endswith("/") for name in names):
            errors.append("archive contains directory entries")
        manifest = bundle.read("SHA256SUMS.txt").decode("ascii").splitlines()
        expected = {}
        for line in manifest:
            digest, name = line.split("  ", 1)
            expected[name] = digest
        for name, digest in expected.items():
            observed = hashlib.sha256(bundle.read(name)).hexdigest()
            if observed != digest:
                errors.append(f"checksum mismatch: {name}")
        unchecked = sorted(set(names) - set(expected) - {"SHA256SUMS.txt"})
        if unchecked:
            errors.append(f"archive entries missing checksums: {unchecked}")
    return errors


def collect_reproducibility_files(root: Path) -> dict[str, Path | bytes]:
    """Collect the frozen fair-v1 inputs, code, schema, and result artifacts."""
    config_path = root / "configs" / "jiis_controlled_maintenance_fair_v1.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["output_dir"] = "reproduced_outputs/jiis_controlled_maintenance_fair_v1"
    config["countries_report_path"] = "results/countries/jiis_audit_case_report.json"
    config["extraction"]["cache_path"] = "data/wdqs_cache.json"
    config["extraction"]["offline"] = True
    files: dict[str, Path | bytes] = {
        "configs/jiis_controlled_maintenance_fair_v1.yaml": yaml.safe_dump(
            config, sort_keys=False, allow_unicode=True
        ).encode("utf-8"),
        "requirements-jiis-lock.txt": root / "requirements-jiis-lock.txt",
        "schemas/scar_audit_record.schema.json": root
        / "schemas"
        / "scar_audit_record.schema.json",
        "data/wdqs_cache.json": root
        / "outputs"
        / "wikidata_scientist_kg_audit_v2"
        / "data"
        / "wdqs_cache.json",
    }
    for path in sorted((root / "src" / "fma").rglob("*.py")):
        files[path.relative_to(root).as_posix()] = path
    for name in (
        "run_wikidata_scientist_audit.py",
        "run_countries_kg_label_validation.py",
        "run_jiis_audit_case.py",
        "jiis_countries_kg_validation_core.py",
    ):
        files[f"scripts/{name}"] = root / "scripts" / name
    wikidata_results = root / "outputs" / "jiis_controlled_maintenance_fair_v1"
    for path in sorted(wikidata_results.rglob("*")):
        if path.is_file():
            files[
                "results/wikidata/" + path.relative_to(wikidata_results).as_posix()
            ] = path
    countries_results = root / "paper" / "JIIS_submission" / "reports" / "jiis_audit_case"
    for path in sorted(countries_results.glob("*")):
        if path.is_file():
            files[f"results/countries/{path.name}"] = path
    countries_cache = (
        root
        / "outputs"
        / "countries_kg_label_validation"
        / "countries_kg_labels_cached.json"
    )
    files["data/countries_kg_labels_cached.json"] = countries_cache
    missing = sorted(name for name, value in files.items() if isinstance(value, Path) and not value.is_file())
    if missing:
        raise FileNotFoundError(f"reproduction inputs are missing: {missing}")
    return files


def archive_readme() -> str:
    return """# JIIS fair-v1 frozen reproduction archive

This archive contains only the frozen Countries-KG cache and the corrected Wikidata v2 substrate used by the paper. It does not download new data or provide external-validity evidence.

Offline reproduction:

1. `python -m pip install -r requirements-jiis-lock.txt`
2. `python scripts/run_wikidata_scientist_audit.py --config configs/jiis_controlled_maintenance_fair_v1.yaml`

The configuration sets `offline: true`; a missing or mismatched cache fails before any network request. Compare the rebuilt JSON metrics under `reproduced_outputs/jiis_controlled_maintenance_fair_v1` with `results/wikidata`.
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--skip-compile", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    workspace = args.workspace.resolve()
    source = workspace / "source"
    build = workspace / "build"
    package = workspace / "submission_package"
    if not args.skip_compile:
        compile_current_source(source, build)
    stage_submission_package(source, build, package)
    archive = package / "reproducibility_archive.zip"
    build_reproducibility_archive(
        collect_reproducibility_files(ROOT),
        archive,
        readme=archive_readme(),
    )
    errors = verify_archive_checksums(archive)
    if errors:
        raise ValueError("; ".join(errors))
    print(f"built {package}")


if __name__ == "__main__":
    main()
