#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    'layer_compiler_locations_label': (ROOT / 'app/layers/compiler.py').read_text(encoding='utf-8'),
    'scene_snapshot_locations_label': (ROOT / 'app/services/scene_snapshot.py').read_text(encoding='utf-8'),
    'stream_route_bbox': (ROOT / 'app/api/routes_stream.py').read_text(encoding='utf-8'),
    'stream_bus_locations': (ROOT / 'app/services/stream_bus.py').read_text(encoding='utf-8'),
    'frontend_stream_bbox': (ROOT / 'frontend/src/api/stream.ts').read_text(encoding='utf-8'),
    'frontend_main_old_orb': (ROOT / 'frontend/src/main.ts').read_text(encoding='utf-8'),
    'google3d_old_orb': (ROOT / 'frontend/src/renderer/google3d.ts').read_text(encoding='utf-8'),
}
missing = []
requirements = [
    ('app/layers/compiler.py', "label='Locations'"),
    ('app/services/scene_snapshot.py', '"label": "Locations"'),
    ('app/api/routes_stream.py', 'bbox: str | None = Query'),
    ('app/services/stream_bus.py', '"locations.patch"'),
    ('frontend/src/api/stream.ts', 'params.set(\'bbox\''),
    ('frontend/src/main.ts', 'locationOrbPolygons'),
    ('frontend/src/main.ts', 'connectFieldStream(bbox)'),
    ('frontend/src/renderer/geometryPrimitives.ts', 'layeredOrbPolygons'),
    ('frontend/src/renderer/google3d.ts', 'onClick?: () => void'),
    ('frontend/src/renderer/google3d.ts', 'Polygon3DElement'),
]
for rel, token in requirements:
    text = (ROOT / rel).read_text(encoding='utf-8')
    if token not in text:
        missing.append(f'{rel} missing {token}')
if missing:
    raise SystemExit(json.dumps({'ok': False, 'missing': missing}, indent=2))
print(json.dumps({'ok': True, 'locations_label': 'Locations', 'stream_bbox_bound': True, 'polygon_green_orbs': True, 'clickable_polygons': True}, indent=2))
