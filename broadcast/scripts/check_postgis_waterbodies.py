#!/usr/bin/env python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.spatial.postgis_repository import PostGISSpatialRepository
from app.spatial.viewport_query import parse_bbox

repo = PostGISSpatialRepository()
if not repo.available():
    print(json.dumps({'ok': True, 'skipped': True, 'reason': 'PostGIS disabled or unavailable'}))
    raise SystemExit(0)
items = repo.query_waterbodies(parse_bbox('-125,32,-117,38'), 'regional')
print(json.dumps({'ok': True, 'skipped': False, 'waterbodies': len(items)}))
