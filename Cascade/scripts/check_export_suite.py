#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from webcad_xbf.geometry import _freecad_command, convert_to_faceted_solids, export_project_file
from webcad_xbf.sample import build_sample


def _project(root: Path, master: Path) -> Path:
    project = root
    (project / "exports").mkdir(parents=True, exist_ok=True)
    shutil.copy2(master, project / "master.xbf")
    return project


def run(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    samples = build_sample(root / "samples")
    exact_project = _project(root / "exact-project", samples["xbf"])
    mesh_project = _project(root / "mesh-project", samples["mesh_xbf"])

    def progress(value: int, message: str) -> None:
        print(f"{value:3d}% {message}")

    exact_reports = {}
    for fmt in ("xbf", "csg"):
        exact_reports[fmt] = export_project_file(
            project_dir=exact_project,
            geometry_kind="exact",
            editor_state=None,
            progress=progress,
            export_format=fmt,
            max_faceted_triangles=10_000,
            max_csg_triangles=100_000,
        )
        path = exact_project / exact_reports[fmt]["relative_path"]
        if not path.exists() or path.stat().st_size < 100:
            raise RuntimeError(f"{fmt.upper()} exact smoke export is missing or empty")
        print(f"{fmt.upper()}: {path} ({path.stat().st_size} bytes)")

    mesh_reports = {}
    for fmt in ("brep", "csg", "fcstd"):
        mesh_reports[fmt] = export_project_file(
            project_dir=mesh_project,
            geometry_kind="mesh",
            editor_state=None,
            progress=progress,
            export_format=fmt,
            max_faceted_triangles=10_000,
            step_timeout_seconds=600,
            max_csg_triangles=100_000,
        )
        path = mesh_project / mesh_reports[fmt]["relative_path"]
        if not path.exists() or path.stat().st_size < 100:
            raise RuntimeError(f"{fmt.upper()} mesh smoke export is missing or empty")
        print(f"{fmt.upper()}: {path} ({path.stat().st_size} bytes)")

    if int(mesh_reports["brep"].get("solid_count", 0)) < 1:
        raise RuntimeError(f"Mesh BREP did not validate as a faceted solid: {mesh_reports['brep']}")
    if int(mesh_reports["fcstd"].get("solid_count", 0)) < 1:
        raise RuntimeError(f"Mesh FCStd did not contain a faceted Part solid: {mesh_reports['fcstd']}")
    if int(mesh_reports["fcstd"].get("mesh_object_count", -1)) != 0:
        raise RuntimeError(f"Mesh FCStd still contains Mesh::Feature objects: {mesh_reports['fcstd']}")
    if int(exact_reports["csg"].get("part_count", 0)) < 2:
        raise RuntimeError(f"CSG did not write separate top-level parts: {exact_reports['csg']}")

    conversion = convert_to_faceted_solids(
        project_dir=mesh_project,
        geometry_kind="mesh",
        editor_state=None,
        preview_tolerance=0.5,
        preview_angular_tolerance=0.3,
        progress=progress,
        max_triangles=10_000,
        timeout_seconds=600,
    )
    if not conversion.get("changed") or int(conversion.get("mesh_triangle_count_after", -1)) != 0:
        raise RuntimeError(f"Faceted XBF conversion did not remove mesh remnants: {conversion}")
    converted_step = export_project_file(
        project_dir=mesh_project,
        geometry_kind="faceted-brep",
        editor_state=None,
        progress=progress,
        export_format="step",
        max_faceted_triangles=10_000,
        step_timeout_seconds=600,
        max_csg_triangles=100_000,
    )
    if int(converted_step.get("source_mesh_triangle_count", -1)) != 0:
        raise RuntimeError(f"STEP still saw mesh remnants after XBF conversion: {converted_step}")

    csg_path = exact_project / exact_reports["csg"]["relative_path"]
    csg_report_path = root / "freecad-csg-validation.json"
    validator = Path(__file__).with_name("freecad_validate_csg.py")
    env = os.environ.copy()
    env.setdefault("HOME", str(root))
    env.setdefault("XDG_CONFIG_HOME", str(root / ".config"))
    (root / ".config").mkdir(exist_ok=True)
    env.update(
        {
            "CASCADE_CAD_FREECAD_SCRIPT": str(validator),
            "CASCADE_CAD_CSG_VALIDATE_FILE": str(csg_path),
            "CASCADE_CAD_CSG_VALIDATE_EXPECTED": str(exact_reports["csg"]["part_count"]),
            "CASCADE_CAD_CSG_VALIDATE_REPORT": str(csg_report_path),
        }
    )
    runner = (
        "import os, runpy\n"
        "runpy.run_path(os.environ['CASCADE_CAD_FREECAD_SCRIPT'], run_name='__main__')\n"
    )
    result = subprocess.run(
        [_freecad_command(), "--console"],
        cwd=str(root),
        env=env,
        input=runner,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FreeCAD CSG part validation failed: {result.stdout[-3000:]}")
    csg_validation = json.loads(csg_report_path.read_text(encoding="utf-8"))
    if int(csg_validation.get("valid_solid_object_count", 0)) < int(exact_reports["csg"]["part_count"]):
        raise RuntimeError(f"FreeCAD did not reconstruct every CSG polyhedron as a valid solid: {csg_validation}")

    print(
        "CascadeCAD unified export smoke test: OK "
        f"(BREP solids={mesh_reports['brep']['solid_count']}, "
        f"FCStd solids={mesh_reports['fcstd']['solid_count']}, "
        f"CSG solids={csg_validation['valid_solid_object_count']}, faceted XBF triangles after={conversion['mesh_triangle_count_after']})"
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    args = parser.parse_args()
    run(Path(args.output).resolve())


if __name__ == "__main__":
    main()
