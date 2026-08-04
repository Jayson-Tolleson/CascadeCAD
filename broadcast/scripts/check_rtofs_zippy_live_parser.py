#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _venv_bootstrap import reexec_into_project_venv
    reexec_into_project_venv(ROOT)
except Exception:
    pass

import numpy as np
try:
    from netCDF4 import Dataset
except Exception as exc:
    print(json.dumps({"ok": True, "skipped": True, "reason": "netCDF4 not installed in this sandbox", "error": str(exc)}))
    raise SystemExit(0)

from app.core.config import get_settings
from app.providers.rtofs_ncep import get_rtofs_provider
from app.schemas.scene import BBox


def make_fixture(path: Path) -> None:
    with Dataset(path, 'w') as ds:
        ds.createDimension('lat', 8)
        ds.createDimension('lon', 9)
        lat = ds.createVariable('lat', 'f4', ('lat',))
        lon = ds.createVariable('lon', 'f4', ('lon',))
        lat.units = 'degrees_north'
        lon.units = 'degrees_east'
        lat[:] = np.linspace(32.0, 38.0, 8)
        lon[:] = np.linspace(235.0, 243.0, 9)  # 0..360 SoCal domain
        sst = ds.createVariable('sst', 'f4', ('lat', 'lon'), fill_value=np.nan)
        u = ds.createVariable('u_velocity', 'f4', ('lat', 'lon'), fill_value=np.nan)
        v = ds.createVariable('v_velocity', 'f4', ('lat', 'lon'), fill_value=np.nan)
        sal = ds.createVariable('sss', 'f4', ('lat', 'lon'), fill_value=np.nan)
        sst.units = 'degree_Celsius'
        u.units = 'm/s'
        v.units = 'm/s'
        sal.units = 'PSU'
        for r in range(8):
            for c in range(9):
                sst[r, c] = 16.0 + r * 0.12 + c * 0.08
                u[r, c] = 0.15 + c * 0.015
                v[r, c] = -0.05 + r * 0.012
                sal[r, c] = 33.2 + c * 0.01


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        fixture = Path(td) / 'rtofs_fixture.nc'
        make_fixture(fixture)
        os.environ['LFTR_RTOFS_LOCAL_NC'] = str(fixture)
        os.environ['LFTR_FIELD_ENGINE_TILE_GRID_SIZE'] = '6'
        os.environ['LFTR_FIELD_ENGINE_GRID_SIZE'] = '12'
        os.environ['LFTR_FIELD_ENGINE_TILE_WORKERS'] = '2'
        os.environ['LFTR_FIELD_ENGINE_MAX_TILES'] = '6'
        os.environ['LFTR_RTOFS_CACHE_DIR'] = str(Path(td) / 'rtofs-cache')
        get_settings.cache_clear()
        frame, status = get_rtofs_provider().fetch_ocean(BBox(west=-125, south=32, east=-117, north=38))
        channels = frame.channels
        required = ['sst_c', 'water_temp_c', 'current_u', 'current_v', 'current_speed', 'current_direction', 'salinity', 'bait_score', 'bait_depth_m']
        missing = [key for key in required if key not in channels]
        if missing:
            raise SystemExit(f'missing parsed channel(s): {missing}; channels={list(channels)}')
        if frame.grid_shape != (12, 12):
            raise SystemExit(f'unexpected stitched grid shape: {frame.grid_shape}')
        contract = frame.metadata.get('rtofs_tiled_contract', {})
        if not contract.get('all_ocean_requests_tiled') or not contract.get('no_whole_viewport_rtofs_call'):
            raise SystemExit(f'tile-only contract missing: {contract}')
        print(json.dumps({
            'ok': True,
            'live_ok': status.live_ok,
            'grid_shape': frame.grid_shape,
            'channels': sorted(channels),
            'tile_count': contract.get('good_tile_count') or contract.get('ocean_tile_count'),
            'parser_status': frame.metadata.get('parser_status'),
            'bait_depth_source': frame.metadata.get('bait_depth_source') or 'stitched',
        }))


if __name__ == '__main__':
    main()
