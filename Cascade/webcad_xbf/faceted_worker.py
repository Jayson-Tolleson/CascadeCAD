from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np


def _shape_on_mesh(vertices: np.ndarray, triangles: np.ndarray):
    """Build a per-facet B-rep shape directly from indexed mesh data."""
    import cadquery as cq
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeShapeOnMesh
    from OCP.Poly import Poly_MeshPurpose_Presentation, Poly_Triangle, Poly_Triangulation
    from OCP.gp import gp_Pnt

    triangulation = Poly_Triangulation(int(vertices.shape[0]), int(triangles.shape[0]), False, True)
    for index, vertex in enumerate(vertices, start=1):
        triangulation.SetNode(index, gp_Pnt(float(vertex[0]), float(vertex[1]), float(vertex[2])))
    for index, triangle in enumerate(triangles, start=1):
        triangulation.SetTriangle(
            index,
            Poly_Triangle(int(triangle[0]) + 1, int(triangle[1]) + 1, int(triangle[2]) + 1),
        )
    triangulation.SetMeshPurpose(Poly_MeshPurpose_Presentation)
    try:
        triangulation.ComputeNormals()
    except Exception:
        pass

    maker = BRepBuilderAPI_MakeShapeOnMesh(triangulation)
    maker.Build()
    if not maker.IsDone():
        raise RuntimeError("BRepBuilderAPI_MakeShapeOnMesh did not complete")
    result = cq.Shape.cast(maker.Shape())
    if result.isNull() or not result.Faces():
        raise RuntimeError("Direct OCP mesh conversion produced no B-rep faces")
    return result


def _try_fast_sewing(shape, tolerance: float) -> tuple[Any, bool, str | None]:
    """Run FastSewing when requested, retaining the direct shape on any defect."""
    import cadquery as cq
    from OCP.BRepBuilderAPI import BRepBuilderAPI_FastSewing

    try:
        sewing = BRepBuilderAPI_FastSewing(float(tolerance))
        accepted = False
        # Add faces separately. This is more portable across OCP builds than
        # relying on FastSewing to unpack an arbitrary compound automatically.
        for face in shape.Faces():
            accepted = bool(sewing.Add(face.wrapped)) or accepted
        if not accepted:
            return shape, False, "FastSewing rejected every generated facet"
        sewing.Perform()
        candidate = cq.Shape.cast(sewing.GetResult())
        if candidate.isNull() or not candidate.Faces() or not candidate.isValid():
            return shape, False, "FastSewing result was empty or invalid; direct shared-edge shape retained"
        return candidate, True, None
    except Exception as exc:
        return shape, False, f"FastSewing fallback: {exc}"


def _try_standard_sewing(shape, tolerance: float) -> tuple[Any, bool, str | None]:
    """Build shell containers when MakeShapeOnMesh returns only loose faces."""
    import cadquery as cq
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing

    try:
        sewing = BRepBuilderAPI_Sewing(float(tolerance), True, True, True, False)
        for face in shape.Faces():
            sewing.Add(face.wrapped)
        sewing.Perform()
        candidate = cq.Shape.cast(sewing.SewedShape())
        if candidate.isNull() or not candidate.Faces() or not candidate.Shells() or not candidate.isValid():
            return shape, False, "Standard sewing did not produce a valid shell container"
        return candidate, True, None
    except Exception as exc:
        return shape, False, f"Standard sewing fallback: {exc}"


def _solidify_shells(shape, tolerance: float):
    """Turn closed shells into solids while retaining all unavoidable open shells."""
    import cadquery as cq
    from OCP.BRep import BRep_Tool

    warnings: list[str] = []
    standard_sewing_used = False
    shells = list(shape.Shells())
    if not shells:
        shape, standard_sewing_used, warning = _try_standard_sewing(shape, tolerance)
        if warning:
            warnings.append(warning)
        shells = list(shape.Shells())
    if not shells:
        warnings.append("Generated facet shape contained no shell container; faces were retained")
        return shape, 0, 1, warnings, standard_sewing_used

    converted = []
    solid_count = 0
    open_shell_count = 0
    for index, shell in enumerate(shells, start=1):
        is_closed = bool(BRep_Tool.IsClosed_s(shell.wrapped))
        if is_closed:
            try:
                solid = cq.Solid.makeSolid(shell)
                if solid.isNull() or not solid.isValid() or not solid.Solids():
                    raise RuntimeError("solid validation failed")
                converted.append(solid)
                solid_count += max(1, len(solid.Solids()))
                continue
            except Exception as exc:
                warnings.append(f"Closed shell {index} could not become a solid and was retained: {exc}")
        converted.append(shell)
        open_shell_count += 1

    if len(converted) == 1:
        result = converted[0]
    else:
        result = cq.Compound.makeCompound(converted)
    if result.isNull() or not result.Faces():
        raise RuntimeError("Shell conversion produced no usable Part geometry")
    return result, solid_count, open_shell_count, warnings, standard_sewing_used


