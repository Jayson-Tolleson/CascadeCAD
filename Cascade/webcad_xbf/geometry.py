from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from .mesh_cleanup import clean_mesh_source

Progress = Callable[[int, str], None]
CancelCheck = Callable[[], bool]


class GeometryJobCancelled(RuntimeError):
    """Raised when a long-running geometry export is cancelled cooperatively."""


def _check_long_job(
    should_cancel: CancelCheck | None,
    deadline: float | None,
    operation: str,
) -> None:
    if should_cancel is not None and should_cancel():
        raise GeometryJobCancelled(f"{operation} cancelled")
    if deadline is not None and time.monotonic() > deadline:
        raise TimeoutError(f"{operation} exceeded the configured time limit")


def _format_eta(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        return "estimating"
    value = int(round(seconds))
    if value < 60:
        return f"{value}s"
    minutes, seconds = divmod(value, 60)
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"

EXACT_EXTENSIONS = {".step", ".stp", ".xbf", ".fcstd"}
MESH_EXTENSIONS = {".stl", ".obj", ".glb", ".gltf", ".ply", ".3mf"}


def source_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in EXACT_EXTENSIONS:
        return "exact"
    if suffix in MESH_EXTENSIONS:
        return "mesh"
    raise ValueError(f"Unsupported file type: {suffix}")


def _safe_component_name(name: str, index: int) -> str:
    value = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name).strip("._")
    return value[:100] or f"mesh_{index:04d}"


def _mesh_scene(path: Path):
    import trimesh

    loaded = trimesh.load(path, force="scene", process=False)
    if isinstance(loaded, trimesh.Trimesh):
        scene = trimesh.Scene()
        scene.add_geometry(loaded, node_name=path.stem, geom_name=path.stem)
        return scene
    if not isinstance(loaded, trimesh.Scene):
        raise ValueError("The mesh loader did not return a mesh scene")
    if not loaded.geometry:
        raise ValueError("The uploaded mesh contains no geometry")
    return loaded


def _iter_scene_meshes(scene):
    seen = 0
    for node_name in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node_name]
        source = scene.geometry[geometry_name]
        mesh = source.copy()
        mesh.apply_transform(transform)
        seen += 1
        yield _safe_component_name(str(node_name or geometry_name), seen), mesh
    if seen == 0:
        for geometry_name, source in scene.geometry.items():
            seen += 1
            yield _safe_component_name(str(geometry_name), seen), source.copy()


def _mesh_to_cq_shape(mesh):
    """Create one OCCT face carrying a Poly_Triangulation presentation."""
    import cadquery as cq
    from OCP.BRep import BRep_Builder
    from OCP.Poly import Poly_MeshPurpose_Presentation, Poly_Triangle, Poly_Triangulation
    from OCP.TopoDS import TopoDS_Face
    from OCP.gp import gp_Pnt

    vertices = mesh.vertices
    faces = mesh.faces
    if len(vertices) == 0 or len(faces) == 0:
        raise ValueError("Mesh component is empty")
    triangulation = Poly_Triangulation(len(vertices), len(faces), False, True)
    for index, vertex in enumerate(vertices, start=1):
        triangulation.SetNode(index, gp_Pnt(float(vertex[0]), float(vertex[1]), float(vertex[2])))
    for index, face_indices in enumerate(faces, start=1):
        a, b, c = (int(value) + 1 for value in face_indices)
        triangulation.SetTriangle(index, Poly_Triangle(a, b, c))
    triangulation.SetMeshPurpose(Poly_MeshPurpose_Presentation)
    try:
        triangulation.ComputeNormals()
    except Exception:
        pass
    occt_face = TopoDS_Face()
    BRep_Builder().MakeFace(occt_face, triangulation)
    return cq.Shape.cast(occt_face)


def _loc_dict(location) -> dict[str, list[float]]:
    try:
        position, rotation = location.toTuple()
    except Exception:
        position, rotation = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return {
        "position": [float(v) for v in position],
        "rotation": [float(v) for v in rotation],
    }


def _material_density_kg_m3(material) -> float:
    if material is None:
        return 0.0
    try:
        value = float(material.density)
        unit = str(material.densityUnit or "").lower().replace(" ", "")
    except Exception:
        return 0.0
    if "g/cm" in unit or "gcm" in unit:
        return value * 1000.0
    if "kg/m" in unit or "kgm" in unit:
        return value
    return value


def _component_material(child) -> dict[str, Any]:
    color = "#b8c1cc"
    try:
        if child.color is not None:
            r, g, b, _a = child.color.toTuple()
            color = "#{:02x}{:02x}{:02x}".format(
                max(0, min(255, round(r * 255))),
                max(0, min(255, round(g * 255))),
                max(0, min(255, round(b * 255))),
            )
    except Exception:
        pass
    material = getattr(child, "material", None)
    try:
        name = str(material.name) if material is not None else "Unassigned"
        description = str(material.description) if material is not None else ""
    except Exception:
        name, description = "Unassigned", ""
    metadata = getattr(child, "metadata", {}) or {}
    stored = metadata.get("cascadecad_material") if isinstance(metadata, dict) else None
    if isinstance(stored, dict):
        name = str(stored.get("name") or name)
        description = str(stored.get("description") or description)
        color = str(stored.get("color") or color)
        density = float(stored.get("density_kg_m3", _material_density_kg_m3(material)) or 0.0)
    else:
        density = _material_density_kg_m3(material)
    return {
        "name": name or "Unassigned",
        "density_kg_m3": density,
        "color": color,
        "description": description,
    }

def _assembly_components(assembly, default_kind: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root_name = str(assembly.name)
    for name, child in assembly.objects.items():
        clean_name = str(name or "component")
        if clean_name == root_name and child is assembly:
            continue
        shapes = list(child.shapes)
        bbox = None
        shape_type = None
        try:
            if shapes:
                box = shapes[0].BoundingBox()
                shape_type = str(shapes[0].ShapeType())
            else:
                # Subassembly wrapper nodes do not own a direct shape, but they
                # need an aggregate bounding box so browser transforms preserve
                # the correct CAD-unit scale when an entire project is moved.
                box = child.toCompound().BoundingBox()
                shape_type = "Assembly"
            bbox = {
                "min": [float(box.xmin), float(box.ymin), float(box.zmin)],
                "max": [float(box.xmax), float(box.ymax), float(box.zmax)],
            }
        except Exception:
            pass
        # CadQuery uses slash-delimited keys for nested assembly objects. Keep
        # that full path as the stable editor identifier, while showing the
        # child node's human-readable leaf name in the tree.
        parent_name = clean_name.rsplit("/", 1)[0] if "/" in clean_name else None
        display_name = str(getattr(child, "name", None) or clean_name.rsplit("/", 1)[-1])
        transform = _loc_dict(child.loc)
        transform["scale"] = [1.0, 1.0, 1.0]
        rows.append(
            {
                "id": clean_name,
                "name": display_name,
                "source_id": clean_name,
                "parent": parent_name,
                "kind": default_kind,
                "shape_type": shape_type,
                "bbox": bbox,
                "transform": transform,
                "material": _component_material(child),
                "visible": True,
                "editable": child.parent is not None,
                "deleted": False,
                "duplicate": False,
            }
        )
    return rows


def mesh_to_assembly(path: Path, progress: Progress):
    import cadquery as cq

    progress(15, "Reading mesh scene")
    scene = _mesh_scene(path)
    assembly = cq.Assembly(name=path.stem)
    triangle_counts: dict[str, tuple[int, int]] = {}
    total = max(1, len(list(scene.graph.nodes_geometry)) or len(scene.geometry))
    for index, (name, mesh) in enumerate(_iter_scene_meshes(scene), start=1):
        progress(15 + math.floor(50 * index / total), f"Packing mesh {index} of {total}")
        shape = _mesh_to_cq_shape(mesh)
        assembly.add(shape, name=name)
        triangle_counts[name] = (int(len(mesh.faces)), int(len(mesh.vertices)))
    components = _assembly_components(assembly, "mesh")
    for component in components:
        counts = triangle_counts.get(component["id"])
        if counts:
            component["triangles"], component["vertices"] = counts
    return assembly, scene, components



def _fcstd_to_assembly(path: Path, project_dir: Path, progress: Progress):
    """Extract final exact FreeCAD shapes into a CadQuery assembly.

    FreeCAD runs in its own console process so optional workbenches, malformed
    documents, or recompute failures cannot contaminate the long-lived Quart
    or CascadeCAD worker process. The original FCStd remains in project/source.
    """
    import cadquery as cq

    helper = Path(__file__).resolve().parents[1] / "scripts" / "freecad_import_fcstd.py"
    if not helper.exists():
        raise RuntimeError("CascadeCAD FCStd import helper is missing")

    temp_root = project_dir / ".fcstd-import"
    temp_root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="job-", dir=temp_root))
    manifest_path = work_dir / "manifest.json"
    log_path = work_dir / "freecad-import.log"
    storage_root = project_dir.parents[1]
    config_home = storage_root / ".config"
    config_home.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update({
        "HOME": str(storage_root),
        "XDG_CONFIG_HOME": str(config_home),
        "FREECAD_USER_HOME": str(storage_root),
        "CASCADE_CAD_FCSTD_SOURCE": str(path),
        "CASCADE_CAD_FCSTD_OUTPUT_DIR": str(work_dir),
        "CASCADE_CAD_FCSTD_MANIFEST": str(manifest_path),
        "CASCADE_CAD_FCSTD_RECOMPUTE": env.get("CASCADE_CAD_FCSTD_RECOMPUTE", "1"),
        "CASCADE_CAD_FCSTD_INCLUDE_HIDDEN": env.get("CASCADE_CAD_FCSTD_INCLUDE_HIDDEN", "0"),
    })
    runner = (
        "import os, runpy\n"
        f"runpy.run_path({str(helper)!r}, run_name='__main__')\n"
    )
    timeout = max(60, int(os.getenv("CASCADE_CAD_FCSTD_IMPORT_TIMEOUT_SECONDS", "3600")))
    progress(10, "Opening FreeCAD document")
    try:
        with log_path.open("w", encoding="utf-8") as log_handle:
            completed = subprocess.run(
                [_freecad_command(), "--console"],
                input=runner,
                text=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                cwd=str(work_dir),
                env=env,
                timeout=timeout,
                check=False,
            )
        if completed.returncode != 0 or not manifest_path.exists():
            tail = log_path.read_text(encoding="utf-8", errors="ignore")[-4000:] if log_path.exists() else ""
            raise RuntimeError(
                "FreeCAD could not extract this FCStd document"
                + (f": {tail.strip()}" if tail.strip() else "")
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = list(manifest.get("items") or [])
        if not items:
            warnings = "; ".join(str(v) for v in manifest.get("warnings") or [])
            raise ValueError("The FCStd document contains no importable exact shapes" + (f" ({warnings})" if warnings else ""))

        assembly = cq.Assembly(name=path.stem)
        metadata_by_name: dict[str, dict[str, Any]] = {}
        total = len(items)
        for index, item in enumerate(items, start=1):
            progress(18 + math.floor(35 * index / max(1, total)), f"Importing FreeCAD part {index} of {total}")
            brep_path = Path(str(item.get("brep_path") or ""))
            if not brep_path.exists():
                raise RuntimeError(f"FreeCAD did not create BREP for {item.get('label') or item.get('name') or index}")
            shape = cq.Shape.importBrep(str(brep_path))
            name = _safe_component_name(str(item.get("component_id") or item.get("name") or item.get("label") or f"part_{index}"), index)
            color_hex = str(item.get("color") or "#b8c1cc")
            color = None
            try:
                color = cq.Color(
                    int(color_hex[1:3], 16) / 255.0,
                    int(color_hex[3:5], 16) / 255.0,
                    int(color_hex[5:7], 16) / 255.0,
                    1.0,
                )
            except Exception:
                pass
            assembly.add(shape, name=name, color=color)
            metadata_by_name[name] = item

        components = _assembly_components(assembly, "exact")
        for component in components:
            item = metadata_by_name.get(component["id"], {})
            component["name"] = str(item.get("label") or component["name"])
            component["source_id"] = str(item.get("name") or component["source_id"])
            component["freecad"] = {
                "name": item.get("name"),
                "label": item.get("label"),
                "type_id": item.get("type_id"),
                "document": path.name,
                "properties": item.get("properties") or {},
            }
            component["visible"] = bool(item.get("visible", True))
            component["material"] = {
                "name": str(item.get("material_name") or "Unassigned"),
                "density_kg_m3": float(item.get("density_kg_m3") or 0.0),
                "color": str(item.get("color") or "#b8c1cc"),
                "description": str(item.get("material_description") or "Imported from FreeCAD"),
            }
        return assembly, components, manifest
    finally:
        # Keep the log and manifest only when extraction failed; successful
        # imports no longer need their intermediate BREP files.
        if manifest_path.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        try:
            temp_root.rmdir()
        except OSError:
            pass

def _atomic_export(assembly, destination: Path, export_type: str, **kwargs: Any) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(f".{destination.stem}.{time.time_ns()}.tmp{destination.suffix}")
    assembly.export(str(temp), export_type, **kwargs)
    os.replace(temp, destination)


def import_project(
    source: Path,
    project_dir: Path,
    preview_tolerance: float,
    preview_angular_tolerance: float,
    progress: Progress,
    cleanup_mesh: bool = False,
) -> dict[str, Any]:
    import cadquery as cq

    kind = source_kind(source)
    cleanup_report = None
    import_source = source
    if kind == "mesh" and cleanup_mesh:
        progress(3, "Starting exact mesh cleanup")
        import_source, cleanup_report = clean_mesh_source(source, project_dir, progress)
    master = project_dir / "master.xbf"
    preview = project_dir / "previews" / "overview.glb"
    if kind == "mesh":
        assembly, scene, components = mesh_to_assembly(import_source, progress)
        progress(70, "Writing binary XBF mesh container")
        _atomic_export(assembly, master, "XBF")
        progress(84, "Writing browser GLB preview")
        temp = preview.with_name(f".{preview.stem}.{time.time_ns()}.tmp.glb")
        scene.export(str(temp), file_type="glb")
        os.replace(temp, preview)
        geometry_kind = "mesh"
        if import_source != source:
            import_source.unlink(missing_ok=True)
    else:
        suffix = source.suffix.lower()
        fcstd_report = None
        if suffix == ".fcstd":
            assembly, components, fcstd_report = _fcstd_to_assembly(source, project_dir, progress)
            geometry_kind = "exact"
        else:
            progress(12, f"Reading {source.suffix.upper()} assembly")
            import_type = "STEP" if suffix in {".step", ".stp"} else "XBF"
            assembly = cq.Assembly.load(str(source), importType=import_type)
            geometry_kind = "exact" if import_type == "STEP" else "unknown"
            components = _assembly_components(assembly, geometry_kind)
        progress(55, "Writing compact binary XBF master")
        _atomic_export(assembly, master, "XBF")
        progress(72, "Generating browser GLB preview")
        _atomic_export(
            assembly,
            preview,
            "GLB",
            tolerance=preview_tolerance,
            angularTolerance=preview_angular_tolerance,
        )
    progress(95, "Finalizing project")
    return {
        "source_kind": kind,
        "geometry_kind": geometry_kind,
        "master_xbf": "master.xbf",
        "preview_glb": "previews/overview.glb",
        "components": components,
        "mesh_cleanup": cleanup_report,
        "fcstd_import": fcstd_report if kind == "exact" and source.suffix.lower() == ".fcstd" else None,
        "cleaned_source": None,
        "message": "Project ready",
    }


def _cad_location(transform: dict[str, Any]):
    import cadquery as cq

    position = transform.get("position", [0.0, 0.0, 0.0])
    rotation = transform.get("rotation", [0.0, 0.0, 0.0])
    return cq.Location(
        float(position[0]), float(position[1]), float(position[2]),
        float(rotation[0]), float(rotation[1]), float(rotation[2]),
    )


def _scaled_shape(shape, scale: list[float]):
    import cadquery as cq

    sx, sy, sz = (float(value) for value in scale)
    if abs(sx - 1.0) < 1.0e-12 and abs(sy - 1.0) < 1.0e-12 and abs(sz - 1.0) < 1.0e-12:
        return shape
    if abs(sx - sy) < 1.0e-12 and abs(sx - sz) < 1.0e-12:
        return shape.scale(sx)
    matrix = cq.Matrix([
        [sx, 0.0, 0.0, 0.0],
        [0.0, sy, 0.0, 0.0],
        [0.0, 0.0, sz, 0.0],
    ])
    return shape.transformGeometry(matrix)


def _apply_component_appearance(child, record: dict[str, Any]) -> None:
    import cadquery as cq

    material = record.get("material") if isinstance(record.get("material"), dict) else {}
    color = str(material.get("color") or "#b8c1cc")
    density = float(material.get("density_kg_m3", 0.0) or 0.0)
    name = str(material.get("name") or "Unassigned")
    description = str(material.get("description") or "")
    try:
        child.color = cq.Color(color)
    except Exception:
        pass
    try:
        child.material = cq.Material(
            name, description=description, density=density, densityUnit="kg/m^3"
        )
    except Exception:
        pass
    try:
        child.metadata = dict(getattr(child, "metadata", {}) or {})
        child.metadata["cascadecad_material"] = {
            "name": name,
            "density_kg_m3": density,
            "color": color,
            "description": description,
        }
    except Exception:
        pass


def apply_editor_state(assembly, editor_state: dict[str, Any]):
    records: dict[str, dict[str, Any]] = editor_state.get("components", {})
    root_name = str(assembly.name)
    templates = {name: child._copy() for name, child in assembly.objects.items() if name != root_name}

    # Apply transforms and persistent appearance before deletions so templates
    # retain the original geometry for duplicates. Scale is baked into exact
    # leaf geometry on commit; translation and rotation remain placements.
    for component_id, record in records.items():
        if record.get("duplicate") or record.get("deleted"):
            continue
        target = assembly.objects.get(component_id)
        if target is not None:
            transform = record.get("transform", {})
            scale = list(transform.get("scale", [1.0, 1.0, 1.0]))
            if any(abs(float(value) - 1.0) > 1.0e-12 for value in scale):
                if getattr(target, "children", None):
                    raise ValueError("Scale individual leaf parts rather than an assembly wrapper")
                shape = target.toCompound()
                if shape is None:
                    raise ValueError(f"Component has no shape to scale: {component_id}")
                target.obj = _scaled_shape(shape, scale)
            target.loc = _cad_location(transform)
            _apply_component_appearance(target, record)

    # Removing a parent removes descendants. Missing descendants are therefore skipped.
    for component_id, record in list(records.items()):
        if record.get("duplicate") or not record.get("deleted"):
            continue
        if component_id in assembly.objects:
            assembly.remove(component_id)

    # Materialize working duplicates as real assembly instances.
    for component_id, record in records.items():
        if not record.get("duplicate") or record.get("deleted"):
            continue
        source_id = str(record.get("source_id") or "")
        source = templates.get(source_id)
        if source is None:
            raise ValueError(f"Duplicate source is missing: {source_id}")
        parent_id = record.get("parent")
        parent = assembly if not parent_id else assembly.objects.get(str(parent_id))
        if parent is None:
            raise ValueError(f"Duplicate parent is missing: {parent_id}")
        duplicate = source._copy()
        transform = record.get("transform", {})
        scale = list(transform.get("scale", [1.0, 1.0, 1.0]))
        if any(abs(float(value) - 1.0) > 1.0e-12 for value in scale):
            if getattr(duplicate, "children", None):
                raise ValueError("Scale individual duplicate parts rather than an assembly wrapper")
            shape = duplicate.toCompound()
            if shape is None:
                raise ValueError(f"Duplicate source has no shape: {source_id}")
            duplicate.obj = _scaled_shape(shape, scale)
        duplicate.name = component_id
        duplicate.loc = _cad_location(transform)
        _apply_component_appearance(duplicate, record)
        parent.add(duplicate, name=component_id, loc=duplicate.loc)
    return assembly


def _snapshot(project_dir: Path, note: str) -> str:
    revision_id = f"rev_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000:06d}"
    destination = project_dir / "revisions" / revision_id
    destination.mkdir(parents=True, exist_ok=False)
    for relative in ("master.xbf", "previews/overview.glb"):
        source = project_dir / relative
        if source.exists():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            # Masters and previews are replaced atomically after a snapshot.
            # A hard link therefore preserves the exact old inode without
            # copying a multi-gigabyte file; cross-filesystem and unsupported
            # filesystems fall back to the original safe copy behavior.
            try:
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)
    (destination / "note.txt").write_text(note + "\n", encoding="utf-8")
    return revision_id


