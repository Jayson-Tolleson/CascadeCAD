#!/usr/bin/env python3
"""Validate that pass #9 broadcast/watch follows the clean-room migration plan."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = [
    ROOT / "docs/broadcast_migration_plan.md",
    ROOT / "docs/broadcast_route_contract.md",
    ROOT / "docs/broadcast_browser_notes.md",
    ROOT / "app/broadcast/README.md",
    ROOT / "frontend/src/broadcast/README.md",
]
REQUIRED_CONTRACT_STRINGS = [
    "/broadcast",
    "/watch",
    "/ws/broadcast",
    "/ws/watch",
    "/ws/chat",
    "/api/broadcast/status",
]
FORBIDDEN_ROUTE_STRINGS = ["/broadcast2", "/watch2"]
REQUIRED_RUNTIME_FILES = [
    ROOT / "app/api/routes_broadcast.py",
    ROOT / "app/broadcast/routes.py",
    ROOT / "frontend/src/broadcast/broadcastApp.ts",
    ROOT / "frontend/src/broadcast/watchApp.ts",
]
FORBIDDEN_BROADCAST_FRONTEND_DEPENDENCIES = [
    "../renderer",
    "../fields",
    "gmp-map-3d",
    "scene-frame",
    "/gfs/api",
]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_DOCS if not path.exists()]
    if missing:
        fail(f"missing required docs/placeholders: {missing}")

    route_doc = read(ROOT / "docs/broadcast_route_contract.md")
    missing_contract = [text for text in REQUIRED_CONTRACT_STRINGS if text not in route_doc]
    if missing_contract:
        fail(f"route contract is missing: {missing_contract}")

    plan_doc = read(ROOT / "docs/broadcast_migration_plan.md").lower()
    if "no gfs renderer loaded by default" not in plan_doc:
        fail("migration plan must state that no GFS renderer loads by default")

    missing_runtime = [str(path.relative_to(ROOT)) for path in REQUIRED_RUNTIME_FILES if not path.exists()]
    if missing_runtime:
        fail(f"missing expected pass #9 runtime files: {missing_runtime}")

    active_route_text = "\n".join(read(path) for path in [ROOT / "app/main.py", *sorted((ROOT / "app/api").glob("*.py"))])
    forbidden_routes = [needle for needle in FORBIDDEN_ROUTE_STRINGS if needle in active_route_text]
    if forbidden_routes:
        fail(f"forbidden duplicate broadcast/watch routes were added: {forbidden_routes}")

    broadcast_frontend = ROOT / "frontend/src/broadcast"
    disallowed_files = []
    dependency_hits = []
    for path in sorted(broadcast_frontend.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(broadcast_frontend)
        if path.stat().st_size > 25_000:
            disallowed_files.append(f"{path.relative_to(ROOT)} is too large")
        text = read(path).lower() if path.suffix in {".md", ".ts", ".js", ".tsx", ".jsx"} else ""
        for needle in FORBIDDEN_BROADCAST_FRONTEND_DEPENDENCIES:
            if needle in text:
                dependency_hits.append(f"{path.relative_to(ROOT)} references {needle}")
    if disallowed_files:
        fail(f"unexpected broadcast frontend implementation files: {disallowed_files}")
    if dependency_hits:
        fail(f"broadcast placeholder depends on globe/GFS frontend pieces: {dependency_hits}")

    sys.path.insert(0, str(ROOT))
    importlib.import_module("app.broadcast")

    result = {
        "ok": True,
        "docs_checked": [str(path.relative_to(ROOT)) for path in REQUIRED_DOCS],
        "contract_routes": REQUIRED_CONTRACT_STRINGS,
        "runtime_routes_added": True,
        "legacy_frontend_copied": False,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