def _try_unify_same_domain(shape) -> tuple[Any, bool, str | None]:
    """Merge truly same-domain neighboring faces when the result remains valid."""
    import cadquery as cq
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    try:
        unifier = ShapeUpgrade_UnifySameDomain(shape.wrapped, True, True, False)
        unifier.Build()
        candidate = cq.Shape.cast(unifier.Shape())
        if candidate.isNull() or not candidate.Faces() or not candidate.isValid():
            return shape, False, "Same-domain unification returned invalid geometry; original facets retained"
        return candidate, True, None
    except Exception as exc:
        return shape, False, f"Same-domain unification skipped: {exc}"


def build_faceted_brep(
    input_path: Path,
    output_path: Path,
    *,
    tolerance: float = 0.05,
    fast_sewing: bool = False,
    unify_same_domain: bool = True,
) -> dict[str, Any]:
    """Convert an indexed triangle array into validated faceted B-rep geometry."""
    import cadquery as cq
    from OCP.BRepTools import BRepTools

    started = time.monotonic()
    with np.load(input_path, allow_pickle=False) as payload:
        vertices = np.asarray(payload["vertices"], dtype=np.float64)
        triangles = np.asarray(payload["triangles"], dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices):
        raise ValueError("Mesh vertex array must be non-empty Nx3 data")
    if triangles.ndim != 2 or triangles.shape[1] != 3 or not len(triangles):
        raise ValueError("Mesh triangle array must be non-empty Nx3 data")
    if int(triangles.min()) < 0 or int(triangles.max()) >= int(vertices.shape[0]):
        raise ValueError("Mesh triangle indices are outside the vertex array")

    warnings: list[str] = []
    shape = _shape_on_mesh(vertices, triangles)
    fast_used = False
    if fast_sewing:
        shape, fast_used, warning = _try_fast_sewing(shape, tolerance)
        if warning:
            warnings.append(warning)

    shape, solid_count, open_shell_count, shell_warnings, standard_sewing_used = _solidify_shells(
        shape, tolerance
    )
    warnings.extend(shell_warnings)

    unified = False
    if unify_same_domain:
        shape, unified, warning = _try_unify_same_domain(shape)
        if warning:
            warnings.append(warning)

    if shape.isNull() or not shape.Faces() or not shape.isValid():
        raise RuntimeError("Final faceted B-rep validation failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    ok = BRepTools.Write_s(shape.wrapped, str(temporary))
    if ok is False or not temporary.exists() or temporary.stat().st_size < 100:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Could not write converted OCP BREP component")
    os.replace(temporary, output_path)

    status = "faceted-solid"
    if solid_count and open_shell_count:
        status = "faceted-mixed-solid-shell"
    elif not solid_count:
        status = "faceted-shell"
    elapsed = max(0.000001, time.monotonic() - started)
    return {
        "backend": "BRepBuilderAPI_MakeShapeOnMesh",
        "representation": status,
        "triangle_count": int(triangles.shape[0]),
        "vertex_count": int(vertices.shape[0]),
        "solid_count": int(solid_count),
        "faceted_open_shell_count": int(open_shell_count),
        "fast_sewing_requested": bool(fast_sewing),
        "fast_sewing_used": bool(fast_used),
        "standard_sewing_used": bool(standard_sewing_used),
        "same_domain_unified": bool(unified),
        "face_count": len(shape.Faces()),
        "shell_count": len(shape.Shells()),
        "elapsed_seconds": elapsed,
        "triangles_per_second": int(round(int(triangles.shape[0]) / elapsed)),
        "file_size": output_path.stat().st_size,
        "warnings": warnings,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert indexed mesh arrays to faceted OCP BREP")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--tolerance", type=float, default=0.05)
    parser.add_argument("--fast-sewing", action="store_true")
    parser.add_argument("--no-unify-same-domain", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = build_faceted_brep(
            Path(args.input),
            Path(args.output),
            tolerance=float(args.tolerance),
            fast_sewing=bool(args.fast_sewing),
            unify_same_domain=not bool(args.no_unify_same_domain),
        )
        report["failed"] = False
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        report_path.write_text(
            json.dumps({"failed": True, "error": f"{type(exc).__name__}: {exc}"}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
