#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROADCAST = ROOT / "frontend/src/broadcast"
REQUIRED = {"broadcastApp.ts", "watchApp.ts", "chat.ts", "media.ts", "signaling.ts", "stt.ts", "uploads.ts", "webSearchPane.ts"}
FORBIDDEN_SNIPPETS = ["../renderer", "../fields", "../layers", "gmp-map-3d", "/gfs/api/scene-frame", "createMap3DPlaceholder"]
missing = sorted(name for name in REQUIRED if not (BROADCAST / name).exists())
for page in [ROOT / "frontend/broadcast.html", ROOT / "frontend/watch.html"]:
    if not page.exists():
        missing.append(str(page.relative_to(ROOT)))
hits = []
large = []
for path in BROADCAST.rglob("*"):
    if path.is_file():
        if path.stat().st_size > 25_000:
            large.append(str(path.relative_to(ROOT)))
        if path.suffix in {".ts", ".js", ".tsx", ".jsx", ".md"}:
            text = path.read_text(encoding="utf-8")
            for snippet in FORBIDDEN_SNIPPETS:
                if snippet in text:
                    hits.append(f"{path.relative_to(ROOT)} contains {snippet}")
if missing or hits or large:
    raise SystemExit(json.dumps({"ok": False, "missing": missing, "forbidden_imports": hits, "large_files": large}, indent=2))
print(json.dumps({"ok": True, "checked": sorted(REQUIRED), "large_legacy_files": False, "gfs_renderer_dependency": False}, indent=2))