def commit_editor(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any],
    preview_tolerance: float,
    preview_angular_tolerance: float,
    progress: Progress,
) -> dict[str, Any]:
    import cadquery as cq

    master = project_dir / "master.xbf"
    preview = project_dir / "previews" / "overview.glb"
    if not master.exists():
        raise FileNotFoundError("Project master.xbf is missing")
    progress(12, "Opening XBF master")
    assembly = cq.Assembly.load(str(master), importType="XBF")
    progress(30, "Applying editor transforms and component changes")
    apply_editor_state(assembly, editor_state)
    progress(48, "Creating revision snapshot")
    revision_id = _snapshot(project_dir, "Before editor commit")
    progress(58, "Writing edited XBF master")
    _atomic_export(assembly, master, "XBF")
    progress(76, "Regenerating browser preview")
    _atomic_export(
        assembly,
        preview,
        "GLB",
        tolerance=preview_tolerance,
        angularTolerance=preview_angular_tolerance,
    )
    progress(94, "Refreshing assembly metadata")
    return {
        "components": _assembly_components(assembly, geometry_kind),
        "revision_id": revision_id,
        "message": "Editor changes committed to XBF",
    }



def _combined_geometry_kind(kinds: list[str]) -> str:
    normalized = {str(kind or "unknown").lower() for kind in kinds}
    if "mixed" in normalized:
        return "mixed"
    if "mesh" in normalized:
        return "mesh" if normalized <= {"mesh"} else "mixed"
    if normalized <= {"exact"}:
        return "exact"
    return "unknown"


def _unique_subassembly_name(assembly, requested: str) -> str:
    base = _safe_component_name(requested, 1)[:80] or "project"
    candidate = base
    index = 2
    while candidate in assembly.objects:
        candidate = f"{base}_{index}"
        index += 1
    return candidate


def combine_projects(
    project_dir: Path,
    target_geometry_kind: str,
    target_editor_state: dict[str, Any],
    sources: list[dict[str, Any]],
    preview_tolerance: float,
    preview_angular_tolerance: float,
    progress: Progress,
) -> dict[str, Any]:
    """Add one or more project XBF assemblies as selectable subassemblies.

    Source projects are read-only. The target project receives a revision
    snapshot, the combined XBF, and a regenerated GLB preview. Each imported
    project is wrapped by a unique top-level assembly node so it can be moved
    or rotated as a unit in the editor.
    """
    import cadquery as cq

    if not sources:
        raise ValueError("Select at least one project to combine")
    master = project_dir / "master.xbf"
    preview = project_dir / "previews" / "overview.glb"
    if not master.exists():
        raise FileNotFoundError("Target project master.xbf is missing")

    progress(8, "Opening target master.xbf")
    assembly = cq.Assembly.load(str(master), importType="XBF")
    apply_editor_state(assembly, target_editor_state)

    combined = []
    total = len(sources)
    for index, source in enumerate(sources, start=1):
        source_master = Path(source["master_path"])
        if not source_master.exists():
            raise FileNotFoundError(f"Source master.xbf is missing: {source.get('name', source_master)}")
        progress(12 + int(38 * index / total), f"Adding project {index} of {total}: {source['name']}")
        source_assembly = cq.Assembly.load(str(source_master), importType="XBF")
        source_state = source.get("editor_state")
        if source_state:
            apply_editor_state(source_assembly, source_state)
        wrapper = _unique_subassembly_name(
            assembly,
            f"project_{source.get('name') or source.get('project_id')}",
        )
        assembly.add(source_assembly, name=wrapper)
        combined.append(
            {
                "project_id": source["project_id"],
                "name": source["name"],
                "assembly_node": wrapper,
                "geometry_kind": source.get("geometry_kind") or "unknown",
            }
        )

    progress(55, "Creating revision snapshot")
    revision_id = _snapshot(project_dir, "Before combining projects")
    progress(64, "Writing combined master.xbf")
    _atomic_export(assembly, master, "XBF")
    progress(80, "Generating combined editable preview")
    _atomic_export(
        assembly,
        preview,
        "GLB",
        tolerance=preview_tolerance,
        angularTolerance=preview_angular_tolerance,
    )
    progress(94, "Refreshing combined assembly metadata")
    kinds = [target_geometry_kind] + [item.get("geometry_kind") or "unknown" for item in sources]
    return {
        "components": _assembly_components(assembly, _combined_geometry_kind(kinds)),
        "geometry_kind": _combined_geometry_kind(kinds),
        "combined_projects": combined,
        "revision_id": revision_id,
        "message": f"Combined {len(sources)} project{'s' if len(sources) != 1 else ''} into this assembly",
    }

def split_component(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any],
    component_id: str,
    preview_tolerance: float,
    preview_angular_tolerance: float,
    progress: Progress,
) -> dict[str, Any]:
    import cadquery as cq

    if geometry_kind in {"mesh", "mixed"}:
        raise ValueError("Split into exact solids is available only for B-rep components")
    master = project_dir / "master.xbf"
    preview = project_dir / "previews" / "overview.glb"
    progress(10, "Opening XBF master")
    assembly = cq.Assembly.load(str(master), importType="XBF")
    apply_editor_state(assembly, editor_state)
    target = assembly.objects.get(component_id)
    if target is None or target.parent is None:
        raise ValueError("The selected component cannot be split")
    solids = []
    for shape in target.shapes:
        try:
            solids.extend(shape.Solids())
        except Exception:
            pass
    if len(solids) < 2:
        raise ValueError("The selected component does not contain multiple solids")
    parent = target.parent
    loc = target.loc
    progress(40, f"Splitting component into {len(solids)} solids")
    assembly.remove(component_id)
    for index, solid in enumerate(solids, start=1):
        parent.add(solid, name=f"{component_id}_solid_{index:04d}", loc=loc)
    progress(55, "Creating revision snapshot")
    revision_id = _snapshot(project_dir, f"Before splitting {component_id}")
    progress(65, "Writing split XBF master")
    _atomic_export(assembly, master, "XBF")
    progress(82, "Regenerating browser preview")
    _atomic_export(
        assembly,
        preview,
        "GLB",
        tolerance=preview_tolerance,
        angularTolerance=preview_angular_tolerance,
    )
    return {
        "components": _assembly_components(assembly, geometry_kind),
        "revision_id": revision_id,
        "message": f"Split {component_id} into {len(solids)} solids",
    }


STEP_EXACT_ENTITIES = (
    "ADVANCED_FACE",
    "MANIFOLD_SOLID_BREP",
    "BREP_WITH_VOIDS",
    "FACETED_BREP",
    "SHELL_BASED_SURFACE_MODEL",
    "ADVANCED_BREP_SHAPE_REPRESENTATION",
)

STEP_TESSELLATED_ENTITIES = (
    "TESSELLATED_SHAPE_REPRESENTATION",
    "TESSELLATED_SHELL",
    "TESSELLATED_SOLID",
    "TRIANGULATED_FACE",
    "COMPLEX_TRIANGULATED_FACE",
    "CARTESIAN_POINT_LIST_3D",
)


def _step_entity_counts(path: Path) -> dict[str, int]:
    """Count geometry-bearing STEP entities without loading the file into RAM."""
    tokens = tuple(dict.fromkeys(STEP_EXACT_ENTITIES + STEP_TESSELLATED_ENTITIES + ("AP242",)))
    encoded = {token: token.encode("ascii") for token in tokens}
    counts = {token: 0 for token in tokens}
    with path.open("rb") as handle:
        for line in handle:
            upper = line.upper()
            for token, marker in encoded.items():
                counts[token] += upper.count(marker)
    return counts


def _step_report_preserves_mesh_source(report: dict[str, Any]) -> bool:
    """Return True when a STEP report contains geometry originating from mesh.

    Hard-speed conversion intentionally removes triangulation-only XBF faces
    before STEP is written.  The resulting AP242 file therefore contains
    ordinary B-rep entities rather than AP242 tessellated entities.  Validate
    the conversion provenance as well as legacy tessellated/fallback writers.
    """
    if int(report.get("tessellated_entity_count", 0) or 0) > 0:
        return True
    if (
        report.get("writer_mode") == "faceted-brep-fallback"
        and int(report.get("faceted_mesh_triangle_count", 0) or 0) > 0
        and int(report.get("exact_entity_count", 0) or 0) > 0
    ):
        return True
    conversion = report.get("faceted_conversion") or {}
    retained_part_geometry = (
        int(conversion.get("solid_count", 0) or 0)
        + int(conversion.get("faceted_open_shell_count", 0) or 0)
    )
    return bool(
        conversion.get("changed")
        and int(conversion.get("source_mesh_triangle_count", 0) or 0) > 0
        and int(conversion.get("converted_component_count", 0) or 0) > 0
        and int(conversion.get("mesh_triangle_count_after", -1)) == 0
        and retained_part_geometry > 0
        and int(report.get("exact_entity_count", 0) or 0) > 0
    )


def _validate_step_output(path: Path, source_shape_count: int) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError("STEP writer did not create an output file")
    size = path.stat().st_size
    if size < 1024:
        raise RuntimeError(f"STEP writer created an implausibly small file ({size} bytes)")
    counts = _step_entity_counts(path)
    exact_count = sum(counts[name] for name in STEP_EXACT_ENTITIES)
    tessellated_count = sum(counts[name] for name in STEP_TESSELLATED_ENTITIES)
    if exact_count + tessellated_count == 0:
        raise RuntimeError(
            "STEP writer produced product/assembly metadata but no geometric entities. "
            "The incomplete file was discarded instead of being offered for download."
        )
    if counts.get("AP242", 0) == 0 and tessellated_count:
        raise RuntimeError("Tessellated STEP geometry was written without an AP242 schema marker")
    return {
        "schema": "AP242",
        "file_size": size,
        "source_shape_count": int(source_shape_count),
        "exact_entity_count": int(exact_count),
        "tessellated_entity_count": int(tessellated_count),
        "entities": {name: int(value) for name, value in counts.items() if value},
    }


def _world_location(assembly, child):
    """Return a component root location relative to the loaded assembly root."""
    import cadquery as cq

    chain = []
    current = child
    while current is not None and current is not assembly:
        chain.append(current.loc)
        current = current.parent
    chain.append(assembly.loc)
    location = cq.Location()
    for item in reversed(chain):
        location = location * item
    return location


def _selection_export_assembly(assembly, component_ids: list[str]):
    """Create a new assembly containing selected components at world placements."""
    import cadquery as cq

    requested = [str(value) for value in component_ids if str(value).strip()]
    if not requested:
        return assembly, []
    missing = [value for value in requested if value not in assembly.objects]
    if missing:
        raise ValueError(f"Selected STEP component is missing: {missing[0]}")

    # Selecting a parent already includes all descendants, so remove redundant
    # descendant selections. Slash-delimited IDs are CadQuery assembly paths.
    unique = []
    for value in requested:
        if value == str(assembly.name):
            continue
        if any(value == parent or value.startswith(parent + "/") for parent in requested if parent != value):
            continue
        child = assembly.objects[value]
        if child.parent is None:
            continue
        unique.append(value)
    if not unique:
        raise ValueError("Select at least one component containing geometry")

    result = cq.Assembly(name=f"{_safe_component_name(str(assembly.name), 1)}_selection")
    used_names: set[str] = set()
    for index, component_id in enumerate(unique, start=1):
        child = assembly.objects[component_id]
        base = _safe_component_name(str(getattr(child, "name", None) or component_id.rsplit("/", 1)[-1]), index)
        name = base
        suffix = 2
        while name in used_names:
            name = f"{base}_{suffix}"
            suffix += 1
        used_names.add(name)
        result.add(child, name=name, loc=_world_location(assembly, child))
    return result, unique


def _configure_step_ap242(output_unit: str = "MM") -> None:
    """Configure OCCT's process-wide STEP writer for AP242 and the requested output unit."""
    from OCP.Interface import Interface_Static

    Interface_Static.SetCVal_s("write.step.schema", "AP242DIS")
    Interface_Static.SetIVal_s("write.step.tessellated", 1)
    Interface_Static.SetIVal_s("read.step.tessellated", 1)
    Interface_Static.SetIVal_s("write.step.assembly", 2)
    Interface_Static.SetIVal_s("write.surfacecurve.mode", 0)
    Interface_Static.SetIVal_s("write.stepcaf.subshapes.name", 1)
    Interface_Static.SetCVal_s("xstep.cascade.unit", "MM")
    Interface_Static.SetCVal_s("write.step.unit", str(output_unit or "MM").upper())


def _face_mesh_payload(face):
    """Return (triangulation, face location) for a triangulation-only face."""
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    face_location = TopLoc_Location()
    try:
        triangulation = BRep_Tool.Triangulation_s(face.wrapped, face_location)
    except Exception:
        return None
    if triangulation is None or triangulation.NbTriangles() <= 0:
        return None
    try:
        surface = BRep_Tool.Surface_s(face.wrapped)
    except Exception:
        surface = None
    # Exact B-rep faces commonly also carry a display triangulation.  Only a
    # face with no analytic surface is a CascadeCAD mesh container.
    if surface is not None:
        try:
            if not surface.IsNull():
                return None
        except AttributeError:
            return None
    return triangulation, face_location


def _assembly_step_profile(assembly) -> dict[str, Any]:
    """Inspect an assembly without materialising triangle faces."""
    source_shape_count = 0
    exact_shape_count = 0
    mesh_face_count = 0
    mesh_triangle_count = 0
    for shape, _name, _location, _color in assembly:
        source_shape_count += 1
        faces = list(shape.Faces())
        mesh_faces = 0
        for face in faces:
            payload = _face_mesh_payload(face)
            if payload is None:
                continue
            triangulation, _face_location = payload
            mesh_faces += 1
            mesh_face_count += 1
            mesh_triangle_count += int(triangulation.NbTriangles())
        if not faces or mesh_faces < len(faces):
            exact_shape_count += 1
    return {
        "source_shape_count": source_shape_count,
        "exact_shape_count": exact_shape_count,
        "mesh_face_count": mesh_face_count,
        "mesh_triangle_count": mesh_triangle_count,
    }


def _native_step_ap242(assembly, destination: Path, profile: dict[str, Any], output_unit: str = "MM") -> dict[str, Any]:
    """Try OCCT's native XDE AP242 tessellated writer first."""
    from cadquery.occ_impl.assembly import toCAF
    from OCP.IFSelect import IFSelect_ReturnStatus
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_StepModelType
    from OCP.XSControl import XSControl_WorkSession

    _configure_step_ap242(output_unit)
    _label, document = toCAF(assembly, True, False)
    session = XSControl_WorkSession()
    writer = STEPCAFControl_Writer(session, False)
    writer.SetColorMode(True)
    writer.SetLayerMode(True)
    writer.SetNameMode(True)
    try:
        writer.Writer().Model(True)
    except Exception:
        pass
    transferred = writer.Transfer(document, STEPControl_StepModelType.STEPControl_AsIs)
    if not transferred:
        raise RuntimeError("Open CASCADE could not transfer the XBF assembly to STEP AP242")
    status = writer.Write(str(destination))
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"Open CASCADE STEP writer failed with status {status}")
    report = _validate_step_output(destination, profile["source_shape_count"])
    report.update(
        {
            "writer_mode": "native-ap242",
            "mesh_representation": "ap242-tessellated" if report["tessellated_entity_count"] else None,
            "source_mesh_triangle_count": profile["mesh_triangle_count"],
            "faceted_mesh_triangle_count": 0,
        }
    )
    return report


