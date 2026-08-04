from pathlib import Path
import zipfile

from webcad_xbf.mesh_cleanup import clean_3mf

MODEL = b'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <resources>
  <object id="1" type="model"><mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object>
  <object id="2" type="model"><mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object>
 </resources>
 <build><item objectid="1"/><item objectid="2"/></build>
</model>'''


def test_exact_coincident_3mf_cleanup(tmp_path: Path):
    source = tmp_path / "duplicate.3mf"
    destination = tmp_path / "cleaned.3mf"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", MODEL)
    report = clean_3mf(source, destination, lambda _value, _message: None)
    assert report["removed_coincident_objects"] == 1
    assert report["removed_object_definitions"] == 1
    with zipfile.ZipFile(destination) as archive:
        cleaned = archive.read("3D/3dmodel.model")
    assert cleaned.count(b"<object ") == 1
    assert cleaned.count(b"<item ") == 1
