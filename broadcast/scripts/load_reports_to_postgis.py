#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.spatial.postgis_repository import PostGISSpatialRepository

if not os.environ.get('LFTR_POSTGIS_DSN'):
    raise SystemExit('LFTR_POSTGIS_DSN is not configured; refusing to load reports')
print(json.dumps(PostGISSpatialRepository().load_reports_csv()))
