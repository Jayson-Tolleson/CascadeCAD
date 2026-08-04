from pathlib import Path

from webcad_xbf.geometry import source_kind
from webcad_xbf.store import ALLOWED_EXTENSIONS


def test_fcstd_is_first_class_exact_import():
    assert ".fcstd" in ALLOWED_EXTENSIONS
    assert source_kind(Path("assembly.FCStd")) == "exact"


def test_fcstd_upload_and_native_worker_are_wired():
    root = Path(__file__).resolve().parents[1]
    page = (root / "webcad_xbf/templates/index.html").read_text(encoding="utf-8")
    geometry = (root / "webcad_xbf/geometry.py").read_text(encoding="utf-8")
    helper = root / "scripts/freecad_import_fcstd.py"
    installer = (root / "install.sh").read_text(encoding="utf-8")

    assert ".fcstd" in page.lower()
    assert "_fcstd_to_assembly" in geometry
    assert 'suffix == ".fcstd"' in geometry
    assert helper.exists()
    assert "App.openDocument" in helper.read_text(encoding="utf-8")
    assert "PartDesign::Feature" in helper.read_text(encoding="utf-8")
    assert "CASCADE_CAD_FCSTD_IMPORT_TIMEOUT_SECONDS" in installer


def test_fcstd_does_not_route_through_mesh_loader():
    root = Path(__file__).resolve().parents[1]
    geometry = (root / "webcad_xbf/geometry.py").read_text(encoding="utf-8")
    exact_line = next(line for line in geometry.splitlines() if line.startswith("EXACT_EXTENSIONS"))
    mesh_line = next(line for line in geometry.splitlines() if line.startswith("MESH_EXTENSIONS"))
    assert ".fcstd" in exact_line
    assert ".fcstd" not in mesh_line
