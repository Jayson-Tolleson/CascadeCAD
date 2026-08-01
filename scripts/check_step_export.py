#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import cadquery as cq
import trimesh
from OCP.Interface import Interface_Static

from webcad_xbf.geometry import (
    _mesh_to_cq_shape,
    _step_report_preserves_mesh_source,
    export_step,
)


def _has_mesh_geometry(report: dict) -> bool:
    return _step_report_preserves_mesh_source(report)


def run(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)
    (root / "exports").mkdir(parents=True)

    assembly = cq.Assembly(name="step_ap242_smoke")
    assembly.add(cq.Workplane("XY").box(20, 30, 40), name="exact_box")
    mesh = trimesh.creation.icosphere(subdivisions=1, radius=8.0)
    assembly.add(_mesh_to_cq_shape(mesh), name="mesh_sphere")
    assembly.export(str(root / "master.xbf"), "XBF")

    progress = lambda _value, _message: None
    whole = export_step(root, "mixed", None, progress, max_faceted_triangles=10_000)
    if whole["exact_entity_count"] < 1 or not _has_mesh_geometry(whole):
        raise RuntimeError(f"Mixed STEP smoke test omitted geometry: {whole}")

    mesh_only = export_step(
        root,
        "mixed",
        None,
        progress,
        component_ids=["mesh_sphere"],
        max_faceted_triangles=10_000,
    )
    if not _has_mesh_geometry(mesh_only):
        raise RuntimeError(f"Selected mesh STEP smoke test omitted geometry: {mesh_only}")

    Interface_Static.SetIVal_s("read.step.tessellated", 1)
    reopened = cq.Assembly.load(str(root / mesh_only["relative_path"]), importType="STEP")
    if sum(1 for _item in reopened) < 1:
        raise RuntimeError("Selected mesh STEP could not be reopened as geometry")

    exact_only = export_step(
        root,
        "mixed",
        None,
        progress,
        component_ids=["exact_box"],
        max_faceted_triangles=10_000,
    )
    if exact_only["exact_entity_count"] < 1:
        raise RuntimeError(f"Selected exact STEP smoke test omitted B-rep geometry: {exact_only}")

    print(
        "CascadeCAD STEP export smoke test: OK "
        f"(mixed={whole.get('writer_mode')}, mesh={mesh_only.get('writer_mode')}, "
        f"exact={exact_only.get('writer_mode')})"
    )


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/cascade-cad-step-export-smoke")
    run(root)


if __name__ == "__main__":
    main()
