#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _venv_bootstrap import reexec_into_project_venv
    reexec_into_project_venv(ROOT)
except Exception:
    pass

missing: list[str] = []
for module in ["pydantic", "pydantic_settings", "fastapi", "numpy"]:
    try:
        __import__(module)
    except Exception as exc:
        missing.append(f"{module}: {exc}")

if missing:
    print("Missing Python dependencies for LFTR:", file=sys.stderr)
    for item in missing:
        print(f" - {item}", file=sys.stderr)
    print("\nFix:", file=sys.stderr)
    print("  cd ~/broadcast", file=sys.stderr)
    print("  .venv/bin/python -m pip install -r requirements.txt", file=sys.stderr)
    print("  .venv/bin/python -m pip install -e .", file=sys.stderr)
    raise SystemExit(1)

import pydantic
import pydantic_settings
print({
    "ok": True,
    "python": sys.executable,
    "pydantic": getattr(pydantic, "__version__", "unknown"),
    "pydantic_settings": getattr(pydantic_settings, "__version__", "unknown"),
})