def _triangle_face(p1, p2, p3):
    """Build one planar TopoDS_Face from three gp_Pnt values."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon

    polygon = BRepBuilderAPI_MakePolygon()
    polygon.Add(p1)
    polygon.Add(p2)
    polygon.Add(p3)
    polygon.Close()
    if not polygon.IsDone():
        return None
    maker = BRepBuilderAPI_MakeFace(polygon.Wire())
    if not maker.IsDone():
        return None
    return maker.Face()



def _shape_geometry_profile(shape) -> dict[str, int]:
    exact_faces = 0
    mesh_faces = 0
    mesh_triangles = 0
    for face in shape.Faces():
        payload = _face_mesh_payload(face)
        if payload is None:
            exact_faces += 1
        else:
            mesh_faces += 1
            mesh_triangles += int(payload[0].NbTriangles())
    return {
        "exact_faces": exact_faces,
        "mesh_faces": mesh_faces,
        "mesh_triangles": mesh_triangles,
    }


def _component_mesh_data(
    shape,
    world_location,
    tolerance: float = 0.5,
    angular_tolerance: float = 0.30,
    include_exact: bool = True,
    include_mesh: bool = True,
):
    """Return world-space vertices and triangle indices for one component.

    Exact faces are tessellated face-by-face. Triangulation-only XBF faces are
    copied from their stored Poly_Triangulation, so the helper works for exact,
    mesh, and mixed assemblies without asking OCCT to remesh mesh containers.
    """
    import cadquery as cq

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    world_transform = world_location.wrapped.Transformation()

    for face in shape.Faces():
        payload = _face_mesh_payload(face)
        if payload is not None:
            if not include_mesh:
                continue
            triangulation, face_location = payload
            combined = world_transform.Multiplied(face_location.Transformation())
            offset = len(vertices)
            for index in range(1, int(triangulation.NbNodes()) + 1):
                point = triangulation.Node(index).Transformed(combined)
                vertices.append((float(point.X()), float(point.Y()), float(point.Z())))
            for index in range(1, int(triangulation.NbTriangles()) + 1):
                tri = triangulation.Triangle(index)
                triangles.append(
                    (
                        offset + int(tri.Value(1)) - 1,
                        offset + int(tri.Value(2)) - 1,
                        offset + int(tri.Value(3)) - 1,
                    )
                )
            continue

        if not include_exact:
            continue
        face_shape = cq.Shape.cast(face.wrapped).moved(world_location)
        face_vertices, face_triangles = face_shape.tessellate(
            tolerance,
            angular_tolerance,
        )
        offset = len(vertices)
        vertices.extend((float(v.x), float(v.y), float(v.z)) for v in face_vertices)
        triangles.extend(
            (offset + int(a), offset + int(b), offset + int(c))
            for a, b, c in face_triangles
        )

    if not vertices and include_exact:
        moved = shape.moved(world_location)
        raw_vertices, raw_triangles = moved.tessellate(tolerance, angular_tolerance)
        vertices.extend((float(v.x), float(v.y), float(v.z)) for v in raw_vertices)
        triangles.extend((int(a), int(b), int(c)) for a, b, c in raw_triangles)
    return vertices, triangles


def _deduplicate_mesh_vertices(
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    digits: int = 9,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Weld coordinate-identical vertices with a vectorized NumPy fast path."""
    if not vertices or not triangles:
        return vertices, triangles
    try:
        import numpy as np

        vertex_array = np.asarray(vertices, dtype=np.float64)
        triangle_array = np.asarray(triangles, dtype=np.int64)
        scale = float(10**int(digits))
        quantized = np.rint(vertex_array * scale).astype(np.int64, copy=False)
        _unique, first_indices, inverse = np.unique(
            quantized,
            axis=0,
            return_index=True,
            return_inverse=True,
        )
        # np.unique sorts its keys; restore first-occurrence ordering so existing
        # component indexing remains deterministic and human-debuggable.
        order = np.argsort(first_indices)
        unique_to_stable = np.empty(len(order), dtype=np.int64)
        unique_to_stable[order] = np.arange(len(order), dtype=np.int64)
        remapped = unique_to_stable[inverse][triangle_array]
        valid = (
            (remapped[:, 0] != remapped[:, 1])
            & (remapped[:, 1] != remapped[:, 2])
            & (remapped[:, 2] != remapped[:, 0])
        )
        welded_array = vertex_array[first_indices[order]]
        return (
            [tuple(map(float, row)) for row in welded_array.tolist()],
            [tuple(map(int, row)) for row in remapped[valid].tolist()],
        )
    except Exception:
        index_by_key: dict[tuple[float, float, float], int] = {}
        remap: list[int] = [0] * len(vertices)
        welded: list[tuple[float, float, float]] = []
        for old_index, vertex in enumerate(vertices):
            key = tuple(round(float(value), digits) for value in vertex)
            new_index = index_by_key.get(key)
            if new_index is None:
                new_index = len(welded)
                index_by_key[key] = new_index
                welded.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
            remap[old_index] = new_index
        welded_triangles: list[tuple[int, int, int]] = []
        for a, b, c in triangles:
            mapped = (remap[int(a)], remap[int(b)], remap[int(c)])
            if len(set(mapped)) == 3:
                welded_triangles.append(mapped)
        return welded, welded_triangles


_FACETED_CACHE_VERSION = "ocp-shape-on-mesh-v1"


def _mesh_cache_key(
    vertices,
    triangles,
    *,
    tolerance: float,
    fast_sewing: bool,
    unify_same_domain: bool,
) -> str:
    """Hash geometry and conversion policy for persistent component reuse."""
    import hashlib
    import numpy as np

    vertex_array = np.ascontiguousarray(vertices, dtype=np.float64)
    triangle_array = np.ascontiguousarray(triangles, dtype=np.int64)
    digest = hashlib.sha256()
    digest.update(_FACETED_CACHE_VERSION.encode("ascii"))
    digest.update(f"|tol={float(tolerance):.12g}|fast={int(fast_sewing)}|unify={int(unify_same_domain)}|".encode("ascii"))
    digest.update(str(vertex_array.shape).encode("ascii"))
    digest.update(vertex_array.tobytes(order="C"))
    digest.update(str(triangle_array.shape).encode("ascii"))
    digest.update(triangle_array.tobytes(order="C"))
    return digest.hexdigest()


def _faceted_cache_root(project_dir: Path) -> Path:
    root = project_dir.parents[1] / "geometry-cache" / "faceted"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _prune_faceted_cache(cache_root: Path, max_bytes: int) -> None:
    """Best-effort LRU pruning without delaying a conversion on filesystem errors."""
    try:
        files = [path for path in cache_root.iterdir() if path.is_file()]
        total = sum(path.stat().st_size for path in files)
        if total <= int(max_bytes):
            return
        for path in sorted(files, key=lambda item: item.stat().st_mtime):
            try:
                size = path.stat().st_size
                path.unlink(missing_ok=True)
                total -= size
            except OSError:
                continue
            if total <= int(max_bytes):
                break
    except OSError:
        return


