#!/usr/bin/env python3
"""Runtime bootstrap contract check for /gfs.

This intentionally uses urllib against the running backend instead of
fastapi/starlette TestClient. Newer Starlette on Python 3.13 requires the
optional httpx2 package for TestClient, and this check should not fail just
because that optional test dependency is missing.

Usage:
    BASE_URL=http://127.0.0.1:8787 .venv/bin/python scripts/check_gfs_runtime_bootstrap.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8787").rstrip("/")


def read_text(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"missing expected file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8", errors="replace")


def http_get(path: str, *, timeout: float = 20.0) -> tuple[int, str, str]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json,text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            content_type = res.headers.get("content-type", "")
            body = res.read().decode("utf-8", errors="replace")
            return int(res.status), content_type, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), exc.headers.get("content-type", ""), body
    except Exception as exc:
        raise SystemExit(f"could not reach {url}: {exc}") from exc


def require_contains(label: str, text: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"missing {label} contract: {missing}")


def main() -> int:
    main_ts = read_text(ROOT / "frontend/src/main.ts")
    site_py = read_text(ROOT / "app/api/routes_site.py")
    app_main_py = read_text(ROOT / "app/main.py")

    require_contains(
        "frontend bootstrap",
        main_ts,
        [
            "DEFAULT_SOCAL_BBOX",
            "loadViewportData(DEFAULT_SOCAL_BBOX",
            "bootstrap retry",
            "connectFieldStream(bbox)",
        ],
    )

    if "/src/main.ts" in site_py and "GFS_FALLBACK_HTML" not in site_py:
        raise SystemExit("backend /gfs still hard-points to Vite dev /src/main.ts")
    if "StaticFiles" not in app_main_py or 'app.mount("/assets"' not in app_main_py:
        raise SystemExit("backend does not mount built frontend assets for direct /gfs runtime")

    status, content_type, body = http_get("/gfs")
    if status != 200:
        raise SystemExit(f"/gfs returned {status}: {body[:300]}")
    if "/assets/gfs-" not in body and "Frontend build assets were not found" not in body:
        raise SystemExit("/gfs did not serve built dist HTML or the explicit build-missing fallback")

    status, content_type, body = http_get("/gfs/api/viewport-spatial?bbox=-125,32,-117,38")
    if status != 200:
        raise SystemExit(f"/gfs/api/viewport-spatial returned {status}: {body[:300]}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"viewport-spatial did not return JSON: {body[:300]}") from exc

    locations = payload.get("locations") or payload.get("reports") or []
    count = payload.get("count") or payload.get("location_count") or len(locations)
    source = payload.get("source") or payload.get("mode") or "unknown"
    if not locations:
        raise SystemExit(
            "viewport-spatial SoCal bootstrap returned zero locations; "
            f"source={source!r}, keys={sorted(payload.keys())}"
        )

    print("ok: /gfs built-asset route + initial data bootstrap + locations payload are wired")
    print(f"base_url={BASE_URL}")
    print(f"locations={len(locations)} count={count} source={source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
