#!/usr/bin/env python3
import asyncio
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

required_imports = ['app.main', 'app.db.migrations', 'app.api.routes_admin_spatial', 'app.providers.gfs_ncss', 'app.providers.rtofs_ncep']
for name in required_imports:
    importlib.import_module(name)

from app.api.routes_health import health
from app.core.config import get_settings
from app.providers.catalog import provider_catalog
from app.providers.gfs_ncss import get_gfs_provider
from app.providers.rtofs_ncep import get_rtofs_provider
from app.services.scene_snapshot import LAYER_CONTRACTS, build_mock_scene_snapshot
from app.services.stream_bus import field_truth_sse_events
from app.spatial.viewport_query import build_viewport_spatial, parse_bbox

settings = get_settings()
assert health() == {'ok': True}
snapshot = build_mock_scene_snapshot()
assert snapshot['ok'] is True
assert any(layer['id'] == 'bait' and layer['kind'] in {'field', 'scalar_field'} for layer in LAYER_CONTRACTS)

async def collect_events():
    stream = field_truth_sse_events()
    return [await stream.__anext__(), await stream.__anext__(), await stream.__anext__()]

events = asyncio.run(collect_events())
assert any('event: scene.heartbeat' in event for event in events)
assert any('field.patch' in event for event in events)

gfs_status = get_gfs_provider().status().model_dump(mode='json')
rtofs_status = get_rtofs_provider().status().model_dump(mode='json')
assert 'postgis_dsn' not in json.dumps(provider_catalog())
assert gfs_status['provider'] == 'gfs_ncss'
assert rtofs_status['provider'] == 'rtofs_ncep'

fl = build_viewport_spatial(parse_bbox('-82,24,-79,28'), tier='regional')
ca = build_viewport_spatial(parse_bbox('-125,32,-117,38'), tier='regional')
assert any('florida' in (item.get('label', '') + item.get('title', '')).lower() or 'Everglades' in item.get('label', '') for item in fl['harbors'] + fl['reports'])
assert any(item.get('id') == 'mock_harbor_la_long_beach' for item in ca['harbors'])
assert not any('everglades' in item.get('id', '').lower() for item in ca['harbors'])

print(json.dumps({'ok': True, 'spatial_mode': settings.spatial_mode, 'events_checked': len(events)}))
