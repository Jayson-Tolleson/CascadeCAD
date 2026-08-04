#!/usr/bin/env python3
"""Verify /gfs/api/stream no longer contains hidden or synthetic render paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
stream = (ROOT / "app/services/stream_bus.py").read_text()
engine = (ROOT / "app/services/field_truth_engine.py").read_text()
gfs = (ROOT / "app/providers/gfs_ncss.py").read_text()
rtofs = (ROOT / "app/providers/rtofs_ncep.py").read_text()
main = (ROOT / "frontend/src/main.ts").read_text()

failed = []
for bad in ["truth" + "_guard_clear_sky", "truth" + "_guard_empty_ocean_features", "non_realtime_atmosphere_hidden", "non_realtime_ocean_hidden", "mock" + "_sse_events", "mock" + "_stream_fps"]:
    if bad in stream + engine:
        failed.append(f"removed stream/engine token still present: {bad}")

for bad in ["_mock_frame", "build_tiled_mock_atmosphere_frame"]:
    if bad in gfs:
        failed.append(f"GFS provider still uses synthetic fallback: {bad}")
for bad in ["_mock_frame", "build_tiled_mock_ocean_frame", "sample_mock_ocean"]:
    if bad in rtofs:
        failed.append(f"RTOFS provider still uses synthetic fallback: {bad}")

for must in ["_no_data_frame", "data_state", "no_data"]:
    if must not in gfs + rtofs + engine:
        failed.append(f"missing honest no-data contract: {must}")

for must in ["locationOrbScaleForBBox", "currentViewportBBox", "clampedScale"]:
    if must not in main:
        failed.append(f"missing zoom-scaled green/fish orb sizing: {must}")

if failed:
    raise SystemExit({"ok": False, "check": "gfs_stream_no_mock_data", "failed": failed})
print({"ok": True, "check": "gfs_stream_no_mock_data", "mock_provider_paths_removed": True})
