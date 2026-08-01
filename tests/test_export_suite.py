from pathlib import Path

from webcad_xbf.store import Store


def test_export_suite_is_wired():
    root = Path(__file__).resolve().parents[1]
    geometry = (root / "webcad_xbf" / "geometry.py").read_text()
    app = (root / "webcad_xbf" / "app.py").read_text()
    worker = (root / "webcad_xbf" / "worker.py").read_text()
    template = (root / "webcad_xbf" / "templates" / "project.html").read_text()
    script = (root / "webcad_xbf" / "static" / "js" / "project.js").read_text()
    for token in ("export_xbf", "export_step", "export_csg", "export_brep", "export_fcstd"):
        assert token in geometry
    assert '/api/projects/<project_id>/export' in app
    assert 'export_project_file' in worker
    for token in ('export-format', 'export-button', 'export-selected-only'):
        assert token in template
    assert 'autoDownloadFormat' in script
    assert '/cancel' in script


def test_queued_job_can_be_cancelled(tmp_path):
    store = Store(tmp_path)
    project = store.create_project("test", "test.xbf")
    store.update_project(project["id"], status="ready")
    job = store.create_job("export_file", project["id"], {"format": "step"})
    cancelled = store.request_job_cancel(job["id"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancel_requested"] is True


def test_part_export_contracts_are_explicit():
    root = Path(__file__).resolve().parents[1]
    geometry = (root / "webcad_xbf" / "geometry.py").read_text()
    freecad_builder = (root / "scripts" / "freecad_faceted_export.py").read_text()
    validator = (root / "scripts" / "freecad_validate_csg.py").read_text()

    assert "freecad_faceted_export.py" in geometry
    assert "faceted-solid" in freecad_builder
    assert "faceted-mixed-solid-shell" in freecad_builder
    assert "retained_shells" in freecad_builder
    assert "faceted_open_shell_count" in freecad_builder
    assert "mixed_source_geometry" in geometry
    assert 'doc.addObject("Part::Feature"' in freecad_builder
    assert 'doc.addObject("Mesh::Feature"' not in freecad_builder
    assert "mesh_object_count" in freecad_builder
    assert "separate closed manifold OpenSCAD polyhedron solids" in geometry
    csg_section = geometry.split("def export_csg(", 1)[1].split("def _freecad_command", 1)[0]
    assert 'handle.write("group()' not in csg_section
    assert "polyhedron(points=[" in geometry
    assert "importCSG.open" in validator



def test_csg_polyhedron_has_no_trailing_list_commas():
    from io import StringIO

    from webcad_xbf.geometry import _write_csg_polyhedron

    output = StringIO()
    _write_csg_polyhedron(
        output,
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)],
        [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
    )
    lines = output.getvalue().splitlines()
    points_end = lines.index("], faces=[")
    faces_end = lines.index("], convexity=10);")
    assert not lines[points_end - 1].endswith(",")
    assert not lines[faces_end - 1].endswith(",")


def test_freecad_helper_uses_environment_contract():
    root = Path(__file__).resolve().parents[1]
    geometry = (root / "webcad_xbf" / "geometry.py").read_text()
    freecad_builder = (root / "scripts" / "freecad_faceted_export.py").read_text()

    assert 'command = [_freecad_command(), "--console"]' in geometry
    assert "runpy.run_path" in geometry
    assert "CASCADE_CAD_FREECAD_SCRIPT" in geometry
    for token in (
        "CASCADE_CAD_FREECAD_MANIFEST",
        "CASCADE_CAD_FREECAD_OUTPUT",
        "CASCADE_CAD_FREECAD_FORMAT",
        "CASCADE_CAD_FREECAD_REPORT",
        "CASCADE_CAD_FREECAD_PROGRESS",
        "CASCADE_CAD_FREECAD_TOLERANCE",
    ):
        assert token in geometry
        assert token in freecad_builder
    freecad_launcher = geometry.split("def _run_freecad_console_helper(", 1)[1].split(
        "def _prepare_freecad_part_manifest", 1
    )[0]
    assert '"--tolerance"' not in freecad_launcher
    assert 'parser.add_argument("--tolerance"' not in freecad_builder


def test_freecad_environment_invocation_is_parsed(monkeypatch):
    import importlib.util
    import sys
    import types

    root = Path(__file__).resolve().parents[1]
    helper_path = root / "scripts" / "freecad_faceted_export.py"
    monkeypatch.setitem(sys.modules, "FreeCAD", types.ModuleType("FreeCAD"))
    monkeypatch.setitem(sys.modules, "Mesh", types.ModuleType("Mesh"))
    monkeypatch.setitem(sys.modules, "Part", types.ModuleType("Part"))
    values = {
        "CASCADE_CAD_FREECAD_MANIFEST": "/tmp/manifest.json",
        "CASCADE_CAD_FREECAD_OUTPUT": "/tmp/project.brep",
        "CASCADE_CAD_FREECAD_FORMAT": "brep",
        "CASCADE_CAD_FREECAD_REPORT": "/tmp/report.json",
        "CASCADE_CAD_FREECAD_PROGRESS": "/tmp/progress.json",
        "CASCADE_CAD_FREECAD_TOLERANCE": "0.125",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    spec = importlib.util.spec_from_file_location("freecad_env_invocation_test", helper_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    args = module._invocation_from_environment()

    assert args.manifest == "/tmp/manifest.json"
    assert args.output == "/tmp/project.brep"
    assert args.format == "brep"
    assert args.report == "/tmp/report.json"
    assert args.progress == "/tmp/progress.json"
    assert args.tolerance == 0.125


def test_coordinate_welding_preserves_parts():
    from webcad_xbf.geometry import _deduplicate_mesh_vertices

    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
    ]
    triangles = [(0, 1, 2), (3, 4, 5)]
    welded, faces = _deduplicate_mesh_vertices(vertices, triangles)
    assert len(welded) == 4
    assert faces == [(0, 1, 2), (0, 1, 3)]


def test_freecad_mixed_closed_and_open_shells_are_both_preserved(monkeypatch):
    import importlib.util
    import sys
    import types

    root = Path(__file__).resolve().parents[1]
    helper_path = root / "scripts" / "freecad_faceted_export.py"

    class FakeShell:
        def __init__(self, name, closed):
            self.name = name
            self.closed = closed

        def isClosed(self):
            return self.closed

    closed_shell = FakeShell("closed", True)
    open_shell = FakeShell("open", False)

    class FakeMeshValue:
        CountFacets = 2
        Topology = object()

    mesh_module = types.ModuleType("Mesh")
    mesh_module.Mesh = lambda _path: FakeMeshValue()

    class FakeShape:
        Faces = [object(), object()]
        Shells = [closed_shell, open_shell]

        def makeShapeFromMesh(self, _topology, _tolerance):
            return None

        def isNull(self):
            return False

    class FakeSolid:
        def __init__(self, shell):
            self.shell = shell
            self.Solids = [self]
            self.Volume = 1.0

        def isNull(self):
            return False

    class FakeCompound:
        def __init__(self, items):
            self.items = list(items)

    part_module = types.ModuleType("Part")
    part_module.Shape = FakeShape
    part_module.makeSolid = lambda shell: FakeSolid(shell)
    part_module.makeCompound = lambda items: FakeCompound(items)

    app_module = types.ModuleType("FreeCAD")
    monkeypatch.setitem(sys.modules, "FreeCAD", app_module)
    monkeypatch.setitem(sys.modules, "Mesh", mesh_module)
    monkeypatch.setitem(sys.modules, "Part", part_module)

    spec = importlib.util.spec_from_file_location("freecad_faceted_export_test", helper_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    converted, status, made_solids, retained_shells, errors = module._mesh_to_part(
        "mixed.stl", 0.05, True
    )

    assert status == "faceted-mixed-solid-shell"
    assert made_solids == 1
    assert retained_shells == 1
    assert errors == []
    assert len(converted.items) == 2
    assert converted.items[0].shell is closed_shell
    assert converted.items[1] is open_shell


def test_freecad_launcher_passes_only_script_and_uses_environment(tmp_path, monkeypatch):
    import json

    import webcad_xbf.geometry as geometry

    storage = tmp_path / "storage"
    project_dir = storage / "projects" / "project-1"
    destination = project_dir / "exports" / "project.brep"
    capture_path = tmp_path / "freecad-capture.json"
    fake_freecad = tmp_path / "fake-freecadcmd"
    fake_freecad.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys
capture = pathlib.Path(os.environ["CASCADE_CAD_TEST_CAPTURE"])
runner = sys.stdin.read()
keys = [
    "CASCADE_CAD_FREECAD_SCRIPT",
    "CASCADE_CAD_FREECAD_MANIFEST",
    "CASCADE_CAD_FREECAD_OUTPUT",
    "CASCADE_CAD_FREECAD_FORMAT",
    "CASCADE_CAD_FREECAD_REPORT",
    "CASCADE_CAD_FREECAD_PROGRESS",
    "CASCADE_CAD_FREECAD_TOLERANCE",
    "FREECAD_USER_HOME",
]
capture.write_text(json.dumps({"argv": sys.argv, "stdin": runner, "env": {key: os.environ.get(key) for key in keys}}))
pathlib.Path(os.environ["CASCADE_CAD_FREECAD_OUTPUT"]).write_bytes(b"BREP" * 100)
pathlib.Path(os.environ["CASCADE_CAD_FREECAD_REPORT"]).write_text(json.dumps({
    "face_count": 4,
    "solid_count": 1,
    "mesh_object_count": 0,
}))
""",
        encoding="utf-8",
    )
    fake_freecad.chmod(0o755)

    def fake_manifest(_assembly, temp_dir, _progress, _should_cancel, max_triangles):
        assert max_triangles == 123
        manifest = temp_dir / "manifest.json"
        manifest.write_text('{"items": [{"kind": "mesh"}]}', encoding="utf-8")
        return manifest, {"source_component_count": 1}

    monkeypatch.setattr(geometry, "_freecad_command", lambda: str(fake_freecad))
    monkeypatch.setattr(geometry, "_prepare_freecad_part_manifest", fake_manifest)
    monkeypatch.setenv("CASCADE_CAD_TEST_CAPTURE", str(capture_path))

    report = geometry._run_freecad_part_export(
        project_dir=project_dir,
        export_assembly=object(),
        destination=destination,
        output_format="brep",
        progress=lambda _percent, _message: None,
        should_cancel=None,
        max_triangles=123,
        timeout_seconds=60,
        tolerance=0.075,
    )

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert captured["argv"] == [str(fake_freecad), "--console"]
    assert "runpy.run_path" in captured["stdin"]
    assert captured["env"]["CASCADE_CAD_FREECAD_SCRIPT"].endswith("scripts/freecad_faceted_export.py")
    assert captured["env"]["CASCADE_CAD_FREECAD_FORMAT"] == "brep"
    assert captured["env"]["CASCADE_CAD_FREECAD_TOLERANCE"] == "0.075"
    assert captured["env"]["FREECAD_USER_HOME"] == str(storage)
    assert destination.stat().st_size == 400
    assert report["face_count"] == 4
    assert report["source_component_count"] == 1


def test_faceted_xbf_conversion_is_wired():
    root = Path(__file__).resolve().parents[1]
    geometry = (root / "webcad_xbf" / "geometry.py").read_text()
    app = (root / "webcad_xbf" / "app.py").read_text()
    worker = (root / "webcad_xbf" / "worker.py").read_text()
    template = (root / "webcad_xbf" / "templates" / "project.html").read_text()
    script = (root / "webcad_xbf" / "static" / "js" / "project.js").read_text()
    helper = (root / "scripts" / "freecad_faceted_export.py").read_text()

    assert "def convert_to_faceted_solids" in geometry
    assert "_prepare_freecad_conversion_manifest" in geometry
    assert 'output_format == "parts"' in helper
    assert '/api/projects/<project_id>/convert/faceted-solids' in app
    assert 'operation == "convert_faceted_solids"' in worker
    assert 'id="convert-faceted-solids"' in template
    assert 'runFacetedConversion' in script
    assert 'mesh_triangle_count_after' in geometry


def test_hard_speed_faceted_conversion_contract_is_wired():
    root = Path(__file__).resolve().parents[1]
    geometry = (root / "webcad_xbf" / "geometry.py").read_text()
    converter = (root / "webcad_xbf" / "faceted_worker.py").read_text()
    config = (root / "webcad_xbf" / "config.py").read_text()
    app = (root / "webcad_xbf" / "app.py").read_text()
    worker = (root / "webcad_xbf" / "worker.py").read_text()
    template = (root / "webcad_xbf" / "templates" / "project.html").read_text()
    script = (root / "webcad_xbf" / "static" / "js" / "project.js").read_text()

    for token in (
        "_run_hard_speed_parts_conversion",
        "_effective_faceted_workers",
        "_mesh_cache_key",
        "geometry-cache",
        "faceted_worker",
        "queue_depth",
        "OMP_NUM_THREADS",
    ):
        assert token in geometry
    for token in (
        "BRepBuilderAPI_MakeShapeOnMesh",
        "BRepBuilderAPI_FastSewing",
        "BRepBuilderAPI_Sewing",
        "ShapeUpgrade_UnifySameDomain",
        "cq.Solid.makeSolid",
        "standard_sewing_used",
    ):
        assert token in converter
    for token in (
        "CASCADE_CAD_FACETED_WORKERS",
        "CASCADE_CAD_FACETED_QUEUE_DEPTH",
        "CASCADE_CAD_FACETED_CACHE_ENABLED",
        "CASCADE_CAD_FACETED_DIRECT_OCP",
    ):
        assert token in config
    assert "fast_render" in app
    assert "fast_render" in worker
    assert 'id="fast-render"' in template
    assert "Fast render (FastSewing)" in template
    assert "fast_render" in script


def test_faceted_cache_key_tracks_geometry_and_mode():
    from webcad_xbf.geometry import _mesh_cache_key

    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    triangles = [(0, 1, 2)]
    normal = _mesh_cache_key(
        vertices,
        triangles,
        tolerance=0.05,
        fast_sewing=False,
        unify_same_domain=True,
    )
    repeated = _mesh_cache_key(
        vertices,
        triangles,
        tolerance=0.05,
        fast_sewing=False,
        unify_same_domain=True,
    )
    fast = _mesh_cache_key(
        vertices,
        triangles,
        tolerance=0.05,
        fast_sewing=True,
        unify_same_domain=False,
    )
    changed = _mesh_cache_key(
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        triangles,
        tolerance=0.05,
        fast_sewing=False,
        unify_same_domain=True,
    )
    assert normal == repeated
    assert normal != fast
    assert normal != changed


def test_csg_splits_disconnected_closed_shells_and_normalizes_winding():
    from webcad_xbf.geometry import _csg_signed_volume, _prepare_csg_polyhedra

    tetra = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ]
    vertices = tetra + [(x + 4.0, y, z) for x, y, z in tetra]
    # Intentionally mix one shell's triangle winding. The topology pass must
    # make both shells consistent and emit OpenSCAD's negative signed volume.
    first = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)]
    second = [(4, 5, 6), (4, 7, 5), (5, 7, 6), (6, 7, 4)]
    polyhedra, stats = _prepare_csg_polyhedra(vertices, first + second)

    assert len(polyhedra) == 2
    assert stats["shell_count"] == 2
    assert stats["closed_shell_count"] == 2
    assert stats["open_shell_count"] == 0
    assert all(_csg_signed_volume(item["vertices"], item["triangles"]) < 0 for item in polyhedra)


def test_csg_marks_open_triangle_sheet_instead_of_writing_a_fake_solid():
    from webcad_xbf.geometry import _prepare_csg_polyhedra

    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    polyhedra, stats = _prepare_csg_polyhedra(vertices, [(0, 1, 2), (0, 2, 3)])

    assert polyhedra == []
    assert stats["open_shell_count"] == 1
    assert stats["boundary_edge_count"] == 4


def test_csg_removes_duplicate_and_degenerate_facets():
    from webcad_xbf.geometry import _prepare_csg_polyhedra

    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ]
    tetra = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)]
    polyhedra, stats = _prepare_csg_polyhedra(
        vertices,
        tetra + [(1, 2, 0), (0, 0, 1)],
    )

    assert len(polyhedra) == 1
    assert stats["duplicate_triangle_count"] == 1
    assert stats["degenerate_triangle_count"] == 1
