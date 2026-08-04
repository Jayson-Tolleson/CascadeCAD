# LFTR PostGIS Pre-Render Data Architecture

This pass introduces an optional PostGIS-backed pre-render feature store for `/gfs`.

The rule is: **PostGIS stores interpreted render features, not raw provider grids and not final particles.**

## Runtime flow

Browser stays simple:

```text
/gfs/api/stream?bbox=...
```

Backend can now do:

```text
viewport bbox
→ query PostGIS cloud/ocean/bait feature recipes
→ stream cached feature patches when available
→ fallback to live Field Engine extraction when cache is empty/unavailable
```

## Pre-render flow

A worker can run separately:

```text
GFS/RTOFS/provider or mock field engine
→ stable 8×8 world tile plan
→ dense scalar fields
→ feature extraction
→ PostGIS cloud/ocean/bait render tables
```

## Tables

- `render_tiles`: metadata for rendered feature tiles/patches.
- `cloud_render_features`: cloud family geometry and particle recipes.
- `ocean_render_features`: current vectors, ocean features, and bait-related ocean features.
- `bait_render_features`: shell for future bait-specific depth/volume features.

## Important design split

PostGIS stores:

```text
feature geometry
family/type
altitude/depth
opacity/density/score
particle_seed
particle_budget
```

Frontend still generates:

```text
ellipsoid particles
wobble/jitter
family-specific rendering
```

That keeps storage small while making visual output stable across pan/zoom.

## Safe defaults

The feature cache defaults off:

```text
LFTR_RENDER_CACHE_ENABLED=false
```

If enabled but unavailable or empty, `/gfs` falls back to the live field engine.

## Manual pre-render

```bash
python3 scripts/prerender_viewport_features.py --bbox=-125,32,-117,38 --tier=regional
```

## Checks

```bash
python3 scripts/check_gfs_postgis_prerender_arch.py
```
