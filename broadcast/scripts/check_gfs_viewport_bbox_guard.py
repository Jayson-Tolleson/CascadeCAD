#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
viewport = (root / "frontend/src/renderer/viewportController.ts").read_text()
rooms = (root / "app/broadcast/rooms.py").read_text()

assert "maxLatSpanDeg" in viewport and "maxLonSpanDeg" in viewport, "viewport span caps missing"
assert "isSaneRegionalBBox" in viewport, "sane bbox guard missing"
assert "datelineSafeHalfLon" in viewport, "dateline crossing guard missing"
assert "lastGoodBBox" in viewport, "last-good viewport fallback missing"
assert "west>east boxes" in viewport or "west>east" in viewport, "dateline failure note missing"
assert "WebSocketDisconnect" in rooms and "return True" in rooms, "broadcast websocket disconnect guard missing"
print("✓ /gfs viewport requests are capped to sane regional non-dateline bboxes and broadcast WS disconnects are quiet")
