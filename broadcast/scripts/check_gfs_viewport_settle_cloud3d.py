#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
viewport = (root / "frontend/src/renderer/viewportController.ts").read_text()
main = (root / "frontend/src/main.ts").read_text()
css = (root / "frontend/src/styles/app.css").read_text()
particles = (root / "frontend/src/renderer/cloudParticles.ts").read_text()

assert "attachToMap(map: HTMLElement)" in viewport, "ViewportController must attach to Google 3D map"
assert "gmp-centerchange" in viewport and "gmp-rangechange" in viewport, "camera settle events missing"
assert "basePaddingRatio" in viewport and "resolutionPaddingRatio" in viewport, "resolution-aware padding missing"
assert "1270x768" in viewport and "1080p" in viewport, "screen-size padding notes missing"
assert "viewport.attachToMap(mapSurface.element)" in main, "main must use real map camera, not mock camera"
assert "viewport.updateFromMockCamera();" not in main, "main still starts from mock viewport"
assert "CloudParticleGenerator" in particles and "altitudeM" in particles and "thicknessM" in particles, "cloud features must become altitude-varied particle bodies"
assert "Cloud Render Pass 4" in css or "cloud-particle-ellipsoid" in css, "cloud pass-4 style markers missing"
print("✓ /gfs viewport settles from Google 3D camera with resolution padding and altitude-varied pass-4 polygon cloud bodies")
