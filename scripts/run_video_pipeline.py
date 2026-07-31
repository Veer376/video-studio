#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "src"))
    runpy.run_module("cli", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

