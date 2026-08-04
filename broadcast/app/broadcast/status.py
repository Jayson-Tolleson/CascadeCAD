from __future__ import annotations

from app.broadcast.messages import MESSAGE_FAMILIES
from app.broadcast.rooms import room_manager

ROUTES = ["/broadcast", "/watch"]
WEBSOCKETS = ["/ws/broadcast", "/ws/watch", "/ws/chat"]


def broadcast_status() -> dict:
    return {
        "ok": True,
        "enabled": True,
        "routes": ROUTES,
        "websockets": WEBSOCKETS,
        "message_families": sorted(MESSAGE_FAMILIES),
        "degraded": False,
        **room_manager.status(),
    }
