#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request

base_url = os.environ.get('BASE_URL', 'http://127.0.0.1:8787').rstrip('/')
bbox = os.environ.get('BBOX', '-87.8,18.0,-73.0,32.5')
url = f'{base_url}/gfs/api/field-truth?{urllib.parse.urlencode({"bbox": bbox})}'
with urllib.request.urlopen(url, timeout=10) as response:
    data = json.load(response)
ocean = data.get('ocean', {})
patch = ocean.get('patch', {})
if patch.get('field_type') != 'ocean':
    raise SystemExit('field-truth response did not include an ocean patch')
payload = patch.get('payload', {})
channels = payload.get('channels', {})
for key in ['sst_c', 'current_u', 'current_v', 'bait_score', 'current_speed', 'current_direction']:
    if key not in channels:
        raise SystemExit(f'missing ocean truth channel: {key}')
print(json.dumps({'ok': True, 'tile_id': patch.get('tile_id'), 'channels': sorted(channels.keys())}))
