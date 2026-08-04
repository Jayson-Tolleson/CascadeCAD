#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def require(path: str, needle: str) -> None:
    text = (ROOT / path).read_text()
    if needle not in text:
        raise SystemExit(f"missing {needle!r} in {path}")

require("frontend/src/broadcast/watchApp.ts", "startStandbyReadyLoop")
require("frontend/src/broadcast/watchApp.ts", "presence-update")
require("frontend/src/broadcast/watchApp.ts", "broadcaster-ready")
require("frontend/src/broadcast/watchApp.ts", "Waiting for live stream… leave this page open.")
require("frontend/src/broadcast/broadcastApp.ts", "facingBtn")
require("frontend/src/broadcast/broadcastApp.ts", "Facing: ${media.facingLabel()}")
require("frontend/src/broadcast/media.ts", "facingModeValue")
require("frontend/src/broadcast/signaling.ts", "reconnectTimer")
require("app/broadcast/rooms.py", "Existing /watch pages must not need reload")
print("✓ watch standby reconnect and facing pill contracts present")
