# LFTR Next

LFTR Next is a clean, runnable architecture checkpoint for the next-generation LFTR Marine Intelligence Globe. Google renders the base world, optional PostGIS contracts own stable place truth, GFS/RTOFS provider adapters define moving field-truth inputs, and TypeScript morphs visuals from streamed field patches. The GFS/RTOFS live paths are probe/stub adapters with cache/mock fallback until real bounded NetCDF/NCSS/NOMADS parsing is implemented.


## LFTR Next 1–6 Checkpoint Status

Complete in this checkpoint:

- Clean FastAPI app spine with health, scene snapshot, SSE stream, WebSocket, provider status, and spatial routes.
- TypeScript/Vite renderer shell with Google `<gmp-map-3d>` placeholder, field store, object pools, animation loop, and morphing layer placeholders.
- GFS atmosphere provider adapter contract with live probe/stub, last-good cache path, and mock fallback.
- RTOFS ocean provider adapter contract with live probe/stub, last-good cache path, depth-ready interface, and mock fallback.
- Optional PostGIS schema/migration/viewport-spatial contract for stable place truth.

Adapter/stub, not finished production parsing:

- Live GFS NCSS NetCDF parsing is now implemented for bounded viewport subsets. The adapter maps parsed GFS cloud/rain/wind/humidity/temperature/pressure fields into LFTR field truth. RTOFS parsing is still guarded until its live parser is implemented.
- Live RTOFS NOMADS NetCDF parsing is TODO. Current live path only probes availability and returns mock-shaped field frames with explicit `live_stub`/`probe` metadata.
- Chlorophyll/ocean-color provider is documented as a disabled future booster for bait score.

Next pass #7 should add USGS/NHD lake ingest into PostGIS spatial truth. Do not add boats, lightning, broadcast/watch migration, or production NOAA/RTOFS parsers in this checkpoint.


## Public Site Index

LFTR Next now separates the public website launcher from the globe and broadcast runtimes:

- `/` is the LFTR.biz public landing page, inspired by the old zippy index page.
- `/gfs` is the Marine Intelligence Globe.
- `/broadcast` is the clean broadcaster runtime.
- `/watch` is the clean watcher runtime.

The public index keeps the old LFTR stacked-preview idea, but it lazy-loads `/watch`, `/gfs`, and the playlist previews so the homepage stays fast and does not boot the GFS globe or broadcast runtime by default. The old zippy page was mined for visual/design behavior only; no legacy route sprawl or old GFS renderer files were imported.


## Renderer Geometry Reality

Current `/gfs` rendering is a hybrid Google 3D renderer:

- The base globe is real `<gmp-map-3d>`.
- Cloud shells, waterbody footprints, and line paths use real Google 3D child elements such as `gmp-polygon-3d` and `gmp-polyline-3d`.
- Cloud fill particles, green fish/location orbs, and several small object layers still use `gmp-marker-3d` / `gmp-marker-3d-interactive` glyph or DOM fallbacks. If they collapse into white dots, the data likely arrived, but the marker child/SVG/CSS fallback did not render as a true mesh.
- `PolygonSpec.extruded` is now wired through to `gmp-polygon-3d`, but polygon extrusion connects a polygon down to ground; floating clouds/orbs still need stacked polygons or `gmp-model-3d` GLB objects.

The installer runs:

```bash
python3 scripts/check_gfs_renderer_geometry_reality.py
```

to print this audit during install. See `docs/gfs_renderer_geometry_reality.md` for the full renderer truth table and next geometry target.

## Architecture

- **Backend:** Python 3, FastAPI, Uvicorn ASGI.
- **Frontend:** TypeScript, Vite, Google `<gmp-map-3d>` placeholder.
- **Streaming:** Server-Sent Events at `/gfs/api/stream` and WebSocket placeholder at `/ws/gfs`.
- **Deployment templates:** systemd and Nginx placeholders in `deploy/`.

## Install

```bash
cd lftr-next
scripts/install.sh
```

