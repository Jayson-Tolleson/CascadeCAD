#!/usr/bin/env python3
"""Audit the LFTR Google 3D renderer geometry path.

Current target after the white-sphere/flat-orb discoveries:
- gmp-map-3d remains the substrate
- cloud bodies, bait, boats, rain, lightning, and location orb bodies avoid marker glyph bodies
- CSV location orbs are stacked native gmp-polygon-3d cylinders with extrusion
- a zippy green gmp-marker-3d-interactive is intentionally retained as the click hit-target for fishing Location Intel panes
- gmp-marker-3d remains available for labels and explicit interactive hit targets
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

main = read("frontend/src/main.ts")
google3d = read("frontend/src/renderer/google3d.ts")
cloud_particles = read("frontend/src/renderer/cloudParticles.ts")
geometry = read("frontend/src/renderer/geometryPrimitives.ts")
index = read("frontend/index.html")
install = read("scripts/install.sh")
doc = read("docs/gfs_renderer_geometry_reality.md")

checks = {
    "uses_gmp_map_3d_script": "libraries=maps3d" in index and "gmp-map-3d" in google3d,
    "google3d_import_library": "importLibrary!('maps3d')" in google3d,
    "polygon_element_supported": "Polygon3DElement" in google3d and "gmp-polygon-3d" in google3d,
    "polyline_element_supported": "Polyline3DElement" in google3d and "gmp-polyline-3d" in google3d,
    "model_element_supported_but_not_required_for_orbs": "Model3DElement" in google3d and "gmp-model-3d" in google3d and "syncModels" in google3d,
    "marker_element_available_but_not_primary": "Marker3DElement" in google3d and "Marker fallback retained" in main,
    "geometry_clicks_supported": "onClick?: () => void" in google3d and "__lftrClick" in google3d,
    "cloud_bodies_are_polygons": "toParticlePolygons" in cloud_particles and "cloud-geometry-polygon-body" in cloud_particles and "syncPolygons('clouds'" in main,
    "cloud_marker_sync_clears_only": ("syncMarkers('clouds', cloudFeatureMarkers(null))" in main or "syncMarkers('clouds', [])" in main) and "return []" in main,
    "locations_are_extruded_cylinder_orbs": "locationOrbPolygons" in main and "location-orb-cylinder" in main and "core-cylinder" in main and main.count("extruded: true") >= 3,
    "location_models_cleared": "syncModels('location-models', [])" in main,
    "locations_marker_hit_target_restored": "syncMarkers('locations', locationOrbMarkers(reports, select, scale))" in main and "template: 'green-orb'" in main,
    "bait_is_polygon_geometry": "baitPolygons" in main and "syncPolygons('bait'" in main,
    "boats_are_polygon_geometry": "boatPolygons" in main and "trianglePath" in geometry and "syncPolygons('boats'" in main,
    "rain_is_polygon_geometry": "rainPolygons" in main and "syncPolygons('rain'" in main,
    "lightning_is_polyline_geometry": "lightningLines" in main and "zigzagLine" in geometry and "syncPolylines('lightning'" in main,
    "polygon_extruded_field_wired": "extruded?: boolean" in google3d and "extruded: spec.extruded ?? false" in google3d,
    "installer_runs_geometry_audit": "check_gfs_renderer_geometry_reality.py" in install,
    "geometry_doc_present": "white-sphere" in doc and "extruded green cylinder orb" in doc,
}

failed = [name for name, ok in checks.items() if not ok]
summary = {
    "ok": not failed,
    "renderer_mode": "google3d_extruded_polygon_orbs_with_zippy_marker_hit_targets_and_polygon_field_visuals",
    "true_geometry_now": [
        "gmp-map-3d",
        "gmp-polygon-3d stacked extruded green location/orb cylinders plus zippy marker hit target",
        "gmp-polygon-3d cloud body ellipses/shells",
        "gmp-polygon-3d bait/rain/boat bodies",
        "gmp-polyline-3d current/lightning lines",
        "gmp-polygon-3d water label shimmer discs",
    ],
    "marker_fallback_now": ["cloud markers remain cleared", "location markers intentionally provide reliable click targets for fishing intel panes"],
    "next_geometry_target": ["higher-fidelity cloud volumes", "GLB boats/fish if native polygon geometry is insufficient"],
    "failed": failed,
}
print(json.dumps(summary, indent=2, sort_keys=True))
if failed:
    raise SystemExit(1)
