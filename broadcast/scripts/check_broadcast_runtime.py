#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.broadcast.rooms import room_manager  # noqa: E402
from app.broadcast.sanitize import clean_room, clean_text, clean_type  # noqa: E402
from app.broadcast.status import broadcast_status  # noqa: E402
from app.main import create_app  # noqa: E402

async def main() -> None:
    assert clean_room("bad room<script>") == "bad-room-script"
    assert "&lt;" in clean_text("<b>safe</b>")
    assert clean_type("webrtc_offer") == "webrtc_offer"
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    for path in ["/broadcast", "/watch", "/api/broadcast/status", "/ws/broadcast", "/ws/watch", "/ws/chat", "/gfs/api/scene-frame", "/ws/gfs"]:
        assert path in routes, path
    status = broadcast_status()
    assert status["ok"] is True and "/ws/chat" in status["websockets"]
    assert room_manager.status()["rooms"] >= 0
    print(json.dumps({"ok": True, "routes": sorted(path for path in routes if "broadcast" in path or path in {"/watch", "/ws/watch", "/ws/chat"})}, indent=2))

asyncio.run(main())
