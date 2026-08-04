#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8787}"
python - "$BASE_URL" <<'PY'
import json, sys, urllib.request
base = sys.argv[1].rstrip('/')
with urllib.request.urlopen(f'{base}/gfs/api/scene-frame', timeout=5) as response:
    data = json.load(response)
required = {'ok','scene_id','generated_at','bbox','viewport','layers','spatial','fields'}
missing = required - data.keys()
if missing:
    raise SystemExit(f'missing keys: {sorted(missing)}')
if data['ok'] is not True:
    raise SystemExit('ok is not true')
print(json.dumps({'ok': True, 'scene_id': data['scene_id'], 'layers': len(data['layers'])}))
PY
