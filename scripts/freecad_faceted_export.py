#!/usr/bin/env python3
"""Build validated BREP or FCStd files from CascadeCAD export manifests.

This script runs under Debian's FreeCAD command-line Python, not the
CascadeCAD virtualenv.  It converts closed mesh components into faceted
Part solids and open meshes into Part shells.  It never creates Mesh::Feature
objects in an FCStd export.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import FreeCAD as App
import Mesh
import Part


def _write_json(path: Path, payload: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _is_null(shape) -> bool:
    try:
        return bool(shape.isNull())
    except Exception:
        return False


def _read_brep(path: str):
    shape = Part.Shape()
    result = shape.read(path)
    if result is False or _is_null(shape) or len(shape.Faces) == 0:
        raise RuntimeError("FreeCAD could not reopen exact BREP component: %s" % path)
    return shape


def _make_solid(shell):
    errors = []
    for factory in (getattr(Part, "makeSolid", None), getattr(Part, "Solid", None)):
        if factory is None:
            continue
        try:
            solid = factory(shell)
            if not _is_null(solid) and len(solid.Solids) > 0:
                try:
                    if float(solid.Volume) < 0:
                        solid.complement()
                except Exception:
                    pass
                return solid
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("Could not make a solid from a closed shell: %s" % "; ".join(errors[-2:]))


def _mesh_to_part(path: str, tolerance: float, watertight_hint: bool):
    mesh = Mesh.Mesh(path)
    if int(mesh.CountFacets) <= 0:
        raise RuntimeError("Mesh component contains no facets: %s" % path)

    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, float(tolerance))
    if _is_null(shape) or len(shape.Faces) == 0:
        raise RuntimeError("Shape-from-mesh produced no Part faces: %s" % path)

    shells = list(shape.Shells)
    if not shells:
        # Some FreeCAD builds can return a face compound without exposing a
        # Shells collection. Preserve that Part geometry instead of dropping it.
        return shape, "faceted-shell", 0, 0, []

    solids = []
    retained_shells = []
    solid_errors = []
    for shell in shells:
        closure_known = False
        shell_closed = False
        try:
            shell_closed = bool(shell.isClosed())
            closure_known = True
        except Exception:
            pass

        # The source-mesh hint is only a fallback when FreeCAD cannot answer.
        # It must never override a per-shell isClosed() result, because one STL
        # component can contain both closed and open disconnected shells.
        if not closure_known and len(shells) == 1:
            shell_closed = bool(watertight_hint)

        if shell_closed:
            try:
                solids.append(_make_solid(shell))
                continue
            except Exception as exc:
                solid_errors.append(str(exc))

        # Preserve open shells and closed shells that failed solid creation.
        retained_shells.append(shell)

    converted_items = solids + retained_shells
    if not converted_items:
        return shape, "faceted-shell", 0, 0, solid_errors
    converted = (
        converted_items[0]
        if len(converted_items) == 1
        else Part.makeCompound(converted_items)
    )

    if solids and retained_shells:
        status = "faceted-mixed-solid-shell"
    elif solids:
        status = "faceted-solid"
    else:
        status = "faceted-shell"
    return converted, status, len(solids), len(retained_shells), solid_errors


def _shape_counts(shape) -> dict:
    return {
        "faces": int(len(shape.Faces)),
        "shells": int(len(shape.Shells)),
        "solids": int(len(shape.Solids)),
    }


def build(manifest_path: Path, output: Path, output_format: str, report_path: Path, progress_path: Path, tolerance: float) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = list(manifest.get("items") or [])
    if not items:
        raise RuntimeError("The FreeCAD export manifest contains no components")

    doc = App.newDocument("CASCADE_CAD")
    root = doc.addObject("App::Part", "CASCADE_CAD_Assembly")
    root.Label = "CascadeCAD Assembly"

    created = []
    created_records = []
    exact_components = 0
    faceted_solid_components = 0
    faceted_shell_components = 0
    faceted_mixed_components = 0
    faceted_mixed_source_components = 0
    faceted_open_shell_count = 0
    solid_count = 0
    face_count = 0
    warnings = []

    for index, item in enumerate(items, start=1):
        kind = str(item.get("kind") or "")
        label = str(item.get("name") or ("Component %04d" % index))
        internal_name = "Component_%04d" % index

        if kind == "brep":
            shape = _read_brep(str(item["path"]))
            status = "exact-brep"
            exact_components += 1
        elif kind == "mesh":
            shape, status, made_solids, retained_shells, errors = _mesh_to_part(
                str(item["path"]),
                tolerance,
                bool(item.get("watertight")),
            )
            solid_count += int(made_solids)
            faceted_open_shell_count += int(retained_shells)
            if status == "faceted-solid":
                faceted_solid_components += 1
            elif status == "faceted-mixed-solid-shell":
                faceted_mixed_components += 1
                warnings.append(
                    "%s contains %d closed faceted solid(s) and %d open or invalid "
                    "faceted shell(s); both were preserved"
                    % (label, int(made_solids), int(retained_shells))
                )
            else:
                faceted_shell_components += 1
                warnings.append("%s was not closed and remains faceted Part shell geometry" % label)
            if bool(item.get("mixed_source_geometry")):
                faceted_mixed_source_components += 1
                warnings.append(
                    "%s contained exact and triangulated faces, so the complete component "
                    "was exported as faceted Part geometry to avoid duplicated subfaces" % label
                )
            warnings.extend("%s: %s" % (label, message) for message in errors)
        else:
            raise RuntimeError("Unknown manifest component kind: %s" % kind)

        counts = _shape_counts(shape)
        face_count += counts["faces"]
        if kind == "brep":
            solid_count += counts["solids"]

        obj = doc.addObject("Part::Feature", internal_name)
        obj.Label = label
        obj.Shape = shape
        obj.addProperty("App::PropertyString", "CASCADE_Representation", "CASCADE_CAD")
        obj.CASCADE_Representation = status
        obj.addProperty("App::PropertyString", "CASCADE_ComponentId", "CASCADE_CAD")
        obj.CASCADE_ComponentId = str(item.get("component_id") or "")
        root.addObject(obj)
        created.append(obj)
        created_records.append((obj, str(item.get("component_id") or ""), label, status, counts))

        _write_json(
            progress_path,
            {
                "completed": index,
                "total": len(items),
                "message": "Converted %d/%d components" % (index, len(items)),
                "component": label,
            },
        )

    doc.recompute()
    output.parent.mkdir(parents=True, exist_ok=True)

    part_reports = []
    if output_format == "fcstd":
        doc.saveAs(str(output))
        App.closeDocument(doc.Name)
        reopened = App.open(str(output))
        part_objects = [
            obj for obj in reopened.Objects
            if getattr(obj, "TypeId", "") == "Part::Feature"
            and hasattr(obj, "Shape")
            and not _is_null(obj.Shape)
            and len(obj.Shape.Faces) > 0
        ]
        mesh_objects = [obj for obj in reopened.Objects if getattr(obj, "TypeId", "").startswith("Mesh::")]
        reopened_solids = sum(len(obj.Shape.Solids) for obj in part_objects)
        reopened_faces = sum(len(obj.Shape.Faces) for obj in part_objects)
        App.closeDocument(reopened.Name)
        if not part_objects or reopened_faces <= 0:
            raise RuntimeError("FCStd validation reopened no Part geometry")
        if mesh_objects:
            raise RuntimeError("FCStd validation found Mesh::Feature objects; solid conversion contract was violated")
        solid_count = int(reopened_solids)
        face_count = int(reopened_faces)
    elif output_format == "brep":
        shapes = [obj.Shape for obj in created if not _is_null(obj.Shape)]
        if not shapes:
            raise RuntimeError("BREP export contains no Part shapes")
        compound = shapes[0] if len(shapes) == 1 else Part.makeCompound(shapes)
        result = compound.exportBrep(str(output))
        if result is False:
            raise RuntimeError("FreeCAD reported failure while writing BREP")
        check = Part.Shape()
        check.read(str(output))
        counts = _shape_counts(check)
        if counts["faces"] <= 0:
            raise RuntimeError("BREP validation reopened no faces")
        solid_count = counts["solids"]
        face_count = counts["faces"]
        App.closeDocument(doc.Name)
    elif output_format == "parts":
        output.mkdir(parents=True, exist_ok=True)
        solid_count = 0
        face_count = 0
        for index, (obj, component_id, label, status, source_counts) in enumerate(created_records, start=1):
            filename = "%04d.brep" % index
            part_path = output / filename
            result = obj.Shape.exportBrep(str(part_path))
            if result is False:
                raise RuntimeError("FreeCAD failed to write converted component BREP: %s" % label)
            reopened = Part.Shape()
            read_result = reopened.read(str(part_path))
            counts = _shape_counts(reopened)
            if read_result is False or counts["faces"] <= 0:
                raise RuntimeError("FreeCAD could not reopen converted component BREP: %s" % label)
            solid_count += counts["solids"]
            face_count += counts["faces"]
            part_reports.append(
                {
                    "component_id": component_id,
                    "name": label,
                    "file": filename,
                    "representation": status,
                    "face_count": counts["faces"],
                    "shell_count": counts["shells"],
                    "solid_count": counts["solids"],
                    "source_face_count": source_counts["faces"],
                    "file_size": int(part_path.stat().st_size),
                }
            )
        App.closeDocument(doc.Name)
        if not part_reports:
            raise RuntimeError("FreeCAD component conversion wrote no BREP parts")
    else:
        raise RuntimeError("Unsupported FreeCAD output format: %s" % output_format)

    if output_format != "parts" and (not output.exists() or output.stat().st_size < 256):
        raise RuntimeError("FreeCAD created an empty or implausibly small %s file" % output_format.upper())

    report = {
        "component_count": len(created),
        "exact_component_count": exact_components,
        "faceted_solid_component_count": faceted_solid_components,
        "faceted_shell_component_count": faceted_shell_components,
        "faceted_mixed_component_count": faceted_mixed_components,
        "faceted_mixed_source_component_count": faceted_mixed_source_components,
        "faceted_open_shell_count": int(faceted_open_shell_count),
        "solid_count": int(solid_count),
        "face_count": int(face_count),
        "mesh_object_count": 0,
        "warnings": warnings,
        "file_size": int(output.stat().st_size) if output.is_file() else sum(item["file_size"] for item in part_reports),
        "parts": part_reports,
        "representation": "Part::Feature exact/faceted B-rep; mixed solids and shells preserved",
    }
    _write_json(report_path, report)
    return report


def _invocation_from_environment():
    """Read the helper contract without exposing data paths to FreeCAD's CLI.

    FreeCAD treats every ordinary argument after the script as another file to
    open unless its version-specific pass-through mode is used.  Debian builds
    can then execute this script with a successful process exit while omitting
    the script arguments, so no validation report is written.  Environment
    variables are stable across FreeCAD versions and avoid that parser boundary.
    """
    names = {
        "manifest": "CASCADE_CAD_FREECAD_MANIFEST",
        "output": "CASCADE_CAD_FREECAD_OUTPUT",
        "format": "CASCADE_CAD_FREECAD_FORMAT",
        "report": "CASCADE_CAD_FREECAD_REPORT",
        "progress": "CASCADE_CAD_FREECAD_PROGRESS",
        "tolerance": "CASCADE_CAD_FREECAD_TOLERANCE",
    }
    required = ("manifest", "output", "format", "report", "progress")
    values = {key: os.environ.get(env_name, "") for key, env_name in names.items()}
    if all(values[key] for key in required):
        output_format = values["format"].lower()
        if output_format not in ("brep", "fcstd", "parts"):
            raise ValueError("Unsupported CASCADE_CAD_FREECAD_FORMAT: %s" % output_format)
        return argparse.Namespace(
            manifest=values["manifest"],
            output=values["output"],
            format=output_format,
            report=values["report"],
            progress=values["progress"],
            tolerance=float(values["tolerance"] or "0.05"),
        )

    # Retain a direct-Python fallback for development and unit testing.  The
    # production FreeCAD launcher deliberately uses the environment contract.
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("output")
    parser.add_argument("format", choices=("brep", "fcstd", "parts"))
    parser.add_argument("report")
    parser.add_argument("progress")
    parser.add_argument("tolerance", nargs="?", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = _invocation_from_environment()
    report_path = Path(args.report)
    try:
        report = build(
            Path(args.manifest),
            Path(args.output),
            args.format,
            report_path,
            Path(args.progress),
            args.tolerance,
        )
    except Exception as exc:
        try:
            _write_json(report_path, {"error": str(exc), "failed": True})
        except Exception:
            pass
        print("CascadeCAD FreeCAD export failed: %s" % exc, file=sys.stderr)
        raise
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