def _effective_faceted_workers(requested: int, task_count: int, memory_budget_gb: float) -> int:
    cpu_limit = max(1, int(os.cpu_count() or 1))
    requested = max(1, int(requested))
    # A direct conversion subprocess is conservatively budgeted at 2 GiB. This
    # keeps the 16 GiB server away from its systemd MemoryHigh threshold.
    memory_limit = max(1, int(max(1.0, float(memory_budget_gb)) // 2.0))
    return max(1, min(requested, cpu_limit, memory_limit, max(1, int(task_count))))


def _ocp_faceted_command(task: dict[str, Any], tolerance: float, fast_sewing: bool, unify_same_domain: bool) -> list[str]:
    import sys

    command = [
        sys.executable,
        "-m",
        "webcad_xbf.faceted_worker",
        "--input",
        str(task["input_path"]),
        "--output",
        str(task["output_path"]),
        "--report",
        str(task["report_path"]),
        "--tolerance",
        str(float(tolerance)),
    ]
    if fast_sewing:
        command.append("--fast-sewing")
    if not unify_same_domain:
        command.append("--no-unify-same-domain")
    return command


def _run_hard_speed_parts_conversion(
    project_dir: Path,
    assembly,
    progress: Progress,
    should_cancel: CancelCheck | None,
    max_triangles: int,
    timeout_seconds: int,
    *,
    tolerance: float = 0.05,
    workers: int = 2,
    queue_depth: int = 60,
    memory_budget_gb: float = 10.0,
    cache_enabled: bool = True,
    cache_max_bytes: int = 20 * 1024**3,
    fast_sewing: bool = False,
    unify_same_domain: bool = True,
) -> dict[str, Any]:
    """Convert mesh-backed assembly components with isolated parallel OCP workers."""
    import json
    import subprocess
    import tempfile

    import cadquery as cq
    import numpy as np

    started = time.monotonic()
    cache_root = _faceted_cache_root(project_dir)
    if cache_enabled:
        _prune_faceted_cache(cache_root, cache_max_bytes)

    rows: list[tuple[str, str, Any, Any, dict[str, int]]] = []
    for component_id, child in assembly.objects.items():
        direct_shapes = list(child.shapes)
        if not direct_shapes:
            continue
        shape = direct_shapes[0] if len(direct_shapes) == 1 else cq.Compound.makeCompound(direct_shapes)
        rows.append(
            (
                str(component_id),
                str(getattr(child, "name", None) or component_id),
                child,
                shape,
                _shape_geometry_profile(shape),
            )
        )
    if not rows:
        raise RuntimeError("The XBF assembly contains no shape-bearing components")

    mesh_rows = [row for row in rows if row[4]["mesh_faces"]]
    if not mesh_rows:
        return {
            "changed": False,
            "backend": "BRepBuilderAPI_MakeShapeOnMesh",
            "source_component_count": len(rows),
            "source_component_ids": [row[0] for row in rows],
            "source_mesh_component_count": 0,
            "source_mesh_triangle_count": 0,
            "mesh_triangle_count_after": 0,
            "parts": [],
        }

    work_parent = project_dir / "revisions"
    work_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cascade-cad-hard-speed-", dir=str(work_parent)) as temp_name:
        temp_dir = Path(temp_name)
        tasks_by_key: dict[str, dict[str, Any]] = {}
        component_keys: dict[str, str] = {}
        component_labels: dict[str, str] = {}
        total_triangles = 0
        cache_hit_components = 0

        for index, (component_id, label, _child, shape, profile) in enumerate(mesh_rows, start=1):
            _check_long_job(should_cancel, None, "Hard-speed faceted conversion")
            progress(
                12 + int(18 * (index - 1) / max(1, len(mesh_rows))),
                f"Reading mesh component {index}/{len(mesh_rows)}",
            )
            vertices, triangles = _component_mesh_data(
                shape,
                cq.Location(),
                include_exact=True,
                include_mesh=True,
            )
            vertices, triangles = _deduplicate_mesh_vertices(vertices, triangles)
            if not vertices or not triangles:
                raise RuntimeError(f"Component {label} contains no usable triangles")
            total_triangles += len(triangles)
            if total_triangles > int(max_triangles):
                raise RuntimeError(
                    f"Faceted conversion reached {total_triangles:,} triangles, above the configured limit of "
                    f"{int(max_triangles):,}. Raise CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES only after confirming RAM."
                )
            vertex_array = np.asarray(vertices, dtype=np.float64)
            triangle_array = np.asarray(triangles, dtype=np.int64)
            cache_key = _mesh_cache_key(
                vertex_array,
                triangle_array,
                tolerance=tolerance,
                fast_sewing=fast_sewing,
                unify_same_domain=unify_same_domain,
            )
            component_keys[component_id] = cache_key
            component_labels[component_id] = label
            if cache_key in tasks_by_key:
                continue
            cache_brep = cache_root / f"{cache_key}.brep"
            cache_report = cache_root / f"{cache_key}.json"
            cached = False
            cached_report: dict[str, Any] | None = None
            if cache_enabled and cache_brep.exists() and cache_brep.stat().st_size >= 100 and cache_report.exists():
                try:
                    cached_report = json.loads(cache_report.read_text(encoding="utf-8"))
                    cached = not bool(cached_report.get("failed"))
                except (OSError, ValueError, TypeError):
                    cached = False
            task = {
                "key": cache_key,
                "cache_brep": cache_brep,
                "cache_report": cache_report,
                "cached": cached,
                "cached_report": cached_report,
                "input_path": temp_dir / f"{cache_key}.npz",
                "output_path": temp_dir / f"{cache_key}.brep",
                "report_path": temp_dir / f"{cache_key}.json",
                "log_path": temp_dir / f"{cache_key}.log",
                "triangles": int(triangle_array.shape[0]),
            }
            if not cached:
                np.savez(task["input_path"], vertices=vertex_array, triangles=triangle_array)
            tasks_by_key[cache_key] = task

        # Repeated component instances share one task and one persistent BREP.
        for component_id, key in component_keys.items():
            if tasks_by_key[key]["cached"]:
                cache_hit_components += 1

        unique_tasks = list(tasks_by_key.values())
        runnable = [task for task in unique_tasks if not task["cached"]]
        effective_workers = _effective_faceted_workers(workers, len(runnable) or 1, memory_budget_gb)
        queue_depth = max(effective_workers, min(max(1, int(queue_depth)), 60))
        deadline = time.monotonic() + max(60, int(timeout_seconds))
        completed_tasks = sum(1 for task in unique_tasks if task["cached"])
        active: dict[subprocess.Popen, tuple[dict[str, Any], Any]] = {}
        task_index = 0
        # Admit at most queue_depth unique component jobs into the runnable
        # window. Each completed job opens one slot for the next component.
        admitted_until = min(len(runnable), queue_depth)
        worker_env = os.environ.copy()
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            worker_env[key] = "1"

        def terminate_active() -> None:
            for process, (_task, handle) in list(active.items()):
                try:
                    process.terminate()
                except OSError:
                    pass
            for process, (_task, handle) in list(active.items()):
                try:
                    process.wait(timeout=5)
                except Exception:
                    try:
                        process.kill()
                    except OSError:
                        pass
                try:
                    handle.close()
                except Exception:
                    pass
            active.clear()

        try:
            while task_index < len(runnable) or active:
                _check_long_job(should_cancel, deadline, "Hard-speed faceted conversion")
                # Only two processes run on the current VM by default. The next
                # sixty unique parts may be staged, but never become 60 active OCP kernels.
                while task_index < admitted_until and len(active) < effective_workers:
                    task = runnable[task_index]
                    task_index += 1
                    log_handle = Path(task["log_path"]).open("w", encoding="utf-8")
                    process = subprocess.Popen(
                        _ocp_faceted_command(task, tolerance, fast_sewing, unify_same_domain),
                        cwd=str(temp_dir),
                        env=worker_env,
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    active[process] = (task, log_handle)

                finished = [process for process in active if process.poll() is not None]
                if not finished:
                    elapsed = max(0.001, time.monotonic() - started)
                    rate = total_triangles / elapsed
                    progress(
                        30 + int(42 * completed_tasks / max(1, len(unique_tasks))),
                        f"Hard-speed conversion: {completed_tasks}/{len(unique_tasks)} unique parts · "
                        f"{len(active)} active/{effective_workers} workers · {rate:,.0f} triangles/s",
                    )
                    time.sleep(0.15)
                    continue

                for process in finished:
                    task, log_handle = active.pop(process)
                    log_handle.close()
                    log_text = Path(task["log_path"]).read_text(encoding="utf-8", errors="replace")
                    try:
                        report = json.loads(Path(task["report_path"]).read_text(encoding="utf-8"))
                    except Exception:
                        report = {"failed": True, "error": "OCP worker did not create a readable report"}
                    if process.returncode != 0 or report.get("failed"):
                        raise RuntimeError(
                            f"Direct OCP conversion failed for {task['key'][:12]}: "
                            f"{report.get('error') or log_text[-2500:] or 'unknown OCP worker error'}"
                        )
                    output_path = Path(task["output_path"])
                    if not output_path.exists() or output_path.stat().st_size < 100:
                        raise RuntimeError("Direct OCP conversion produced an empty component BREP")
                    if cache_enabled:
                        cache_tmp = Path(task["cache_brep"]).with_suffix(".brep.tmp")
                        shutil.copy2(output_path, cache_tmp)
                        os.replace(cache_tmp, task["cache_brep"])
                        report_tmp = Path(task["cache_report"]).with_suffix(".json.tmp")
                        report_tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                        os.replace(report_tmp, task["cache_report"])
                    task["cached_report"] = report
                    completed_tasks += 1
                    admitted_until = min(len(runnable), admitted_until + 1)
                    progress(
                        30 + int(42 * completed_tasks / max(1, len(unique_tasks))),
                        f"Converted unique part {completed_tasks}/{len(unique_tasks)}",
                    )
        except Exception:
            terminate_active()
            raise
        finally:
            terminate_active()

        aggregate_parts = []
        warnings: list[str] = []
        solid_count = 0
        open_shell_count = 0
        mixed_count = 0
        shell_component_count = 0
        fast_used_count = 0
        standard_sewing_count = 0
        unified_count = 0
        for index, (component_id, _label, child, _shape, profile) in enumerate(mesh_rows, start=1):
            _check_long_job(should_cancel, deadline, "Installing hard-speed faceted geometry")
            task = tasks_by_key[component_keys[component_id]]
            result_path = Path(task["cache_brep"]) if task["cached"] or cache_enabled else Path(task["output_path"])
            if not result_path.exists():
                result_path = Path(task["output_path"])
            converted = cq.Shape.importBrep(str(result_path))
            converted_profile = _shape_geometry_profile(converted)
            if converted_profile["mesh_faces"] or not converted_profile["exact_faces"]:
                raise RuntimeError(f"Converted component still contains mesh-only geometry: {component_id}")
            report = dict(task.get("cached_report") or {})
            representation = str(report.get("representation") or "faceted-brep")
            child.obj = converted
            child.metadata = {
                **dict(getattr(child, "metadata", {}) or {}),
                "CASCADE_Representation": representation,
                "CASCADE_FacetedBackend": "BRepBuilderAPI_MakeShapeOnMesh",
                "CASCADE_FacetedCacheKey": component_keys[component_id],
            }
            component_solids = int(report.get("solid_count", 0))
            component_open = int(report.get("faceted_open_shell_count", 0))
            solid_count += component_solids
            open_shell_count += component_open
            mixed_count += int(representation == "faceted-mixed-solid-shell")
            shell_component_count += int(representation == "faceted-shell")
            fast_used_count += int(bool(report.get("fast_sewing_used")))
            standard_sewing_count += int(bool(report.get("standard_sewing_used")))
            unified_count += int(bool(report.get("same_domain_unified")))
            warnings.extend(str(item) for item in report.get("warnings") or [])
            aggregate_parts.append(
                {
                    "component_id": component_id,
                    "representation": representation,
                    "solid_count": component_solids,
                    "retained_shells": component_open,
                    "triangles": int(report.get("triangle_count", profile["mesh_triangles"])),
                    "cache_key": component_keys[component_id],
                }
            )
            progress(74 + int(12 * index / max(1, len(mesh_rows))), f"Installing faceted part {index}/{len(mesh_rows)}")

        after = _assembly_step_profile(assembly)
        if int(after.get("mesh_triangle_count", 0)) != 0:
            raise RuntimeError("Hard-speed conversion left triangulation-only XBF remnants")
        elapsed = max(0.000001, time.monotonic() - started)
        cache_miss_unique = len(runnable)
        report = {
            "changed": True,
            "backend": "BRepBuilderAPI_MakeShapeOnMesh",
            "source_component_count": len(rows),
            "source_component_ids": [row[0] for row in rows],
            "source_mesh_component_count": len(mesh_rows),
            "source_mesh_triangle_count": total_triangles,
            "converted_component_count": len(mesh_rows),
            "unique_geometry_count": len(unique_tasks),
            "reused_instance_count": max(0, len(mesh_rows) - len(unique_tasks)),
            "cache_hit_component_count": cache_hit_components,
            "cache_miss_unique_count": cache_miss_unique,
            "workers_used": effective_workers,
            "queue_depth": queue_depth,
            "fast_sewing_requested": bool(fast_sewing),
            "fast_sewing_component_count": fast_used_count,
            "standard_sewing_component_count": standard_sewing_count,
            "same_domain_unified_component_count": unified_count,
            "solid_count": solid_count,
            "faceted_solid_component_count": sum(
                1 for item in aggregate_parts if item["representation"] == "faceted-solid"
            ),
            "faceted_shell_component_count": shell_component_count,
            "faceted_mixed_component_count": mixed_count,
            "faceted_open_shell_count": open_shell_count,
            "mesh_triangle_count_after": 0,
            "elapsed_seconds": elapsed,
            "triangles_per_second": int(round(total_triangles / elapsed)),
            "parts": aggregate_parts,
            "warnings": sorted(set(warnings)),
        }
        if cache_enabled:
            _prune_faceted_cache(cache_root, cache_max_bytes)
        return report


def _convert_assembly_meshes(
    project_dir: Path,
    assembly,
    progress: Progress,
    should_cancel: CancelCheck | None,
    max_triangles: int,
    timeout_seconds: int,
    *,
    tolerance: float = 0.05,
    workers: int = 2,
    queue_depth: int = 60,
    memory_budget_gb: float = 10.0,
    cache_enabled: bool = True,
    cache_max_bytes: int = 20 * 1024**3,
    direct_ocp: bool = True,
    freecad_fallback: bool = True,
    fast_render: bool = False,
    unify_same_domain: bool = True,
) -> dict[str, Any]:
    """Use the hard-speed path first and preserve FreeCAD as a compatibility fallback."""
    if direct_ocp:
        try:
            return _run_hard_speed_parts_conversion(
                project_dir,
                assembly,
                progress,
                should_cancel,
                max_triangles,
                timeout_seconds,
                tolerance=tolerance,
                workers=workers,
                queue_depth=queue_depth,
                memory_budget_gb=memory_budget_gb,
                cache_enabled=cache_enabled,
                cache_max_bytes=cache_max_bytes,
                fast_sewing=bool(fast_render),
                # Fast render favors immediate conversion and intentionally skips
                # the optional same-domain optimization pass.
                unify_same_domain=bool(unify_same_domain and not fast_render),
            )
        except Exception as exc:
            if not freecad_fallback:
                raise
            progress(34, "Direct OCP conversion failed; using isolated FreeCAD fallback")
            fallback = _run_freecad_parts_conversion(
                project_dir=project_dir,
                assembly=assembly,
                progress=progress,
                should_cancel=should_cancel,
                max_triangles=max_triangles,
                timeout_seconds=timeout_seconds,
                tolerance=tolerance,
            )
            fallback["backend"] = "FreeCAD-fallback"
            fallback["direct_ocp_error"] = f"{type(exc).__name__}: {exc}"
            fallback["fast_sewing_requested"] = bool(fast_render)
            return fallback
    return _run_freecad_parts_conversion(
        project_dir=project_dir,
        assembly=assembly,
        progress=progress,
        should_cancel=should_cancel,
        max_triangles=max_triangles,
        timeout_seconds=timeout_seconds,
        tolerance=tolerance,
    )


def _iter_faceted_chunks(shape, world_location, chunk_triangles: int = 1000):
    """Yield bounded compounds of planar faces reconstructed from mesh triangles."""
    import cadquery as cq
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    faces_in_chunk = []
    emitted = 0
    for face in shape.Faces():
        payload = _face_mesh_payload(face)
        if payload is None:
            continue
        triangulation, face_location = payload
        face_transform = face_location.Transformation()
        for index in range(1, int(triangulation.NbTriangles()) + 1):
            triangle = triangulation.Triangle(index)
            p1 = triangulation.Node(int(triangle.Value(1))).Transformed(face_transform)
            p2 = triangulation.Node(int(triangle.Value(2))).Transformed(face_transform)
            p3 = triangulation.Node(int(triangle.Value(3))).Transformed(face_transform)
            cad_face = _triangle_face(p1, p2, p3)
            if cad_face is None:
                continue
            faces_in_chunk.append(cad_face)
            emitted += 1
            if len(faces_in_chunk) >= chunk_triangles:
                compound = TopoDS_Compound()
                builder = BRep_Builder()
                builder.MakeCompound(compound)
                for item in faces_in_chunk:
                    builder.Add(compound, item)
                yield cq.Shape.cast(compound).moved(world_location), len(faces_in_chunk)
                faces_in_chunk.clear()
    if faces_in_chunk:
        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for item in faces_in_chunk:
            builder.Add(compound, item)
        yield cq.Shape.cast(compound).moved(world_location), len(faces_in_chunk)
    if emitted == 0:
        raise RuntimeError("Mesh component contained no valid triangles for faceted STEP fallback")


def _faceted_step_fallback(
    assembly,
    destination: Path,
    profile: dict[str, Any],
    max_faceted_triangles: int,
    native_error: str | None = None,
    progress: Progress | None = None,
    should_cancel: CancelCheck | None = None,
    timeout_seconds: int = 3600,
    chunk_triangles: int = 1000,
    output_unit: str = "MM",
) -> dict[str, Any]:
    """Write mesh triangles as bounded planar STEP faces with live progress."""
    from OCP.IFSelect import IFSelect_ReturnStatus
    from OCP.STEPControl import STEPControl_StepModelType, STEPControl_Writer

    triangle_count = int(profile["mesh_triangle_count"])
    if triangle_count <= 0:
        raise RuntimeError("Faceted STEP fallback was requested without mesh triangles")
    if triangle_count > int(max_faceted_triangles):
        raise RuntimeError(
            "This mesh contains "
            f"{triangle_count:,} triangles, above the safe faceted STEP limit of "
            f"{int(max_faceted_triangles):,}. Export a smaller selected part, enable mesh cleanup, "
            "or raise CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES after confirming sufficient RAM and disk."
        )

    deadline = time.monotonic() + max(60, int(timeout_seconds))
    started = time.monotonic()
    _configure_step_ap242(output_unit)
    writer = STEPControl_Writer()
    transferred_shapes = 0
    faceted_triangles = 0
    for shape, _name, world_location, _color in assembly:
        _check_long_job(should_cancel, deadline, "STEP export")
        faces = list(shape.Faces())
        mesh_face_count = sum(1 for face in faces if _face_mesh_payload(face) is not None)
        pure_mesh = bool(faces) and mesh_face_count == len(faces)
        if not pure_mesh:
            status = writer.Transfer(
                shape.moved(world_location).wrapped,
                STEPControl_StepModelType.STEPControl_AsIs,
            )
            if status != IFSelect_ReturnStatus.IFSelect_RetDone:
                raise RuntimeError(f"STEP fallback could not transfer an exact component: {status}")
            transferred_shapes += 1
        if mesh_face_count:
            for chunk, chunk_count in _iter_faceted_chunks(
                shape,
                world_location,
                chunk_triangles=max(100, int(chunk_triangles)),
            ):
                _check_long_job(should_cancel, deadline, "STEP export")
                status = writer.Transfer(
                    chunk.wrapped,
                    STEPControl_StepModelType.STEPControl_ShellBasedSurfaceModel,
                )
                if status != IFSelect_ReturnStatus.IFSelect_RetDone:
                    raise RuntimeError(f"STEP fallback could not transfer a faceted mesh chunk: {status}")
                faceted_triangles += int(chunk_count)
                transferred_shapes += 1
                elapsed = max(0.001, time.monotonic() - started)
                rate = faceted_triangles / elapsed
                remaining = max(0, triangle_count - faceted_triangles)
                eta = _format_eta(remaining / rate) if rate > 0 else "estimating"
                if progress:
                    percent = 52 + int(34 * faceted_triangles / max(1, triangle_count))
                    progress(
                        min(86, percent),
                        f"Building faceted STEP: {faceted_triangles:,}/{triangle_count:,} triangles · ETA {eta}",
                    )

    if transferred_shapes == 0 or faceted_triangles == 0:
        raise RuntimeError("Faceted STEP fallback produced no transferable geometry")
    _check_long_job(should_cancel, deadline, "STEP export")
    if progress:
        progress(88, "Writing STEP file")
    status = writer.Write(str(destination))
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"Faceted STEP writer failed with status {status}")
    report = _validate_step_output(destination, profile["source_shape_count"])
    report.update(
        {
            "writer_mode": "faceted-brep-fallback",
            "mesh_representation": "planar-triangle-brep",
            "source_mesh_triangle_count": triangle_count,
            "faceted_mesh_triangle_count": faceted_triangles,
            "native_writer_error": native_error,
        }
    )
    return report


def _write_step_ap242(
    assembly,
    destination: Path,
    max_faceted_triangles: int = 5_000_000,
    progress: Progress | None = None,
    should_cancel: CancelCheck | None = None,
    timeout_seconds: int = 3600,
    chunk_triangles: int = 1000,
    output_unit: str = "MM",
) -> dict[str, Any]:
    """Write STEP using native AP242 tessellation or a validated B-rep fallback."""
    profile = _assembly_step_profile(assembly)
    if profile["source_shape_count"] == 0:
        raise ValueError("The selected assembly contains no exportable geometry")

    destination.parent.mkdir(parents=True, exist_ok=True)
    native_temp = destination.with_name(f".{destination.stem}.{time.time_ns()}.native.tmp{destination.suffix}")
    fallback_temp = destination.with_name(f".{destination.stem}.{time.time_ns()}.faceted.tmp{destination.suffix}")
    native_error = None
    try:
        _check_long_job(should_cancel, None, "STEP export")
        try:
            if progress:
                progress(45, "Trying native STEP AP242 writer")
            report = _native_step_ap242(assembly, native_temp, profile, output_unit=output_unit)
            native_has_mesh = report.get("tessellated_entity_count", 0) > 0
            if profile["mesh_triangle_count"] == 0 or native_has_mesh:
                os.replace(native_temp, destination)
                return report
            native_error = (
                "Native AP242 transfer omitted triangulated mesh geometry "
                f"({profile['mesh_triangle_count']:,} source triangles)."
            )
        except Exception as exc:
            native_error = str(exc)

        if progress:
            progress(52, "Native mesh STEP unavailable; starting planar-facet fallback")
        report = _faceted_step_fallback(
            assembly,
            fallback_temp,
            profile,
            max_faceted_triangles=max_faceted_triangles,
            native_error=native_error,
            progress=progress,
            should_cancel=should_cancel,
            timeout_seconds=timeout_seconds,
            chunk_triangles=chunk_triangles,
            output_unit=output_unit,
        )
        os.replace(fallback_temp, destination)
        return report
    finally:
        native_temp.unlink(missing_ok=True)
        fallback_temp.unlink(missing_ok=True)


def _load_export_assembly(
    project_dir: Path,
    editor_state: dict[str, Any] | None,
    component_ids: list[str] | None,
    progress: Progress,
):
    import cadquery as cq

    master = project_dir / "master.xbf"
    if not master.exists():
        raise FileNotFoundError("Project master.xbf is missing")
    progress(12, "Opening XBF master")
    assembly = cq.Assembly.load(str(master), importType="XBF")
    if editor_state:
        progress(24, "Applying working editor changes")
        apply_editor_state(assembly, editor_state)
    export_assembly, selected = _selection_export_assembly(assembly, list(component_ids or []))
    return export_assembly, selected, ("selected" if selected else "project")


def _prepare_faceted_export_assembly(
    project_dir: Path,
    assembly,
    progress: Progress,
    should_cancel: CancelCheck | None,
    max_triangles: int,
    timeout_seconds: int,
    *,
    fast_render: bool,
    faceted_workers: int,
    faceted_queue_depth: int,
    faceted_memory_budget_gb: float,
    faceted_cache_enabled: bool,
    faceted_cache_max_bytes: int,
    faceted_direct_ocp: bool,
    faceted_freecad_fallback: bool,
    faceted_unify_same_domain: bool,
) -> dict[str, Any] | None:
    profile = _assembly_step_profile(assembly)
    if int(profile.get("mesh_triangle_count", 0)) <= 0:
        return None
    progress(28, "Preparing mesh-backed parts as cached faceted BREP")
    return _convert_assembly_meshes(
        project_dir=project_dir,
        assembly=assembly,
        progress=progress,
        should_cancel=should_cancel,
        max_triangles=max_triangles,
        timeout_seconds=timeout_seconds,
        workers=faceted_workers,
        queue_depth=faceted_queue_depth,
        memory_budget_gb=faceted_memory_budget_gb,
        cache_enabled=faceted_cache_enabled,
        cache_max_bytes=faceted_cache_max_bytes,
        direct_ocp=faceted_direct_ocp,
        freecad_fallback=faceted_freecad_fallback,
        fast_render=fast_render,
        unify_same_domain=faceted_unify_same_domain,
    )


def export_step(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any] | None,
    progress: Progress,
    component_ids: list[str] | None = None,
    max_faceted_triangles: int = 5_000_000,
    should_cancel: CancelCheck | None = None,
    timeout_seconds: int = 3600,
    chunk_triangles: int = 1000,
    *,
    fast_render: bool = False,
    faceted_workers: int = 2,
    faceted_queue_depth: int = 60,
    faceted_memory_budget_gb: float = 10.0,
    faceted_cache_enabled: bool = True,
    faceted_cache_max_bytes: int = 20 * 1024**3,
    faceted_direct_ocp: bool = True,
    faceted_freecad_fallback: bool = True,
    faceted_unify_same_domain: bool = True,
    unit_system: str = "imperial",
) -> dict[str, Any]:
    unit_system = str(unit_system or "imperial").lower()
    if unit_system not in {"imperial", "metric"}:
        raise ValueError("unit_system must be imperial or metric")
    output_unit = "INCH" if unit_system == "imperial" else "MM"
    export_assembly, selected, scope = _load_export_assembly(
        project_dir, editor_state, component_ids, progress
    )
    unit_suffix = "in" if output_unit == "INCH" else "mm"
    filename = f"{'selected' if selected else 'project'}-ap242-{unit_suffix}.step"
    destination = project_dir / "exports" / filename
    conversion_report = _prepare_faceted_export_assembly(
        project_dir,
        export_assembly,
        progress,
        should_cancel,
        max_faceted_triangles,
        timeout_seconds,
        fast_render=fast_render,
        faceted_workers=faceted_workers,
        faceted_queue_depth=faceted_queue_depth,
        faceted_memory_budget_gb=faceted_memory_budget_gb,
        faceted_cache_enabled=faceted_cache_enabled,
        faceted_cache_max_bytes=faceted_cache_max_bytes,
        faceted_direct_ocp=faceted_direct_ocp,
        faceted_freecad_fallback=faceted_freecad_fallback,
        faceted_unify_same_domain=faceted_unify_same_domain,
    )
    progress(38, "Preparing STEP AP242 geometry")
    report = _write_step_ap242(
        export_assembly,
        destination,
        max_faceted_triangles=max_faceted_triangles,
        progress=progress,
        should_cancel=should_cancel,
        timeout_seconds=timeout_seconds,
        chunk_triangles=chunk_triangles,
        output_unit=output_unit,
    )
    progress(94, "Validating STEP geometric entities")
    report.update(
        {
            "format": "step",
            "scope": scope,
            "selected_component_ids": selected,
            "geometry_kind": str(geometry_kind or "unknown"),
            "relative_path": f"exports/{filename}",
            "fast_render": bool(fast_render),
            "faceted_conversion": conversion_report,
            "unit_system": unit_system,
            "output_unit": output_unit,
            "internal_unit": "MM",
        }
    )
    if conversion_report and conversion_report.get("changed"):
        # The direct OCP path has already replaced triangulation containers
        # with Part solids/shells, so a correct native AP242 file contains
        # B-rep entities and no tessellated STEP entities. Preserve that mesh
        # provenance explicitly instead of reporting mesh_representation=None.
        report.update(
            {
                "mesh_representation": "faceted-solid-brep",
                "source_mesh_triangle_count": int(
                    conversion_report.get("source_mesh_triangle_count", 0) or 0
                ),
                "mesh_triangle_count_after_conversion": int(
                    conversion_report.get("mesh_triangle_count_after", -1)
                ),
                "faceted_brep_component_count": int(
                    conversion_report.get("converted_component_count", 0) or 0
                ),
                "faceted_brep_solid_count": int(
                    conversion_report.get("solid_count", 0) or 0
                ),
                "faceted_brep_open_shell_count": int(
                    conversion_report.get("faceted_open_shell_count", 0) or 0
                ),
            }
        )
    return report


def export_xbf(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any] | None,
    progress: Progress,
    component_ids: list[str] | None = None,
    should_cancel: CancelCheck | None = None,
) -> dict[str, Any]:
    export_assembly, selected, scope = _load_export_assembly(
        project_dir, editor_state, component_ids, progress
    )
    _check_long_job(should_cancel, None, "XBF export")
    filename = "selected.xbf" if selected else "project.xbf"
    destination = project_dir / "exports" / filename
    progress(60, "Writing XBF assembly")
    _atomic_export(export_assembly, destination, "XBF")
    return {
        "format": "xbf",
        "scope": scope,
        "selected_component_ids": selected,
        "geometry_kind": str(geometry_kind or "unknown"),
        "file_size": destination.stat().st_size,
        "relative_path": f"exports/{filename}",
    }


