from __future__ import annotations

from typing import Any

from app.broadcast.messages import envelope
from app.broadcast.rooms import BroadcastRoom, room_manager

SIGNAL_TYPES = {"offer", "answer", "ice", "webrtc_offer", "webrtc_answer", "webrtc_ice", "media-state", "debug"}


async def from_broadcaster(room: BroadcastRoom, payload: dict[str, Any]) -> None:
    kind = payload.get("type", "signaling")
    if kind == "media-state":
        room.media_state.update(payload.get("state", {})) if isinstance(payload.get("state"), dict) else None
        await room_manager.broadcast_presence(room)
    message = envelope("signaling", room.room_id, {"type": kind, "from": "broadcast", "payload": payload})
    for ws in list(room.watchers.values()):
        await room_manager.send(ws, message)


async def from_watcher(room: BroadcastRoom, client_id: str, payload: dict[str, Any]) -> None:
    kind = payload.get("type", "signaling")
    message = envelope("signaling", room.room_id, {"type": kind, "from": "watch", "viewer_id": client_id, "payload": payload})
    await room_manager.send(room.broadcaster, message)
