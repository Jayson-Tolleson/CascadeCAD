from pathlib import Path

import pytest

from webcad_xbf.geometry import _parameter_plane, _parse_point_list


def test_point_list_accepts_2d_and_3d_points():
    assert _parse_point_list({"points": "0,0; 10,20,30"}, minimum=2) == [
        (0.0, 0.0, 0.0),
        (10.0, 20.0, 30.0),
    ]


def test_point_list_rejects_too_few_points():
    with pytest.raises(ValueError):
        _parse_point_list({"points": "0,0,0"}, minimum=2)


def test_advanced_modeling_ui_and_upload_contract():
    root = Path(__file__).resolve().parents[1]
    project = (root / "webcad_xbf/templates/project.html").read_text()
    index = (root / "webcad_xbf/templates/index.html").read_text()
    geometry = (root / "webcad_xbf/geometry.py").read_text()
    for token in ("Extrude", "Revolve", "Cross Sections", "Sweep", "Loft", "B-spline", "N-side", "Ellipse"):
        assert token in project
    assert "Make Solid(s) from Mesh" in index
    assert "Even in Assemblies" in index
    for token in ("_extrude_selected", "_revolve_selected", "_sweep_selected", "_loft_selected"):
        assert token in geometry
    assert _parameter_plane({"plane": "xz"}) == "XZ"