def _prepare_freecad_part_manifest(
    export_assembly,
    temp_dir: Path,
    progress: Progress,
    should_cancel: CancelCheck | None,
    max_triangles: int,
) -> tuple[Path, dict[str, Any]]:
    """Create exact-BREP or STL inputs for the headless FreeCAD converter.

    A component containing any triangulation-only faces is exported as one
    faceted component so exact and mesh subfaces are not duplicated. Pure
    exact components remain exact B-rep.
    """
    import json
    import trimesh
    from OCP.BRepTools import BRepTools

    rows = list(export_assembly)
    if not rows:
        raise RuntimeError("The selected assembly contains no exportable components")

    items: list[dict[str, Any]] = []
    mesh_triangles = 0
    for index, (shape, name, world_location, _color) in enumerate(rows, start=1):
        _check_long_job(should_cancel, None, "Part export")
        progress(
            18 + int(22 * (index - 1) / max(1, len(rows))),
            f"Preparing component {index}/{len(rows)} for solid conversion",
        )
        profile = _shape_geometry_profile(shape)
        safe_name = _safe_component_name(str(name), index)
        item: dict[str, Any] = {
            "component_id": str(name),
            "name": str(name),
        }

        if profile["mesh_faces"]:
            vertices, triangles = _component_mesh_data(
                shape,
                world_location,
                include_exact=True,
                include_mesh=True,
            )
            vertices, triangles = _deduplicate_mesh_vertices(vertices, triangles)
            if not vertices or not triangles:
                raise RuntimeError(f"Component {name} contains no usable triangles")
            mesh_triangles += len(triangles)
            if mesh_triangles > int(max_triangles):
                raise RuntimeError(
                    f"Faceted solid conversion reached {mesh_triangles:,} triangles, above the safe limit of "
                    f"{int(max_triangles):,}. Export a smaller selection or raise "
                    "CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES after confirming sufficient RAM."
                )
            mesh = trimesh.Trimesh(vertices=vertices, faces=triangles, process=False)
            stl_path = temp_dir / f"{index:04d}-{safe_name}.stl"
            mesh.export(stl_path, file_type="stl")
            item.update(
                {
                    "kind": "mesh",
                    "path": str(stl_path),
                    "triangles": len(triangles),
                    "watertight": bool(mesh.is_watertight),
                    "winding_consistent": bool(mesh.is_winding_consistent),
                    "mixed_source_geometry": bool(profile["exact_faces"] and profile["mesh_faces"]),
                }
            )
        elif profile["exact_faces"]:
            brep_path = temp_dir / f"{index:04d}-{safe_name}.brep"
            moved = shape.moved(world_location)
            ok = BRepTools.Write_s(moved.wrapped, str(brep_path))
            if ok is False or not brep_path.exists() or brep_path.stat().st_size < 100:
                raise RuntimeError(f"Could not stage exact BREP component: {name}")
            item.update({"kind": "brep", "path": str(brep_path)})
        else:
            raise RuntimeError(f"Component {name} contains neither exact faces nor mesh triangles")
        items.append(item)

    manifest_path = temp_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"items": items}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path, {
        "source_component_count": len(items),
        "source_mesh_triangle_count": mesh_triangles,
    }


def _run_freecad_console_helper(
    project_dir: Path,
    temp_dir: Path,
    manifest_path: Path,
    output_path: Path,
    output_format: str,
    report_path: Path,
    progress_path: Path,
    tolerance: float,
    progress: Progress,
    should_cancel: CancelCheck | None,
    timeout_seconds: int,
    operation_label: str,
) -> tuple[int, str]:
    """Execute the FreeCAD helper through console stdin.

    Debian FreeCADCmd 1.0 can start successfully yet ignore a Python filename
    supplied as an ordinary file argument. Console stdin is the documented
    headless interpreter path and avoids both FreeCAD option parsing and file
    opening heuristics.
    """
    import subprocess

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "freecad_faceted_export.py"
    if not script_path.exists():
        raise RuntimeError("CascadeCAD FreeCAD faceted export helper is missing")

    storage_root = project_dir.parents[1]
    storage_root.mkdir(parents=True, exist_ok=True)
    config_home = storage_root / ".config"
    config_home.mkdir(parents=True, exist_ok=True)
    log_path = temp_dir / "freecad.log"
    env = os.environ.copy()
    env["HOME"] = str(storage_root)
    env["XDG_CONFIG_HOME"] = str(config_home)
    env["FREECAD_USER_HOME"] = str(storage_root)
    env.update(
        {
            "CASCADE_CAD_FREECAD_SCRIPT": str(script_path),
            "CASCADE_CAD_FREECAD_MANIFEST": str(manifest_path),
            "CASCADE_CAD_FREECAD_OUTPUT": str(output_path),
            "CASCADE_CAD_FREECAD_FORMAT": output_format,
            "CASCADE_CAD_FREECAD_REPORT": str(report_path),
            "CASCADE_CAD_FREECAD_PROGRESS": str(progress_path),
            "CASCADE_CAD_FREECAD_TOLERANCE": str(float(tolerance)),
        }
    )
    command = [_freecad_command(), "--console"]
    runner = (
        "import os, runpy\n"
        "runpy.run_path(os.environ['CASCADE_CAD_FREECAD_SCRIPT'], run_name='__main__')\n"
    )

    deadline = time.monotonic() + max(60, int(timeout_seconds))
    last_completed = -1
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=str(temp_dir),
            env=env,
            stdin=subprocess.PIPE,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            if process.stdin is None:
                raise RuntimeError("FreeCAD console stdin was not created")
            process.stdin.write(runner)
            process.stdin.flush()
            process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            while process.poll() is None:
                _check_long_job(should_cancel, deadline, operation_label)
                if progress_path.exists():
                    try:
                        status = __import__("json").loads(progress_path.read_text(encoding="utf-8"))
                        completed = int(status.get("completed", 0))
                        total = max(1, int(status.get("total", 1)))
                        if completed != last_completed:
                            last_completed = completed
                            percent = 42 + int(40 * completed / total)
                            progress(
                                min(82, percent),
                                status.get("message") or f"Converted {completed}/{total} components",
                            )
                    except (OSError, ValueError, TypeError):
                        pass
                time.sleep(0.5)
        except Exception:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            raise

    output_log = log_path.read_text(encoding="utf-8", errors="replace")
    return int(process.returncode or 0), output_log


