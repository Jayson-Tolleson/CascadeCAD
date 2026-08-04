# Ocean → Bait + Boats morph/depth pass

This pass keeps the `/gfs` ocean truth field as the shared source for Bait and Boats while preventing redraw flashes.

## Ocean feature stability

`ocean.features.patch` now emits stable IDs for current vectors and bait clusters.  The old random UUID cluster suffix made every school look new on every SSE/PostGIS refresh; the frontend now receives stable cluster IDs based on rounded lon/lat/depth.

The RTOFS provider already tile-plans every request with the marine land mask.  Landlocked bboxes return a no-data patch with `should_query_ocean=false`; tiled coastal requests only keep water/harbor/bay tiles to avoid repeated NAN-heavy land calls.

## Bait renderer

Bait now renders as persistent schools:

- transparent orange shell around the school;
- mirror silver/white 4–8 inch particle glyphs inside the shell;
- even particle count per school, held stable while morphing;
- current-vector advection while old data is retained;
- smooth morph toward new PostGIS/RTOFS cluster position, score, radius, and scalar XYZ depth;
- depth is exposed in marker titles and the Location Intel pane as positive-down meters.

## Boats renderer

Boats now use the same ocean truth field:

- ocean hazard map drawn from current speed, bait score, and shallow-depth risk;
- 50 ft `ship2.gltf` model hook at each boat location;
- bow/heading faces the current-derived heading;
- overhead current speed text label with safety color;
- legacy polygon hull remains as fallback/visibility halo.

`frontend/public/models/ship2.gltf` is included from the user upload.  The supplied glTF references `ship2.bin`; place that binary beside the glTF if the browser reports the model buffer is missing.  The polygon hull/hazard/label renderer still works without the binary.
