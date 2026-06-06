"""Compatibility shim for local, non-installed imports.

The installable FMA package lives in ``src/fma``. This shim keeps direct
``python scripts/...`` workflows working before ``pip install -e .``.
"""

from __future__ import annotations

from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "fma"
if _SRC_PACKAGE.exists():
    __path__.insert(0, str(_SRC_PACKAGE))

__all__: list[str] = []
