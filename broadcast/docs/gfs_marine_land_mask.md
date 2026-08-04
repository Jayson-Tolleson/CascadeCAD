# GFS Marine Land Mask

This build adds a backend marine land mask in front of expensive ocean-provider paths.

Goal:

- avoid SST/current/bait/chlorophyll/RTOFS calls for obvious landlocked tiles;
- keep ocean, coast, islands, harbors, bays, estuaries, sounds, deltas, and nearshore boxes queryable;
- return honest `no_data` when a bbox is landlocked instead of creating mock ocean data.

The mask is deliberately conservative. It only blocks bboxes whose sampled points all fall inside trimmed interior land-core boxes. Unknown/coastal points are treated as marine-possible so bays and harbors are not accidentally excluded.

## Runtime route

```bash
curl -sS "http://127.0.0.1:8787/gfs/api/marine-mask?bbox=-117.25,32.62,-117.10,32.76" | jq
```

Useful examples:

```bash
# Inland: should_query_ocean=false
curl -sS "http://127.0.0.1:8787/gfs/api/marine-mask?bbox=-112.3,33.2,-111.7,33.8" | jq

# San Diego Bay: should_query_ocean=true
curl -sS "http://127.0.0.1:8787/gfs/api/marine-mask?bbox=-117.25,32.62,-117.10,32.76" | jq

# LA / Long Beach Harbor: should_query_ocean=true
curl -sS "http://127.0.0.1:8787/gfs/api/marine-mask?bbox=-118.30,33.70,-118.05,33.83" | jq
```

## Settings

```env
LFTR_MARINE_LAND_MASK_ENABLED=true
LFTR_MARINE_LAND_MASK_SAMPLE_GRID=5
LFTR_MARINE_LAND_MASK_COAST_BUFFER_DEG=0.12
LFTR_MARINE_LAND_MASK_ALLOW_HARBORS_BAYS=true
```

## Check

```bash
cd ~/broadcast
.venv/bin/python scripts/check_gfs_marine_land_mask.py
```
