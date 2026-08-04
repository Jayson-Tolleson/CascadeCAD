# Boats Strict Land-Mask Patch

This patch separates two land-mask policies:

- **Provider/ocean mask:** permissive near coasts so RTOFS/ocean tiles still load around harbors, bays, islands, deltas and unknown shoreline water.
- **Boat visual mask:** stricter for rendered boat entities so seeded boats cannot appear on obvious mainland or island land.

## Backend changes

- `app/services/marine_land_mask.py`
  - Adds `BOAT_RENDER_LAND_EXCLUSION_BOXES`.
  - Adds `marine_mask_for_boat_point()`.
  - Adds `should_render_boat_point()`.
  - Harbor/bay boxes are checked before strict exclusions, so San Diego Bay, Mission Bay, LA/Long Beach Harbor, Newport Bay, etc. still allow boats.
  - Broad nearshore helper boxes no longer punch holes through island/mainland exclusions for boats.

- `app/services/boat_generator.py`
  - Uses `marine_mask_for_boat_point()` instead of the looser ocean-provider point mask.
  - Boat payloads include `safety_metadata.boat_mask_checked = true` and the exact point-mask decision.
  - Source is now `viewport_seeded_boat_entities_strict_land_masked`.

## Frontend changes

- `frontend/src/renderer/boatLegacyVisual.ts`
  - Adds a final renderer guard that rejects boat entities whose payload mask says they are unsafe.
  - Adds matching client-side visual exclusion boxes as a last-resort safety net for legacy/stale boat payloads.
  - The merged old/new boat renderer now filters through this guard before drawing hulls, wakes, halos or markers.

## Checks

Run:

```bash
python3 scripts/check_boats_strict_land_mask.py
python3 scripts/check_ocean_tiled_landmask_shark_intel.py
```

Expected:

```text
✓ boats strict land-mask checks passed
✓ ocean/RTOFS tiling, point-level land mask, boats/bait/shark intel wiring checks passed
```