The installer creates `.venv`, installs backend dependencies, installs frontend packages when `npm` exists, builds the frontend, and prints the next commands.

The backend dependency set explicitly includes `pydantic` and `pydantic-settings`; rerun the installer or run `.venv/bin/python -m pip install -e .` after updating an existing server copy.

## Run

Backend:

```bash
cd lftr-next
. .venv/bin/activate
python -m app.main
```

Frontend development server:

```bash
cd lftr-next/frontend
npm run dev
```

Open the Vite URL, usually <http://127.0.0.1:5173>. The page boots a Google 3D map placeholder, layer pills, a mock scene fetch, and an SSE debug pane.



## Provider Catalog

The provider catalog is available in code at `app/providers/catalog.py`, in docs at `docs/providers.md`, and at runtime via `GET /gfs/api/providers/catalog`. Runtime config values are authoritative; documented URLs are templates/examples for future parser work.

### GFS NCSS Atmosphere

`gfs_ncss_atmosphere` is the moving atmosphere field-truth adapter for clouds, rain, wind, humidity, temperature, and pressure. It documents NCSS query parameters (`var`, `north`, `south`, `east`, `west`, `time=present`, `accept=netcdf4`, `addLatLon=true`), expected GFS variables, normalized LFTR channels, units, and parser TODOs. Current live behavior is a probe/stub with mock fallback, not real parsed NetCDF field truth.

### RTOFS/NOMADS Ocean

`rtofs_ncep_ocean` is the moving ocean field-truth adapter for SST, current vectors, salinity/depth metadata, and derived bait score. It documents NOMADS source templates, product files, aliases, normalized ocean channels, depth levels, and the future `sample(lon, lat, depth_m, time)` interface. Current live behavior is a probe/stub with mock fallback, not real parsed RTOFS NetCDF field truth.

### Chlorophyll / Ocean Color Future Booster

`chlorophyll_ocean_color` is disabled by default. It documents NOAA CoastWatch ERDDAP and NASA OceanColor source families and possible chlorophyll aliases. Chlorophyll can boost or shape `bait_score` later, but it must never block ocean rendering; if missing, bait score still derives from SST/current/depth.

## Field Truth Engine

LFTR Next is organized around four truth/rendering responsibilities:

- **PostGIS = stable place truth:** future durable geometry, harbors, coast masks, lakes, named areas, and report joins. PostGIS is optional in this pass and disabled by default.
- **Field Engine = moving atmosphere/ocean truth:** Python builds compact scalar fields for clouds, rain, wind, humidity, sea-surface temperature, currents, and bait score.
- **Google map = base world renderer:** `<gmp-map-3d>` remains the world/camera substrate.
- **TypeScript renderer = morphing visual layer:** browser code samples compact field patches and morphs visual layers instead of receiving thousands of rendered objects.

The stream currently uses JSON field patches for readability. Binary Float32Array/quantized encodings are explicit TODOs after the contract stabilizes. Stream tick rate is configured by `LFTR_STREAM_TICK_HZ` and defaults to 1 Hz; `LFTR_TARGET_STREAM_FPS` records the future 5-10 fps target.



## GFS Atmosphere Provider

GFS is now modeled as a **provider adapter**, not a renderer. The adapter targets bounded NCSS NetCDF access and maps available GFS variables such as total cloud cover, precipitation rate, humidity, temperature, pressure, and u/v wind into LFTR atmosphere field truth channels. The browser still receives compact field patches; it never receives thousands of server-made cloud objects.

Provider mode is controlled by `LFTR_PROVIDER_MODE=mock|live|hybrid`. The installer now defaults `LFTR_GFS_ENABLED=true` so live parsed GFS clouds/rain can render when NCSS is reachable. If live GFS fails, the provider attempts a last-good cache from `LFTR_GFS_CACHE_DIR`; if no cache exists, it returns a degraded mock frame with explicit provider metadata instead of crashing scene or stream endpoints.

Debug endpoints:

