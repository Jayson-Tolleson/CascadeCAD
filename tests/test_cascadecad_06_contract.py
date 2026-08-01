from pathlib import Path


def test_cascadecad_06_editor_contract():
    root = Path(__file__).resolve().parents[1]
    template = (root / "webcad_xbf/templates/project.html").read_text()
    script = (root / "webcad_xbf/static/js/project.js").read_text()
    app = (root / "webcad_xbf/app.py").read_text()
    geometry = (root / "webcad_xbf/geometry.py").read_text()

    for token in (
        "CascadeCAD", "toolbar-row-primary", "toolbar-row-modeling", "tool-scale", "tool-array",
        "tool-osnap", "tool-material", "tool-measure", "tool-info", "tool-fillet", "tool-chamfer",
        "tool-additive-helix", "tool-subtractive-helix", "part-properties-pane", "material-color",
        "resolution-select", "preference-grid", "preference-origin",
    ):
        assert token in template
    for token in (
        "requestRender", "applyContextualSnap", "toggleComponentVisibility", "createArray",
        "applyMaterialToSelection", "inspectSelection", "unit_system: unitSystem", "event.code === 'Space'",
    ):
        assert token in script
    for token in ('"fillet"', '"chamfer"', '"additive_helix"', '"subtractive_helix"', '/inspect'):
        assert token in app
    for token in ("inspect_components", "write.step.unit", "INCH", "_helix_feature_selected"):
        assert token in geometry
