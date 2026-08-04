# Clouds pill: persistent morph + advect renderer

This build changes the `/gfs` Clouds pill from a redraw model to a persistent-body model.

Old behavior:

```text
SSE/PostGIS update arrives
→ build a fresh polygon list
→ syncPolygons drops IDs missing from the new list
→ clouds can flash while GFS/PostGIS regenerates
```

New behavior:

```text
SSE/PostGIS update arrives
→ build target cloud polygons
→ CloudMorphController keeps existing gmp-polygon-3d bodies alive
→ matching bodies morph toward new paths/altitudes/opacity
→ missing bodies hold, advect with wind, then fade out
→ new bodies fade in
```

Important files:

```text
frontend/src/renderer/cloudMorph.ts
frontend/src/main.ts
frontend/src/renderer/cloudParticles.ts
frontend/src/renderer/google3d.ts
```

Renderer policy:

- Do not clear Clouds on viewport stream reconnect.
- Do not reset `cachedCloudFeatures` during `connectFieldStream()`.
- Empty cloud feature payloads retain/advect the last good visible cloud field.
- Existing polygon IDs are reused when possible.
- If backend/PostGIS feature IDs shift, nearby same-layer cloud bodies are reused when they are close enough; otherwise the old body fades while the new one fades in.
- Wind advection uses east/north `advectU` and `advectV` metadata in meters per second.
- Marker cloud fallbacks remain cleared so clouds stay as real `gmp-polygon-3d` bodies.

Tuning defaults in `cloudMorph.ts`:

```text
fade-in:     14 seconds
hold:        30 seconds from main.ts
fade-out:    80 seconds from main.ts
morph:       34 seconds from main.ts
frame tick:   420 ms
```

The result should feel like live clouds are already loaded into the world: data changes guide and reshape them instead of destroying and recreating the whole cloud layer.
