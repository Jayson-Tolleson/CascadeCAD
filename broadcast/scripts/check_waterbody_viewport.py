#!/usr/bin/env python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.spatial.viewport_query import build_viewport_spatial, parse_bbox

payload = build_viewport_spatial(parse_bbox('-125,32,-117,38'), tier='regional')
items = payload.get('waterbodies', [])
if not items:
    raise SystemExit('viewport-spatial returned no waterbodies')
for key in ['id', 'stable_id', 'name', 'kind', 'source', 'label_point', 'bbox']:
    if key not in items[0]:
        raise SystemExit(f'missing waterbody key: {key}')
print(json.dumps({'ok': True, 'waterbodies': len(items), 'source': payload.get('diagnostics', {}).get('source')}))
