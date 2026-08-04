#!/usr/bin/env python3
"""Re-exec check/diagnostic scripts inside the project .venv when available.

This lets server operators run `python3 scripts/check_*.py` and still use the
project dependencies installed by scripts/install.sh. Set LFTR_NO_VENV_REEXEC=1
to disable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def reexec_into_project_venv(root: Path | None = None) -> None:
    if os.environ.get("LFTR_NO_VENV_REEXEC") == "1":
        return
    root = root or Path(__file__).resolve().parents[1]
    venv_python = root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return
    current = Path(sys.executable).resolve()
    target = venv_python.resolve()
    if current == target:
        return
    env = os.environ.copy()
    env["LFTR_VENV_REEXECED"] = "1"
    os.execve(str(target), [str(target), *sys.argv], env)