def _run_freecad_part_export(
    project_dir: Path,
    export_assembly,
    destination: Path,
    output_format: str,
    progress: Progress,
    should_cancel: CancelCheck | None,
    max_triangles: int,
    timeout_seconds: int,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Run the FreeCAD Part converter with live progress and validation."""
    import json
    import tempfile

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"cascade-cad-{output_format}-",
        dir=str(destination.parent),
    ) as temp_name:
        temp_dir = Path(temp_name)
        manifest_path, source_report = _prepare_freecad_part_manifest(
            export_assembly,
            temp_dir,
            progress,
            should_cancel,
            max_triangles=max_triangles,
        )
        temp_output = temp_dir / destination.name
        report_path = temp_dir / "report.json"
        progress_path = temp_dir / "progress.json"
        returncode, output_log = _run_freecad_console_helper(
            project_dir=project_dir,
            temp_dir=temp_dir,
            manifest_path=manifest_path,
            output_path=temp_output,
            output_format=output_format,
            report_path=report_path,
            progress_path=progress_path,
            tolerance=tolerance,
            progress=progress,
            should_cancel=should_cancel,
            timeout_seconds=timeout_seconds,
            operation_label=f"{output_format.upper()} export",
        )

        if returncode != 0:
            error = ""
            if report_path.exists():
                try:
                    error = str(json.loads(report_path.read_text(encoding="utf-8")).get("error") or "")
                except Exception:
                    pass
            raise RuntimeError(
                f"FreeCAD {output_format.upper()} conversion failed: "
                f"{error or output_log[-3000:] or 'unknown FreeCAD error'}"
            )
        if not report_path.exists():
            log_tail = output_log[-3000:].strip()
            detail = f"; FreeCAD log: {log_tail}" if log_tail else ""
            raise RuntimeError(
                f"FreeCAD {output_format.upper()} conversion produced no validation report"
                f" (process exit {returncode}; helper was sent through console stdin){detail}"
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("failed"):
            raise RuntimeError(
                f"FreeCAD {output_format.upper()} conversion failed: "
                f"{report.get('error') or output_log[-3000:] or 'unknown helper error'}"
            )
        if not temp_output.exists() or temp_output.stat().st_size < 256:
            raise RuntimeError(f"FreeCAD created an empty {output_format.upper()} file")
        if int(report.get("face_count", 0)) <= 0:
            raise RuntimeError(f"FreeCAD {output_format.upper()} validation reopened no Part faces")
        if output_format == "fcstd" and int(report.get("mesh_object_count", 0)) != 0:
            raise RuntimeError("FCStd validation found Mesh::Feature objects instead of Part geometry")

        progress(88, f"Finalizing validated {output_format.upper()} file")
        os.replace(temp_output, destination)
        report.update(source_report)
        report["file_size"] = destination.stat().st_size
        return report


def _prepare_freecad_conversion_manifest(
    assembly,
    temp_dir: Path,
    progress: Progress,
    should_cancel: CancelCheck | None,
    max_triangles: int,
) -> tuple[Path, dict[str, Any]]:
    """Stage each shape-bearing XBF node in its local assembly coordinates."""
    import json
    import cadquery as cq
    import trimesh
    from OCP.BRepTools import BRepTools

    rows = []
    for component_id, child in assembly.objects.items():
        direct_shapes = list(child.shapes)
        if not direct_shapes:
            continue
        shape = direct_shapes[0] if len(direct_shapes) == 1 else cq.Compound.makeCompound(direct_shapes)
        rows.append((str(component_id), str(getattr(child, "name", None) or component_id), shape))
    if not rows:
        raise RuntimeError("The XBF assembly contains no shape-bearing components")

    items: list[dict[str, Any]] = []
    mesh_triangles = 0
    mesh_components = 0
    for index, (component_id, label, shape) in enumerate(rows, start=1):
        _check_long_job(should_cancel, None, "Faceted solid conversion")
        progress(
            12 + int(24 * (index - 1) / max(1, len(rows))),
            f"Preparing XBF component {index}/{len(rows)}",
        )
        profile = _shape_geometry_profile(shape)
        safe_name = _safe_component_name(label, index)
        item: dict[str, Any] = {"component_id": component_id, "name": label}
        if profile["mesh_faces"]:
            vertices, triangles = _component_mesh_data(
                shape,
                cq.Location(),
                include_exact=True,
                include_mesh=True,
            )
            vertices, triangles = _deduplicate_mesh_vertices(vertices, triangles)
            if not vertices or not triangles:
                raise RuntimeError(f"Component {label} contains no usable triangles")
            mesh_triangles += len(triangles)
            mesh_components += 1
            if mesh_triangles > int(max_triangles):
                raise RuntimeError(
                    f"Faceted XBF conversion reached {mesh_triangles:,} triangles, above the safe limit of "
                    f"{int(max_triangles):,}. Convert a smaller project or raise "
                    "CASCADE_CAD_MAX_FACETED_STEP_TRIANGLES after confirming sufficient RAM."
                )
            mesh = trimesh.Trimesh(vertices=vertices, faces=triangles, process=False)
            stl_path = temp_dir / f"{index:04d}-{safe_name}.stl"
            mesh.export(stl_path, file_type="stl")
            item.update(
                {
                    "kind": "mesh",
                    "path": str(stl_path),
                    "triangles": len(triangles),
                    "watertight": bool(mesh.is_watertight),
                    "winding_consistent": bool(mesh.is_winding_consistent),
                    "mixed_source_geometry": bool(profile["exact_faces"] and profile["mesh_faces"]),
                }
            )
        elif profile["exact_faces"]:
            brep_path = temp_dir / f"{index:04d}-{safe_name}.brep"
            ok = BRepTools.Write_s(shape.wrapped, str(brep_path))
            if ok is False or not brep_path.exists() or brep_path.stat().st_size < 100:
                raise RuntimeError(f"Could not stage exact BREP component: {label}")
            item.update({"kind": "brep", "path": str(brep_path)})
        else:
            raise RuntimeError(f"Component {label} contains neither exact faces nor mesh triangles")
        items.append(item)

    manifest_path = temp_dir / "conversion-manifest.json"
    manifest_path.write_text(json.dumps({"items": items}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path, {
        "source_component_count": len(items),
        "source_component_ids": [item["component_id"] for item in items],
        "source_mesh_component_count": mesh_components,
        "source_mesh_triangle_count": mesh_triangles,
    }


def _run_freecad_parts_conversion(
    project_dir: Path,
    assembly,
    progress: Progress,
    should_cancel: CancelCheck | None,
    max_triangles: int,
    timeout_seconds: int,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Replace triangulation-only assembly objects with local faceted BREP shapes."""
    import json
    import tempfile
    import cadquery as cq

    work_parent = project_dir / "revisions"
    work_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cascade-cad-faceted-xbf-", dir=str(work_parent)) as temp_name:
        temp_dir = Path(temp_name)
        manifest_path, source_report = _prepare_freecad_conversion_manifest(
            assembly,
            temp_dir,
            progress,
            should_cancel,
            max_triangles=max_triangles,
        )
        if int(source_report.get("source_mesh_component_count", 0)) <= 0:
            return {**source_report, "changed": False, "parts": [], "mesh_triangle_count_after": 0}

        parts_dir = temp_dir / "converted-parts"
        report_path = temp_dir / "conversion-report.json"
        progress_path = temp_dir / "conversion-progress.json"
        returncode, output_log = _run_freecad_console_helper(
            project_dir=project_dir,
            temp_dir=temp_dir,
            manifest_path=manifest_path,
            output_path=parts_dir,
            output_format="parts",
            report_path=report_path,
            progress_path=progress_path,
            tolerance=tolerance,
            progress=progress,
            should_cancel=should_cancel,
            timeout_seconds=timeout_seconds,
            operation_label="Faceted solid conversion",
        )
        if returncode != 0:
            raise RuntimeError(
                "FreeCAD faceted XBF conversion failed: "
                f"{output_log[-3000:] or 'unknown FreeCAD error'}"
            )
        if not report_path.exists():
            raise RuntimeError(
                "FreeCAD faceted XBF conversion produced no validation report "
                f"(process exit {returncode}; helper was sent through console stdin); "
                f"FreeCAD log: {output_log[-3000:].strip()}"
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("failed"):
            raise RuntimeError(f"FreeCAD faceted XBF conversion failed: {report.get('error')}")
        parts = list(report.get("parts") or [])
        expected = set(source_report.get("source_component_ids") or [])
        received = {str(item.get("component_id") or "") for item in parts}
        if received != expected:
            missing = sorted(expected - received)
            raise RuntimeError(
                "FreeCAD faceted XBF conversion did not return every component"
                + (f": {missing[0]}" if missing else "")
            )

        for index, item in enumerate(parts, start=1):
            _check_long_job(should_cancel, None, "Faceted solid conversion")
            component_id = str(item.get("component_id") or "")
            child = assembly.objects.get(component_id)
            if child is None:
                raise RuntimeError(f"Converted XBF component disappeared: {component_id}")
            filename = Path(str(item.get("file") or "")).name
            part_path = parts_dir / filename
            if not filename or not part_path.exists():
                raise RuntimeError(f"Converted component BREP is missing: {component_id}")
            converted = cq.Shape.importBrep(str(part_path))
            profile = _shape_geometry_profile(converted)
            if profile["mesh_faces"]:
                raise RuntimeError(f"Converted component still contains triangulation-only faces: {component_id}")
            child.obj = converted
            child.metadata = {
                **dict(getattr(child, "metadata", {}) or {}),
                "CASCADE_Representation": str(item.get("representation") or "faceted-brep"),
            }
            progress(48 + int(20 * index / max(1, len(parts))), f"Installing faceted component {index}/{len(parts)}")

        after = _assembly_step_profile(assembly)
        if int(after.get("mesh_triangle_count", 0)) != 0:
            raise RuntimeError("Converted XBF still contains triangulation-only mesh remnants")
        report.update(source_report)
        report.update(
            {
                "changed": True,
                "converted_component_count": len(parts),
                "mesh_triangle_count_after": 0,
            }
        )
        return report

def export_brep(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any] | None,
    progress: Progress,
    component_ids: list[str] | None = None,
    should_cancel: CancelCheck | None = None,
    max_triangles: int = 750_000,
    timeout_seconds: int = 3600,
    *,
    fast_render: bool = False,
    faceted_workers: int = 2,
    faceted_queue_depth: int = 60,
    faceted_memory_budget_gb: float = 10.0,
    faceted_cache_enabled: bool = True,
    faceted_cache_max_bytes: int = 20 * 1024**3,
    faceted_direct_ocp: bool = True,
    faceted_freecad_fallback: bool = True,
    faceted_unify_same_domain: bool = True,
) -> dict[str, Any]:
    """Write validated Open CASCADE BREP without relaunching FreeCAD."""
    import cadquery as cq
    from OCP.BRepTools import BRepTools

    export_assembly, selected, scope = _load_export_assembly(
        project_dir, editor_state, component_ids, progress
    )
    conversion_report = _prepare_faceted_export_assembly(
        project_dir,
        export_assembly,
        progress,
        should_cancel,
        max_triangles,
        timeout_seconds,
        fast_render=fast_render,
        faceted_workers=faceted_workers,
        faceted_queue_depth=faceted_queue_depth,
        faceted_memory_budget_gb=faceted_memory_budget_gb,
        faceted_cache_enabled=faceted_cache_enabled,
        faceted_cache_max_bytes=faceted_cache_max_bytes,
        faceted_direct_ocp=faceted_direct_ocp,
        faceted_freecad_fallback=faceted_freecad_fallback,
        faceted_unify_same_domain=faceted_unify_same_domain,
    )
    filename = "selected.brep" if selected else "project.brep"
    destination = project_dir / "exports" / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = list(export_assembly)
    shapes = [shape.moved(world_location) for shape, _name, world_location, _color in rows]
    if not shapes:
        raise RuntimeError("BREP export contains no Part geometry")
    combined = shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    progress(84, "Writing cached faceted BREP assembly")
    ok = BRepTools.Write_s(combined.wrapped, str(temporary))
    if ok is False or not temporary.exists() or temporary.stat().st_size < 100:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Open CASCADE BREP writer produced an empty file")
    reopened = cq.Shape.importBrep(str(temporary))
    if reopened.isNull() or not reopened.Faces():
        temporary.unlink(missing_ok=True)
        raise RuntimeError("BREP validation reopened no Part faces")
    os.replace(temporary, destination)
    return {
        "format": "brep",
        "scope": scope,
        "selected_component_ids": selected,
        "geometry_kind": str(geometry_kind or "unknown"),
        "relative_path": f"exports/{filename}",
        "file_size": destination.stat().st_size,
        "component_count": len(rows),
        "face_count": len(reopened.Faces()),
        "shell_count": len(reopened.Shells()),
        "solid_count": len(reopened.Solids()),
        "writer_mode": "direct-ocp-brep",
        "fast_render": bool(fast_render),
        "faceted_conversion": conversion_report,
    }

def _csg_number(value: float) -> str:
    return format(float(value), ".9g")


def _csg_triangle_area_squared(vertices, triangle) -> float:
    a, b, c = triangle
    ax, ay, az = vertices[a]
    bx, by, bz = vertices[b]
    cx, cy, cz = vertices[c]
    abx, aby, abz = bx - ax, by - ay, bz - az
    acx, acy, acz = cx - ax, cy - ay, cz - az
    nx = aby * acz - abz * acy
    ny = abz * acx - abx * acz
    nz = abx * acy - aby * acx
    return nx * nx + ny * ny + nz * nz


def _csg_signed_volume(vertices, triangles) -> float:
    """Return signed volume using right-hand triangle orientation."""
    volume6 = 0.0
    for a, b, c in triangles:
        ax, ay, az = vertices[a]
        bx, by, bz = vertices[b]
        cx, cy, cz = vertices[c]
        volume6 += (
            ax * (by * cz - bz * cy)
            + ay * (bz * cx - bx * cz)
            + az * (bx * cy - by * cx)
        )
    return volume6 / 6.0


def _prepare_csg_polyhedra(vertices, triangles) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create closed, consistently oriented OpenSCAD polyhedra.

    FreeCAD's OpenSCAD importer calls Part.makeShell() and Part.Solid() once for
    each polyhedron.  A single polyhedron must therefore describe exactly one
    connected, closed, orientable two-manifold shell.  This helper removes bad
    facets, splits disconnected shells, fixes local winding, verifies every
    edge is shared by exactly two facets, and emits OpenSCAD's clockwise-from-
    outside winding (negative right-hand signed volume).
    """
    welded_vertices, welded_triangles = _deduplicate_mesh_vertices(vertices, triangles, digits=7)
    stats: dict[str, Any] = {
        "input_vertex_count": len(vertices),
        "input_triangle_count": len(triangles),
        "welded_vertex_count": len(welded_vertices),
        "weld_decimal_digits": 7,
        # Coordinate welding can collapse a facet to fewer than three unique
        # vertices; _deduplicate_mesh_vertices intentionally removes it.
        "degenerate_triangle_count": max(0, len(triangles) - len(welded_triangles)),
        "duplicate_triangle_count": 0,
        "invalid_index_triangle_count": 0,
        "shell_count": 0,
        "closed_shell_count": 0,
        "open_shell_count": 0,
        "nonmanifold_shell_count": 0,
        "nonorientable_shell_count": 0,
        "zero_volume_shell_count": 0,
        "boundary_edge_count": 0,
        "nonmanifold_edge_count": 0,
        "reoriented_triangle_count": 0,
    }
    if not welded_vertices or not welded_triangles:
        return [], stats

    xs = [point[0] for point in welded_vertices]
    ys = [point[1] for point in welded_vertices]
    zs = [point[2] for point in welded_vertices]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dz = max(zs) - min(zs)
    diagonal2 = dx * dx + dy * dy + dz * dz
    area2_epsilon = max(1.0e-30, diagonal2 * diagonal2 * 1.0e-28)
    volume_epsilon = max(1.0e-18, (diagonal2 ** 1.5) * 1.0e-15)

    cleaned: list[tuple[int, int, int]] = []
    seen_faces: set[tuple[int, int, int]] = set()
    vertex_count = len(welded_vertices)
    for raw in welded_triangles:
        try:
            a, b, c = (int(raw[0]), int(raw[1]), int(raw[2]))
        except Exception:
            stats["invalid_index_triangle_count"] += 1
            continue
        if min(a, b, c) < 0 or max(a, b, c) >= vertex_count:
            stats["invalid_index_triangle_count"] += 1
            continue
        if a == b or b == c or c == a or _csg_triangle_area_squared(welded_vertices, (a, b, c)) <= area2_epsilon:
            stats["degenerate_triangle_count"] += 1
            continue
        canonical = tuple(sorted((a, b, c)))
        if canonical in seen_faces:
            stats["duplicate_triangle_count"] += 1
            continue
        seen_faces.add(canonical)
        cleaned.append((a, b, c))

    if not cleaned:
        return [], stats

    # Union triangles sharing an edge so each disconnected shell becomes its
    # own top-level polyhedron instead of being forced into one invalid solid.
    parent = list(range(len(cleaned)))
    rank = [0] * len(cleaned)

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if rank[left_root] < rank[right_root]:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root
        if rank[left_root] == rank[right_root]:
            rank[left_root] += 1

    edge_to_entries: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for triangle_index, (a, b, c) in enumerate(cleaned):
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            direction = 0 if (u, v) == key else 1
            entries = edge_to_entries.setdefault(key, [])
            if entries:
                union(entries[0][0], triangle_index)
            entries.append((triangle_index, direction))

    groups: dict[int, list[int]] = {}
    for triangle_index in range(len(cleaned)):
        groups.setdefault(find(triangle_index), []).append(triangle_index)

    polyhedra: list[dict[str, Any]] = []
    for shell_number, shell_indices in enumerate(groups.values(), start=1):
        stats["shell_count"] += 1
        shell_set = set(shell_indices)
        shell_edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for edge, entries in edge_to_entries.items():
            selected = [entry for entry in entries if entry[0] in shell_set]
            if selected:
                shell_edges[edge] = selected

        boundary_edges = sum(1 for entries in shell_edges.values() if len(entries) == 1)
        nonmanifold_edges = sum(1 for entries in shell_edges.values() if len(entries) > 2)
        stats["boundary_edge_count"] += boundary_edges
        stats["nonmanifold_edge_count"] += nonmanifold_edges
        if nonmanifold_edges:
            stats["nonmanifold_shell_count"] += 1
            continue
        if boundary_edges:
            stats["open_shell_count"] += 1
            continue

        adjacency: dict[int, list[tuple[int, int, int]]] = {index: [] for index in shell_indices}
        for entries in shell_edges.values():
            if len(entries) != 2:
                continue
            (left, left_direction), (right, right_direction) = entries
            adjacency[left].append((right, left_direction, right_direction))
            adjacency[right].append((left, right_direction, left_direction))

        flips: dict[int, int] = {}
        orientable = True
        for seed in shell_indices:
            if seed in flips:
                continue
            flips[seed] = 0
            stack = [seed]
            while stack and orientable:
                current = stack.pop()
                current_flip = flips[current]
                for neighbor, current_direction, neighbor_direction in adjacency[current]:
                    required = current_flip ^ current_direction ^ neighbor_direction ^ 1
                    previous = flips.get(neighbor)
                    if previous is None:
                        flips[neighbor] = required
                        stack.append(neighbor)
                    elif previous != required:
                        orientable = False
                        break
        if not orientable:
            stats["nonorientable_shell_count"] += 1
            continue

        oriented = []
        local_reoriented = 0
        for index in shell_indices:
            a, b, c = cleaned[index]
            if flips.get(index, 0):
                oriented.append((a, c, b))
                local_reoriented += 1
            else:
                oriented.append((a, b, c))

        signed_volume = _csg_signed_volume(welded_vertices, oriented)
        if abs(signed_volume) <= volume_epsilon:
            stats["zero_volume_shell_count"] += 1
            continue

        # OpenSCAD documents clockwise point order when viewed from outside.
        # That is negative signed volume under the right-hand convention.
        if signed_volume > 0.0:
            oriented = [(a, c, b) for a, b, c in oriented]
            local_reoriented += len(oriented)
            signed_volume = -signed_volume

        used = sorted({vertex for triangle in oriented for vertex in triangle})
        remap = {old: new for new, old in enumerate(used)}
        compact_vertices = [welded_vertices[index] for index in used]
        compact_triangles = [tuple(remap[index] for index in triangle) for triangle in oriented]
        polyhedra.append(
            {
                "shell_index": shell_number,
                "vertices": compact_vertices,
                "triangles": compact_triangles,
                "signed_volume": float(signed_volume),
            }
        )
        stats["closed_shell_count"] += 1
        stats["reoriented_triangle_count"] += local_reoriented

    return polyhedra, stats


def _write_csg_polyhedron(handle, vertices, triangles) -> None:
    """Write one validated FreeCAD/OpenSCAD-compatible polyhedron."""
    handle.write("polyhedron(points=[\n")
    for index, (x, y, z) in enumerate(vertices):
        suffix = "," if index + 1 < len(vertices) else ""
        handle.write(
            f"  [{_csg_number(x)},{_csg_number(y)},{_csg_number(z)}]{suffix}\n"
        )
    handle.write("], faces=[\n")
    for index, (a, b, c) in enumerate(triangles):
        suffix = "," if index + 1 < len(triangles) else ""
        handle.write(f"  [{a},{b},{c}]{suffix}\n")
    handle.write("], convexity=10);\n\n")


def export_csg(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any] | None,
    progress: Progress,
    component_ids: list[str] | None = None,
    should_cancel: CancelCheck | None = None,
    max_triangles: int = 10_000_000,
) -> dict[str, Any]:
    """Write one top-level polyhedron for each closed connected shell.

    FreeCAD's importer turns every polyhedron into one Part shell and then one
    Part solid. Disconnected, open, non-manifold, or inconsistently wound face
    sets must not be placed in the same polyhedron. Invalid CSG is discarded
    rather than offered as a misleading belt/strip-shaped model.
    """
    import json

    export_assembly, selected, scope = _load_export_assembly(
        project_dir, editor_state, component_ids, progress
    )
    filename = "selected.csg" if selected else "project.csg"
    destination = project_dir / "exports" / filename
    temp = destination.with_name(f".{destination.name}.{time.time_ns()}.tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = list(export_assembly)
    total_input_triangles = 0
    total_output_triangles = 0
    source_component_count = 0
    polyhedron_count = 0
    aggregate = {
        "shell_count": 0,
        "closed_shell_count": 0,
        "open_shell_count": 0,
        "nonmanifold_shell_count": 0,
        "nonorientable_shell_count": 0,
        "zero_volume_shell_count": 0,
        "boundary_edge_count": 0,
        "nonmanifold_edge_count": 0,
        "degenerate_triangle_count": 0,
        "duplicate_triangle_count": 0,
        "invalid_index_triangle_count": 0,
        "reoriented_triangle_count": 0,
    }
    invalid_components: list[str] = []

    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("// CascadeCAD OpenSCAD-compatible CSG solid export\n")
            handle.write("// Every top-level polyhedron is one closed connected manifold shell.\n")
            handle.write("// Triangle winding follows OpenSCAD's clockwise-from-outside rule.\n\n")
            for index, (shape, name, world_location, _color) in enumerate(rows, start=1):
                _check_long_job(should_cancel, None, "CSG export")
                progress(
                    18 + int(62 * (index - 1) / max(1, len(rows))),
                    f"Validating CSG solid {index}/{len(rows)}",
                )
                vertices, triangles = _component_mesh_data(shape, world_location)
                if not vertices or not triangles:
                    continue
                source_component_count += 1
                total_input_triangles += len(triangles)
                if total_input_triangles > int(max_triangles):
                    raise RuntimeError(
                        f"CSG export reached {total_input_triangles:,} triangles, above the configured limit of "
                        f"{int(max_triangles):,}. Export a smaller selection or raise CASCADE_CAD_MAX_CSG_TRIANGLES."
                    )

                polyhedra, stats = _prepare_csg_polyhedra(vertices, triangles)
                for key in aggregate:
                    aggregate[key] += int(stats.get(key, 0))
                invalid_shells = (
                    int(stats.get("open_shell_count", 0))
                    + int(stats.get("nonmanifold_shell_count", 0))
                    + int(stats.get("nonorientable_shell_count", 0))
                    + int(stats.get("zero_volume_shell_count", 0))
                )
                if invalid_shells:
                    invalid_components.append(
                        f"{name}: open={stats['open_shell_count']}, "
                        f"non-manifold={stats['nonmanifold_shell_count']}, "
                        f"non-orientable={stats['nonorientable_shell_count']}, "
                        f"zero-volume={stats['zero_volume_shell_count']}, "
                        f"boundary-edges={stats['boundary_edge_count']}"
                    )
                    continue
                if not polyhedra:
                    invalid_components.append(f"{name}: no closed solid shell was found")
                    continue

                for shell_ordinal, polyhedron in enumerate(polyhedra, start=1):
                    polyhedron_count += 1
                    output_triangles = polyhedron["triangles"]
                    total_output_triangles += len(output_triangles)
                    metadata = json.dumps(
                        {
                            "index": polyhedron_count,
                            "component_id": str(name),
                            "name": str(name),
                            "shell": shell_ordinal,
                            "component_shell_count": len(polyhedra),
                        },
                        ensure_ascii=True,
                        separators=(",", ":"),
                    )
                    handle.write(f"// CASCADE_CAD_PART {metadata}\n")
                    _write_csg_polyhedron(
                        handle,
                        polyhedron["vertices"],
                        output_triangles,
                    )

        if invalid_components:
            preview = "; ".join(invalid_components[:4])
            if len(invalid_components) > 4:
                preview += f"; plus {len(invalid_components) - 4} more"
            raise RuntimeError(
                "CSG solid export was stopped because FreeCAD/OpenSCAD polyhedron() requires "
                "closed manifold shells. Repair/fill the listed mesh shells, or run Convert to "
                f"Tessellated (Faceted) Solids and repair any retained open shells. Details: {preview}"
            )
        if total_output_triangles == 0 or polyhedron_count == 0:
            raise RuntimeError("CSG export produced no closed manifold polyhedron solids")
        if (
            temp.stat().st_size < 100
            or temp.read_text(encoding="utf-8", errors="ignore").count("polyhedron(") != polyhedron_count
        ):
            raise RuntimeError("CSG validation did not find the expected separate polyhedron solids")
        os.replace(temp, destination)
    except Exception:
        temp.unlink(missing_ok=True)
        raise

    return {
        "format": "csg",
        "scope": scope,
        "selected_component_ids": selected,
        "geometry_kind": str(geometry_kind or "unknown"),
        "source_component_count": source_component_count,
        "triangle_count": total_output_triangles,
        "input_triangle_count": total_input_triangles,
        "part_count": polyhedron_count,
        "polyhedron_count": polyhedron_count,
        "file_size": destination.stat().st_size,
        "relative_path": f"exports/{filename}",
        "representation": "separate closed manifold OpenSCAD polyhedron solids",
        "topology_validation": aggregate,
    }

def _freecad_command() -> str:
    candidates = [
        shutil.which("freecadcmd-python3"),
        shutil.which("freecadcmd"),
        "/usr/lib/freecad/bin/freecadcmd-python3",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("BREP/FCStd solid export requires Debian package freecad-python3")


def export_fcstd(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any] | None,
    progress: Progress,
    component_ids: list[str] | None = None,
    should_cancel: CancelCheck | None = None,
    max_triangles: int = 750_000,
    timeout_seconds: int = 3600,
    *,
    fast_render: bool = False,
    faceted_workers: int = 2,
    faceted_queue_depth: int = 60,
    faceted_memory_budget_gb: float = 10.0,
    faceted_cache_enabled: bool = True,
    faceted_cache_max_bytes: int = 20 * 1024**3,
    faceted_direct_ocp: bool = True,
    faceted_freecad_fallback: bool = True,
    faceted_unify_same_domain: bool = True,
) -> dict[str, Any]:
    """Create a real Part-based FCStd document.

    Pure exact components remain exact Part::Feature objects. Closed mesh
    shells are converted to faceted Part solids; open shells remain faceted
    Part shells, including when both occur in one component. Components with
    exact and triangulated faces are exported entirely as faceted geometry to
    avoid duplicate subfaces. No Mesh::Feature objects are written.
    """
    export_assembly, selected, scope = _load_export_assembly(
        project_dir, editor_state, component_ids, progress
    )
    conversion_report = _prepare_faceted_export_assembly(
        project_dir,
        export_assembly,
        progress,
        should_cancel,
        max_triangles,
        timeout_seconds,
        fast_render=fast_render,
        faceted_workers=faceted_workers,
        faceted_queue_depth=faceted_queue_depth,
        faceted_memory_budget_gb=faceted_memory_budget_gb,
        faceted_cache_enabled=faceted_cache_enabled,
        faceted_cache_max_bytes=faceted_cache_max_bytes,
        faceted_direct_ocp=faceted_direct_ocp,
        faceted_freecad_fallback=faceted_freecad_fallback,
        faceted_unify_same_domain=faceted_unify_same_domain,
    )
    filename = "selected.FCStd" if selected else "project.FCStd"
    destination = project_dir / "exports" / filename
    report = _run_freecad_part_export(
        project_dir,
        export_assembly,
        destination,
        "fcstd",
        progress,
        should_cancel,
        max_triangles=max_triangles,
        timeout_seconds=timeout_seconds,
    )
    report.update(
        {
            "format": "fcstd",
            "scope": scope,
            "selected_component_ids": selected,
            "geometry_kind": str(geometry_kind or "unknown"),
            "relative_path": f"exports/{filename}",
            "fast_render": bool(fast_render),
            "faceted_conversion": conversion_report,
        }
    )
    return report


def convert_to_faceted_solids(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any] | None,
    preview_tolerance: float,
    preview_angular_tolerance: float,
    progress: Progress,
    should_cancel: CancelCheck | None = None,
    max_triangles: int = 750_000,
    timeout_seconds: int = 3600,
    *,
    fast_render: bool = False,
    faceted_workers: int = 2,
    faceted_queue_depth: int = 60,
    faceted_memory_budget_gb: float = 10.0,
    faceted_cache_enabled: bool = True,
    faceted_cache_max_bytes: int = 20 * 1024**3,
    faceted_direct_ocp: bool = True,
    faceted_freecad_fallback: bool = True,
    faceted_unify_same_domain: bool = True,
) -> dict[str, Any]:
    """Rewrite mesh-backed XBF parts as faceted BREP solids or shells.

    Exact BREP components remain exact. Closed triangulated shells become
    faceted solids, while unavoidable open shells remain BREP shells. The
    committed master.xbf and browser preview are replaced atomically after a
    revision snapshot is created.
    """
    import cadquery as cq

    master = project_dir / "master.xbf"
    preview = project_dir / "previews" / "overview.glb"
    if not master.exists():
        raise FileNotFoundError("Project master.xbf is missing")
    progress(6, "Opening XBF master")
    assembly = cq.Assembly.load(str(master), importType="XBF")
    if editor_state:
        progress(10, "Applying working editor changes")
        apply_editor_state(assembly, editor_state)

    before = _assembly_step_profile(assembly)
    before_triangles = int(before.get("mesh_triangle_count", 0))
    before_mesh_faces = int(before.get("mesh_face_count", 0))
    if before_triangles <= 0:
        progress(92, "No triangulation-only XBF remnants found")
        resulting_kind = "exact" if geometry_kind in {"unknown", "mesh", "mixed"} else geometry_kind
        return {
            "changed": False,
            "components": _assembly_components(assembly, resulting_kind),
            "geometry_kind": resulting_kind,
            "revision_id": None,
            "source_mesh_triangle_count": 0,
            "source_mesh_face_count": 0,
            "mesh_triangle_count_after": 0,
            "message": "XBF already contains BREP geometry; no conversion was needed",
        }

    progress(14, f"Converting {before_triangles:,} mesh triangles into faceted BREP")
    report = _convert_assembly_meshes(
        project_dir=project_dir,
        assembly=assembly,
        progress=progress,
        should_cancel=should_cancel,
        max_triangles=max_triangles,
        timeout_seconds=timeout_seconds,
        workers=faceted_workers,
        queue_depth=faceted_queue_depth,
        memory_budget_gb=faceted_memory_budget_gb,
        cache_enabled=faceted_cache_enabled,
        cache_max_bytes=faceted_cache_max_bytes,
        direct_ocp=faceted_direct_ocp,
        freecad_fallback=faceted_freecad_fallback,
        fast_render=fast_render,
        unify_same_domain=faceted_unify_same_domain,
    )
    after = _assembly_step_profile(assembly)
    if int(after.get("mesh_triangle_count", 0)) != 0:
        raise RuntimeError("Faceted conversion validation found remaining triangulation-only faces")

    progress(72, "Creating revision snapshot")
    revision_id = _snapshot(project_dir, "Before converting XBF mesh remnants to faceted BREP")
    progress(78, "Writing faceted BREP XBF master")
    _atomic_export(assembly, master, "XBF")
    progress(88, "Regenerating browser preview")
    _atomic_export(
        assembly,
        preview,
        "GLB",
        tolerance=preview_tolerance,
        angularTolerance=preview_angular_tolerance,
    )
    progress(96, "Verifying converted XBF component metadata")
    components = _assembly_components(assembly, "faceted-brep")
    open_shells = int(report.get("faceted_open_shell_count", 0))
    solid_count = int(report.get("solid_count", 0))
    report.update(
        {
            "source_mesh_face_count": before_mesh_faces,
            "source_mesh_triangle_count": before_triangles,
            "mesh_triangle_count_after": 0,
            "changed": True,
            "revision_id": revision_id,
        }
    )
    suffix = f"; {open_shells} open shell(s) retained" if open_shells else ""
    return {
        **report,
        "components": components,
        "geometry_kind": "faceted-brep",
        "revision_id": revision_id,
        "message": (
            f"Converted XBF mesh remnants into {solid_count} faceted BREP solid(s){suffix} "
            f"using {report.get('backend', 'faceted conversion')}"
            + (" with FastSewing" if fast_render else "")
        ),
    }

def export_project_file(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any] | None,
    progress: Progress,
    export_format: str,
    component_ids: list[str] | None = None,
    unit_system: str = "imperial",
    should_cancel: CancelCheck | None = None,
    max_faceted_triangles: int = 5_000_000,
    step_timeout_seconds: int = 3600,
    faceted_chunk_triangles: int = 1000,
    max_csg_triangles: int = 10_000_000,
    *,
    fast_render: bool = False,
    faceted_workers: int = 2,
    faceted_queue_depth: int = 60,
    faceted_memory_budget_gb: float = 10.0,
    faceted_cache_enabled: bool = True,
    faceted_cache_max_bytes: int = 20 * 1024**3,
    faceted_direct_ocp: bool = True,
    faceted_freecad_fallback: bool = True,
    faceted_unify_same_domain: bool = True,
) -> dict[str, Any]:
    export_format = str(export_format).lower().lstrip(".")
    if export_format == "step":
        return export_step(
            project_dir,
            geometry_kind,
            editor_state,
            progress,
            component_ids,
            max_faceted_triangles=max_faceted_triangles,
            should_cancel=should_cancel,
            timeout_seconds=step_timeout_seconds,
            chunk_triangles=faceted_chunk_triangles,
            fast_render=fast_render,
            faceted_workers=faceted_workers,
            faceted_queue_depth=faceted_queue_depth,
            faceted_memory_budget_gb=faceted_memory_budget_gb,
            faceted_cache_enabled=faceted_cache_enabled,
            faceted_cache_max_bytes=faceted_cache_max_bytes,
            faceted_direct_ocp=faceted_direct_ocp,
            faceted_freecad_fallback=faceted_freecad_fallback,
            faceted_unify_same_domain=faceted_unify_same_domain,
            unit_system=unit_system,
        )
    if export_format == "xbf":
        return export_xbf(project_dir, geometry_kind, editor_state, progress, component_ids, should_cancel)
    if export_format == "brep":
        return export_brep(
            project_dir,
            geometry_kind,
            editor_state,
            progress,
            component_ids,
            should_cancel,
            max_triangles=max_faceted_triangles,
            timeout_seconds=step_timeout_seconds,
            fast_render=fast_render,
            faceted_workers=faceted_workers,
            faceted_queue_depth=faceted_queue_depth,
            faceted_memory_budget_gb=faceted_memory_budget_gb,
            faceted_cache_enabled=faceted_cache_enabled,
            faceted_cache_max_bytes=faceted_cache_max_bytes,
            faceted_direct_ocp=faceted_direct_ocp,
            faceted_freecad_fallback=faceted_freecad_fallback,
            faceted_unify_same_domain=faceted_unify_same_domain,
        )
    if export_format == "csg":
        return export_csg(
            project_dir,
            geometry_kind,
            editor_state,
            progress,
            component_ids,
            should_cancel,
            max_triangles=max_csg_triangles,
        )
    if export_format == "fcstd":
        return export_fcstd(
            project_dir,
            geometry_kind,
            editor_state,
            progress,
            component_ids,
            should_cancel,
            max_triangles=max_faceted_triangles,
            timeout_seconds=step_timeout_seconds,
            fast_render=fast_render,
            faceted_workers=faceted_workers,
            faceted_queue_depth=faceted_queue_depth,
            faceted_memory_budget_gb=faceted_memory_budget_gb,
            faceted_cache_enabled=faceted_cache_enabled,
            faceted_cache_max_bytes=faceted_cache_max_bytes,
            faceted_direct_ocp=faceted_direct_ocp,
            faceted_freecad_fallback=faceted_freecad_fallback,
            faceted_unify_same_domain=faceted_unify_same_domain,
        )
    raise ValueError(f"Unsupported export format: {export_format}")

def _parameter_number(parameters: dict[str, Any], name: str, default: float, minimum: float = 0.000001) -> float:
    value = float(parameters.get(name, default))
    if not math.isfinite(value) or value < minimum or value > 1.0e9:
        raise ValueError(f"{name} must be between {minimum} and 1e9")
    return value


def _parameter_vector(parameters: dict[str, Any], name: str = "position") -> tuple[float, float, float]:
    raw = parameters.get(name, [0.0, 0.0, 0.0])
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise ValueError(f"{name} must contain X, Y, and Z")
    values = tuple(float(item) for item in raw)
    if not all(math.isfinite(item) and abs(item) <= 1.0e9 for item in values):
        raise ValueError(f"{name} contains an invalid coordinate")
    return values



def _parameter_integer(
    parameters: dict[str, Any],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = int(float(parameters.get(name, default)))
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _parameter_bool(parameters: dict[str, Any], name: str, default: bool = False) -> bool:
    value = parameters.get(name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parameter_plane(parameters: dict[str, Any], name: str = "plane", default: str = "XY") -> str:
    plane = str(parameters.get(name, default)).strip().upper()
    if plane not in {"XY", "XZ", "YZ"}:
        raise ValueError(f"{name} must be XY, XZ, or YZ")
    return plane


def _parse_point_list(
    parameters: dict[str, Any],
    *,
    minimum: int,
    maximum: int = 500,
) -> list[tuple[float, float, float]]:
    raw = parameters.get("points")
    if isinstance(raw, str):
        rows = [row.strip() for row in raw.replace("\n", ";").split(";") if row.strip()]
        parsed: list[tuple[float, float, float]] = []
        for index, row in enumerate(rows, start=1):
            parts = [item.strip() for item in row.split(",")]
            if len(parts) not in {2, 3}:
                raise ValueError(f"Point {index} must be X,Y or X,Y,Z")
            values = [float(item) for item in parts]
            if len(values) == 2:
                values.append(0.0)
            if not all(math.isfinite(item) and abs(item) <= 1.0e9 for item in values):
                raise ValueError(f"Point {index} contains an invalid coordinate")
            parsed.append((values[0], values[1], values[2]))
    elif isinstance(raw, (list, tuple)):
        parsed = []
        for index, row in enumerate(raw, start=1):
            if not isinstance(row, (list, tuple)) or len(row) not in {2, 3}:
                raise ValueError(f"Point {index} must contain X,Y or X,Y,Z")
            values = [float(item) for item in row]
            if len(values) == 2:
                values.append(0.0)
            if not all(math.isfinite(item) and abs(item) <= 1.0e9 for item in values):
                raise ValueError(f"Point {index} contains an invalid coordinate")
            parsed.append((values[0], values[1], values[2]))
    else:
        raise ValueError("points must be a semicolon-separated X,Y,Z list")
    if len(parsed) < minimum or len(parsed) > maximum:
        raise ValueError(f"points must contain between {minimum} and {maximum} coordinates")
    return parsed


def _normalized_vector(value: tuple[float, float, float], name: str) -> tuple[float, float, float]:
    length = math.sqrt(sum(item * item for item in value))
    if length <= 1.0e-12:
        raise ValueError(f"{name} must not be a zero vector")
    return tuple(item / length for item in value)


def _make_draft_shape(operation: str, parameters: dict[str, Any]):
    import cadquery as cq

    position = _parameter_vector(parameters)
    location = cq.Location(cq.Vector(*position))
    if operation == "line":
        points = _parse_point_list(parameters, minimum=2, maximum=2)
        return cq.Edge.makeLine(cq.Vector(*points[0]), cq.Vector(*points[1]))
    if operation == "bspline":
        points = _parse_point_list(parameters, minimum=3)
        return cq.Edge.makeSpline([cq.Vector(*point) for point in points])
    if operation == "polyline":
        points = _parse_point_list(parameters, minimum=2)
        close = _parameter_bool(parameters, "close", False)
        return cq.Wire.makePolygon([cq.Vector(*point) for point in points], close=close)

    plane = _parameter_plane(parameters)
    workplane = cq.Workplane(plane)
    if operation == "circle":
        radius = _parameter_number(parameters, "radius", 50.0)
        wire = workplane.circle(radius).val()
    elif operation == "rectangle":
        width = _parameter_number(parameters, "width", 100.0)
        height = _parameter_number(parameters, "height", width)
        wire = workplane.rect(width, height).val()
    elif operation == "polygon":
        sides = _parameter_integer(parameters, "sides", 6, 3, 256)
        radius = _parameter_number(parameters, "radius", 50.0)
        wire = workplane.polygon(sides, radius * 2.0).val()
    elif operation == "ellipse":
        x_radius = _parameter_number(parameters, "x_radius", 60.0)
        y_radius = _parameter_number(parameters, "y_radius", 35.0)
        wire = workplane.ellipse(x_radius, y_radius).val()
    else:
        raise ValueError(f"Unsupported draft operation: {operation}")
    # Closed draft profiles are stored as exact planar faces so they remain
    # visible in the GLB preview and can be consumed directly by solid tools.
    face = cq.Face.makeFromWires(wire)
    return face.moved(location)


def _largest_shape(items: list[Any], metric: str):
    if not items:
        return None
    def value(item):
        try:
            return float(getattr(item, metric)())
        except Exception:
            return 0.0
    return max(items, key=value)


def _profile_wire(shape, *, require_closed: bool = True):
    import cadquery as cq

    faces = list(shape.Faces())
    if faces:
        face = _largest_shape(faces, "Area")
        wire = face.outerWire()
    else:
        wires = list(shape.Wires())
        wire = _largest_shape(wires, "Length")
        if wire is None:
            edges = list(shape.Edges())
            if not edges:
                raise ValueError("Selected component contains no profile edge or wire")
            wire = cq.Wire.assembleEdges(edges)
    if require_closed:
        try:
            closed = bool(wire.IsClosed())
        except Exception:
            closed = False
        if not closed:
            raise ValueError("Selected profile must be closed")
    return wire


def _profile_face(shape):
    import cadquery as cq

    faces = list(shape.Faces())
    if faces:
        return _largest_shape(faces, "Area")
    return cq.Face.makeFromWires(_profile_wire(shape, require_closed=True))


def _compound_or_single(shapes: list[Any]):
    import cadquery as cq

    usable = [shape for shape in shapes if shape is not None]
    if not usable:
        raise ValueError("Modeling operation produced no usable geometry")
    return usable[0] if len(usable) == 1 else cq.Compound.makeCompound(usable)


def _extrude_selected(selected, parameters: dict[str, Any]):
    import cadquery as cq
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    distance = _parameter_number(parameters, "distance", 100.0)
    direction = _normalized_vector(_parameter_vector(parameters, "direction"), "direction")
    vector = gp_Vec(*(item * distance for item in direction))
    shapes = []
    for _component_id, _child, shape in selected:
        face = _profile_face(shape)
        shapes.append(cq.Shape.cast(BRepPrimAPI_MakePrism(face.wrapped, vector, True).Shape()))
    return _compound_or_single(shapes)


def _revolve_selected(selected, parameters: dict[str, Any]):
    import cadquery as cq
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    angle = _parameter_number(parameters, "angle", 360.0, minimum=0.001)
    if angle > 360.0:
        raise ValueError("angle must not exceed 360 degrees")
    start = _parameter_vector(parameters, "axis_start")
    end = _parameter_vector(parameters, "axis_end")
    direction = _normalized_vector(tuple(end[i] - start[i] for i in range(3)), "revolve axis")
    axis = gp_Ax1(gp_Pnt(*start), gp_Dir(*direction))
    shapes = []
    for _component_id, _child, shape in selected:
        face = _profile_face(shape)
        shapes.append(cq.Shape.cast(BRepPrimAPI_MakeRevol(face.wrapped, axis, math.radians(angle), True).Shape()))
    return _compound_or_single(shapes)


def _sweep_selected(selected, parameters: dict[str, Any]):
    import cadquery as cq
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell

    if len(selected) != 2:
        raise ValueError("Sweep requires exactly two selected components: primary profile, then path")
    profile = _profile_wire(selected[0][2], require_closed=True)
    path = _profile_wire(selected[1][2], require_closed=False)
    builder = BRepOffsetAPI_MakePipeShell(path.wrapped)
    builder.Add(profile.wrapped, False, False)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("Open CASCADE could not build the sweep")
    if not builder.MakeSolid():
        raise ValueError("Sweep profile did not produce a closed solid")
    return cq.Shape.cast(builder.Shape())


def _loft_selected(selected, parameters: dict[str, Any]):
    import cadquery as cq
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

    if len(selected) < 2:
        raise ValueError("Loft requires at least two selected closed profiles")
    builder = BRepOffsetAPI_ThruSections(True, False, 1.0e-7)
    for _component_id, _child, shape in selected:
        builder.AddWire(_profile_wire(shape, require_closed=True).wrapped)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("Open CASCADE could not build the loft")
    return cq.Shape.cast(builder.Shape())


def _cross_section_selected(selected, parameters: dict[str, Any]):
    import cadquery as cq
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    plane = _parameter_plane(parameters)
    offset = float(parameters.get("offset", 0.0))
    spacing = float(parameters.get("spacing", 10.0))
    count = _parameter_integer(parameters, "count", 1, 1, 200)
    if not math.isfinite(offset) or not math.isfinite(spacing) or abs(offset) > 1.0e9 or abs(spacing) > 1.0e9:
        raise ValueError("Cross-section offset or spacing is invalid")
    boxes = [shape.BoundingBox() for _component_id, _child, shape in selected]
    extent = max(
        [100.0]
        + [abs(value) for box in boxes for value in (box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax)]
    )
    span = max(1000.0, extent * 4.0)
    result_shapes = []
    for index in range(count):
        coordinate = offset + index * spacing
        if plane == "XY":
            pln = gp_Pln(gp_Pnt(0, 0, coordinate), gp_Dir(0, 0, 1))
        elif plane == "XZ":
            pln = gp_Pln(gp_Pnt(0, coordinate, 0), gp_Dir(0, 1, 0))
        else:
            pln = gp_Pln(gp_Pnt(coordinate, 0, 0), gp_Dir(1, 0, 0))
        cutting_face = BRepBuilderAPI_MakeFace(pln, -span, span, -span, span).Face()
        for _component_id, _child, shape in selected:
            section = BRepAlgoAPI_Section(shape.wrapped, cutting_face)
            section.Build()
            if section.IsDone():
                candidate = cq.Shape.cast(section.Shape())
                wires = list(candidate.Wires())
                if wires:
                    for wire in wires:
                        try:
                            result_shapes.append(cq.Face.makeFromWires(wire) if wire.IsClosed() else wire)
                        except Exception:
                            result_shapes.append(wire)
                elif candidate.Edges():
                    result_shapes.append(candidate)
    return _compound_or_single(result_shapes)

def _make_primitive(operation: str, parameters: dict[str, Any]):
    import cadquery as cq
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakeCone,
        BRepPrimAPI_MakeSphere,
        BRepPrimAPI_MakeTorus,
    )
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    position = _parameter_vector(parameters)
    if operation == "box":
        length = _parameter_number(parameters, "length", 100.0)
        width = _parameter_number(parameters, "width", 100.0)
        height = _parameter_number(parameters, "height", 100.0)
        raw = BRepPrimAPI_MakeBox(gp_Pnt(-length / 2, -width / 2, -height / 2), length, width, height).Shape()
    elif operation == "cylinder":
        radius = _parameter_number(parameters, "radius", 50.0)
        height = _parameter_number(parameters, "height", 100.0)
        axis = gp_Ax2(gp_Pnt(0, 0, -height / 2), gp_Dir(0, 0, 1))
        raw = BRepPrimAPI_MakeCylinder(axis, radius, height).Shape()
    elif operation == "pipe":
        outer_radius = _parameter_number(parameters, "outer_radius", 50.0)
        inner_radius = _parameter_number(parameters, "inner_radius", 40.0)
        height = _parameter_number(parameters, "height", 100.0)
        if inner_radius >= outer_radius:
            raise ValueError("inner_radius must be smaller than outer_radius")
        axis = gp_Ax2(gp_Pnt(0, 0, -height / 2), gp_Dir(0, 0, 1))
        outer = cq.Shape.cast(BRepPrimAPI_MakeCylinder(axis, outer_radius, height).Shape())
        inner = cq.Shape.cast(BRepPrimAPI_MakeCylinder(axis, inner_radius, height).Shape())
        return outer.cut(inner).moved(cq.Location(cq.Vector(*position)))
    elif operation == "cone":
        radius1 = _parameter_number(parameters, "radius1", 50.0)
        radius2 = float(parameters.get("radius2", 0.0))
        height = _parameter_number(parameters, "height", 100.0)
        if not math.isfinite(radius2) or radius2 < 0.0 or radius2 > 1.0e9:
            raise ValueError("radius2 must be between 0 and 1e9")
        if radius1 == radius2:
            raise ValueError("Cone radii must differ; use Cylinder for equal radii")
        axis = gp_Ax2(gp_Pnt(0, 0, -height / 2), gp_Dir(0, 0, 1))
        raw = BRepPrimAPI_MakeCone(axis, radius1, radius2, height).Shape()
    elif operation == "sphere":
        radius = _parameter_number(parameters, "radius", 50.0)
        raw = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), radius).Shape()
    elif operation == "torus":
        major_radius = _parameter_number(parameters, "major_radius", 75.0)
        minor_radius = _parameter_number(parameters, "minor_radius", 15.0)
        if minor_radius >= major_radius:
            raise ValueError("minor_radius must be smaller than major_radius")
        axis = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
        raw = BRepPrimAPI_MakeTorus(axis, major_radius, minor_radius).Shape()
    else:
        raise ValueError(f"Unsupported primitive: {operation}")
    return cq.Shape.cast(raw).moved(cq.Location(cq.Vector(*position)))


def _selected_shapes(assembly, component_ids: list[str]):
    rows = []
    for component_id in component_ids:
        child = assembly.objects.get(component_id)
        if child is None or child.parent is None:
            raise ValueError(f"Component cannot be used for this operation: {component_id}")
        compound = child.toCompound()
        if compound is None:
            raise ValueError(f"Component has no usable shape: {component_id}")
        rows.append((component_id, child, compound))
    return rows


def _edge_indices(parameters: dict[str, Any], edge_count: int) -> list[int]:
    raw = parameters.get("edge_indices", "")
    if raw in (None, "", []):
        return list(range(edge_count))
    if isinstance(raw, str):
        tokens = [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]
    elif isinstance(raw, (list, tuple)):
        tokens = list(raw)
    else:
        raise ValueError("edge_indices must be a comma-separated list")
    result = []
    for token in tokens:
        # UI is one-based because that is friendlier to a person reading FCInfo.
        index = int(token) - 1
        if index < 0 or index >= edge_count:
            raise ValueError(f"Edge index {index + 1} is outside 1..{edge_count}")
        if index not in result:
            result.append(index)
    if not result:
        raise ValueError("Select at least one edge")
    return result


def _round_or_chamfer_selected(selected, parameters: dict[str, Any], operation: str):
    amount_name = "radius" if operation == "fillet" else "distance"
    amount = _parameter_number(parameters, amount_name, 2.0)
    distance2 = None
    if operation == "chamfer" and parameters.get("distance2") not in (None, ""):
        distance2 = _parameter_number(parameters, "distance2", amount)
    results = []
    for _component_id, _child, shape in selected:
        edges = list(shape.Edges())
        if not edges:
            raise ValueError("The selected component has no exact edges")
        chosen = [edges[index] for index in _edge_indices(parameters, len(edges))]
        if operation == "fillet":
            result = shape.fillet(amount, chosen)
        else:
            result = shape.chamfer(amount, distance2, chosen)
        if not result or not result.isValid():
            raise ValueError(f"Open CASCADE could not create the requested {operation}")
        results.append(result)
    return results


def _helix_feature_selected(selected, parameters: dict[str, Any], additive: bool):
    import cadquery as cq
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell

    if len(selected) != 2:
        raise ValueError("Helix requires exactly two selected components: primary profile, then base solid")
    profile = _profile_wire(selected[0][2], require_closed=True)
    base = selected[1][2]
    pitch = _parameter_number(parameters, "pitch", 10.0)
    height = _parameter_number(parameters, "height", 50.0)
    radius = _parameter_number(parameters, "radius", 20.0)
    center = _parameter_vector(parameters, "center")
    direction = _normalized_vector(_parameter_vector(parameters, "direction"), "helix direction")
    taper = float(parameters.get("taper_angle", 0.0) or 0.0)
    if not math.isfinite(taper) or abs(taper) >= 89.0:
        raise ValueError("taper_angle must be between -89 and 89 degrees")
    start_angle = float(parameters.get("start_angle", 0.0) or 0.0)
    if not math.isfinite(start_angle) or abs(start_angle) > 1.0e9:
        raise ValueError("start_angle is invalid")
    left_hand = _parameter_bool(parameters, "left_hand", False)
    # CadQuery's angle argument is the conical surface semi-angle in degrees;
    # 360 selects a cylindrical helix.
    path = cq.Wire.makeHelix(
        pitch, height, radius, center=center, dir=direction,
        angle=taper if abs(taper) > 1.0e-12 else 360.0,
        lefthand=left_hand,
    )
    if abs(start_angle) > 1.0e-12:
        axis_end = tuple(center[index] + direction[index] for index in range(3))
        path = path.rotate(center, axis_end, start_angle)
        profile = profile.rotate(center, axis_end, start_angle)
    builder = BRepOffsetAPI_MakePipeShell(path.wrapped)
    builder.Add(profile.wrapped, False, False)
    builder.Build()
    if not builder.IsDone() or not builder.MakeSolid():
        raise ValueError("Open CASCADE could not sweep the profile along the helix")
    feature = cq.Shape.cast(builder.Shape())
    result = base.fuse(feature) if additive else base.cut(feature)
    try:
        result = result.clean()
    except Exception:
        pass
    if not result or not result.isValid():
        raise ValueError("The helical feature produced invalid geometry")
    return result


def inspect_components(
    project_dir: Path,
    editor_state: dict[str, Any],
    component_ids: list[str],
) -> dict[str, Any]:
    """Return FCInfo-style exact properties for selected assembly components."""
    import cadquery as cq

    master = project_dir / "master.xbf"
    if not master.exists():
        raise FileNotFoundError("Project master.xbf is missing")
    if not component_ids:
        raise ValueError("Select at least one component")
    assembly = cq.Assembly.load(str(master), importType="XBF")
    apply_editor_state(assembly, editor_state)
    selected = _selected_shapes(assembly, component_ids)
    records = editor_state.get("components", {})
    items = []
    total_volume = 0.0
    total_area = 0.0
    total_length = 0.0
    total_mass = 0.0
    for component_id, _child, shape in selected:
        box = shape.BoundingBox()
        x_length = float(box.xlen)
        y_length = float(box.ylen)
        z_length = float(box.zlen)
        diagonal = math.sqrt(x_length * x_length + y_length * y_length + z_length * z_length)
        volume = float(shape.Volume())
        area = float(shape.Area())
        edge_length = sum(float(edge.Length()) for edge in shape.Edges())
        center = shape.Center()
        radii = []
        for edge in shape.Edges():
            try:
                if str(edge.geomType()).upper() == "CIRCLE":
                    radius = float(edge.radius())
                    if radius > 0 and all(abs(radius - prior) > 1.0e-6 for prior in radii):
                        radii.append(radius)
            except Exception:
                continue
        radii.sort()
        material = records.get(component_id, {}).get("material") or _component_material(_child)
        density = float(material.get("density_kg_m3", 0.0) or 0.0)
        mass_kg = volume * 1.0e-9 * density
        total_volume += volume
        total_area += area
        total_length += edge_length
        total_mass += mass_kg
        items.append({
            "id": component_id,
            "name": records.get(component_id, {}).get("name") or getattr(_child, "name", component_id),
            "shape_type": str(shape.ShapeType()),
            "counts": {
                "solids": len(shape.Solids()), "shells": len(shape.Shells()),
                "faces": len(shape.Faces()), "edges": len(shape.Edges()),
                "vertices": len(shape.Vertices()),
            },
            "bbox": {
                "min": [float(box.xmin), float(box.ymin), float(box.zmin)],
                "max": [float(box.xmax), float(box.ymax), float(box.zmax)],
                "x_length": x_length, "y_length": y_length, "z_length": z_length,
                "diagonal": diagonal,
            },
            "center_of_mass": [float(center.x), float(center.y), float(center.z)],
            "volume_mm3": volume,
            "area_mm2": area,
            "edge_length_mm": edge_length,
            "perimeter_mm": edge_length,
            "radii_mm": radii[:50],
            "diameters_mm": [value * 2.0 for value in radii[:50]],
            "material": material,
            "mass_kg": mass_kg,
        })
    distance = None
    closest_points = None
    if len(selected) == 2:
        first = selected[0][2]
        second = selected[1][2]
        distance = float(first.distance(second))
        try:
            from cadquery.occ_impl.shapes import closest
            a, b = closest(first, second)
            closest_points = [[float(a.x), float(a.y), float(a.z)], [float(b.x), float(b.y), float(b.z)]]
        except Exception:
            pass
    return {
        "items": items,
        "selection_count": len(items),
        "totals": {
            "volume_mm3": total_volume,
            "area_mm2": total_area,
            "edge_length_mm": total_length,
            "mass_kg": total_mass,
        },
        "minimum_distance_mm": distance,
        "closest_points": closest_points,
    }


def model_operation(
    project_dir: Path,
    geometry_kind: str,
    editor_state: dict[str, Any],
    operation: str,
    component_ids: list[str],
    parameters: dict[str, Any],
    preview_tolerance: float,
    preview_angular_tolerance: float,
    progress: Progress,
) -> dict[str, Any]:
    """Apply an exact modeling operation and immediately write a new XBF revision."""
    import cadquery as cq

    master = project_dir / "master.xbf"
    preview = project_dir / "previews" / "overview.glb"
    if not master.exists():
        raise FileNotFoundError("Project master.xbf is missing")
    operation = str(operation).lower()
    progress(8, "Opening XBF master")
    assembly = cq.Assembly.load(str(master), importType="XBF")
    apply_editor_state(assembly, editor_state)
    progress(25, f"Preparing {operation} operation")

    added_name = None
    resulting_kind = geometry_kind
    primitive_operations = {"box", "cylinder", "pipe", "sphere", "torus", "cone"}
    draft_operations = {"line", "bspline", "polyline", "circle", "rectangle", "polygon", "ellipse"}
    if operation in primitive_operations:
        shape = _make_primitive(operation, parameters)
        requested_name = str(parameters.get("name") or operation).strip()
        added_name = _unique_subassembly_name(assembly, requested_name)
        assembly.add(shape, name=added_name)
        if geometry_kind == "mesh":
            resulting_kind = "mixed"
    elif operation in draft_operations:
        shape = _make_draft_shape(operation, parameters)
        requested_name = str(parameters.get("name") or operation).strip()
        added_name = _unique_subassembly_name(assembly, requested_name)
        assembly.add(shape, name=added_name)
        if geometry_kind == "mesh":
            resulting_kind = "mixed"
    elif operation in {"extrude", "revolve", "cross_section", "sweep", "loft"}:
        selected = _selected_shapes(assembly, component_ids)
        if operation == "extrude":
            if not selected:
                raise ValueError("Extrude requires one or more selected closed profiles")
            result = _extrude_selected(selected, parameters)
        elif operation == "revolve":
            if not selected:
                raise ValueError("Revolve requires one or more selected closed profiles")
            result = _revolve_selected(selected, parameters)
        elif operation == "cross_section":
            if not selected:
                raise ValueError("Cross Sections requires one or more selected exact solids")
            result = _cross_section_selected(selected, parameters)
        elif operation == "sweep":
            result = _sweep_selected(selected, parameters)
        else:
            result = _loft_selected(selected, parameters)
        added_name = _unique_subassembly_name(assembly, str(parameters.get("name") or operation))
        assembly.add(result, name=added_name)
    elif operation in {"fillet", "chamfer"}:
        if not component_ids:
            raise ValueError(f"{operation} requires one or more selected exact components")
        selected = _selected_shapes(assembly, component_ids)
        results = _round_or_chamfer_selected(selected, parameters, operation)
        for component_id, _child, _shape in selected:
            if component_id in assembly.objects:
                assembly.remove(component_id)
        for index, result in enumerate(results, start=1):
            requested = str(parameters.get("name") or operation)
            name = _unique_subassembly_name(assembly, requested if len(results) == 1 else f"{requested}_{index}")
            assembly.add(result, name=name)
            if added_name is None:
                added_name = name
    elif operation in {"additive_helix", "subtractive_helix"}:
        selected = _selected_shapes(assembly, component_ids)
        result = _helix_feature_selected(selected, parameters, additive=operation == "additive_helix")
        # The primary selection is the swept profile; the second is the base solid.
        for component_id, _child, _shape in selected:
            if component_id in assembly.objects:
                assembly.remove(component_id)
        requested = str(parameters.get("name") or ("AdditiveHelix" if operation == "additive_helix" else "SubtractiveHelix"))
        added_name = _unique_subassembly_name(assembly, requested)
        assembly.add(result, name=added_name)
    elif operation in {"fuse", "subtract"}:
        if len(component_ids) < 2:
            raise ValueError(f"{operation} requires at least two selected exact components")
        selected = _selected_shapes(assembly, component_ids)
        result = selected[0][2]
        if operation == "fuse":
            result = result.fuse(*(row[2] for row in selected[1:]))
        else:
            result = result.cut(*(row[2] for row in selected[1:]))
        try:
            result = result.clean()
        except Exception:
            pass
        for component_id, _child, _shape in selected:
            if component_id in assembly.objects:
                assembly.remove(component_id)
        added_name = _unique_subassembly_name(assembly, str(parameters.get("name") or operation))
        assembly.add(result, name=added_name)
    elif operation == "mirror":
        if len(component_ids) != 1:
            raise ValueError("Mirror requires exactly one selected exact component")
        plane = str(parameters.get("plane", "YZ")).upper()
        if plane not in {"XY", "XZ", "YZ"}:
            raise ValueError("Mirror plane must be XY, XZ, or YZ")
        base_point = _parameter_vector(parameters, "base_point") if "base_point" in parameters else (0.0, 0.0, 0.0)
        selected = _selected_shapes(assembly, component_ids)
        mirrored = selected[0][2].mirror(plane, base_point)
        added_name = _unique_subassembly_name(assembly, str(parameters.get("name") or f"{component_ids[0]}_mirror"))
        assembly.add(mirrored, name=added_name)
    elif operation == "facebinder":
        if not component_ids:
            raise ValueError("Face Binder requires one or more selected exact components")
        selected = _selected_shapes(assembly, component_ids)
        faces = [face for _component_id, _child, shape in selected for face in shape.Faces()]
        if not faces:
            raise ValueError("The selected components contain no exact faces")
        binder = cq.Compound.makeCompound(faces)
        added_name = _unique_subassembly_name(assembly, str(parameters.get("name") or "FaceBinder"))
        assembly.add(binder, name=added_name)
    else:
        raise ValueError(f"Unsupported modeling operation: {operation}")

    progress(52, "Creating revision snapshot")
    revision_id = _snapshot(project_dir, f"Before {operation} operation")
    progress(62, "Writing modeled XBF master")
    _atomic_export(assembly, master, "XBF")
    progress(80, "Regenerating editable GLB preview")
    _atomic_export(
        assembly,
        preview,
        "GLB",
        tolerance=preview_tolerance,
        angularTolerance=preview_angular_tolerance,
    )
    progress(95, "Refreshing assembly metadata")
    return {
        "components": _assembly_components(assembly, resulting_kind),
        "geometry_kind": resulting_kind,
        "revision_id": revision_id,
        "added_component": added_name,
        "message": f"Completed {operation} operation",
    }