- `GET /gfs/api/providers/status` reports provider mode and GFS adapter status.
- `GET /gfs/api/providers/gfs?bbox=minLon,minLat,maxLon,maxLat` returns the atmosphere frame and provider metadata.
- `GET /gfs/api/field-truth?bbox=minLon,minLat,maxLon,maxLat` returns the encoded atmosphere field patch used by the stream.

Use `scripts/check_gfs_provider.py` and `scripts/check_provider_catalog.py` to validate mock/hybrid provider behavior and provider catalog honesty.


## RTOFS Ocean Provider

RTOFS is the ocean field-truth provider. Like GFS, it is an adapter that feeds compact backend fields rather than rendered objects. The ocean renderer samples those fields client-side for current streamlets, SST hints, bait glow, and future boat orientation.

The RTOFS provider is safe by default: `LFTR_RTOFS_PROVIDER_MODE=hybrid` and `LFTR_RTOFS_ENABLED=false` return degraded mock ocean truth with explicit metadata. Live RTOFS failures fall back to last-good cache from `LFTR_RTOFS_CACHE_DIR`; if no cache exists, the provider returns mock ocean fields and never crashes scene or stream endpoints.

Ocean truth channels include `sst_c`, `current_u`, `current_v`, and derived `bait_score`, plus optional/diagnostic `salinity`, `depth_m`, `current_speed`, and `current_direction`. Bait score is a deterministic scalar field derived from SST suitability, current-speed suitability, and optional depth suitability. Chlorophyll is reserved as a future booster and does not block rendering.

The provider interface is depth-ready for future 3D truth via `sample(lon, lat, depth_m, time)`. This pass begins with surface data (`depth 0` / `surface`) while preserving depth-level metadata and aliases for SST, current vectors, salinity, and depth.

Debug scripts:

- `scripts/check_rtofs_provider.py` validates `/gfs/api/providers/rtofs`.
- `scripts/check_ocean_truth.py` validates the encoded ocean field-truth patch from `/gfs/api/field-truth`.

## Morphing Renderer Lifecycle

The first renderer architecture intentionally avoids delete/redraw cycles:

1. **Snapshot:** the browser loads `/gfs/api/scene-frame` once to establish stable scene contracts.
2. **Stream:** the browser opens `/gfs/api/stream` and receives reconnect-friendly event IDs for heartbeat, atmosphere patches, ocean patches, and report patches.
3. **Field store:** incoming field patches update target state only; they do not directly redraw layers.
4. **Target state:** cloud, rain, ocean, bait, and report layers sample the latest compact field patches through capped budgets.
5. **Animation loop:** `requestAnimationFrame` ticks all animated layers.
6. **Morphing scene graph:** stable pooled DOM placeholders morph opacity, scale, footprint, altitude, and position toward the newest target values, fading unused objects instead of deleting them immediately.

Budgets are tiered as `global`, `regional`, and `local` so the renderer never creates unbounded particles or markers. Cloud placeholders sample `cloud_density` with wind advection TODO hooks from `wind_u`/`wind_v`; rain placeholders sample `rain_rate`; ocean placeholders sample `sst_c`, `current_u`/`current_v`, and `bait_score`.


## PostGIS Stable Spatial Truth

PostGIS is optional and owns stable place/world geometry only: coast and land-water masks, harbors, lakes/waterbodies, islands, spatial tiles, label anchors, simplified tier geometries, viewport intersections, and CSV report points. It must not store high-frequency GFS/RTOFS field frames.

Responsibilities remain split:

- **PostGIS = stable place truth** with spatial indexes and viewport queries.
- **GFS/RTOFS = moving field truth** for atmosphere, ocean, bait score, current, and SST fields.
- **Google `<gmp-map-3d>` = base world renderer** for terrain/buildings.
- **TypeScript renderer = morphing display layer** with object pools, field sampling, and budgets.

