"""CLI entry point for structural reflection diagnostics.

All business logic lives in ``fma.graph.diagnostics``. This script only
parses arguments and delegates to the installable package.
"""

from __future__ import annotations

import json
import sys

from fma.graph.diagnostics import main

if __name__ == "__main__":
    result = main(sys.argv[1:])
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0)
