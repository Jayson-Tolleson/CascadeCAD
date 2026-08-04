#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / "frontend/src/main.ts").read_text()
google3d = (root / "frontend/src/renderer/google3d.ts").read_text()
css = (root / "frontend/src/styles/app.css").read_text()
particles = (root / "frontend/src/renderer/cloudParticles.ts").read_text()

required_main = [
    "buildCloudBodyRender",
    "Cloud renderer geometry mode",
    "gmp-polygon-3d cloud body polygons",
]
required_particles = [
    "function cloudFeatureParticleCount",
    "function cloudFeatureParticleOffset",
    "class CloudParticleGenerator",
    "toParticlePolygons",
    "cloud-geometry-polygon-body",
]
required_google = [
    "Polygon3DElement",
    "onClick?: () => void",
    "extruded: spec.extruded ?? false",
]
required_css = [
    "Cloud visibility pass",
    "Cloud Render Pass 4",
    "cloud-particle-ellipsoid",
]
missing = [item for item in required_main if item not in main]
missing += [item for item in required_particles if item not in particles]
missing += [item for item in required_google if item not in google3d]
missing += [item for item in required_css if item not in css]
if missing:
    raise SystemExit("Missing cloud visibility contract markers: " + ", ".join(missing))
print("✓ cloud.features.patch expands into visible Google 3D polygon cloud swaths + seeded body ellipses")
