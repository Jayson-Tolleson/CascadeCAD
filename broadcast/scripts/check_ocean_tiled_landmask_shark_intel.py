#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

# Server-friendly: when called as `python3 scripts/this_check.py`, jump into
# the project venv created by scripts/install.sh before importing app deps.
try:
    from _venv_bootstrap import reexec_into_project_venv
    reexec_into_project_venv(ROOT)
except Exception:
    pass

checks = [
    (ROOT / 'app/providers/rtofs_ncep.py', ['stable_tile_plan', 'run_tiles_parallel', 'all_ocean_requests_tiled', 'no_whole_viewport_rtofs_call', '_live_tile_frame']),
    (ROOT / 'app/services/marine_land_mask.py', ['marine_mask_for_point', 'should_render_marine_point', 'marine_point_filter_summary']),
    (ROOT / 'app/fields/ocean.py', ['apply_marine_point_mask', 'stitch_ocean_tile_frames', 'marine_point_mask']),
    (ROOT / 'app/services/ocean_features.py', ['current_vector_mask', 'bait_cluster_mask', 'marine_mask_for_point']),
    (ROOT / 'app/services/boat_generator.py', ['viewport_seeded_boat_entities_strict_land_masked', 'marine_point_mask', 'marine_mask_for_boat_point']),
    (ROOT / 'frontend/src/ui/intelligencePane.ts', ['selectSharkIntel', 'Area prediction', 'shark-prediction-score']),
    (ROOT / 'frontend/src/main.ts', ['sharkOceanIntel', 'sharkReportIntel', 'sharkIntelMarkers(cachedLocations, oceanSamples', 'reportAllowsMarineIntel']),
]

for path, needles in checks:
    text = path.read_text(encoding='utf-8')
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f'{path.relative_to(ROOT)} missing {missing}')

code = """
from app.spatial.viewport_query import parse_bbox, query_reports
from app.providers.rtofs_ncep import get_rtofs_provider
from app.services.marine_land_mask import marine_mask_for_point, marine_mask_for_boat_point
from app.services.boat_generator import generate_viewport_boats

bbox = parse_bbox('-125,32,-117,38')
frame, status = get_rtofs_provider().fetch_ocean(bbox)
contract = status.details.get('rtofs_tiled_contract') or frame.metadata.get('rtofs_tiled_contract') or {}
assert contract.get('all_ocean_requests_tiled') is True
assert contract.get('no_whole_viewport_rtofs_call') is True
assert contract.get('ocean_tile_count', 0) >= 1
boats = generate_viewport_boats(bbox, count=4)
assert boats['source'].endswith('land_masked')
assert boats['marine_point_mask']['point_level_mask'] is True
assert marine_mask_for_point(-104.99, 39.74)['should_render_ocean'] is False
assert marine_mask_for_boat_point(-117.90, 33.80)['should_render_boat'] is False
assert marine_mask_for_boat_point(-117.17, 32.70)['should_render_boat'] is True
for report in query_reports(bbox):
    assert hasattr(report, 'marine_mask')
print('ok')
"""
result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, text=True, capture_output=True)
if result.returncode:
    sys.stderr.write(result.stdout)
    sys.stderr.write(result.stderr)
    raise SystemExit(result.returncode)
print('✓ ocean/RTOFS tiling, point-level land mask, boats/bait/shark intel wiring checks passed')
