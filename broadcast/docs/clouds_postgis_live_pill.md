# Clouds Pill — PostGIS-first live renderer

This build moves the `/gfs` Clouds pill to a PostGIS-first live-data contract without promoting mock cloud data.

## Runtime flow

1. `/gfs/api/stream?bbox=west,south,east,north&tier=regional` emits `atmosphere.field.patch` and `cloud.features.patch`.
2. GFS NCSS live/last-good frames are parsed by `app/providers/gfs_ncss.py`.
3. `app/services/cloud_features.py` extracts meteorology-facing cloud families:
   - `cumulus`
   - `stratus`
   - `cirrus`
   - `marine-stratus`
   - `cumulonimbus`
4. `app/services/field_truth_engine.py` checks PostGIS first when enabled:
   - read: `lftr.cloud_render_features`
   - fallback: live GFS feature extraction
   - write-through: live-provider cloud feature recipes only
5. `frontend/src/main.ts` and `frontend/src/renderer/cloudParticles.ts` render seeded `gmp-polygon-3d` cloud particles and shell swaths.

## New cloud endpoints

```bash
curl "http://127.0.0.1:8787/gfs/api/layers/clouds?bbox=-125,32,-117,38&tier=regional" | jq '.clouds.feature_count,.clouds.metadata.render_cache'
```

```bash
curl -X POST "http://127.0.0.1:8787/gfs/api/prerender/clouds?bbox=-125,32,-117,38&tier=regional" | jq
```

## PostGIS defaults

The installer now defaults to:

```bash
LFTR_POSTGIS_DSN=postgresql:///lftr_next
LFTR_POSTGIS_ENABLED=true
LFTR_SPATIAL_MODE=postgis
LFTR_RENDER_CACHE_ENABLED=true
LFTR_RENDER_CACHE_PREFER_POSTGIS=true
LFTR_RENDER_CACHE_WRITE_THROUGH=true
LFTR_RENDER_CACHE_ALLOW_DEGRADED=false
```

If local PostgreSQL/PostGIS is available, the installer creates/uses `lftr_next`, enables the `postgis` extension, and runs migrations. If the DB is not reachable, Clouds still render from live/last-good GFS extraction and report a cache miss/error in metadata instead of crashing.

## Checks

```bash
python scripts/check_gfs_cloud_postgis_live_contract.py
python scripts/check_gfs_cloud_shell_fill_particles.py
python scripts/check_gfs_cloud_retained_swaths.py
python scripts/check_gfs_renderer_geometry_reality.py
python scripts/check_gfs_truth_guard_no_mock_postgis.py
python scripts/check_gfs_postgis_prerender_arch.py
```
