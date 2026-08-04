#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import cadquery as cq

from webcad_xbf.editor import new_state
from webcad_xbf.geometry import _assembly_components, combine_projects


def export_pair(directory: Path, name: str, shape) -> tuple[Path, dict]:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "previews").mkdir(exist_ok=True)
    (directory / "revisions").mkdir(exist_ok=True)
    assembly = cq.Assembly(name=name).add(shape, name=f"{name}_body")
    master = directory / "master.xbf"
    preview = directory / "previews" / "overview.glb"
    assembly.export(str(master), "XBF")
    assembly.export(str(preview), "GLB", tolerance=0.5, angularTolerance=0.3)
    return master, new_state(_assembly_components(assembly, "exact"))


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/cascade-cad-combine-smoke")
    shutil.rmtree(root, ignore_errors=True)
    target = root / "target"
    source = root / "source"

    _target_master, target_state = export_pair(
        target,
        "frame",
        cq.Workplane("XY").box(100, 40, 10),
    )
    source_master, source_state = export_pair(
        source,
        "cab",
        cq.Workplane("XY").box(35, 35, 30),
    )

    result = combine_projects(
        project_dir=target,
        target_geometry_kind="exact",
        target_editor_state=target_state,
        sources=[
            {
                "project_id": "prj_smoke_source",
                "name": "Cab project",
                "geometry_kind": "exact",
                "master_path": str(source_master),
                "editor_state": source_state,
            }
        ],
        preview_tolerance=0.5,
        preview_angular_tolerance=0.3,
        progress=lambda _value, _message: None,
    )

    combined = cq.Assembly.load(str(target / "master.xbf"), importType="XBF")
    if not result.get("combined_projects"):
        raise RuntimeError("Combine smoke test did not report the imported project")
    wrapper = result["combined_projects"][0]["assembly_node"]
    if wrapper not in combined.objects:
        raise RuntimeError(f"Combined XBF is missing wrapper node: {wrapper}")
    preview = target / "previews" / "overview.glb"
    if not preview.exists() or preview.stat().st_size == 0:
        raise RuntimeError("Combined GLB preview was not generated")
    if result.get("geometry_kind") != "exact":
        raise RuntimeError("Exact + exact combine should remain exact")
    print(f"CascadeCAD combine smoke test: OK ({wrapper})")


if __name__ == "__main__":
    main()
