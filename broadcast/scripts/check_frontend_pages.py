#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
required = [
    FRONTEND / "site.html",
    FRONTEND / "index.html",
    FRONTEND / "broadcast.html",
    FRONTEND / "watch.html",
    FRONTEND / "src" / "site" / "siteApp.ts",
    FRONTEND / "src" / "styles" / "site.css",
]
missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
site = (FRONTEND / "src" / "site" / "siteApp.ts").read_text() if (FRONTEND / "src" / "site" / "siteApp.ts").exists() else ""
forbidden_imports = ["../renderer/", "../fields/", "../layers/", "maps3d", "gmp-map-3d"]
violations = [token for token in forbidden_imports if token in site]
large_legacy = []
for p in (FRONTEND / "src" / "site").glob("*.ts"):
    if p.stat().st_size > 20000:
        large_legacy.append(str(p.relative_to(ROOT)))
if missing or violations or large_legacy:
    raise SystemExit(json.dumps({"ok": False, "missing": missing, "forbidden_imports": violations, "large_legacy": large_legacy}, indent=2))
print(json.dumps({"ok": True, "pages": [str(p.relative_to(ROOT)) for p in required]}, indent=2))
