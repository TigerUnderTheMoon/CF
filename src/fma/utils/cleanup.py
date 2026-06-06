"""Output cleanup and archival helpers for FMA artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


CORE_OUTPUT_DIRS = (
    Path("outputs") / "figures",
    Path("outputs") / "phase5",
    Path("outputs") / "phase6",
    Path("outputs") / "phase7",
)

FAILED_PILOT_DIRS = (
    Path("outputs") / "s_fma_v2_fresh_holdout",
    Path("outputs") / "s_fma_v2_2_fresh_holdout",
)

PRESERVED_OUTPUT_NAMES = {
    "phase5",
    "phase6",
    "phase7",
    "figures",
    "archive",
    "s_fma_v2_1_fresh_holdout",
    "real_task_v3",
    "benchmarks",
}


@dataclass(frozen=True)
class CleanupReport:
    """Summary of output cleanup actions."""

    archived: list[str]
    preserved_core: list[str]
    skipped: list[str]


def cleanup_outputs(
    repo_root: str | Path,
    *,
    keep_core: bool,
    archive_failed: bool,
    archive_legacy: bool = True,
) -> CleanupReport:
    """Preserve core Phase 5-7 outputs and archive failed pilot routes.

    Args:
        repo_root: repository root path.
        keep_core: if True, do not touch ``outputs/phase{5,6,7}/``.
        archive_failed: if True, move ``s_fma_v2*`` failed pilots to
            ``outputs/archive/``.
        archive_legacy: if True, move all other top-level files and
            directories under ``outputs/`` that are not in the preserved
            set into ``outputs/archive/legacy/``.
    """

    root = Path(repo_root)
    archived: list[str] = []
    preserved_core: list[str] = []
    skipped: list[str] = []

    outputs_dir = root / "outputs"
    if not outputs_dir.exists():
        return CleanupReport(archived=archived, preserved_core=preserved_core, skipped=skipped)

    if keep_core:
        for path in CORE_OUTPUT_DIRS:
            full = root / path
            if full.exists():
                preserved_core.append(_as_posix(path))

    if archive_failed:
        archive_root = outputs_dir / "archive"
        for relative_source in FAILED_PILOT_DIRS:
            source = root / relative_source
            if not source.exists():
                skipped.append(_as_posix(relative_source))
                continue

            destination = _available_archive_path(archive_root / source.name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            archived.append(
                f"{_as_posix(relative_source)} -> {_as_posix(destination.relative_to(root))}"
            )

    if archive_legacy:
        legacy_root = outputs_dir / "archive" / "legacy"
        for item in outputs_dir.iterdir():
            if item.name in PRESERVED_OUTPUT_NAMES:
                continue
            if item.name == ".gitkeep":
                continue
            destination = _available_archive_path(legacy_root / item.name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(destination))
            archived.append(
                f"{_as_posix(item.relative_to(root))} -> {_as_posix(destination.relative_to(root))}"
            )

    return CleanupReport(
        archived=archived,
        preserved_core=preserved_core,
        skipped=skipped,
    )


def _available_archive_path(destination: Path) -> Path:
    if not destination.exists():
        return destination

    for index in range(1, 1000):
        candidate = destination.with_name(f"{destination.name}_{index}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not allocate archive path for {destination}")


def _as_posix(path: Path) -> str:
    return path.as_posix()
