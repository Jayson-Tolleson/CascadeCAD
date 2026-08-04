# /gfs Runtime Bootstrap Fix

This patch fixes a production/runtime case where `/gfs` could show the Google globe but no visible layer rendering or pill behavior.

## What went wrong

Two separate paths could leave the map visually empty:

1. The backend `/gfs` fallback HTML pointed to `/src/main.ts`, which only exists when the Vite dev server is running. If the backend route was hit directly, the page could show a shell/globe state without the built layer runtime.
2. The first live data load waited for a Google 3D camera-settle event. Some Maps 3D builds do not emit a useful initial settle/change event on page load, so locations, stream patches, boats, and rain/cloud/bait draw calls never started until a later camera event.

## Fix

- Backend `/gfs` now serves `frontend/dist/index.html` when it exists.
- FastAPI now mounts built `/assets` and `/models` for direct backend runtime.
- Frontend now immediately bootstraps a safe SoCal bbox:

```text
-125,32,-117,38
```

- The viewport controller still replaces this with the true padded camera bbox when Maps 3D emits camera changes.
- A retry runs if no locations have loaded after boot.
- The SSE stream is connected immediately on the safe bbox, so pills have data to toggle.

## Check

```bash
cd ~/broadcast
.venv/bin/python scripts/check_gfs_runtime_bootstrap.py
```

Expected:

```text
ok: /gfs built-asset route + initial data bootstrap + locations payload are wired
```
