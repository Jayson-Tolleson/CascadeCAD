# Ocean tiling + land-mask + Shark Intel click patch

This patch makes the ocean side obey the same architectural rule as the atmosphere side: provider work is planned as stable lon/lat tiles first, then stitched into the viewport field.

## Provider rule

RTOFS/ocean requests now expose an explicit tiled contract:

- `all_ocean_requests_tiled: true`
- `no_whole_viewport_rtofs_call: true`
- stable world-lattice tile IDs from `stable_tile_plan`
- per-tile `marine_mask_for_bbox` before any provider request is allowed
- parallel tile execution through `run_tiles_parallel`
- stitched output through `stitch_ocean_tile_frames`

The live NetCDF tile parser is still the narrow implementation point: `RTOFSNCEPProvider._live_tile_frame(tile)`. That function is intentionally the only place real RTOFS NetCDF opening/subsetting belongs. The old whole-viewport path should not be reintroduced.

## Land-mask rule

The land mask now has two levels:

1. **Tile/bbox gate**: decides whether an ocean provider tile is worth querying.
2. **Point gate**: filters render/data points after stitching.

Point-level filtering applies to:

- ocean sample grids
- bait score cells and bait clusters
- current vectors
- boat spawn points
- shark intel prediction points
- shark CSV report markers where the report is inside conservative land core

Named harbors, bays, estuaries, nearshore boxes, and unknown coastal points are preserved so the mask does not accidentally erase useful inshore water.

## Shark Intel pane

Shark Intel now has clickable markers for both:

- CSV shark/ray/big-bite report locations
- ocean-condition prediction areas derived from bait score, current, and surface temperature

Clicking either marker opens the near-transparent glass pane with an area prediction score and evidence fields.
