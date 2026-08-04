#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
checks = {
    "tile planner module": root / "app/fields/tiles.py",
    "atmosphere tiled builder": root / "app/fields/atmosphere.py",
    "ocean tiled builder": root / "app/fields/ocean.py",
    "gfs provider": root / "app/providers/gfs_ncss.py",
    "rtofs provider": root / "app/providers/rtofs_ncep.py",
    "config": root / "app/core/config.py",
}
text = {name: path.read_text() for name, path in checks.items()}
assert "stable_tile_plan" in text["tile planner module"], "stable tile planner missing"
assert "stable_world_lattice_8x8_cap64" in text["tile planner module"], "world lattice 8x8/64 cap missing"
assert "run_tiles_parallel" in text["tile planner module"], "parallel tile runner missing"
assert "build_tiled_mock_atmosphere_frame" in text["atmosphere tiled builder"], "tiled atmosphere frame builder missing"
assert "coordinate_model" in text["atmosphere tiled builder"] and "stable_world_space_lon_lat_not_viewport_normalized" in text["atmosphere tiled builder"], "stable world-space atmosphere model missing"
assert "build_tiled_mock_ocean_frame" in text["ocean tiled builder"], "tiled ocean frame builder missing"
assert "future_live_fetch_contract" in text["ocean tiled builder"], "future live tile fetch contract missing"
assert "field_engine_max_tiles" in text["config"] and "field_engine_tile_workers" in text["config"], "tile budgets missing from config"
assert "_no_data_frame" in text["gfs provider"] and "build_tiled_mock_atmosphere_frame" not in text["gfs provider"], "GFS provider must not use synthetic tiled fallback"
assert "_no_data_frame" in text["rtofs provider"] and "build_tiled_mock_ocean_frame" not in text["rtofs provider"], "RTOFS provider must not use synthetic tiled fallback"

# Runtime sanity: ensure a regional SoCal bbox produces a stable tile plan <= 64 and both
# atmosphere/ocean frames carry tile metadata.
sys.path.insert(0, str(root))
from app.fields.atmosphere import build_tiled_mock_atmosphere_frame
from app.fields.ocean import build_tiled_mock_ocean_frame
from app.fields.tiles import stable_tile_plan
from app.schemas.scene import BBox

bbox = BBox(west=-125, south=32, east=-117, north=38)
tiles, meta = stable_tile_plan(bbox, max_axis_tiles=8, max_tiles=64)
assert 1 <= len(tiles) <= 64, f"tile count out of range: {len(tiles)}"
assert meta["stable_across_zoom"] is True
atm = build_tiled_mock_atmosphere_frame(bbox, grid_shape=(64, 64), max_tiles=64, max_workers=8)
ocn = build_tiled_mock_ocean_frame(bbox, grid_shape=(64, 64), max_tiles=64, max_workers=8)
assert atm.grid_shape == (64, 64) and ocn.grid_shape == (64, 64)
assert atm.metadata["tile_plan"]["tile_count"] <= 64
assert ocn.metadata["tile_plan"]["tile_count"] <= 64
assert "cloud_density" in atm.channels and "current_u" in ocn.channels and "bait_score" in ocn.channels
print("✓ LFTR backend tile engine utilities remain available, while live providers no longer use synthetic tiled fallbacks")