Safe defaults keep the app runnable without a database: `LFTR_SPATIAL_MODE=mock`, `LFTR_POSTGIS_ENABLED=false`, and no DSN required. In `hybrid` mode, viewport spatial queries use PostGIS when available and fall back to CSV/mock data without exposing the DSN.

PostGIS utilities:

- `scripts/install_postgis.sh` prints conservative Ubuntu/Debian install notes and runs migrations only when `LFTR_POSTGIS_DSN` is configured.
- `scripts/migrate_postgis.py` runs idempotent schema creation without destroying data.
- `scripts/load_reports_to_postgis.py` loads `data/reports.csv` into `spatial_reports`.
- `scripts/check_postgis.py` reports sanitized PostGIS status.
- `scripts/check_viewport_spatial.py` validates `/gfs/api/viewport-spatial`.

Admin/debug endpoints:

- `GET /gfs/api/spatial/status` returns sanitized spatial/PostGIS status.
- `POST /gfs/api/spatial/migrate` runs idempotent migrations when DB access is configured.
- `POST /gfs/api/spatial/load-reports` loads CSV reports into PostGIS.
- `GET /gfs/api/spatial/reports?bbox=minLon,minLat,maxLon,maxLat` queries report points.
- `GET /gfs/api/spatial/waterbodies?bbox=minLon,minLat,maxLon,maxLat&tier=regional` queries simplified waterbodies.



## Visual Layer Contracts (#8)

Pass #8 adds clean visual layer contracts and first lightweight adapters over existing truth systems. Clouds/rain sample atmosphere fields; ocean/current sample ocean fields; bait is a bounded scalar-field glow from `bait_score`; boats are stable viewport entities generated from viewport/spatial/ocean-current truth; lightning is a short-lived TTL event layer; inland water consumes stable USGS/PostGIS waterbody IDs and labels; reports remain CSV/PostGIS spatial points.

The renderer flow remains `snapshot → stream → field store → target state → animation loop → morphing object pools`. This pass does not add broadcast/watch, WebRTC, STT, AI chat, full NOAA/RTOFS parsers, or giant legacy frontend code.

Layer endpoints:

- `GET /gfs/api/layers/status` returns layer contracts, budgets, provider/spatial status, and renderer expectations.
- `GET /gfs/api/layers/boats?bbox=minLon,minLat,maxLon,maxLat` returns deterministic stable viewport boats.
- `GET /gfs/api/layers/lightning?bbox=minLon,minLat,maxLon,maxLat` returns TTL mock/GLM-style flashes.
- `GET /gfs/api/layers/bait?bbox=minLon,minLat,maxLon,maxLat` summarizes field-derived bait score metadata.

## USGS Hydrography / Inland Water Pass #7

Pass #7 adds stable inland-water geometry only. USGS 3DHP/current hydrography should be preferred when configured, while NHDPlus HR and NHD are legacy/reference source families. Supported source adapters are `3dhp`, `nhdplus_hr`, `nhd`, `arcgis_rest`, `geojson`, `shapefile_zip`, and `mock`.

The ingest normalizes source features into LFTR waterbody objects with stable IDs, source metadata, kind, area, geometry, label point, bbox, properties, and ingest batch ID. PostGIS is optional but recommended for durable stable spatial truth; mock and GeoJSON modes run without network or PostGIS.

This pass does **not** add live lake temperature, inland bait scoring, boats, lightning, or a new renderer. Waterbody geometry persists independently of GFS/RTOFS weather and ocean fields.

USGS endpoints and scripts:

- `GET /gfs/api/spatial/usgs/status` reports sanitized config and cache/PostGIS availability.
- `POST /gfs/api/spatial/usgs/ingest?bbox=minLon,minLat,maxLon,maxLat` runs configured ingest for a bbox.
- `GET /gfs/api/spatial/waterbodies?bbox=minLon,minLat,maxLon,maxLat&tier=regional` returns PostGIS or mock/cache waterbodies.
- `scripts/ingest_usgs_waterbodies.py`, `scripts/check_usgs_ingest.py`, `scripts/check_waterbody_viewport.py`, and `scripts/check_postgis_waterbodies.py` support local checks.

