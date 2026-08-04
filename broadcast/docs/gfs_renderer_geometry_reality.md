# GFS Renderer Geometry Reality

## Current truth after the white-sphere diagnosis

`/gfs` is a real Google Photorealistic 3D map using `gmp-map-3d`, but Google 3D marker elements can still collapse custom DOM/SVG marker children into plain white marker spheres in some browser builds.

This package therefore moves the main visible objects away from marker glyph bodies and into Google 3D geometry:

| Layer/object | Current visual path |
|---|---|
| Cloud shell/body fill | `gmp-polygon-3d` shell + seeded polygon ellipses |
| CSV location/fish orbs | stacked extruded `gmp-polygon-3d` green cylinders plus faint ground glow |
| Bait | `gmp-polygon-3d` glowing ellipses |
| Rain | `gmp-polygon-3d` precipitation discs |
| Boats | `gmp-polygon-3d` heading triangles |
| Currents | `gmp-polyline-3d` vectors |
| Lightning | `gmp-polyline-3d` zig-zags |
| Inland water bodies | `gmp-polygon-3d` waterbody polygons |
| Water labels | small `gmp-polygon-3d` shimmer discs |

## What the white-sphere symptom means

If a layer renders only as white spheres, the data may still be arriving correctly. The problem is usually that a `gmp-marker-3d` element has ignored the custom glyph/SVG/CSS child and rendered the default marker body. That is why the primary layers now avoid marker visuals and use polygon/polyline geometry instead.

## Polygon extrusion note

`PolygonSpec` supports `extruded?: boolean`, and `syncPolygons()` forwards that value to Google’s `gmp-polygon-3d`. Extrusion connects a polygon to the ground. It is useful for walls/columns but is not a full sphere/cloud mesh. For clouds this package uses stacked/scalloped positive-altitude polygon ellipses. For green location/fish orbs this package now uses stacked translucent extruded cylinders: the path altitude is the cylinder top, and `extruded: true` connects the ring down to terrain.

## Next geometry target

The green orbs now use native polygon extrusion instead of model or marker fallback. The next high-fidelity pass should add GLB bodies for boats/fish where useful while keeping polygon geometry fallback. Clouds can continue improving through stacked/scalloped polygon ellipses or later a model/mesh strategy.

## Installer audit

The installer runs:

```bash
python3 scripts/check_gfs_renderer_geometry_reality.py
```

The expected renderer mode is:

```txt
google3d_extruded_polygon_cylinder_orbs_polygons_for_field_visuals_marker_fallback_disabled_for_main_objects
```

## 2026-06-18 no-mock provider update

The `/gfs/api/stream` route is now a plain field stream. Providers emit live/last-good parsed data or honest `no_data` patches. The after-the-fact hiding layer and synthetic provider fallbacks have been removed from the renderer path.

Default renderer behavior:

- live/last-good GFS NCSS arrays render clouds/rain
- unavailable atmosphere becomes `no_data` with zero cloud features, not fake clouds
- unavailable ocean/RTOFS becomes `no_data` with zero current vectors/bait clusters, not fake ocean
- raw provider diagnostics are still available through `/gfs/api/providers/status` and `/gfs/api/field-truth?debug_raw=true`
- PostGIS write-through caches only `source_kind=live_provider` rows by default

Operational fix:

- installer now creates `.cache/gfs`, `.cache/rtofs`, and `.cache/postgis` before service boot
- systemd now has `TimeoutStopSec=12` and `KillMode=control-group` so open browser streams do not hold restarts forever


## 2026-06-17 live GFS parser update

The earlier hidden-payload layer stopped synthetic cloud/ocean payloads, but it also made the map visually empty because the GFS live adapter was only a URL probe. This patch advances the atmosphere side from probe/stub to a bounded NCSS NetCDF parser:

- `LFTR_GFS_ENABLED` now defaults to `true` in the installer.
- The default GFS NCSS endpoint targets the `Global_0p25deg/Best` grid endpoint.
- `app/providers/gfs_ncss.py` downloads a bounded viewport NetCDF subset with `time=present`, `accept=netcdf4`, `addLatLon=true`, and `horizStride=1`.
- The parser normalizes GFS cloud cover, rain, wind, humidity, temperature, and pressure channels into LFTR field truth.
- Parsed live output is marked `live_parsed` / `gfs_ncss_live_parsed`, so the stream accepts clouds/rain without re-enabling synthetic atmosphere fields.
- Last-good parsed GFS cache is allowed to render as last-good parsed data; synthetic fields are not produced by the provider path.

RTOFS/ocean remains `no_data` until its real parser is implemented, so ocean/bait/current may stay sparse rather than drawing synthetic truth.

## 2026-06-18 extruded green cylinder orb update

The location/fish orbs no longer depend on `gmp-model-3d` or marker/SVG fallback. They now render as a stack of native `gmp-polygon-3d` circles with `extruded: true` on the main body layers. This should look like bright green 3D columns/glowing orb pillars instead of flat discs or white marker spheres.


## July 2026 note: fishing-orb hit target

The visible location body is still the stacked extruded green `gmp-polygon-3d` orb/cylinder.  A zippy-style `gmp-marker-3d-interactive` green orb is intentionally kept above it as the reliable click target for the fishing Location Intel pane, because polygon hit-testing varies across browser/GPU builds.

## Rain geometry

The Rain pill now renders colored precipitation spheres as small stacks of `gmp-polygon-3d` ellipses, falling from derived cloud top to near-ground floor.  Precipitation rate controls color, sphere count, fall speed, shaft width, and footprint.
