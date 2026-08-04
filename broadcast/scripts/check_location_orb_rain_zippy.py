#!/usr/bin/env python3
from pathlib import Path
root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
google = (root / 'frontend/src/renderer/google3d.ts').read_text()
css = (root / 'frontend/src/styles/app.css').read_text()
required = [
    "overlay.syncMarkers('locations', locationOrbMarkers(reports, select, scale))",
    "template: 'green-orb'",
    "pane.selectReport(report, buildLocationIntelContext(report))",
    "function rainCloudTopM",
    "function rainSpherePolygons",
    "rain-cloud-top:",
    "rain-floor-splash:",
    "sphere-ring",
    "white", "blue", "green", "yellow", "orange", "red", "black core",
]
missing = [item for item in required if item not in main]
if "ensureGreenOrb" not in google or "lftr-old-green-orb" not in google:
    missing.append('old zippy green orb renderer')
if "location-hit-target" not in css:
    missing.append('location hit target css')
if missing:
    raise SystemExit('Missing orb/rain contract pieces: ' + ', '.join(missing))
print('ok: zippy location orb hit-target restored and rain colored sphere renderer wired')
