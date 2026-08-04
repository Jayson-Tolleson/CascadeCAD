#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import create_app  # noqa: E402

REQUIRED_HTTP = {"/", "/gfs", "/broadcast", "/watch", "/api/broadcast/status", "/health", "/gfs/api/scene-frame"}
REQUIRED_WS = {"/ws/gfs", "/ws/broadcast", "/ws/watch", "/ws/chat"}
FORBIDDEN = {"/broadcast2", "/watch2", "/gfs/broadcast", "/gfs/watch"}

app = create_app()
http = {getattr(route, "path", "") for route in app.routes if "GET" in getattr(route, "methods", set())}
ws = {getattr(route, "path", "") for route in app.routes if route.__class__.__name__.lower().endswith("websocketroute")}
missing_http = sorted(REQUIRED_HTTP - http)
missing_ws = sorted(REQUIRED_WS - ws)
forbidden = sorted((http | ws) & FORBIDDEN)
duplicates = [path for path in REQUIRED_HTTP | REQUIRED_WS if sum(1 for route in app.routes if getattr(route, "path", "") == path) != 1]
if missing_http or missing_ws or forbidden or duplicates:
    raise SystemExit(json.dumps({"ok": False, "missing_http": missing_http, "missing_ws": missing_ws, "forbidden": forbidden, "duplicates": duplicates}, indent=2))
print(json.dumps({"ok": True, "site_routes": sorted(REQUIRED_HTTP), "websockets": sorted(REQUIRED_WS)}, indent=2))