## API Contracts

### `GET /health`

Returns:

```json
{"ok": true}
```

### `GET /gfs/api/scene-frame`

Returns a mock scene snapshot with these top-level keys:

- `ok`
- `scene_id`
- `generated_at`
- `bbox`
- `viewport`
- `layers`
- `spatial`
- `fields`

### `GET /gfs/api/reports?bbox=minLon,minLat,maxLon,maxLat`

Returns CSV-backed report points inside the requested bbox. If `data/reports.csv` is missing, the backend creates a small example CSV.

### `GET /gfs/api/viewport-spatial?bbox=minLon,minLat,maxLon,maxLat&tier=regional`

Returns reports, waterbodies/lakes, harbors, coast mask metadata, spatial mode, sanitized PostGIS status, geometry tier, stable IDs, and diagnostics for viewport-aware spatial truth.

### `GET /gfs/api/stream`

Streams mock SSE events:

- `scene.heartbeat`
- `atmosphere.field.patch`
- `ocean.field.patch`

### `WS /ws/gfs`

Accepts a WebSocket connection and echoes messages after an initial heartbeat placeholder.

## Checks

With the backend running:

```bash
scripts/check_health.sh
scripts/check_scene_snapshot.sh
scripts/check_gfs_provider.py
scripts/check_rtofs_provider.py
scripts/check_ocean_truth.py
scripts/check_postgis.py
scripts/check_viewport_spatial.py
scripts/check_provider_catalog.py
scripts/check_pre7_checkpoint.sh
scripts/check_usgs_ingest.py
scripts/check_waterbody_viewport.py
scripts/check_postgis_waterbodies.py
scripts/check_layers.py
scripts/check_bait_boats_lightning.py
scripts/check_broadcast_migration_plan.py
scripts/check_broadcast_routes.py
scripts/check_broadcast_runtime.py
scripts/check_broadcast_frontend.py
curl -N http://127.0.0.1:8787/gfs/api/stream
```

Frontend compile/build:

```bash
cd frontend
npm run build
```

## Deployment Templates

- `deploy/systemd/lftr-next.service` assumes installation under `/opt/lftr-next` and a `lftr` service user.
- `deploy/nginx/lftr-next.conf` serves the built frontend and proxies `/health`, `/gfs/api/`, and `/ws/gfs` to Uvicorn.

## TODO Boundaries

- Implement real bounded GFS NCSS NetCDF parsing behind the existing adapter.
- Implement real bounded RTOFS NOMADS NetCDF parsing behind the existing adapter.
- Pass #7: USGS/3DHP/NHD/NHDPlus stable inland-water geometry ingest is now scaffolded; future work should add production source configs and richer validation.
- Keep chlorophyll as a future optional bait-score booster until a dataset is selected.
- Replace placeholder layer modules with efficient globe-native rendering.

## Broadcast/Watch Runtime (#9)

Pass #9 adds a compact broadcast/watch runtime that is isolated from the GFS globe renderer. The globe continues to use `/gfs`, `/gfs/api/scene-frame`, `/gfs/api/stream`, and `/ws/gfs`; broadcast/watch uses only `/broadcast`, `/watch`, `/ws/broadcast`, `/ws/watch`, `/ws/chat`, and `/api/broadcast/status`.

The runtime intentionally avoids legacy route sprawl: there are no `/broadcast2` or `/watch2` routes, no old GFS-prefixed broadcast aliases, and no duplicated chat sockets or media-loop routes. Broadcast/watch pages do not import `frontend/src/renderer/*`, `frontend/src/fields/*`, Google map modules, or `/gfs/api/scene-frame`.

### Broadcast routes

