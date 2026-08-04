#!/usr/bin/env python3
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
google3d = (ROOT / "frontend/src/renderer/google3d.ts").read_text(encoding="utf-8")
main = (ROOT / "frontend/src/main.ts").read_text(encoding="utf-8")
geometry = (ROOT / "frontend/src/renderer/geometryPrimitives.ts").read_text(encoding="utf-8")
checks = {
    "location_orb_polygon_function": "function locationOrbPolygons" in main,
    "native_cylinder_ids": "location-orb-cylinder" in main,
    "stacked_cylinder_layers": all(token in main for token in ["outer-cylinder", "core-cylinder", "upper-cap", "white-spark", "ground-glow"]),
    "extruded_true_layers": main.count("extruded: true") >= 3,
    "relative_to_ground": "altitudeMode: 'RELATIVE_TO_GROUND'" in main,
    "polygon_extrusion_wired": "extruded?: boolean" in google3d and "extruded: spec.extruded ?? false" in google3d,
    "uses_ellipse_path": "ellipsePath" in main and "segments: 32" in main,
    "markers_cleared": "overlay.syncMarkers('locations', [])" in main,
    "models_cleared": "overlay.syncModels('location-models', [])" in main,
    "old_model_orb_not_primary": "locationOrbModels" not in main and "LFTR_GREEN_ORB_MODEL" not in main,
    "geometry_helper_available": "ellipsePath" in geometry and "polygonSpec" in geometry,
    "zoom_scaled_orb_size": all(token in main for token in ["locationOrbScaleForBBox", "currentViewportBBox", "clampedScale", "span <= 0.20"]),
    "larger_brighter_higher_orbs": all(token in main for token in ["baseAltitude + 1220", "baseAltitude + 1040", "rgba(0,255,85,.72)", "Math.min(4.6, scale)"]),
}
failed = [name for name, ok in checks.items() if not ok]
print(json.dumps({"ok": not failed, "check": "gfs_green_orbs_stacked_extruded_cylinders", "failed": failed}, indent=2, sort_keys=True))
if failed:
    sys.exit(1)
