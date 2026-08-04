#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

required_files = [
    ROOT / "app" / "prerender" / "postgis_repository.py",
    ROOT / "app" / "prerender" / "cache.py",
    ROOT / "app" / "prerender" / "worker.py",
    ROOT / "app" / "api" / "routes_prerender.py",
    ROOT / "scripts" / "prerender_viewport_features.py",
]
missing = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
if missing:
    print(json.dumps({"ok": False, "missing": missing}, indent=2))
    raise SystemExit(1)

schema = (ROOT / "app" / "db" / "schema.sql").read_text()
for token in ["cloud_render_features", "ocean_render_features", "bait_render_features", "render_tiles"]:
    if token not in schema:
        print(json.dumps({"ok": False, "missing_schema_token": token}, indent=2))
        raise SystemExit(1)

from app.core.config import get_settings
from app.prerender.cache import get_render_cache
from app.prerender.worker import precompute_viewport_render_features
from app.spatial.viewport_query import parse_bbox

settings = get_settings()
status = get_render_cache().status()
# Run a safe precompute probe with cache disabled/unavailable fallback semantics.  If
# PostGIS is not configured, the worker still computes patches and reports skipped writes.
result = precompute_viewport_render_features(parse_bbox("-125,32,-117,38"), tier="regional")

# This check must pass in offline build environments too.  It verifies the
# PostGIS/prerender architecture and safe worker semantics, not internet reachability.
ok = (
    result.get("ok") is True
    and isinstance(result.get("clouds"), dict)
    and isinstance(result.get("ocean"), dict)
    and "cloud_table" in status
    and "ocean_table" in status
    and "render_tiles_table" in status
)
print(json.dumps({
    "ok": ok,
    "postgis_available": status.get("available"),
    "render_cache_enabled": settings.render_cache_enabled,
    "cloud_features": result["clouds"].get("feature_count"),
    "cloud_write": result["clouds"].get("write"),
    "ocean_current_vectors": result["ocean"].get("current_vectors"),
    "ocean_write": result["ocean"].get("write"),
    "tables": ["render_tiles", "cloud_render_features", "ocean_render_features", "bait_render_features"],
}, indent=2, sort_keys=True))
raise SystemExit(0 if ok else 1)