- `GET /broadcast` returns the broadcaster page.
- `GET /watch` returns the watcher page.
- `GET /api/broadcast/status` returns safe room/socket status without secrets.
- `WS /ws/broadcast` handles broadcaster presence, media status, and signaling relay.
- `WS /ws/watch` handles watcher presence and signaling relay back to the broadcaster.
- `WS /ws/chat` handles sanitized chat, STT transcript events, AI placeholders, upload metadata placeholders, web/search placeholders, debug, and system notices.

### Frontend behavior

The broadcaster page has camera preview, start/stop camera, front/back camera switching, microphone permission check, chat, STT browser hook, AI/upload/web-search placeholders, and status/debug panels. The watcher page has a muted autoplay-friendly video element, collapsible chat panel, Enter-to-send chat, upload/search placeholders, and playback/debug status.

Server-side STT, external AI APIs, and real upload storage are intentionally deferred. The current upload path is a bounded placeholder: chat can carry upload metadata, but no file endpoint is enabled by default.

## GCP / web installer

This package is intended to extract as `~/broadcast` and can be installed with:

```bash
cd ~/broadcast
sudo bash broadcast.sh
```

The installer now mirrors the old LFTR `broadcast.sh` behavior while keeping the new compact app architecture. It provides whiptail/dialog prompts when available, with plain-text fallback. It can configure:

- Python virtual environment and package install
- TypeScript/Vite frontend build with the Google Maps key
- backend app port, default `8787`
- public HTTP/HTTPS ports, defaults `80` and `443`
- nginx route separation for `/`, `/gfs`, `/broadcast`, and `/watch`
- SSE and WebSocket proxy paths
- local `ufw` firewall ports
- optional Google Cloud firewall rule creation/update for selected TCP ports
- Google Cloud project, default `broadcaster-fishmap`
- Vertex AI/Speech/Text-to-Speech API enablement when `gcloud` is available
- optional service-account JSON key path or attached service account ADC
- optional Let’s Encrypt certificate via Certbot when a real domain points to the VM
- systemd service, default `broadcast.service`

The installer writes selected deployment values to `/etc/broadcast/install.env` and app runtime values to `~/broadcast/.env`.



## Installer npm/reify note

This package intentionally does not ship a `frontend/package-lock.json`.
If npm appears to stall at `reify`, check whether an old lockfile points at an internal mirror such as
`packages.applied-caas-gateway1.internal.api.openai.org`. The installer now removes that bad lockfile automatically
and writes `frontend/.npmrc` to use `https://registry.npmjs.org/`.

Manual recovery on an existing server:

```bash
cd ~/broadcast/frontend
rm -rf node_modules package-lock.json
cat > .npmrc <<'NPMRC'
registry=https://registry.npmjs.org/
audit=false
fund=false
NPMRC
npm install --no-audit --no-fund --registry=https://registry.npmjs.org/
npm run build
```

Or run:

```bash
bash ~/broadcast/scripts/fix_frontend_npm.sh ~/broadcast
```

### Runtime env repair

If an older installer run wrote Google/Vertex variables and the backend logs show
`Extra inputs are not permitted`, run:

```bash
cd ~/broadcast
bash scripts/fix_runtime_env.sh ~/broadcast
sudo systemctl restart broadcast
curl -i http://127.0.0.1:8787/health
```

The app settings intentionally ignore unknown deployment variables and accept LFTR_*
Google/Vertex placeholders so installer configuration cannot prevent startup.

## Correction checkpoint: real Google 3D globe and simple launcher

The `/gfs` frontend now boots the actual Google 3D Maps surface with `maps3d`, `Map3DElement`, and a `gmp-map-3d` fallback element. LFTR data overlays are appended to the Google 3D map using `Marker3DElement`, `Polyline3DElement`, and `Polygon3DElement` instead of a separate screen-space div projection.

The public `/` page is intentionally simple:

- `Open Globe` → `/gfs`
- `Broadcast` → `/broadcast`
- `Watch` → `/watch`

The broadcaster page includes local browser recording with a downloadable `.webm` file and a direct link to `/watch`.

Check:

```bash
python scripts/check_google3d_contract.py
```


### Broadcast/watch live-stream behavior

