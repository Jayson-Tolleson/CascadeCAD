#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.spatial.usgs.ingest import ingest_waterbodies
from app.spatial.viewport_query import parse_bbox

bbox = parse_bbox(os.environ.get('BBOX', os.environ.get('LFTR_USGS_DEFAULT_BBOX', '-125,32,-117,38')))
print(json.dumps(ingest_waterbodies(bbox), default=str))
