#!/usr/bin/env python3
"""Validate CascadeCAD geometry runtime imports before accepting jobs."""
from __future__ import annotations

import argparse
import importlib
import sys
import shutil
from pathlib import Path
from importlib import metadata

REQUIRED = (
    ("cadquery", "cadquery"),
    ("OCP", "cadquery-ocp"),
    ("trimesh", "trimesh"),
    ("networkx", "networkx"),
    ("numpy", "numpy"),
)


def version_for(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    failures: list[str] = []
    loaded: list[tuple[str, str]] = []
    for module_name, distribution in REQUIRED:
        try:
            importlib.import_module(module_name)
            loaded.append((module_name, version_for(distribution)))
        except Exception as exc:  # Import errors from native libraries matter too.
            failures.append(f"{module_name}: {type(exc).__name__}: {exc}")

    try:
        from OCP.BRepBuilderAPI import (  # noqa: F401
            BRepBuilderAPI_FastSewing,
            BRepBuilderAPI_MakeShapeOnMesh,
            BRepBuilderAPI_Sewing,
        )
    except Exception as exc:
        failures.append(
            "OCP hard-speed classes are missing: "
            f"{type(exc).__name__}: {exc}"
        )

    freecad_cmd = shutil.which("freecadcmd-python3") or shutil.which("freecadcmd") or "/usr/lib/freecad/bin/freecadcmd-python3"
    if not Path(freecad_cmd).exists():
        failures.append("freecad-python3 command is missing; BREP/FCStd solid export is unavailable")

    if failures:
        print("CascadeCAD geometry runtime check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "Repair with: sudo /opt/cascade-cad/.venv/bin/pip install --upgrade "
            "'networkx>=3.4,<4'; sudo apt install freecad-python3; sudo systemctl restart cascade-cad-worker",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print("CascadeCAD geometry runtime OK")
        for module_name, version in loaded:
            print(f"  {module_name}: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