`/watch` is designed to remain open in standby. If a broadcaster starts later, reconnects, or switches tracks, the watcher sends bounded `watcher-ready` notices and accepts a new WebRTC offer without requiring a reload. `/broadcast` includes a front/back camera facing pill that toggles `facingMode` between `user` and `environment` and renegotiates tracks for existing watchers.

### Broadcast finish pill set

`/broadcast` is intentionally simple now: camera auto-starts for browser permissions, `Facing` switches front/back camera, `SCREEN compositor` captures the screen with a camera overlay, `Record` toggles start/stop and auto-downloads a `.webm`, and `RTMP` remains staged for future outbound streaming. Removed controls: CAM on, MIC on/off, NoiseCancel, and separate Download.

## `/gfs` Locations Layer

The final pill is now **Locations**. It renders CSV-backed LFTR fishing locations from `data/fishloclist.csv` as green glowing 3D orbs on the Google 3D map. Clicking a location opens a transparent glass pane with the original CSV location fields and `report_#` indices.

Use this viewport intake check after the service is running:

```bash
bash scripts/check_gfs_viewport_data_intake.sh http://127.0.0.1:8787 -125,32,-117,38 regional
```

## /gfs layer-pill render toggles

The `/gfs` pills now own real render groups instead of acting as labels only. Toggling a pill clears or restores that layer's Google 3D objects:

- Locations: zippy CSV green-orb markers and click-open glass pane
- Clouds: cloud-density glyphs
- Rain: rain-rate glyphs
- Ocean: current arrows and current vector lines
- Bait: bait-score glow markers
- Boats: viewport boat markers
- Inland Water: waterbody polygons and labels
- Lightning: short-lived flash markers

Locations intentionally load first and remain the leftmost pill because they are the stable CSV intelligence layer.

### GFS Cloud Renderer Pass 1

`/gfs` now begins from a top-down zippy-style weather view. Locations load first, then the Clouds layer renders family-aware cloud objects on the Google 3D map. The first cloud pass supports wisps, puffs, sheets, marine layer, and storm masses using the active atmosphere field patch. This is a rendering pass only; live GFS parsing remains governed by the provider adapter status.

## LFTR Field Engine Pass 1 — cloud + ocean compatible

This build replaces the old 4x4 atmosphere mock with dense viewport scalar fields.  The backend now has shared x/y/z scalar primitives:

- `ScalarField2D.bilinear(lon, lat)`
- `ScalarField3D.trilinear(lon, lat, z)`

Atmosphere uses altitude-style levels for cloud families.  Ocean uses depth levels in meters positive downward (`surface`, `10m`, `25m`, `50m`, `100m`) so later RTOFS parsing can fill the same interface.

Streaming now includes:

- `atmosphere.field.patch` — dense 64x64 cloud/rain/wind field
- `cloud.features.patch` — connected cloud masses classified as wisp, puff, sheet, marine-layer, or storm
- `ocean.field.patch` — dense 64x64 surface ocean fields plus backend depth metadata
- `ocean.features.patch` — current vectors and bait clusters derived from the ocean scalar field

The frontend renders clouds from `cloud.features.patch` when available and falls back to raw grid sampling when needed.  The ocean renderer remains compatible with `ocean.field.patch`, while the backend is ready to compute deeper ocean/bait truth from the same x/y/depth interface.


## PostGIS Pre-Render Feature Store

The `/gfs` field engine can now optionally pre-render cloud/ocean/bait feature recipes into PostGIS. See `docs/postgis_prerender_arch.md`. The browser still opens one viewport stream; the backend can answer from cached feature geometry and fall back to live field extraction when the cache is empty or disabled.

## GFS renderer geometry reality

`/gfs` uses Google Photorealistic 3D via `gmp-map-3d`. Main visible layers now avoid marker glyph bodies and use `gmp-polygon-3d` / `gmp-polyline-3d` geometry where practical. Run `python3 scripts/check_gfs_renderer_geometry_reality.py` for the install audit.

