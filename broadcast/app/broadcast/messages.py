from __future__ import annotations

from time import time
from typing import Any

MESSAGE_FAMILIES = {"presence", "signaling", "chat", "stt", "ai", "upload", "debug", "system"}


def now_ms() -> int:
    return int(time() * 1000)


def envelope(family: str, room: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"family": family if family in MESSAGE_FAMILIES else "debug", "room": room, "ts": now_ms(), **(payload or {})}


def system(room: str, text: str) -> dict[str, Any]:
    return envelope("system", room, {"type": "system", "text": text})
