#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.spatial.postgis_repository import PostGISSpatialRepository

status = PostGISSpatialRepository().status()
print(json.dumps({'ok': True, 'postgis': status, 'dsn_exposed': False}))
