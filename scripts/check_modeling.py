#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import cadquery as cq

from webcad_xbf.editor import new_state
from webcad_xbf.geometry import _assembly_components, model_operation


def run(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)
    (root / "previews").mkdir(parents=True)
    (root / "revisions").mkdir()
    assembly = cq.Assembly(name="modeling_smoke")
    assembly.add(cq.Workplane("XY").box(40, 40, 20), name="box")
    assembly.add(cq.Workplane("XY").cylinder(30, 12), name="cylinder")
    assembly.export(str(root / "master.xbf"), "XBF")
    assembly.export(str(root / "previews" / "overview.glb"), "GLB", tolerance=0.5, angularTolerance=0.3)
    state = new_state(_assembly_components(assembly, "exact"))

    fused = model_operation(
        project_dir=root,
        geometry_kind="exact",
        editor_state=state,
        operation="fuse",
        component_ids=["box", "cylinder"],
        parameters={"name": "fusion"},
        preview_tolerance=0.5,
        preview_angular_tolerance=0.3,
        progress=lambda _value, _message: None,
    )
    fusion_id = fused.get("added_component")
    if not fusion_id:
        raise RuntimeError("Fuse smoke test did not create a component")

    state = new_state(fused["components"])
    mirrored = model_operation(
        project_dir=root,
        geometry_kind="exact",
        editor_state=state,
        operation="mirror",
        component_ids=[fusion_id],
        parameters={"name": "fusion_mirror", "plane": "YZ"},
        preview_tolerance=0.5,
        preview_angular_tolerance=0.3,
        progress=lambda _value, _message: None,
    )
    if not mirrored.get("added_component"):
        raise RuntimeError("Mirror smoke test did not create a component")

    state = new_state(mirrored["components"])
    torus = model_operation(
        project_dir=root,
        geometry_kind="exact",
        editor_state=state,
        operation="torus",
        component_ids=[],
        parameters={"name": "torus", "major_radius": 20, "minor_radius": 4, "position": [60, 0, 0]},
        preview_tolerance=0.5,
        preview_angular_tolerance=0.3,
        progress=lambda _value, _message: None,
    )
    if not torus.get("added_component"):
        raise RuntimeError("Torus smoke test did not create a component")
    if not (root / "master.xbf").exists() or not (root / "previews" / "overview.glb").exists():
        raise RuntimeError("Modeling smoke test did not write XBF and GLB")
    print("CascadeCAD modeling smoke test: OK")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/cascade-cad-modeling-smoke")
    run(root)


if __name__ == "__main__":
    main()
