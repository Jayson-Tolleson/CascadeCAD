#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = []

pane = (ROOT / 'frontend/src/ui/intelligencePane.ts').read_text()
main = (ROOT / 'frontend/src/main.ts').read_text()
repo = (ROOT / 'app/spatial/postgis_repository.py').read_text()
routes = (ROOT / 'app/api/routes_spatial.py').read_text()
stream = (ROOT / 'app/services/stream_bus.py').read_text()
css = (ROOT / 'frontend/src/styles/app.css').read_text()

def require(name: str, ok: bool):
    checks.append((name, ok))

require('pane exposes LocationIntelContext', 'export interface LocationIntelContext' in pane)
require('pane renders Best Intel', 'Best Intel' in pane and 'bestReadSummary' in pane)
require('pane renders original zippy notes timeline', 'Original zippy notes' in pane and 'report_indices' in pane)
require('pane renders all csv/postgis fields', 'All CSV / PostGIS fields' in pane and 'csv_fields' in pane)
require('main builds nearest live ocean/atmosphere context', 'buildLocationIntelContext' in main and 'nearestSample' in main and 'baitScore' in main and 'cloudFamily' in main)
require('main passes context on location click', 'pane.selectReport(report, buildLocationIntelContext(report))' in main)
require('postgis loader prefers fishloclist', 'fishloclist.csv' in repo and 'reports_path = fish_locations if fish_locations.exists()' in repo)
require('postgis query preserves csv fields', '"csv_fields": csv_fields' in repo and '"report_indices": report_indices' in repo and '"marine_mask": marine_mask' in repo)
require('routes use viewport spatial postgis path', 'build_viewport_spatial(parsed, tier=tier)' in routes and 'postgis' in routes)
require('sse locations use viewport spatial postgis path', 'build_viewport_spatial(bbox, tier=tier)' in stream and 'postgis' in stream)
require('glass intel css installed', 'restored zippy-style Location Intel' in css and '.intel-metric-grid' in css)

failed = [name for name, ok in checks if not ok]
if failed:
    print('FAIL location_intel_glass_pane')
    for item in failed:
        print('-', item)
    raise SystemExit(1)
print('ok location_intel_glass_pane')
for name, _ in checks:
    print('-', name)
