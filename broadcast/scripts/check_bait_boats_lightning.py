#!/usr/bin/env python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.bait_field import bait_field_summary
from app.services.boat_generator import generate_viewport_boats
from app.services.lightning_service import lightning_flashes
from app.spatial.viewport_query import parse_bbox

bbox = parse_bbox('-125,32,-117,38')
bait = bait_field_summary(bbox)
boats = generate_viewport_boats(bbox)
lightning = lightning_flashes(bbox, count=2)
if 'max_score' not in bait:
    raise SystemExit('bait summary missing max_score')
if len(boats.get('boats', [])) != 12:
    raise SystemExit('boat generator did not return default 12 boats')
if 'flashes' not in lightning:
    raise SystemExit('lightning response missing flashes')
print(json.dumps({'ok': True, 'bait_max': bait['max_score'], 'boats': len(boats['boats']), 'flashes': len(lightning['flashes'])}))
