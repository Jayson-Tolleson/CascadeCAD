from pathlib import Path

import pytest

from webcad_xbf.geometry import (
    _step_entity_counts,
    _step_report_preserves_mesh_source,
    _validate_step_output,
)


def _write_step(path: Path, body: str) -> None:
    path.write_text(
        "ISO-10303-21;\nHEADER;\n"
        "FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));\n"
        "ENDSEC;\nDATA;\n"
        + body
        + "\nENDSEC;\nEND-ISO-10303-21;\n"
        + (" " * 1200),
        encoding="ascii",
    )


def test_step_validation_accepts_tessellated_ap242(tmp_path: Path):
    path = tmp_path / "mesh.step"
    _write_step(path, "#1=TRIANGULATED_FACE('mesh',#2,$,.T.);\n#2=CARTESIAN_POINT_LIST_3D('',((0.,0.,0.)));" )
    report = _validate_step_output(path, 1)
    assert report["schema"] == "AP242"
    assert report["tessellated_entity_count"] >= 2
    assert report["exact_entity_count"] == 0


def test_step_validation_accepts_exact_brep(tmp_path: Path):
    path = tmp_path / "solid.step"
    _write_step(path, "#1=ADVANCED_FACE('',(),#2,.T.);\n#2=MANIFOLD_SOLID_BREP('',#3);" )
    report = _validate_step_output(path, 1)
    assert report["exact_entity_count"] >= 2


def test_step_validation_rejects_metadata_only_file(tmp_path: Path):
    path = tmp_path / "empty.step"
    _write_step(path, "#1=PRODUCT('empty','empty','',());")
    with pytest.raises(RuntimeError, match="no geometric entities"):
        _validate_step_output(path, 1)


def test_step_entity_counter_is_streaming_and_case_insensitive(tmp_path: Path):
    path = tmp_path / "case.step"
    _write_step(path, "#1=complex_triangulated_face('mesh',#2,$,.T.);")
    counts = _step_entity_counts(path)
    assert counts["COMPLEX_TRIANGULATED_FACE"] == 1
    assert counts["AP242"] == 1


def test_faceted_fallback_report_is_mesh_geometry():
    report = {
        "writer_mode": "faceted-brep-fallback",
        "faceted_mesh_triangle_count": 80,
        "exact_entity_count": 80,
        "tessellated_entity_count": 0,
    }
    assert report["faceted_mesh_triangle_count"] > 0
    assert report["writer_mode"] == "faceted-brep-fallback"


def test_hard_speed_native_ap242_report_preserves_mesh_source():
    report = {
        "writer_mode": "native-ap242",
        "exact_entity_count": 90,
        "tessellated_entity_count": 0,
        "mesh_representation": "faceted-solid-brep",
        "source_mesh_triangle_count": 80,
        "faceted_conversion": {
            "changed": True,
            "source_mesh_triangle_count": 80,
            "converted_component_count": 1,
            "mesh_triangle_count_after": 0,
            "solid_count": 1,
            "faceted_open_shell_count": 0,
        },
    }
    assert _step_report_preserves_mesh_source(report)


def test_native_ap242_exact_only_report_is_not_mesh_source():
    report = {
        "writer_mode": "native-ap242",
        "exact_entity_count": 90,
        "tessellated_entity_count": 0,
        "source_mesh_triangle_count": 0,
        "faceted_conversion": None,
    }
    assert not _step_report_preserves_mesh_source(report)