## No-mock provider data — no synthetic cloud/ocean recipes in PostGIS

Earlier architecture builds could generate stable synthetic atmosphere and ocean fields and, when `LFTR_RENDER_CACHE_ENABLED=true` with write-through, store those recipes into PostGIS. They looked realtime because their `valid_time` was updated at runtime, but the source was still synthetic field-engine fallback. Providers now return live/last-good parsed data or honest `no_data`, and PostGIS only caches `source_kind=live_provider` rows by default.

Defaults:

```env
LFTR_RENDER_CACHE_ALLOW_DEGRADED="false"
LFTR_PROVIDER_MODE="live"
LFTR_RTOFS_PROVIDER_MODE="live"
LFTR_STREAM_TICK_HZ="1.0"
```

With those defaults, `/gfs/api/stream` will not draw cloud/ocean feature bodies from synthetic providers, and PostGIS prerender queries only serve rows marked `_lftr_source_kind=live_provider` and still inside the render-cache TTL. The GFS live adapter is now parsed NCSS data; RTOFS returns `no_data` until its parser is completed. Clouds should render only when parsed GFS reports cloud cover, while ocean/bait/current may intentionally remain sparse until the RTOFS parser is completed.

If an older install already has mock rows in PostGIS, audit and purge them with:

```bash
cd ~/broadcast
python3 scripts/purge_gfs_mock_prerender_cache.py
python3 scripts/purge_gfs_mock_prerender_cache.py --apply
```

## Green orb geometry update

The old marker orb could collapse to a white Google marker sphere. The replacement polygon orb initially looked flat because it was only horizontal discs. This build adds two vertical polygon cross-sections per orb, so locations read more like a small 3D green globe while still avoiding the marker glyph fallback path.


## No-mock provider data

`/gfs/api/stream` no longer uses a separate truth-guard hiding layer and the provider paths no longer manufacture mock GFS/RTOFS fields. Providers now return either live/last-good parsed data or honest `no_data` patches with empty feature arrays. This keeps fake cloudy/ocean scenes out of the realtime renderer without relying on after-the-fact filtering.

Use this compact stream audit after install:

```bash
timeout 12 curl -sN "http://127.0.0.1:8787/gfs/api/stream?bbox=-119,33,-117,35&tier=regional" \
  | sed -n 's/^data: //p' \
  | jq -c 'paths(scalars) as $p | {path:($p|map(tostring)|join(".")), value:getpath($p)} | select(.value|tostring|test("mock|stub|synthetic";"i"))'
```

No output is ideal. `no_data` output is acceptable when a provider has no live parser or last-good cache yet.


## 2026-06-17 live-cloud/orb recovery patch

After fake clouds were removed, the map became too empty because GFS was still only probing URLs. This patch adds a bounded GFS NCSS NetCDF parser and enables `LFTR_GFS_ENABLED=true` by default in the installer, so clouds and rain can draw from parsed realtime atmosphere data instead of synthetic fields.

The flat green orbs were corrected again: CSV location/fish orbs now render as stacked native `gmp-polygon-3d` green cylinders with `extruded: true`, plus a faint ground glow. This avoids both marker white-sphere fallback and flat-only polygon discs.


### 2026-06-18 Green orb cylinder pass

Locations now use stacked extruded `gmp-polygon-3d` cylinders. In Google 3D polygons, cylinder height comes from the path altitude plus `extruded: true`; there is no separate native `height` property. The renderer clears the old `location-models` and `locations` marker groups so the visible location body is native polygon geometry.

### Marine land mask

The backend now gates ocean-provider calls with a conservative marine land mask. Obvious landlocked bboxes skip future SST/RTOFS/chlorophyll/bait-current calls, while harbors, bays, estuaries, sounds, islands, deltas, and nearshore tiles stay queryable. Test it with `/gfs/api/marine-mask?bbox=west,south,east,north` or run `scripts/check_gfs_marine_land_mask.py`.
