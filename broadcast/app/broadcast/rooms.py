from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.broadcast.messages import envelope


@dataclass
class BroadcastRoom:
    room_id: str
    broadcaster: WebSocket | None = None
    broadcaster_id: str | None = None
    watchers: dict[str, WebSocket] = field(default_factory=dict)
    chats: dict[str, WebSocket] = field(default_factory=dict)
    media_state: dict[str, Any] = field(default_factory=lambda: {"live": False, "audio": False, "video": False})

    def snapshot(self) -> dict[str, Any]:
        return {
            "room": self.room_id,
            "broadcaster_present": self.broadcaster is not None,
            "watcher_count": len(self.watchers),
            "chat_count": len(self.chats),
            "media_state": self.media_state,
        }


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, BroadcastRoom] = {}

    def get(self, room_id: str) -> BroadcastRoom:
        if room_id not in self.rooms:
            self.rooms[room_id] = BroadcastRoom(room_id=room_id)
        return self.rooms[room_id]

    def status(self) -> dict[str, Any]:
        return {"rooms": len(self.rooms), "active": [room.snapshot() for room in self.rooms.values()]}

    async def register_broadcaster(self, room_id: str, client_id: str, ws: WebSocket) -> BroadcastRoom:
        room = self.get(room_id)
        room.broadcaster = ws
        room.broadcaster_id = client_id
        await self.broadcast_presence(room)
        # Existing /watch pages must not need reload. Tell them to announce readiness
        # whenever a new broadcaster appears.
        for watcher_id, watcher_ws in list(room.watchers.items()):
            await self.send(watcher_ws, envelope("signaling", room.room_id, {"type": "broadcaster-ready", "viewer_id": watcher_id, "payload": {"type": "broadcaster-ready"}}))
        return room

    async def register_watcher(self, room_id: str, client_id: str, ws: WebSocket) -> BroadcastRoom:
        room = self.get(room_id)
        room.watchers[client_id] = ws
        await self.broadcast_presence(room)
        return room

    async def register_chat(self, room_id: str, client_id: str, ws: WebSocket) -> BroadcastRoom:
        room = self.get(room_id)
        room.chats[client_id] = ws
        await self.send(ws, envelope("presence", room_id, {"type": "presence", **room.snapshot()}))
        return room

    async def unregister(self, room_id: str, client_id: str, kind: str) -> None:
        room = self.rooms.get(room_id)
        if not room:
            return
        if kind == "broadcast" and room.broadcaster_id == client_id:
            room.broadcaster = None
            room.broadcaster_id = None
        elif kind == "watch":
            room.watchers.pop(client_id, None)
        elif kind == "chat":
            room.chats.pop(client_id, None)
        await self.broadcast_presence(room)
        if not room.broadcaster and not room.watchers and not room.chats:
            self.rooms.pop(room_id, None)

    async def send(self, ws: WebSocket | None, message: dict[str, Any]) -> bool:
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except (RuntimeError, WebSocketDisconnect, OSError):
            # Mobile browsers and refreshes often close without a WebSocket close
            # frame. Treat that as normal churn, not an ASGI error.
            return False

    async def broadcast_presence(self, room: BroadcastRoom) -> None:
        message = envelope("presence", room.room_id, {"type": "presence", **room.snapshot()})
        if room.broadcaster is not None and not await self.send(room.broadcaster, message):
            room.broadcaster = None
            room.broadcaster_id = None
        for watcher_id, ws in list(room.watchers.items()):
            if not await self.send(ws, message):
                room.watchers.pop(watcher_id, None)
        for chat_id, ws in list(room.chats.items()):
            if not await self.send(ws, message):
                room.chats.pop(chat_id, None)

    async def broadcast_chat(self, room_id: str, message: dict[str, Any]) -> None:
        room = self.get(room_id)
        for ws in list(room.chats.values()):
            await self.send(ws, message)


room_manager = RoomManager()
