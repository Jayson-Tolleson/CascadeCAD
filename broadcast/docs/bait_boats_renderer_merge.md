# Bait + Boats renderer merge wiring

This patch keeps the newest LFTR data spine authoritative and harvests the older renderer feel for bait and boats.

## Contract

- `ocean.field.patch` remains the raw ocean truth for SST, current, depth, and bait score.
- `ocean.features.patch` supplies merged current vectors and bait clusters when available.
- `boats.patch` remains the boat entity feed.
- There is still no standalone Ocean pill; Bait, Boats, and Shark Intel own the ocean visual surface.

## New renderer modules

- `frontend/src/renderer/baitLegacyVisual.ts`
  - normalizes raw ocean samples plus `ocean.features.patch.bait_clusters` into `BaitRenderFeature`.
  - renders old-style bait glow fields, core glows, side/depth sheets, spark markers, and drift lines.

- `frontend/src/renderer/boatLegacyVisual.ts`
  - normalizes boat entities plus nearest ocean current samples into `BoatRenderFeature`.
  - renders bow-forward hull triangles, safety halos, wake lines, and old-style boat markers.

## Lifecycle wiring

`frontend/src/main.ts` now draws bait and boats through the merged renderer adapters. Ocean field or feature updates refresh bait and also redraw boats, so heading/wake can react to new current truth without adding back the Ocean pill.
