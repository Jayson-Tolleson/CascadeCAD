#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request

base_url = os.environ.get('BASE_URL', 'http://127.0.0.1:8787').rstrip('/')
bbox = os.environ.get('BBOX', '-87.8,18.0,-73.0,32.5')
tier = os.environ.get('TIER', 'regional')
url = f'{base_url}/gfs/api/viewport-spatial?{urllib.parse.urlencode({"bbox": bbox, "tier": tier})}'
with urllib.request.urlopen(url, timeout=10) as response:
    data = json.load(response)
if not data.get('ok'):
    raise SystemExit('viewport spatial response was not ok')
for key in ['reports', 'harbors', 'coast_mask', 'spatial_mode', 'postgis', 'geometry_tier']:
    if key not in data:
        raise SystemExit(f'missing viewport key: {key}')
print(json.dumps({'ok': True, 'spatial_mode': data.get('spatial_mode'), 'reports': len(data.get('reports', [])), 'tier': data.get('geometry_tier')}))
