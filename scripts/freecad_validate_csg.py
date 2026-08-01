#!/usr/bin/env python3
"""Validate that a CascadeCAD CSG opens as separate FreeCAD Part objects."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import FreeCAD as App
import sys

try:
    import importCSG
except ImportError:
    candidates = [
        Path(App.getHomePath()) / "Mod" / "OpenSCAD",
        Path("/usr/share/freecad/Mod/OpenSCAD"),
        Path("/usr/lib/freecad/Mod/OpenSCAD"),
    ]
    for candidate in candidates:
        if candidate.exists():
            sys.path.insert(0, str(candidate))
    import importCSG


def _is_null(shape) -> bool:
    try:
        return bool(shape.isNull())
    except Exception:
        return False


def main() -> None:
    if all(os.environ.get(name) for name in (
        "CASCADE_CAD_CSG_VALIDATE_FILE",
        "CASCADE_CAD_CSG_VALIDATE_EXPECTED",
        "CASCADE_CAD_CSG_VALIDATE_REPORT",
    )):
        args = argparse.Namespace(
            csg=os.environ["CASCADE_CAD_CSG_VALIDATE_FILE"],
            expected_parts=int(os.environ["CASCADE_CAD_CSG_VALIDATE_EXPECTED"]),
            report=os.environ["CASCADE_CAD_CSG_VALIDATE_REPORT"],
        )
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("csg")
        parser.add_argument("expected_parts", type=int)
        parser.add_argument("report")
        args = parser.parse_args()

    path = Path(args.csg).resolve()
    importCSG.open(str(path))
    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("FreeCAD did not create a document for the CSG file")

    part_objects = [
        obj for obj in doc.Objects
        if getattr(obj, "TypeId", "") == "Part::Feature"
        and hasattr(obj, "Shape")
        and not _is_null(obj.Shape)
        and len(obj.Shape.Faces) > 0
    ]
    root_parts = [obj for obj in part_objects if not list(getattr(obj, "InList", []))]
    solids = sum(len(obj.Shape.Solids) for obj in part_objects)
    valid_solid_objects = []
    invalid_objects = []
    total_volume = 0.0
    for obj in part_objects:
        shape = obj.Shape
        try:
            valid = bool(shape.isValid())
        except Exception:
            valid = True
        try:
            object_solids = len(shape.Solids)
        except Exception:
            object_solids = 0
        try:
            volume = abs(float(shape.Volume))
        except Exception:
            volume = 0.0
        total_volume += volume
        if valid and object_solids > 0 and volume > 1.0e-12:
            valid_solid_objects.append(obj)
        else:
            invalid_objects.append(obj)
    report = {
        "part_feature_count": len(part_objects),
        "root_part_count": len(root_parts),
        "solid_count": int(solids),
        "valid_solid_object_count": len(valid_solid_objects),
        "invalid_part_object_count": len(invalid_objects),
        "total_volume": float(total_volume),
        "expected_parts": int(args.expected_parts),
    }
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    App.closeDocument(doc.Name)

    # Some FreeCAD versions attach imported polyhedra to lightweight helper
    # objects, so validate all Part::Feature objects rather than only roots.
    if len(part_objects) < int(args.expected_parts):
        raise RuntimeError(
            "CSG imported as %d Part objects; expected at least %d separate parts"
            % (len(part_objects), int(args.expected_parts))
        )
    if len(valid_solid_objects) < int(args.expected_parts):
        raise RuntimeError(
            "CSG imported only %d valid nonzero-volume solids; expected %d. "
            "The polyhedron topology or winding is invalid."
            % (len(valid_solid_objects), int(args.expected_parts))
        )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
