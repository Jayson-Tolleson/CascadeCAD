#!/usr/bin/env python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.spatial.usgs.ingest import ingest_waterbodies
from app.spatial.viewport_query import parse_bbox

result = ingest_waterbodies(parse_bbox('-125,32,-117,38'), source_family='mock', load_postgis=False)
if not result['waterbodies']:
    raise SystemExit('mock USGS ingest returned no waterbodies')
assert any(item['stable_id'].startswith('mock_') for item in result['waterbodies'])
print(json.dumps({'ok': True, 'count': result['count'], 'batch_id': result['batch_id']}))
