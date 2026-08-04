# LFTR Site Index

The public `/` route is a clean LFTR.biz landing page inspired by the old `zippy` homepage. The old page stacked `/watch`, `/gfs`, and a YouTube playlist in iframes. LFTR Next keeps that launch idea, but lazy-loads the previews so the public homepage does not boot the GFS globe or broadcast runtime by default.

Route contract:

- `/` — public website launcher and optional lazy previews.
- `/gfs` — Marine Intelligence Globe.
- `/broadcast` — broadcaster runtime.
- `/watch` — watcher runtime.

The site index may call lightweight status endpoints, but it must not require them to succeed.

The old zippy route was mined for visual/design behavior only. No legacy backend route sprawl, old GFS renderer files, or old WebSocket aliases were imported.

## /gfs Cloud Renderer Pass 1

The `/gfs` renderer now starts from a zippy-style top-down regional view so weather fields are readable before later oblique/volumetric polish.
Cloud rendering is family-aware, not one generic icon:

- `wisp` for high/thin cloud signatures
- `puff` for broken/mid cloud signatures
- `sheet` for broader cloud decks
- `marine-layer` for low/humid/coastal layer signatures
- `storm` for dense/rain-associated cloud masses

The renderer samples the active atmosphere patch, classifies each cloudy sample from cloud density, low/mid/high cloud aliases when available, rain rate, humidity, and wind, then places bounded `gmp-marker-3d` cloud family markers directly on the Google 3D map. Cloud markers remain controlled by the Clouds pill and are not screen-space debug overlays.

- [Clouds PostGIS live pill](clouds_postgis_live_pill.md)
