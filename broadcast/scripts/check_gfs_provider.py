#!/usr/bin/env python3
import json
import os
import sys
import urllib.request

base_url = os.environ.get('BASE_URL', 'http://127.0.0.1:8787').rstrip('/')
bbox = os.environ.get('BBOX', '-87.8,18.0,-73.0,32.5')
url = f'{base_url}/gfs/api/providers/gfs?bbox={bbox}'
with urllib.request.urlopen(url, timeout=10) as response:
    data = json.load(response)
if not data.get('ok'):
    raise SystemExit('provider response was not ok')
status = data.get('status', {})
frame = data.get('frame', {})
for key in ['cloud_density', 'rain_rate', 'wind_u', 'wind_v', 'humidity']:
    if key not in frame.get('channels', {}):
        raise SystemExit(f'missing atmosphere channel: {key}')
print(json.dumps({'ok': True, 'provider_mode': status.get('mode'), 'degraded': status.get('degraded'), 'cache_hit': status.get('cache_hit')}))
