from __future__ import annotations

import argparse
from pathlib import Path


def build_sample(output_dir: Path) -> dict[str, Path]:
    import cadquery as cq
    import numpy as np
    import trimesh

    from .geometry import _mesh_to_cq_shape

    output_dir.mkdir(parents=True, exist_ok=True)

    # Exact B-rep XBF round trip.
    assembly = cq.Assembly(name="sample_truck_parts")
    chassis = cq.Workplane("XY").box(120, 45, 8)
    cab = cq.Workplane("XY").box(38, 42, 38).translate((-25, 0, 23))
    wheel = cq.Workplane("YZ").circle(10).extrude(6)
    assembly.add(chassis, name="chassis", color=cq.Color("gray"))
    assembly.add(cab, name="cab", color=cq.Color("blue"))
    assembly.add(wheel.translate((-42, -26, -7)), name="wheel_fl", color=cq.Color("black"))
    assembly.add(wheel.translate((-42, 20, -7)), name="wheel_fr", color=cq.Color("black"))
    assembly.add(wheel.translate((35, -26, -7)), name="wheel_rl", color=cq.Color("black"))
    assembly.add(wheel.translate((35, 20, -7)), name="wheel_rr", color=cq.Color("black"))
    xbf = output_dir / "sample-truck.xbf"
    step = output_dir / "sample-truck.step"
    glb = output_dir / "sample-truck.glb"
    assembly.export(str(xbf), "XBF")
    reopened = cq.Assembly.load(str(xbf), importType="XBF")
    reopened.export(str(step), "STEP")
    reopened.export(str(glb), "GLB", tolerance=1.0, angularTolerance=0.3)
    if not xbf.exists() or xbf.stat().st_size < 100:
        raise RuntimeError("Exact XBF smoke test did not produce a valid file")

    # Mesh-presentation XBF round trip. This tests the front-page mesh converter.
    vertices = np.array(
        [[0, 0, 0], [20, 0, 0], [0, 20, 0], [0, 0, 20]], dtype=float
    )
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]], dtype=int)
    tetra = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh_assembly = cq.Assembly(name="mesh_sample")
    mesh_assembly.add(_mesh_to_cq_shape(tetra), name="tetra_mesh")
    mesh_xbf = output_dir / "sample-mesh.xbf"
    mesh_assembly.export(str(mesh_xbf), "XBF")
    mesh_reopened = cq.Assembly.load(str(mesh_xbf), importType="XBF")
    if not any(child.shapes for _, child in mesh_reopened.traverse()):
        raise RuntimeError("Mesh XBF reopened without any shapes")
    if mesh_xbf.stat().st_size < 100:
        raise RuntimeError("Mesh XBF smoke test did not produce a valid file")

    return {"xbf": xbf, "step": step, "glb": glb, "mesh_xbf": mesh_xbf}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and verify small exact and mesh XBF samples")
    parser.add_argument("output", nargs="?", default="./sample-output")
    args = parser.parse_args()
    paths = build_sample(Path(args.output).resolve())
    for kind, path in paths.items():
        print(f"{kind.upper()}: {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
