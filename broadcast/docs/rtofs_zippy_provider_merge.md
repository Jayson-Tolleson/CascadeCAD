# RTOFS zippy provider merge

This pass keeps the zippy/ocean policy that matters most for production: **all RTOFS ocean calls are tile-only and land-mask-filtered**.  The app must not issue one large moving viewport request for SST/currents, because inland/land-heavy viewports produce mostly NaN cells and waste provider/server work.

## What changed

- Implemented the previously missing bounded NetCDF tile parser in `app/providers/rtofs_ncep.py`.
- Kept the stable world tile planner and per-tile marine land-mask gate.
- Added NOMADS bounded filter URL candidates before any direct file fallback.
- Added optional `LFTR_RTOFS_LOCAL_NC=/path/to/file.nc` for fixture/dev/proxy testing.
- Normalizes channels into the app contract:
  - `sst_c`
  - `water_temp_c`
  - `current_u`
  - `current_v`
  - `current_speed`
  - `current_direction`
  - `salinity`
  - `depth_m`
  - `bait_score`
  - `bait_depth_m`
- Preserves last-good tile and stitched-viewport caches.
- Publishes parser metadata into provider status and the intel pane path.

## Runtime path

```text
/gfs viewport bbox
→ stable world tile plan
→ marine land-mask filters out landlocked tiles
→ bounded NOMADS RTOFS NetCDF download per ocean tile
→ normalize RTOFS variables
→ derive current speed/direction + bait score/depth proxy
→ stitch tile frames into one viewport ocean frame
→ PostGIS feature cache write-through
→ bait / boats / intel panes consume ocean truth
```

## Notes

The first live pass uses RTOFS 2-D surface products.  That provides SST and currents for bait/boats immediately.  `bait_depth_m` is currently a surface-derived best-column proxy so the XYZ/depth render contract remains stable.  A later 3-D RTOFS product can replace only that depth derivation while leaving the frontend morphing/advecting code intact.

The provider intentionally returns honest `no_data` if NetCDF parsing or live downloads fail and no last-good cache exists.  It does not promote synthetic/mock ocean into the live/PostGIS pipeline.
