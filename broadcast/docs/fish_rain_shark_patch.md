# Fish Location / Rain / Shark Intel Patch

This patch targets the GFS Marine Intelligence Globe frontend and layer contract.

## Changes

- Fish/location CSV orbs now have a real `gmp-marker-3d-interactive` hit target layered above the 3D orb polygons.
- Clicking a fish location opens the near-transparent glass Location Intel pane with lat/lon, source, observed time, summary, and CSV report fields.
- Rain now renders as falling Google 3D rain streaks/drops from cloud top toward the floor, with intensity colors on a white → blue → green → yellow → orange → red → black scale.
- The standalone Ocean pill is removed. Ocean field data still feeds Bait, Boats, and Shark Intel.
- A Shark Intel pill is added. It renders CSV shark/ray/big-bite report rings and ocean-intel rings derived from bait score, current strength, and temperature band.

## Validation

Run:

```bash
cd ~/broadcast
python3 scripts/check_fish_rain_shark_patch.py
python3 scripts/check_layers.py
python3 scripts/check_gfs_layer_toggles.py
cd frontend && npm run build
```

The Vite build may warn that `%VITE_GOOGLE_MAPS_API_KEY%` is not defined when building outside the server environment; this is the existing placeholder behavior.
